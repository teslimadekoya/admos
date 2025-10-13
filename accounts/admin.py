from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models.deletion import ProtectedError
from django.contrib import messages
from .models import User

class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ("first_name", "last_name", "email", "phone_number", "role", "orders_count", "total_spent", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active")
    search_fields = ("phone_number", "email", "first_name", "last_name")
    ordering = ("phone_number",)
    
    def orders_count(self, obj):
        """Show number of orders for customers."""
        if obj.role == 'customer':
            # Only count successful payments for accurate order count
            return obj.payments.filter(status='success').count()
        return '-'
    orders_count.short_description = 'Orders'
    orders_count.admin_order_field = 'payments__count'
    
    def total_spent(self, obj):
        """Show total amount spent for customers."""
        if obj.role == 'customer':
            # Only count successful payments for accurate calculations
            successful_payments = obj.payments.filter(status='success')
            total = sum(payment.amount for payment in successful_payments)
            return f'₦{total:,.0f}' if total > 0 else '₦0'
        return '-'
    total_spent.short_description = 'Total Spent'

    fieldsets = (
        (None, {"fields": ("phone_number", "password")}),
        ("Personal Info", {"fields": ("first_name", "last_name", "email", "delivery_address", "role")}),
        ("Permissions", {"fields": ("is_staff", "is_active", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login",)}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("phone_number", "first_name", "last_name", "email", "delivery_address", "role", "password1", "password2", "is_staff", "is_active")}
        ),
    )

    def delete_model(self, request, obj):
        """Override delete to prevent deletion of users with orders/payments."""
        try:
            super().delete_model(request, obj)
        except ProtectedError:
            messages.error(request, f"Cannot delete user '{obj.get_full_name() or obj.phone_number}' because they have orders or payments. To deactivate this user instead, uncheck the 'Active' status.")
            return

    def delete_queryset(self, request, queryset):
        """Override bulk delete to prevent deletion of users with orders/payments."""
        deleted_count = 0
        for obj in queryset:
            try:
                obj.delete()
                deleted_count += 1
            except ProtectedError:
                messages.error(request, f"Cannot delete user '{obj.get_full_name() or obj.phone_number}' because they have orders or payments.")
        
        if deleted_count > 0:
            messages.success(request, f"Successfully deleted {deleted_count} user(s).")

    def save_model(self, request, obj, form, change):
        """Override save to prevent creating multiple admin users."""
        if obj.role == 'admin' and not change:  # Creating new admin user
            if User.objects.filter(role='admin').exists():
                messages.error(request, "Only one admin account is allowed.")
                return
        super().save_model(request, obj, form, change)

admin.site.register(User, CustomUserAdmin)
