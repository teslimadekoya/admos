"""
URL patterns for customer-facing website.
"""
from django.urls import path
from . import views

app_name = "customer_site"

urlpatterns = [
    # Main pages
    path("", views.homepage, name="homepage"),
    path("search/", views.search, name="search"),
    path("cart/", views.cart, name="cart"),
    path("checkout/", views.checkout, name="checkout"),
    # Friendly alias for orders history
    path("order-history/", views.order_history, name="order_history_alias"),
    path("orders/", views.order_history, name="order_history"),
    path("orders/<int:order_id>/", views.order_tracking, name="order_tracking"),
    path("order-tracking/<int:order_id>/", views.order_tracking, name="order_tracking_alias"),
    path("payment/success/", views.payment_success, name="payment_success"),
    path("profile/", views.profile, name="profile"),
    
    # AJAX endpoints
    path("api/add-to-cart/", views.add_to_cart, name="add_to_cart"),
    path("api/update-cart/", views.update_cart_item, name="update_cart_item"),
    path("api/remove-from-cart/", views.remove_from_cart, name="remove_from_cart"),
    path("api/get-cart/", views.get_cart, name="get_cart"),
    path("api/clear-cart/", views.clear_cart, name="clear_cart"),
    
    # Bag management endpoints
    path("api/create-bag/", views.create_bag, name="create_bag"),
    path("api/get-bags/", views.get_bags, name="get_bags"),
    path("api/switch-bag/", views.switch_bag, name="switch_bag"),
    path("api/delete-bag/", views.delete_bag, name="delete_bag"),
    
    # Order creation from cart
    path("api/create-order-from-cart/", views.create_order_from_cart, name="create_order_from_cart"),
    
    # User orders API
    path("api/user-orders/", views.get_user_orders_api, name="get_user_orders_api"),
    
    # Manual cart clearing (for debugging)
    path("clear-cart-now/", views.manual_clear_cart, name="manual_clear_cart"),
    path("debug-session/", views.debug_session, name="debug_session"),
]
