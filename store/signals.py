from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from .models import FoodItem, Category, Bag, BagItem, Plate, Payment, Order
import logging

logger = logging.getLogger(__name__)

# -------------------------------
# Prevent items from being assigned to "All" category
# -------------------------------
@receiver(pre_save, sender=FoodItem)
def prevent_all_category_assignment(sender, instance, **kwargs):
    """Prevent food items from being assigned to the 'All' category."""
    if instance.category and instance.category.name == 'All':
        # Find the first available category that's not 'All'
        other_category = Category.objects.exclude(name='All').first()
        if other_category:
            logger.warning(f"Prevented {instance.name} from being assigned to 'All' category. Assigned to {other_category.name} instead.")
            instance.category = other_category
        else:
            logger.error("No valid categories found! Cannot assign food item.")
            from django.core.exceptions import ValidationError
            raise ValidationError("No valid categories available. Please create a category first.")

# -------------------------------
# Assign default BagItem and Plates when a FoodItem is added to a bag
# -------------------------------
@receiver(post_save, sender=BagItem)
def handle_fooditem_in_bag(sender, instance, created, **kwargs):
    """
    If the item is Food:
    - Ensure at least 1 plate exists per bag if not set
    """
    if instance.food_item.category.name.lower() in ["food", "main courses"]:
        if instance.plates is None or instance.plates == 0:
            instance.plates = 1
            instance.save()

        # Ensure Bag has a Plate object for this item
        Plate.objects.get_or_create(
            bag=instance.bag,
            defaults={"count": instance.plates, "fee_per_plate": 50.00},
        )

# -------------------------------
# Clean up Plates when last FoodItem is removed from a bag
# -------------------------------
@receiver(post_delete, sender=BagItem)
def cleanup_plates_on_fooditem_delete(sender, instance, **kwargs):
    """
    If a FoodItem is removed and no more Food items exist in the bag,
    delete associated Plate objects.
    """
    if instance.food_item.category.name.lower() in ["food", "main courses"]:
        remaining_food = instance.bag.items.filter(
            food_item__category__name__in=["Food", "Main Courses"]
        ).exists()
        if not remaining_food:
            instance.bag.plates.all().delete()

# -------------------------------
# Ensure order status is 'Pending' when payment is successful
# -------------------------------
@receiver(post_save, sender=Payment)
def update_order_status_on_payment_success(sender, instance, created, **kwargs):
    """
    When a payment is successful, ensure the order status is 'Pending'.
    This ensures that paid orders appear in the dashboard as 'Pending (Paid)'.
    """
    if instance.status == 'success' and hasattr(instance, 'order') and instance.order is not None:
        order = instance.order
        if order.status != 'Pending':
            order.status = 'Pending'
            order.save(update_fields=['status'])


# -------------------------------
# Inventory Audit Logging
# -------------------------------
@receiver(pre_save, sender=FoodItem)
def log_inventory_changes(sender, instance, **kwargs):
    """Log inventory changes for audit purposes."""
    if instance.pk:  # Only for existing items
        try:
            old_instance = FoodItem.objects.get(pk=instance.pk)
            if old_instance.portions != instance.portions:
                logger.info(
                    f"INVENTORY CHANGE: {instance.name} - "
                    f"Portions changed from {old_instance.portions} to {instance.portions} "
                    f"(Change: {instance.portions - old_instance.portions:+d})"
                )
        except FoodItem.DoesNotExist:
            pass  # New item, no old data to compare


# -------------------------------
# Order Delivery Tracking
# -------------------------------
@receiver(pre_save, sender=Order)
def track_delivery_time(sender, instance, **kwargs):
    """Set delivered_at when order status changes to 'Delivered'."""
    if instance.pk:  # Only for existing orders
        try:
            old_instance = Order.objects.get(pk=instance.pk)
            # If status changed from non-Delivered to Delivered, set delivered_at
            if (old_instance.status != 'Delivered' and 
                instance.status == 'Delivered' and 
                not instance.delivered_at):
                from django.utils import timezone
                instance.delivered_at = timezone.now()
                logger.info(f"Order #{instance.id} marked as delivered at {instance.delivered_at}")
        except Order.DoesNotExist:
            pass  # New order, no old data to compare
