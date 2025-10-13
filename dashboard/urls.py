from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("login/", views.dashboard_login, name="login"),
    path("login/otp/", views.otp_login, name="otp_login"),
    path("forgot-password/", views.forgot_password, name="forgot_password"),
    path("reset-password/", views.reset_password, name="reset_password"),
    path("logout/", views.dashboard_logout, name="logout"),
    path("", views.dashboard_home, name="home"),
    
    # Categories
    path("categories/", views.dashboard_categories, name="categories"),
    path("categories/add/", views.add_category, name="add_category"),
    path("categories/<int:category_id>/edit/", views.edit_category, name="edit_category"),
    path("categories/<int:category_id>/delete/", views.delete_category, name="delete_category"),
    path("categories/undo-delete/", views.undo_delete_category, name="undo_delete_category"),
    
    # Items
    path("items/", views.dashboard_items, name="items"),
    path("items/add/", views.add_item, name="add_item"),
    path("items/<int:item_id>/edit/", views.edit_item, name="edit_item"),
    path("items/<int:item_id>/delete/", views.delete_item, name="delete_item"),
    path("items/undo-delete/", views.undo_delete_item, name="undo_delete_item"),
    
    # Orders
    path("orders/", views.dashboard_orders, name="orders"),
    path("orders/delivered/", views.delivered_orders, name="delivered_orders"),
    path("orders/<int:order_id>/", views.order_details, name="order_details"),
    path("orders/<int:order_id>/update-status/", views.update_order_status, name="update_order_status"),
    path("orders/bulk-send-delivery/", views.bulk_send_for_delivery, name="bulk_send_delivery"),
    path("orders/bulk-mark-delivered/", views.bulk_mark_delivered, name="bulk_mark_delivered"),
    
    # Other pages
    path("payments/", views.dashboard_payments, name="payments"),
    path("users/", views.dashboard_users, name="users"),
    path("users/<int:customer_id>/orders/", views.customer_orders, name="customer_orders"),
    path("inventory/", views.dashboard_inventory, name="inventory"),
    path("inventory/add/", views.add_inventory_item, name="add_inventory_item"),
    path("inventory/<int:item_id>/edit/", views.edit_inventory_item, name="edit_inventory_item"),
    path("inventory/<int:item_id>/delete/", views.delete_inventory_item, name="delete_inventory_item"),
    
    # Staff Management
    path("staff/", views.dashboard_staff, name="staff"),
    path("staff/<int:user_id>/edit/", views.edit_staff, name="edit_staff"),
    
    # System Settings
    path("settings/", views.system_settings, name="system_settings"),
]
