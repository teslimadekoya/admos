"""
Order creation utilities to prevent relationship errors.
This module ensures proper creation of orders with correct bag relationships.
"""
from django.utils import timezone
from django.db import transaction
from accounts.models import User
from store.models import Category, FoodItem, Bag, BagItem, Order, Payment
import random


def create_order_with_items(customer_phone, items_data, delivery_fee=500, service_charge=100):
    """
    Create a complete order with proper relationships.
    
    Args:
        customer_phone (str): Customer's phone number
        items_data (list): List of dicts with 'item_id', 'portions', 'plates'
        delivery_fee (int): Delivery fee amount
        service_charge (int): Service charge amount
        
    Returns:
        dict: Order details with success status
    """
    try:
        with transaction.atomic():
            # Get or create customer
            customer, created = User.objects.get_or_create(
                phone_number=customer_phone,
                defaults={
                    'first_name': 'Test',
                    'last_name': 'Customer',
                    'role': 'customer',
                    'delivery_address': '123 Test Street, Lagos'
                }
            )
            
            # Create order first
            order = Order.objects.create(
                user=customer,
                status='Pending',
                delivery_fee=delivery_fee,
                service_charge=service_charge
            )
            
            # Create bags and bag items
            bags = []
            total_cost = 0
            
            for i, item_data in enumerate(items_data, 1):
                # Create bag with owner
                bag = Bag.objects.create(owner=customer)
                bags.append(bag)
                
                # Get food item
                try:
                    food_item = FoodItem.objects.get(id=item_data['item_id'])
                except FoodItem.DoesNotExist:
                    raise ValueError(f"Food item with ID {item_data['item_id']} not found")
                
                # Create bag item
                bag_item = BagItem.objects.create(
                    bag=bag,
                    food_item=food_item,
                    portions=item_data.get('portions', 1),
                    plates=item_data.get('plates', 1)
                )
                
                bag_total = bag.total
                total_cost += bag_total
            
            # Link bags to order using ManyToManyField
            order.bags.add(*bags)
            
            # Calculate final total
            final_total = total_cost + order.delivery_fee + order.service_charge
            
            # Create payment
            payment = Payment.objects.create(
                order=order,
                user=customer,
                amount=final_total,
                reference=f'PAY_{order.id:06d}',
                status='success'
            )
            
            return {
                'success': True,
                'order_id': order.id,
                'customer': customer,
                'bags_count': len(bags),
                'subtotal': total_cost,
                'total': final_total,
                'payment_reference': payment.reference,
                'status': order.status
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def create_random_order(customer_phone=None, num_items=3):
    """
    Create a random order with available items.
    
    Args:
        customer_phone (str): Customer phone (defaults to random)
        num_items (int): Number of items to include
        
    Returns:
        dict: Order creation result
    """
    if not customer_phone:
        customer_phone = f'23480{random.randint(10000000, 99999999)}'
    
    # Get available food items (excluding 'All' category)
    available_items = FoodItem.objects.filter(
        availability=True
    ).exclude(category__name__iexact='All')
    
    if not available_items.exists():
        return {
            'success': False,
            'error': 'No available food items found'
        }
    
    # Select random items
    selected_items = random.sample(list(available_items), min(num_items, len(available_items)))
    
    # Prepare items data
    items_data = []
    for item in selected_items:
        items_data.append({
            'item_id': item.id,
            'portions': random.randint(1, 3),
            'plates': random.randint(1, 2)
        })
    
    return create_order_with_items(customer_phone, items_data)


def verify_order_integrity(order_id):
    """
    Verify that an order has proper relationships and data.
    
    Args:
        order_id (int): Order ID to verify
        
    Returns:
        dict: Verification results
    """
    try:
        order = Order.objects.get(id=order_id)
        
        # Check bags relationship
        bags = order.bags.all()
        bags_count = bags.count()
        
        # Check bag items
        total_items = 0
        items_details = []
        
        for bag in bags:
            items = bag.items.all()
            total_items += items.count()
            for item in items:
                items_details.append({
                    'bag_id': bag.id,
                    'item_name': item.food_item.name if item.food_item else item.item_name,
                    'portions': item.portions,
                    'plates': item.plates
                })
        
        # Check payment
        try:
            payment = order.payment
            payment_valid = True
            payment_amount = payment.amount
        except:
            payment_valid = False
            payment_amount = 0
        
        # Calculate expected total
        subtotal = order.subtotal
        expected_total = subtotal + order.delivery_fee + order.service_charge
        
        return {
            'success': True,
            'order_id': order.id,
            'status': order.status,
            'bags_count': bags_count,
            'total_items': total_items,
            'items_details': items_details,
            'subtotal': subtotal,
            'expected_total': expected_total,
            'payment_valid': payment_valid,
            'payment_amount': payment_amount,
            'totals_match': abs(payment_amount - expected_total) < 0.01
        }
        
    except Order.DoesNotExist:
        return {
            'success': False,
            'error': f'Order {order_id} not found'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
