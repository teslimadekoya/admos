"""
Order creation utilities to ensure proper bag linking and prevent orphaned orders.
"""
from django.db import transaction
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError
from .models import Order, Bag, Payment, FoodItem

User = get_user_model()


def create_order_with_bags(user, bag_ids, delivery_address='', contact_phone='', delivery_fee=500, service_charge=100):
    """
    Create an order with proper bag linking to prevent orphaned orders.
    
    Args:
        user: The user creating the order
        bag_ids: List of bag IDs to include in the order
        delivery_address: Delivery address
        contact_phone: Contact phone number
        delivery_fee: Delivery fee (default 500)
        service_charge: Service charge (default 100)
    
    Returns:
        Order: The created order with bags properly linked
    
    Raises:
        ValidationError: If validation fails
    """
    # Validate input parameters
    if not delivery_address or len(delivery_address.strip()) < 10:
        raise ValidationError("Valid delivery address is required (minimum 10 characters).")
    
    if not contact_phone or len(contact_phone.strip()) < 10:
        raise ValidationError("Valid contact phone number is required.")
    
    if delivery_fee < 0 or delivery_fee > 10000:
        raise ValidationError("Delivery fee must be between 0 and 10,000.")
    
    if service_charge < 0 or service_charge > 5000:
        raise ValidationError("Service charge must be between 0 and 5,000.")
    
    if not bag_ids:
        raise ValidationError("At least one bag must be provided.")
    
    # Validate all bags exist and belong to the user
    bags = Bag.objects.filter(id__in=bag_ids, owner=user)
    if len(bags) != len(bag_ids):
        raise ValidationError("One or more bags not found or don't belong to you.")
    
    # Validate each bag has items
    for bag in bags:
        if not bag.items.exists():
            raise ValidationError(f"Bag '{bag.name}' is empty. All bags must contain items.")
    
    # Validate each bag
    for bag in bags:
        # Validate plate requirements
        try:
            bag.validate_plate_requirements()
        except ValidationError as e:
            raise ValidationError(f"Bag '{bag.name}': {str(e)}")
        
        # Validate portions availability for all items in the bag
        for item in bag.items.all():
            if item.food_item and not item.food_item.can_order_portions(item.portions):
                if item.food_item.portions == 0:
                    raise ValidationError(f"Bag '{bag.name}': Sorry, {item.food_item.name} is currently out of stock.")
                else:
                    raise ValidationError(f"Bag '{bag.name}': Sorry, only {item.food_item.portions} {item.food_item.quantity_display.split(' ', 1)[1]} of {item.food_item.name} available. You have {item.portions} in your bag.")
    
    # Create order and link bags in a transaction with bulletproof inventory management
    with transaction.atomic():
        # Step 1: Pre-validate inventory reduction (double-check before creating order)
        inventory_reductions = []
        for bag in bags:
            for item in bag.items.all():
                if item.food_item and not item.food_item.is_plate_item:
                    # Double-check availability right before order creation
                    if not item.food_item.can_order_portions(item.portions):
                        raise ValidationError(f"CRITICAL: {item.food_item.name} stock changed during order creation. Only {item.food_item.portions} portions available, but {item.portions} requested.")
                    
                    # Store what we plan to reduce for rollback if needed
                    inventory_reductions.append({
                        'food_item': item.food_item,
                        'portions': item.portions,
                        'original_portions': item.food_item.portions
                    })
        
        # Step 2: Create the order
        order = Order.objects.create(
            user=user,
            delivery_address=delivery_address,
            contact_phone=contact_phone,
            delivery_fee=delivery_fee,
            service_charge=service_charge,
            status='Pending'
        )
        
        # Step 3: Link bags to the order
        order.bags.set(bags)
        
        # Step 4: Reduce inventory with bulletproof error handling
        failed_reductions = []
        for reduction in inventory_reductions:
            food_item = reduction['food_item']
            portions = reduction['portions']
            original_portions = reduction['original_portions']
            
            try:
                # Lock the food item for update to prevent race conditions
                food_item = FoodItem.objects.select_for_update().get(id=food_item.id)
                
                # Final check before reduction
                if food_item.portions < portions:
                    failed_reductions.append({
                        'food_item': food_item.name,
                        'requested': portions,
                        'available': food_item.portions
                    })
                    continue
                
                # Perform the reduction
                if not food_item.reduce_portions(portions):
                    failed_reductions.append({
                        'food_item': food_item.name,
                        'requested': portions,
                        'available': food_item.portions
                    })
                    continue
                    
            except Exception as e:
                failed_reductions.append({
                    'food_item': food_item.name,
                    'error': str(e)
                })
        
        # Step 5: If any inventory reduction failed, rollback everything
        if failed_reductions:
            # Rollback successful reductions
            for reduction in inventory_reductions:
                # Check if this reduction was successful (not in failed_reductions)
                was_successful = True
                for failure in failed_reductions:
                    if (failure.get('food_item') == reduction['food_item'].name and 
                        'error' not in failure):
                        was_successful = False
                        break
                
                if was_successful:
                    try:
                        reduction['food_item'].increase_portions(reduction['portions'])
                    except:
                        pass  # Log this but don't fail the rollback
            
            # Delete the order
            order.delete()
            
            # Create detailed error message
            error_details = []
            for failure in failed_reductions:
                if 'error' in failure:
                    error_details.append(f"{failure['food_item']}: {failure['error']}")
                else:
                    error_details.append(f"{failure['food_item']}: Only {failure['available']} available, {failure['requested']} requested")
            
            raise ValidationError(f"INVENTORY ERROR: Failed to reduce inventory for: {', '.join(error_details)}")
        
        # Step 6: Final validation to ensure order is complete
        if not order.is_complete:
            # Rollback inventory if order is incomplete
            for reduction in inventory_reductions:
                try:
                    reduction['food_item'].increase_portions(reduction['portions'])
                except:
                    pass
            order.delete()
            raise ValidationError("Order creation failed: Order is incomplete after creation.")
        
        return order


def create_payment_for_order(user, order, amount=None, reference=None, status='success'):
    """
    Create a payment for an order with proper amount calculation.
    
    Args:
        user: The user making the payment
        order: The order to create payment for
        amount: Payment amount (if None, uses order total)
        reference: Payment reference
        status: Payment status (default 'success')
    
    Returns:
        Payment: The created payment
    """
    if amount is None:
        amount = order.total
    
    if reference is None:
        from django.utils import timezone
        reference = f'PAY_{order.id}_{timezone.now().strftime("%Y%m%d_%H%M%S")}'
    
    payment = Payment.objects.create(
        user=user,
        order=order,
        amount=amount,
        reference=reference,
        status=status
    )
    
    return payment


def create_complete_order(user, bag_ids, delivery_address='', contact_phone='', delivery_fee=500, service_charge=100, payment_status='success'):
    """
    Create a complete order with bags and payment in one transaction.
    
    Args:
        user: The user creating the order
        bag_ids: List of bag IDs to include in the order
        delivery_address: Delivery address
        contact_phone: Contact phone number
        delivery_fee: Delivery fee (default 500)
        service_charge: Service charge (default 100)
        payment_status: Payment status (default 'success')
    
    Returns:
        tuple: (order, payment) - The created order and payment
    """
    with transaction.atomic():
        # Create order with proper bag linking
        order = create_order_with_bags(
            user=user,
            bag_ids=bag_ids,
            delivery_address=delivery_address,
            contact_phone=contact_phone,
            delivery_fee=delivery_fee,
            service_charge=service_charge
        )
        
        # Create payment
        payment = create_payment_for_order(
            user=user,
            order=order,
            status=payment_status
        )
        
        return order, payment


def validate_order_integrity(order):
    """
    Validate that an order has proper bag linking and is not orphaned.
    
    Args:
        order: Order instance to validate
    
    Returns:
        bool: True if order is valid, False otherwise
    
    Raises:
        ValidationError: If order is invalid
    """
    if not order.bags.exists():
        raise ValidationError(f"Order #{order.id} has no bags linked to it. This is an orphaned order.")
    
    # Check if all bags have items
    for bag in order.bags.all():
        if not bag.items.exists():
            raise ValidationError(f"Order #{order.id} has bag '{bag.name}' with no items.")
    
    return True


def fix_orphaned_order(order):
    """
    Attempt to fix an orphaned order by finding and linking appropriate bags.
    This is a recovery function for orders that were created without proper bag linking.
    
    Args:
        order: Order instance to fix
    
    Returns:
        bool: True if order was fixed, False otherwise
    """
    if order.bags.exists():
        return True  # Order is not orphaned
    
    # Try to find bags that might belong to this order
    # This is a best-effort recovery - in production, you might want more sophisticated logic
    user_bags = Bag.objects.filter(owner=order.user)
    
    if user_bags.exists():
        # Link the most recent bag as a fallback
        # In a real scenario, you might want to implement more sophisticated matching
        order.bags.set([user_bags.first()])
        return True
    
    return False
