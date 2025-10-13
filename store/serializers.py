from rest_framework import serializers
from .models import (
    Category, FoodItem, Bag, Plate, BagItem, PizzaOption,
    Order, OrderNotification, InventoryItem, Payment
)

# ------------------------------
# Category
# ------------------------------
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']


# ------------------------------
# PizzaOption
# ------------------------------
class PizzaOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PizzaOption
        fields = ['id', 'size', 'price']


# ------------------------------
# FoodItem
# ------------------------------
class FoodItemSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(
        slug_field="name",
        queryset=Category.objects.all()
    )
    is_food_category = serializers.ReadOnlyField()
    quantity_display = serializers.ReadOnlyField()
    is_out_of_stock = serializers.ReadOnlyField()
    can_order = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    is_plate_item = serializers.ReadOnlyField()
    show_stock = serializers.SerializerMethodField()

    class Meta:
        model = FoodItem
        fields = [
            'id', 'name', 'price', 'image_url', 'image',
            'category', 'availability', 'portions', 'is_food_category', 
            'quantity_display', 'is_out_of_stock', 'can_order', 'is_plate_item', 'show_stock'
        ]
    
    def get_can_order(self, obj):
        """Check if the item can be ordered (not out of stock, or always for Plate items)."""
        if obj.is_plate_item:
            return True  # Plate items can always be ordered
        return obj.portions > 0
    
    def get_image(self, obj):
        """Return the best available image (uploaded image takes priority over URL)."""
        if obj.image:
            # Return the full URL for uploaded images
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        elif obj.image_url:
            return obj.image_url
        return None
    
    def get_show_stock(self, obj):
        """Determine if stock information should be shown (not for Plate items)."""
        return not obj.is_plate_item


# ------------------------------
# Plate
# ------------------------------
class PlateSerializer(serializers.ModelSerializer):
    total_fee = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = Plate
        fields = ['id', 'count', 'fee_per_plate', 'total_fee', 'bag']


# ------------------------------
# BagItem
# ------------------------------
class BagItemSerializer(serializers.ModelSerializer):
    food_item = FoodItemSerializer(read_only=True)
    food_item_id = serializers.PrimaryKeyRelatedField(
        queryset=FoodItem.objects.all(), source='food_item', write_only=True
    )
    bag_id = serializers.PrimaryKeyRelatedField(
        queryset=Bag.objects.all(), source='bag', write_only=True
    )
    is_food_category = serializers.ReadOnlyField()
    quantity_display = serializers.ReadOnlyField()
    is_out_of_stock = serializers.SerializerMethodField()

    class Meta:
        model = BagItem
        fields = ['id', 'bag_id', 'food_item', 'food_item_id', 'portions', 'plates', 'food_cost', 'plate_cost', 'subtotal', 'is_food_category', 'quantity_display', 'is_out_of_stock']
    
    def get_is_out_of_stock(self, obj):
        """Check if the food item is out of stock."""
        return obj.food_item.portions == 0 if obj.food_item else False

    def validate(self, data):
        """Validate portions availability and plate requirements for food category items."""
        food_item = data.get('food_item')
        portions = data.get('portions', 1)
        plates = data.get('plates', 0)
        
        # Validate portions availability
        if food_item and not food_item.can_order_portions(portions):
            if food_item.portions == 0:
                raise serializers.ValidationError(f"Sorry, {food_item.name} is currently out of stock.")
            else:
                raise serializers.ValidationError(f"Sorry, only {food_item.portions} {food_item.quantity_display.split(' ', 1)[1]} of {food_item.name} available. You requested {portions}.")
        
        # Validate plate requirements for food category items
        if food_item and food_item.is_food_category and plates == 0:
            raise serializers.ValidationError("At least one plate is required for food category items")
        
        # Ensure non-food items have 0 plates
        if food_item and not food_item.is_food_category:
            data['plates'] = 0  # Force plates to 0 for non-food items
        
        return data

# ------------------------------
# Bag
# ------------------------------
class BagSerializer(serializers.ModelSerializer):
    items = BagItemSerializer(many=True, read_only=True)
    plates = PlateSerializer(many=True, read_only=True)
    owner = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()
    service_charge = serializers.SerializerMethodField()
    total_fee = serializers.SerializerMethodField()
    has_food_items = serializers.ReadOnlyField()

    class Meta:
        model = Bag
        fields = [
            'id', 'name', 'owner', 'items', 'plates',
            'subtotal', 'service_charge', 'total_fee', 'has_food_items'
        ]
        read_only_fields = ['owner']

    def validate(self, data):
        """Validate overall bag plate requirements."""
        # This validation will be called when the bag is saved
        # The actual validation happens in the model's validate_plate_requirements method
        return data

    def get_owner(self, obj):
        return {
            'first_name': obj.owner.first_name,
            'last_name': obj.owner.last_name,
            'phone_number': obj.owner.phone_number
        }

    def get_subtotal(self, obj):
        return sum([item.subtotal for item in obj.items.all()])

    def get_service_charge(self, obj):
        # Flat service charge per bag (or customize)
        return 200

    def get_total_fee(self, obj):
        return self.get_subtotal(obj) + self.get_service_charge(obj)


# ------------------------------
# Order
# ------------------------------
class OrderCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating orders with proper bag linking."""
    bag_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        help_text="List of bag IDs to include in this order"
    )
    bags = BagSerializer(many=True, read_only=True)
    subtotal = serializers.ReadOnlyField()
    service_charge = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'user', 'bags', 'bag_ids', 'delivery_address', 'contact_phone',
            'delivery_fee', 'subtotal', 'service_charge',
            'total', 'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'status']

    def get_user(self, obj):
        return {
            'id': obj.user.id,
            'first_name': obj.user.first_name,
            'last_name': obj.user.last_name,
            'phone_number': obj.user.phone_number
        }

    def get_service_charge(self, obj):
        return obj.service_charge or 0

    def get_total(self, obj):
        delivery_fee = obj.delivery_fee or 0
        return obj.subtotal + self.get_service_charge(obj) + delivery_fee

    def validate_bag_ids(self, value):
        """Validate that all bag IDs exist and belong to the user."""
        user = self.context['request'].user
        if not value:
            raise serializers.ValidationError("At least one bag must be provided.")
        
        # Check if all bags exist and belong to the user
        existing_bags = Bag.objects.filter(id__in=value, owner=user)
        if len(existing_bags) != len(value):
            raise serializers.ValidationError("One or more bags not found or don't belong to you.")
        
        return value

    def create(self, validated_data):
        """Create order and properly link bags."""
        bag_ids = validated_data.pop('bag_ids')
        user = self.context['request'].user
        
        # Create the order
        order = Order.objects.create(
            user=user,
            delivery_address=validated_data.get('delivery_address', ''),
            contact_phone=validated_data.get('contact_phone', ''),
            delivery_fee=validated_data.get('delivery_fee', 500),
            service_charge=validated_data.get('service_charge', 100)
        )
        
        # Link bags to the order
        bags = Bag.objects.filter(id__in=bag_ids, owner=user)
        order.bags.set(bags)
        
        return order


class OrderSerializer(serializers.ModelSerializer):
    """Read-only serializer for displaying orders."""
    bags = BagSerializer(many=True, read_only=True)
    subtotal = serializers.ReadOnlyField()
    service_charge = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()
    payment = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'user', 'bags', 'delivery_address', 'contact_phone',
            'delivery_fee', 'subtotal', 'service_charge',
            'total', 'status', 'payment', 'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'status']

    def get_user(self, obj):
        return {
            'id': obj.user.id,
            'first_name': obj.user.first_name,
            'last_name': obj.user.last_name,
            'phone_number': obj.user.phone_number
        }

    def get_service_charge(self, obj):
        return obj.service_charge or 0

    def get_total(self, obj):
        delivery_fee = obj.delivery_fee or 0
        return obj.subtotal + self.get_service_charge(obj) + delivery_fee

    def get_payment(self, obj):
        """Get payment information for the order."""
        if hasattr(obj, 'payment') and obj.payment:
            return {
                'id': obj.payment.id,
                'payment_method': obj.payment.payment_method,
                'status': obj.payment.status,
                'reference': obj.payment.reference,
                'amount': obj.payment.amount,
                'created_at': obj.payment.created_at
            }
        return None


# ------------------------------
# Order Status Update
# ------------------------------
class OrderStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ['status']


# ------------------------------
# Inventory Item
# ------------------------------
class InventoryItemSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True)

    class Meta:
        model = InventoryItem
        fields = [
            'id', 'name', 'quantity', 'description',
            'created_at', 'updated_at', 'created_by', 'updated_by',
            'created_by_name', 'updated_by_name'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']


# ------------------------------
# Payment
# ------------------------------
class PaymentSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    order_id = serializers.IntegerField(source='order.id', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'user', 'order', 'order_id', 'reference', 'amount', 
            'status', 'payment_method', 'access_code', 'authorization_url',
            'created_at', 'updated_at', 'user_name'
        ]
        read_only_fields = ['user', 'order', 'reference', 'access_code', 'authorization_url']

    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.phone_number


# ------------------------------
# Notifications
# ------------------------------
class NotificationSerializer(serializers.ModelSerializer):
    user_first_name = serializers.CharField(source='order.user.first_name', read_only=True)
    user_last_name = serializers.CharField(source='order.user.last_name', read_only=True)
    user_phone = serializers.CharField(source='order.user.phone_number', read_only=True)

    class Meta:
        model = OrderNotification
        fields = [
            'id', 'order', 'message', 'seen', 'created_at',
            'user_first_name', 'user_last_name', 'user_phone'
        ]