from django.urls import path
from .views import (
    # Categories
    CategoryListCreateView, CategoryRetrieveUpdateDeleteView,

    # Food Items
    FoodItemListCreateView, FoodItemRetrieveUpdateDeleteView,

    # Bags
    BagListCreateView, BagRetrieveUpdateDeleteView,

    # Bag Items
    BagItemListCreateView, BagItemRetrieveUpdateDeleteView,

    # Orders
    OrderListCreateView, OrderRetrieveUpdateDeleteView,
    OrderStatusUpdateView,

    # Notifications
    NotificationListView, NotificationMarkSeenView,

    # Payments
    InitializePaymentView, VerifyPaymentView, PaystackWebhookView,

    # Customer Statistics
    CustomerStatsView,

    # Inventory Items
    InventoryItemListCreateView, InventoryItemRetrieveUpdateDeleteView,
    
    # Delivery Fee Calculation
    CalculateDeliveryFeeView,
)
from .security_views import (
    secure_food_items,
    secure_create_bag_item,
    secure_create_order,
    secure_user_orders,
    secure_payment_verification,
)

app_name = "store"

urlpatterns = [
    # -----------------
    # Categories
    # -----------------
    path("categories/", CategoryListCreateView.as_view(), name="category-list-create"),
    path("categories/<int:id>/", CategoryRetrieveUpdateDeleteView.as_view(), name="category-rud"),

    # -----------------
    # Food Items
    # -----------------
    path("items/", FoodItemListCreateView.as_view(), name="fooditem-list-create"),
    path("items/<int:id>/", FoodItemRetrieveUpdateDeleteView.as_view(), name="fooditem-rud"),

    # -----------------
    # Bags
    # -----------------
    path("bags/", BagListCreateView.as_view(), name="bag-list-create"),
    path("bags/<int:id>/", BagRetrieveUpdateDeleteView.as_view(), name="bag-rud"),

    # -----------------
    # Bag Items
    # -----------------
    path("bag-items/", BagItemListCreateView.as_view(), name="bagitem-list-create"),
    path("bag-items/<int:id>/", BagItemRetrieveUpdateDeleteView.as_view(), name="bagitem-rud"),

    # -----------------
    # Orders
    # -----------------
    path("orders/", OrderListCreateView.as_view(), name="order-list-create"),
    path("orders/<int:id>/", OrderRetrieveUpdateDeleteView.as_view(), name="order-rud"),
    path("orders/<int:id>/status/", OrderStatusUpdateView.as_view(), name="order-status-update"),

    # -----------------
    # Notifications
    # -----------------
    path("notifications/", NotificationListView.as_view(), name="notifications"),
    path("notifications/<int:id>/mark-seen/", NotificationMarkSeenView.as_view(), name="notification-mark-seen"),

    # -----------------
    # Payments
    # -----------------
    path("payments/initialize/", InitializePaymentView.as_view(), name="initialize-payment"),
    path("payments/verify/<str:reference>/", VerifyPaymentView.as_view(), name="verify-payment"),
    path("payments/webhook/", PaystackWebhookView.as_view(), name="paystack-webhook"),

    # -----------------
    # Customer Statistics
    # -----------------
    path("customers/stats/", CustomerStatsView.as_view(), name="customer-stats"),

    # -----------------
    # Inventory Items
    # -----------------
    path("inventory/", InventoryItemListCreateView.as_view(), name="inventory-list-create"),
    path("inventory/<int:id>/", InventoryItemRetrieveUpdateDeleteView.as_view(), name="inventory-rud"),
    
    # -----------------
    # Delivery Fee Calculation
    # -----------------
    path("delivery-fee/calculate/", CalculateDeliveryFeeView.as_view(), name="calculate-delivery-fee"),
    
    # -----------------
    # Secure API Endpoints
    # -----------------
    path("secure/items/", secure_food_items, name="secure-food-items"),
    path("secure/bag-items/", secure_create_bag_item, name="secure-create-bag-item"),
    path("secure/orders/", secure_create_order, name="secure-create-order"),
    path("secure/user-orders/", secure_user_orders, name="secure-user-orders"),
    path("secure/payment-verify/", secure_payment_verification, name="secure-payment-verification"),
]
