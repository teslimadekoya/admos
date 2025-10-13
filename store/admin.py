from django.contrib import admin
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import (
    Order, OrderNotification,
    Category, FoodItem, Bag, BagItem, Plate, PizzaOption, InventoryItem, SystemSettings
)


# --- ORDERS ADMIN ---
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user', 'status', 'delivery_fee', 'service_charge', 'vat_percentage', 'vat_amount',
        'total', 'created_at', 'updated_at'
    )
    list_filter = ('status', 'created_at', 'updated_at')
    search_fields = ('user__first_name', 'user__last_name', 'user__phone_number', 'delivery_address', 'contact_phone')
    readonly_fields = ('total',)
    filter_horizontal = ('bags',)  # ManyToManyField support


@admin.register(OrderNotification)
class OrderNotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'message', 'seen', 'created_at')
    list_filter = ('seen', 'created_at')
    search_fields = ('order__user__username', 'message')


# --- MENU ADMIN ---
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'food_items_count']
    search_fields = ['name']
    
    def food_items_count(self, obj):
        return obj.food_items.count()
    food_items_count.short_description = 'Food Items Count'
    
    def delete_model(self, request, obj):
        """Override delete to handle category and food item deletion intelligently."""
        with transaction.atomic():
            # Get all food items in this category
            food_items = FoodItem.objects.filter(category=obj)
            
            # Ensure all bag items have historical data before deletion
            self._populate_historical_data_for_food_items(food_items)
            
            # Clear cart items from deleted food items (only for unpaid orders)
            self._clear_cart_items_for_food_items(food_items)
            
            # Delete the category (this will CASCADE delete all food items)
            super().delete_model(request, obj)
    
    def delete_queryset(self, request, queryset):
        """Override bulk delete to handle category and food item deletion intelligently."""
        with transaction.atomic():
            # Get all food items in these categories
            food_items = FoodItem.objects.filter(category__in=queryset)
            
            # Ensure all bag items have historical data before deletion
            self._populate_historical_data_for_food_items(food_items)
            
            # Clear cart items from deleted food items (only for unpaid orders)
            self._clear_cart_items_for_food_items(food_items)
            
            # Delete the categories (this will CASCADE delete all food items)
            super().delete_queryset(request, queryset)
    
    def _clear_cart_items_for_food_items(self, food_items):
        """Clear cart items for food items that are being deleted."""
        # Get all bag items that reference these food items
        bag_items = BagItem.objects.filter(food_item__in=food_items)
        
        # Only clear items from bags that are NOT in any orders (i.e., active carts)
        # This preserves historical data for delivered/paid orders
        active_bag_items = bag_items.filter(bag__orders__isnull=True)
        
        # Delete the active cart items
        active_bag_items.delete()
        
        # For bag items that ARE in orders (unpaid orders), we should also clear them
        # since the food items are no longer available
        ordered_bag_items = bag_items.filter(bag__orders__isnull=False)
        
        # Only clear from unpaid orders (not delivered ones) - based on payment status
        unpaid_orders = Order.objects.filter(payment__isnull=True)
        unpaid_bag_items = ordered_bag_items.filter(bag__orders__in=unpaid_orders)
        
        # Delete items from unpaid orders
        unpaid_bag_items.delete()
    
    def _populate_historical_data_for_food_items(self, food_items):
        """Ensure all bag items have historical data before food items are deleted."""
        for food_item in food_items:
            # Get all bag items that reference this food item
            bag_items = BagItem.objects.filter(food_item=food_item)
            
            # Update bag items that don't have historical data
            for bag_item in bag_items:
                if not bag_item.item_name:
                    bag_item.item_name = food_item.name
                    bag_item.item_price = food_item.price
                    if food_item.category:
                        bag_item.item_category = food_item.category.name
                    bag_item.save()


@admin.register(FoodItem)
class FoodItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'category', 'price', 'portions', 'availability', 'created_by', 'updated_by', 'bags_list']
    list_filter = ['category', 'availability', 'created_by', 'updated_by']
    search_fields = ['name', 'category__name']
    readonly_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "category":
            # Exclude the "All" category from the dropdown
            kwargs["queryset"] = Category.objects.exclude(name__iexact='All').order_by('id')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def bags_list(self, obj):
        bags = Bag.objects.filter(items__food_item=obj).distinct()
        return ", ".join([bag.name for bag in bags])
    bags_list.short_description = "Bags"
    
    def save_model(self, request, obj, form, change):
        """Set created_by and updated_by fields when saving."""
        if not change:  # Creating new object
            obj.created_by = request.user
        obj.updated_by = request.user
        
        # Call clean method to validate data
        obj.full_clean()
        
        super().save_model(request, obj, form, change)
    
    def delete_model(self, request, obj):
        """Override delete to clear cart items for deleted food item."""
        with transaction.atomic():
            # Ensure all bag items have historical data before deletion
            self._populate_historical_data_for_food_item(obj)
            
            # Clear cart items for this food item
            self._clear_cart_items_for_food_item(obj)
            
            # Delete the food item
            super().delete_model(request, obj)
    
    def delete_queryset(self, request, queryset):
        """Override bulk delete to clear cart items for deleted food items."""
        with transaction.atomic():
            # Ensure all bag items have historical data before deletion
            for food_item in queryset:
                self._populate_historical_data_for_food_item(food_item)
            
            # Clear cart items for these food items
            for food_item in queryset:
                self._clear_cart_items_for_food_item(food_item)
            
            # Delete the food items
            super().delete_queryset(request, queryset)
    
    def _clear_cart_items_for_food_item(self, food_item):
        """Clear cart items for a specific food item being deleted."""
        # Get all bag items that reference this food item
        bag_items = BagItem.objects.filter(food_item=food_item)
        
        # Only clear items from bags that are NOT in any orders (i.e., active carts)
        active_bag_items = bag_items.filter(bag__orders__isnull=True)
        
        # Delete the active cart items
        active_bag_items.delete()
        
        # For bag items that ARE in orders (unpaid orders), clear them too - based on payment status
        ordered_bag_items = bag_items.filter(bag__orders__isnull=False)
        unpaid_orders = Order.objects.filter(payment__isnull=True)
        unpaid_bag_items = ordered_bag_items.filter(bag__orders__in=unpaid_orders)
        
        # Delete items from unpaid orders
        unpaid_bag_items.delete()
    
    def _populate_historical_data_for_food_item(self, food_item):
        """Ensure all bag items have historical data before food item is deleted."""
        # Get all bag items that reference this food item
        bag_items = BagItem.objects.filter(food_item=food_item)
        
        # Update bag items that don't have historical data
        for bag_item in bag_items:
            if not bag_item.item_name:
                bag_item.item_name = food_item.name
                bag_item.item_price = food_item.price
                if food_item.category:
                    bag_item.item_category = food_item.category.name
                bag_item.save()


@admin.register(Bag)
class BagAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'owner_first_name', 'owner_last_name', 'owner_phone', 'created_at']
    search_fields = ['name', 'owner__first_name', 'owner__last_name', 'owner__phone_number']

    def owner_first_name(self, obj):
        return obj.owner.first_name
    owner_first_name.short_description = 'First Name'

    def owner_last_name(self, obj):
        return obj.owner.last_name
    owner_last_name.short_description = 'Last Name'

    def owner_phone(self, obj):
        return obj.owner.phone_number
    owner_phone.short_description = 'Phone Number'


@admin.register(Plate)
class PlateAdmin(admin.ModelAdmin):
    list_display = ['id', 'bag', 'count', 'fee_per_plate', 'total_fee']
    list_filter = ['bag']
    search_fields = ['bag__name']


@admin.register(PizzaOption)
class PizzaOptionAdmin(admin.ModelAdmin):
    list_display = ['id', 'food_item', 'size', 'price']
    list_filter = ['size']
    search_fields = ['food_item__name']


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'quantity', 'description', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ['id', 'setting_type', 'value', 'is_active', 'updated_by', 'updated_at']
    list_filter = ['setting_type', 'is_active', 'updated_at']
    search_fields = ['setting_type', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Setting Information', {
            'fields': ('setting_type', 'value', 'description', 'is_active')
        }),
        ('Audit Information', {
            'fields': ('updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Set updated_by field when saving."""
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of critical system settings."""
        if obj and obj.setting_type in ['service_charge', 'vat_percentage']:
            return False
        return super().has_delete_permission(request, obj)


# --- CUSTOM ADMIN DASHBOARD ---
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import views as auth_views
from django.urls import path

class CustomAdminSite(admin.AdminSite):
    site_header = "Admos Place Admin"
    site_title = "Admos Place Admin Portal"
    index_title = "Welcome to Admos Place Administration"
    
    def get_urls(self):
        """Override to use CSRF-exempt login view"""
        urls = super().get_urls()
        # Replace the login view with a CSRF-exempt version
        custom_urls = [
            path('login/', csrf_exempt(auth_views.LoginView.as_view()), name='login'),
        ]
        return custom_urls + urls

    def index(self, request, extra_context=None):
        """Custom admin index with customer statistics."""
        User = get_user_model()
        
        # Get customer statistics
        total_customers = User.objects.filter(
            role='customer',
            payments__isnull=False
        ).distinct().count()
        
        # Get new customers this month
        this_month = timezone.now().replace(day=1)
        new_customers_this_month = User.objects.filter(
            role='customer',
            payments__isnull=False,
            payments__created_at__gte=this_month
        ).distinct().count()
        
        # Get active customers (last 30 days)
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        active_customers = User.objects.filter(
            role='customer',
            payments__isnull=False,
            payments__created_at__gte=thirty_days_ago
        ).distinct().count()
        
        # Get top customer
        top_customer = User.objects.filter(
            role='customer',
            payments__isnull=False,
            payments__status='success'  # Only count successful payments
        ).annotate(
            total_orders=Count('payments'),
            total_spent=Sum('payments__amount')
        ).order_by('-total_orders').first()
        
        # Get today's orders
        today = timezone.now().date()
        today_orders = Order.objects.filter(
            payment__isnull=False,
            payment__status='success',
            status__in=['Pending', 'On the Way']  # Only count active orders
        ).count()
        
        # Get today's revenue
        from store.models import Payment
        today_revenue = Payment.objects.filter(
            status='success',
            created_at__date=today
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Get inventory stats
        total_items = FoodItem.objects.count()
        available_items = FoodItem.objects.filter(portions__gt=0).count()
        out_of_stock_items = FoodItem.objects.filter(portions=0).count()
        
        extra_context = extra_context or {}
        extra_context.update({
            'total_customers': total_customers,
            'new_customers_this_month': new_customers_this_month,
            'active_customers': active_customers,
            'top_customer': top_customer,
            'today_orders': today_orders,
            'today_revenue': today_revenue,
            'total_items': total_items,
            'available_items': available_items,
            'out_of_stock_items': out_of_stock_items,
        })
        
        return super().index(request, extra_context)


# Replace the default admin site
admin_site = CustomAdminSite(name='custom_admin')

# Register all models with the custom admin site
admin_site.register(Order, OrderAdmin)
admin_site.register(OrderNotification, OrderNotificationAdmin)
admin_site.register(Category, CategoryAdmin)
admin_site.register(FoodItem, FoodItemAdmin)
admin_site.register(Bag, BagAdmin)
admin_site.register(Plate, PlateAdmin)
admin_site.register(PizzaOption, PizzaOptionAdmin)
admin_site.register(InventoryItem, InventoryItemAdmin)
admin_site.register(SystemSettings, SystemSettingsAdmin)

# Register User model
User = get_user_model()
from accounts.admin import CustomUserAdmin
admin_site.register(User, CustomUserAdmin)
