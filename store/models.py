from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from decimal import Decimal


# ============================================================
# CATEGORY MODEL
# ============================================================

class Category(models.Model):
    """Food categories like Pizza, Drinks, etc."""
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Categories"


# ============================================================
# FOOD ITEM MODEL
# ============================================================

class FoodItem(models.Model):
    """Individual food items that can be ordered."""
    name = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price per portion")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='food_items')
    image_url = models.URLField(blank=True, null=True)
    image = models.ImageField(upload_to='food_items/', blank=True, null=True)
    availability = models.BooleanField(default=True)
    portions = models.PositiveIntegerField(default=0, help_text="Available portions in stock")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_food_items'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_food_items'
    )

    def __str__(self):
        return self.name

    def clean(self):
        """Validate food item data before saving."""
        from django.core.exceptions import ValidationError
        
        # Prevent assignment to 'All' category
        if self.category and self.category.name == 'All':
            raise ValidationError({
                'category': 'Items cannot be assigned to the "All" category. Please select a specific category like Food, Drinks, Snacks, Pizza, or Bread.'
            })
        
        # Validate price
        if self.price <= 0:
            raise ValidationError({
                'price': 'Price must be greater than 0.'
            })
        
        # Validate portions
        if self.portions < 0:
            raise ValidationError({
                'portions': 'Portions cannot be negative.'
            })

    @property
    def is_food_category(self):
        """Check if this item belongs to the food category."""
        return self.category and self.category.name.lower() == 'food'
    
    @property
    def is_plate_item(self):
        """Check if this item is a Plate (supply item that never runs out)."""
        return self.name.lower() == 'plate'

    @property
    def quantity_display(self):
        """Get quantity with appropriate unit based on category."""
        if not self.category:
            unit = "item" if self.portions == 1 else "items"
            return f"{self.portions} {unit}"
        
        category_name = self.category.name.lower()
        if category_name == 'food':
            unit = "portion" if self.portions == 1 else "portions"
            return f"{self.portions} {unit}"
        elif category_name == 'drinks':
            unit = "bottle" if self.portions == 1 else "bottles"
            return f"{self.portions} {unit}"
        elif category_name == 'pizza':
            unit = "pack" if self.portions == 1 else "packs"
            return f"{self.portions} {unit}"
        elif category_name == 'snacks':
            unit = "snack" if self.portions == 1 else "snacks"
            return f"{self.portions} {unit}"
        elif category_name == 'bread':
            unit = "loaf" if self.portions == 1 else "loaves"
            return f"{self.portions} {unit}"
        else:
            unit = "item" if self.portions == 1 else "items"
            return f"{self.portions} {unit}"

    @property
    def is_available(self):
        """Check if item is available (portions > 0, or always available for Plate items)."""
        if self.is_plate_item:
            return True  # Plate items are always available
        return self.portions > 0

    @property
    def is_out_of_stock(self):
        """Check if item is out of stock (portions = 0, but Plate items never run out)."""
        if self.is_plate_item:
            return False  # Plate items never run out
        return self.portions == 0

    @property
    def out_of_stock_toggle(self):
        """Toggle for out of stock status."""
        return self.portions == 0

    @out_of_stock_toggle.setter
    def out_of_stock_toggle(self, value):
        """Set out of stock status."""
        if value:
            self.portions = 0
            self.availability = False
        else:
            if self.portions == 0:
                self.portions = 1
            self.availability = True

    def can_order_portions(self, requested_portions):
        """Check if the requested portions can be ordered (Plate items always can)."""
        if self.is_plate_item:
            return True  # Plate items can always be ordered
        return self.portions >= requested_portions

    def reduce_portions(self, portions):
        """Reduce the available portions with bulletproof validation (Plate items don't reduce stock)."""
        from django.core.exceptions import ValidationError
        
        # Validate input
        if not isinstance(portions, int) or portions <= 0:
            raise ValidationError(f"Invalid portions value: {portions}. Must be a positive integer.")
        
        # Plate items don't reduce stock
        if self.is_plate_item:
            return True
        
        # Check if we have enough portions
        if self.portions < portions:
            return False
        
        # Perform the reduction atomically
        try:
            old_portions = self.portions
            self.portions -= portions
            
            # Update availability based on new portions
            if self.portions == 0:
                self.availability = False
            elif self.portions > 0 and not self.availability:
                self.availability = True
            
            # Save with validation
            self.full_clean()
            self.save()
            
            # Verify the reduction was successful
            self.refresh_from_db()
            if self.portions != old_portions - portions:
                raise ValidationError(f"Inventory reduction failed. Expected {old_portions - portions}, got {self.portions}")
            
            return True
            
        except Exception as e:
            # Rollback the change
            self.portions = old_portions
            self.save()
            raise ValidationError(f"Failed to reduce inventory for {self.name}: {str(e)}")

    def increase_portions(self, portions):
        """Increase the available portions with bulletproof validation."""
        from django.core.exceptions import ValidationError
        
        # Validate input
        if not isinstance(portions, int) or portions <= 0:
            raise ValidationError(f"Invalid portions value: {portions}. Must be a positive integer.")
        
        # Perform the increase atomically
        try:
            old_portions = self.portions
            self.portions += portions
            
            # Update availability
            if self.portions > 0:
                self.availability = True
            
            # Save with validation
            self.full_clean()
            self.save()
            
            # Verify the increase was successful
            self.refresh_from_db()
            if self.portions != old_portions + portions:
                raise ValidationError(f"Inventory increase failed. Expected {old_portions + portions}, got {self.portions}")
            
            return True
            
        except Exception as e:
            # Rollback the change
            self.portions = old_portions
            self.save()
            raise ValidationError(f"Failed to increase inventory for {self.name}: {str(e)}")

    class Meta:
        ordering = ['name']


# ============================================================
# BAG MODEL
# ============================================================

class Bag(models.Model):
    """A bag owned by a user to hold selected food items."""
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bags'
    )
    name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.owner.get_full_name()}'s Bag - {self.name}"

    @property
    def total_cost(self):
        """Calculate total cost of all items in the bag."""
        return sum(item.subtotal for item in self.items.all())
    
    @property
    def total(self):
        """Alias for total_cost for compatibility."""
        return self.total_cost

    @property
    def has_food_items(self):
        """Check if bag contains any food category items."""
        return any(item.is_food_category for item in self.items.all())

    def validate_plate_requirements(self):
        """Validate that bag has proper plate requirements."""
        if self.has_food_items:
            # If there are food items, ensure at least one item has plates
            food_items_with_plates = any(
                item.is_food_category and item.plates > 0 
                for item in self.items.all()
            )
            if not food_items_with_plates:
                raise ValidationError("At least one plate is required when ordering food category items")


# ============================================================
# BAG ITEM MODEL
# ============================================================

class BagItem(models.Model):
    """Food item added to a bag with optional plates."""
    bag = models.ForeignKey(Bag, on_delete=models.CASCADE, related_name="items")
    food_item = models.ForeignKey(FoodItem, on_delete=models.SET_NULL, null=True, blank=True)
    portions = models.PositiveIntegerField(default=1, help_text="Number of portions ordered")
    plates = models.PositiveIntegerField(default=0, help_text="Number of plates (only for food category items)")
    
    # Store food item details for historical data preservation
    item_name = models.CharField(max_length=100, blank=True, help_text="Name of the food item when ordered")
    item_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Price per portion when ordered")
    item_category = models.CharField(max_length=100, blank=True, help_text="Category of the food item when ordered")

    def __str__(self):
        return f"{self.item_name or self.food_item.name} x{self.portions}"

    @property
    def is_food_category(self):
        """Check if this bag item is from the food category."""
        if self.food_item:
            return self.food_item.is_food_category
        elif self.item_category:
            return self.item_category.lower() == 'food'
        return False

    @property
    def quantity_display(self):
        """Get quantity with appropriate unit based on category."""
        if self.food_item and self.food_item.category:
            category_name = self.food_item.category.name.lower()
        elif self.item_category:
            category_name = self.item_category.lower()
        else:
            unit = "item" if self.portions == 1 else "items"
            return f"{self.portions} {unit}"
        
        if category_name == 'food':
            unit = "portion" if self.portions == 1 else "portions"
            return f"{self.portions} {unit}"
        elif category_name == 'drinks':
            unit = "bottle" if self.portions == 1 else "bottles"
            return f"{self.portions} {unit}"
        elif category_name == 'pizza':
            unit = "pack" if self.portions == 1 else "packs"
            return f"{self.portions} {unit}"
        elif category_name == 'snacks':
            unit = "snack" if self.portions == 1 else "snacks"
            return f"{self.portions} {unit}"
        elif category_name == 'bread':
            unit = "loaf" if self.portions == 1 else "loaves"
            return f"{self.portions} {unit}"
        else:
            unit = "item" if self.portions == 1 else "items"
            return f"{self.portions} {unit}"

    @property
    def food_cost(self):
        """Calculate food cost (price per portion * portions)."""
        if self.food_item:
            return self.food_item.price * self.portions
        elif self.item_price:
            return self.item_price * self.portions
        return 0

    @property
    def plate_cost(self):
        """Calculate plate cost (plates * dynamic plate fee for food category items only, excluding Plate items)."""
        if self.is_food_category and self.food_item and self.food_item.name.lower() != 'plate':
            # Get dynamic plate fee from system settings
            from decimal import Decimal
            plate_fee = Decimal(str(SystemSettings.get_setting('plate_fee', 50)))
            return self.plates * plate_fee
        return 0

    @property
    def subtotal(self):
        """Calculate subtotal (food cost + plate cost)."""
        return self.food_cost + self.plate_cost

    def save(self, *args, **kwargs):
        """Auto-populate stored item details and validate portions/plates when saving."""
        # Validate portions availability if food_item exists
        if self.food_item and not self.food_item.can_order_portions(self.portions):
            raise ValidationError(f"Not enough {self.food_item.name} in stock. Available: {self.food_item.portions}")
        
        # Auto-populate stored details if not already set
        if self.food_item and not self.item_name:
            self.item_name = self.food_item.name
            self.item_price = self.food_item.price
            self.item_category = self.food_item.category.name if self.food_item.category else ""
        
        # Check if this is a food category item (after auto-population)
        is_food = False
        if self.food_item:
            is_food = self.food_item.is_food_category
        elif self.item_category:
            is_food = self.item_category.lower() == 'food'
        
        # Validate plate requirements for food category items
        if is_food and self.plates == 0:
            raise ValidationError("At least one plate is required for food category items")
        
        # Ensure non-food category items have 0 plates
        if not is_food:
            self.plates = 0
        
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['id']


# ============================================================
# ORDER MODEL
# ============================================================

class Order(models.Model):
    """Represents a placed order consisting of one or more bags."""
    STATUS_CHOICES = [
        ('Pending', 'Pending'),        # payment confirmed, ready for delivery
        ('On the Way', 'On the Way'),  # rider dispatched
        ('Delivered', 'Delivered'),    # completed
    ]
    

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders')
    bags = models.ManyToManyField(Bag, related_name='orders')
    delivery_address = models.TextField(blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=500)
    service_charge = models.DecimalField(max_digits=10, decimal_places=2, default=500)
    vat_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=7.5, help_text="VAT percentage")
    vat_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="VAT amount in Naira")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    delivered_at = models.DateTimeField(null=True, blank=True, help_text="When the order was actually delivered")

    def __str__(self):
        return f"Order #{self.id} - {self.user.get_full_name()}"

    def clean(self):
        """Validate order completeness before saving."""
        from django.core.exceptions import ValidationError
        
        # Only validate bags if the order has been saved (has an ID)
        if self.pk:
            # Check if order has bags
            if not self.bags.exists():
                raise ValidationError("Order must have at least one bag.")
            
            # Check if all bags have items
            for bag in self.bags.all():
                if not bag.items.exists():
                    raise ValidationError(f"Bag '{bag.name}' is empty. All bags must contain items.")
        
        # Only validate required fields for new orders or when explicitly creating
        # This prevents validation errors when updating existing orders (like status changes)
        if not self.pk:  # Only for new orders
            # Validate delivery address
            if not self.delivery_address or len(self.delivery_address.strip()) < 10:
                raise ValidationError("Valid delivery address is required (minimum 10 characters).")
            
            # Validate contact phone
            if not self.contact_phone or len(self.contact_phone.strip()) < 10:
                raise ValidationError("Valid contact phone number is required.")
        
        # Always validate fees (these should be valid regardless)
        if self.delivery_fee < 0 or self.delivery_fee > 10000:
            raise ValidationError("Delivery fee must be between 0 and 10,000.")
        
        # Ensure service charge is always set (minimum 100 for all orders)
        if not self.service_charge or self.service_charge < 100:
            self.service_charge = 100
        
        if self.service_charge < 0 or self.service_charge > 5000:
            raise ValidationError("Service charge must be between 0 and 5,000.")

    def save(self, *args, **kwargs):
        """Override save to ensure validation."""
        self.clean()
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        """Calculate subtotal (bags total without delivery and service charges)."""
        return sum(bag.total_cost for bag in self.bags.all())

    @property
    def total(self):
        """Calculate total order cost including delivery, service charges, and VAT."""
        return self.subtotal + self.delivery_fee + self.service_charge + self.vat_amount

    @property
    def is_complete(self):
        """Check if order is complete and valid."""
        try:
            # Check if order has bags
            if not self.bags.exists():
                return False
            
            # Check if all bags have items
            for bag in self.bags.all():
                if not bag.items.exists():
                    return False
            
            # For existing orders, be more lenient with address/phone validation
            # Only check if they exist (not length requirements)
            if not self.delivery_address or not self.delivery_address.strip():
                return False
            
            if not self.contact_phone or not self.contact_phone.strip():
                return False
            
            # Check if order has valid total
            if self.total <= 0:
                return False
            
            return True
        except Exception:
            return False

    class Meta:
        ordering = ['-created_at']


# ============================================================
# ORDER NOTIFICATION MODEL
# ============================================================

class OrderNotification(models.Model):
    """Notifications tied to an order (e.g., status updates)."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    seen = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for Order {self.order.id} - {self.message}"


# ============================================================
# PAYMENT MODEL
# ============================================================

class Payment(models.Model):
    """Payment details tied to an order."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('paystack', 'Paystack'),
    ]
    
    PAYMENT_TYPE_CHOICES = [
        ('card', 'Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('ussd', 'USSD'),
        ('mobile_money', 'Mobile Money'),
        ('qr', 'QR Code'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payments")
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="payment", null=True, blank=True)
    reference = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES, default="paystack")
    payment_type = models.CharField(max_length=15, choices=PAYMENT_TYPE_CHOICES, blank=True, null=True, help_text="Specific payment type for Paystack payments")
    access_code = models.CharField(max_length=100, blank=True, null=True)
    authorization_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.order:
            return f"Payment for Order {self.order.id} - {self.status}"
        else:
            return f"Payment {self.reference} - {self.status}"
    
    def clean(self):
        """Validate payment data."""
        super().clean()
        # Note: We no longer validate that payment amount matches order total
        # because we want to preserve the actual amount paid through Paystack
        # which might differ from the calculated order total due to frontend/backend calculation differences
    
    def save(self, *args, **kwargs):
        """Override save to preserve actual payment amount from Paystack."""
        # CRITICAL: Preserve the actual payment amount from Paystack
        # Only update amount if it's not already set (for new payments)
        # This ensures we keep the actual amount paid, not the calculated order total
        if self.order_id is not None and self.amount is None:
            from decimal import Decimal, ROUND_HALF_UP
            # Only set to order total if amount is not already set
            self.amount = Decimal(str(self.order.total)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Validate before saving
        self.full_clean()
        super().save(*args, **kwargs)
    
    @classmethod
    def create(cls, **kwargs):
        """Override create to preserve actual payment amount."""
        # Preserve the amount if provided (from Paystack)
        # Only use order total if amount is not provided
        if 'order' in kwargs and 'amount' not in kwargs:
            from decimal import Decimal, ROUND_HALF_UP
            # Only set to order total if amount is not provided
            kwargs['amount'] = Decimal(str(kwargs['order'].total)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return super().create(**kwargs)
    
    class Meta:
        ordering = ['-created_at']


# ============================================================
# INVENTORY MODEL
# ============================================================

class InventoryItem(models.Model):
    """Physical inventory items (separate from food items)."""
    name = models.CharField(max_length=100, unique=True)
    quantity = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_inventory_items'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_inventory_items'
    )

    def __str__(self):
        return f"{self.name} (Qty: {self.quantity})"
    
    def clean(self):
        """Validate the inventory item data."""
        from django.core.exceptions import ValidationError
        
        # Ensure quantity is not negative
        if self.quantity < 0:
            raise ValidationError("Quantity cannot be negative.")
        
        # Ensure name is not empty
        if not self.name or not self.name.strip():
            raise ValidationError("Name is required.")
    
    def save(self, *args, **kwargs):
        """Override save to ensure validation and prevent field name confusion."""
        # Run validation
        self.clean()
        
        # Ensure quantity is always a positive integer
        if self.quantity < 0:
            self.quantity = 0
        
        # Call parent save
        super().save(*args, **kwargs)
    
    def get_quantity_display(self):
        """Get formatted quantity display."""
        return f"{self.quantity} {'unit' if self.quantity == 1 else 'units'}"

    class Meta:
        ordering = ['name']
        verbose_name_plural = "Inventory Items"


# ============================================================
# PLATE MODEL
# ============================================================

class Plate(models.Model):
    """Plate count and fees for bags."""
    bag = models.ForeignKey(Bag, on_delete=models.CASCADE, related_name='plates')
    count = models.PositiveIntegerField(default=1)
    fee_per_plate = models.DecimalField(max_digits=10, decimal_places=2, default=50.0)

    def __str__(self):
        return f"{self.bag.name} - {self.count} plates"

    @property
    def total_fee(self):
        """Calculate total plate fee."""
        return self.count * self.fee_per_plate


# ============================================================
# PIZZA OPTION MODEL
# ============================================================

class PizzaOption(models.Model):
    """Pizza size options with different prices."""
    SIZE_CHOICES = [
        ('S', 'Small'),
        ('M', 'Medium'),
        ('L', 'Large'),
    ]

    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE, related_name='pizza_options')
    size = models.CharField(max_length=1, choices=SIZE_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.food_item.name} - {self.get_size_display()}"

    class Meta:
        unique_together = ['food_item', 'size']


# ============================================================
# SYSTEM SETTINGS MODEL
# ============================================================

class SystemSettings(models.Model):
    """System-wide configurable settings for the food ordering platform."""
    SETTING_TYPES = [
        ('service_charge', 'Service Charge'),
        ('vat_percentage', 'VAT Percentage'),
        ('delivery_fee_base', 'Base Delivery Fee'),
        ('plate_fee', 'Plate Fee'),
    ]
    
    setting_type = models.CharField(max_length=20, choices=SETTING_TYPES, unique=True)
    value = models.DecimalField(max_digits=10, decimal_places=2, help_text="Setting value")
    description = models.TextField(blank=True, help_text="Description of what this setting controls")
    is_active = models.BooleanField(default=True, help_text="Whether this setting is currently active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_system_settings'
    )

    def __str__(self):
        return f"{self.get_setting_type_display()}: {self.value}"

    def clean(self):
        """Validate setting values."""
        from django.core.exceptions import ValidationError
        
        if self.setting_type == 'service_charge':
            if self.value < 0:
                raise ValidationError("Service charge must be 0 or greater.")
        elif self.setting_type == 'vat_percentage':
            if self.value < 0 or self.value > 50:
                raise ValidationError("VAT percentage must be between 0 and 50%.")
        elif self.setting_type == 'delivery_fee_base':
            if self.value < 0 or self.value > 10000:
                raise ValidationError("Base delivery fee must be between 0 and 10,000.")
        elif self.setting_type == 'plate_fee':
            if self.value < 0 or self.value > 1000:
                raise ValidationError("Plate fee must be between 0 and 1,000.")

    def save(self, *args, **kwargs):
        """Override save to ensure validation."""
        self.clean()
        super().save(*args, **kwargs)

    @classmethod
    def get_setting(cls, setting_type, default_value=0):
        """Get a setting value by type, with fallback to default."""
        try:
            setting = cls.objects.get(setting_type=setting_type, is_active=True)
            return setting.value
        except cls.DoesNotExist:
            return default_value

    @classmethod
    def set_setting(cls, setting_type, value, description="", updated_by=None):
        """Set a setting value, creating or updating as needed."""
        try:
            setting, created = cls.objects.get_or_create(
                setting_type=setting_type,
                defaults={
                    'value': value,
                    'description': description,
                    'updated_by': updated_by
                }
            )
            if not created:
                setting.value = value
                setting.description = description
                setting.updated_by = updated_by
                setting.full_clean()  # Explicitly call validation
                setting.save()
            return setting
        except Exception as e:
            raise Exception(f"Failed to set {setting_type}: {str(e)}")

    class Meta:
        ordering = ['setting_type']
        verbose_name = "System Setting"
        verbose_name_plural = "System Settings"
