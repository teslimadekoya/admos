from rest_framework import generics, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from django_filters.rest_framework import DjangoFilterBackend
from django.conf import settings
import requests

from .models import (
    Category, FoodItem, Bag, BagItem, Plate,
    Order, OrderNotification, Payment, InventoryItem
)
from .serializers import (
    CategorySerializer, FoodItemSerializer,
    BagSerializer, BagItemSerializer, PlateSerializer,
    OrderSerializer, OrderCreateSerializer, OrderStatusUpdateSerializer, NotificationSerializer,
    InventoryItemSerializer
)
from .permissions import IsAdminOrOwnerOrReadOnly
from .order_utils import create_order_with_bags, validate_order_integrity


# ------------------------
# CATEGORY
# ------------------------
class CategoryListCreateView(generics.ListCreateAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated, IsAdminOrOwnerOrReadOnly]


class CategoryRetrieveUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    lookup_field = 'id'


# ------------------------
# FOOD ITEM
# ------------------------
class FoodItemListCreateView(generics.ListCreateAPIView):
    serializer_class = FoodItemSerializer
    permission_classes = [IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    queryset = FoodItem.objects.all()  # Show all items including out-of-stock
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category', 'availability']
    search_fields = ['name']


class FoodItemRetrieveUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    queryset = FoodItem.objects.all()
    serializer_class = FoodItemSerializer
    permission_classes = [IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    lookup_field = 'id'


# ------------------------
# BAG
# ------------------------
class BagListCreateView(generics.ListCreateAPIView):
    serializer_class = BagSerializer
    permission_classes = [IsAuthenticated, IsAdminOrOwnerOrReadOnly]

    def get_queryset(self):
        return Bag.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['delivery_fee'] = float(self.request.query_params.get('delivery_fee', 0))
        return context


class BagRetrieveUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BagSerializer
    permission_classes = [IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    lookup_field = 'id'

    def get_queryset(self):
        return Bag.objects.filter(owner=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['delivery_fee'] = float(self.request.query_params.get('delivery_fee', 0))
        return context


# ------------------------
# BAG ITEM
# ------------------------
class BagItemListCreateView(generics.ListCreateAPIView):
    serializer_class = BagItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return BagItem.objects.filter(bag__owner=self.request.user)

    def perform_create(self, serializer):
        bag = serializer.validated_data['bag']
        if bag.owner != self.request.user:
            raise PermissionDenied("You cannot add items to someone else's bag.")
        
        # Validate portions availability before adding to bag
        food_item = serializer.validated_data['food_item']
        requested_portions = serializer.validated_data['portions']
        
        if not food_item.can_order_portions(requested_portions):
            if food_item.portions == 0:
                raise ValidationError(f"Sorry, {food_item.name} is currently out of stock.")
            else:
                raise ValidationError(f"Sorry, only {food_item.portions} portions of {food_item.name} available. You requested {requested_portions}.")
        
        # Validate plate requirements for food category items
        plates = serializer.validated_data.get('plates', 0)
        if food_item.is_food_category and plates == 0:
            raise ValidationError("At least one plate is required for food category items.")
        
        # Ensure non-food items have 0 plates
        if not food_item.is_food_category:
            serializer.validated_data['plates'] = 0
        
        serializer.save()


class BagItemRetrieveUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BagItemSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_queryset(self):
        return BagItem.objects.filter(bag__owner=self.request.user)
    
    def perform_update(self, serializer):
        """Validate portions availability and plate requirements when updating bag items."""
        instance = self.get_object()
        food_item = serializer.validated_data.get('food_item', instance.food_item)
        requested_portions = serializer.validated_data.get('portions', instance.portions)
        
        if food_item and not food_item.can_order_portions(requested_portions):
            if food_item.portions == 0:
                raise ValidationError(f"Sorry, {food_item.name} is currently out of stock.")
            else:
                raise ValidationError(f"Sorry, only {food_item.portions} portions of {food_item.name} available. You requested {requested_portions}.")
        
        # Validate plate requirements for food category items
        plates = serializer.validated_data.get('plates', instance.plates)
        if food_item and food_item.is_food_category and plates == 0:
            raise ValidationError("At least one plate is required for food category items.")
        
        # Ensure non-food items have 0 plates
        if food_item and not food_item.is_food_category:
            serializer.validated_data['plates'] = 0
        
        serializer.save()


# ------------------------
# ORDER
# ------------------------
class OrderListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return OrderCreateSerializer
        return OrderSerializer

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "role", None) == 'admin':
            return Order.objects.all()
        return Order.objects.filter(user=user)

    def perform_create(self, serializer):
        """Create order with proper validation and bag linking using utility function."""
        # Get bag IDs from the request
        bag_ids = self.request.data.get('bag_ids', [])
        delivery_address = self.request.data.get('delivery_address', '')
        contact_phone = self.request.data.get('contact_phone', '')
        delivery_fee = float(self.request.data.get('delivery_fee', 500))
        service_charge = float(self.request.data.get('service_charge', 100))
        
        # Use the utility function to create order with proper bag linking
        order = create_order_with_bags(
            user=self.request.user,
            bag_ids=bag_ids,
            delivery_address=delivery_address,
            contact_phone=contact_phone,
            delivery_fee=delivery_fee,
            service_charge=service_charge
        )
        
        # Validate the created order integrity
        validate_order_integrity(order)
        
        # Update the serializer instance with the created order
        serializer.instance = order


class OrderRetrieveUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "role", None) == 'admin':
            return Order.objects.all()
        return Order.objects.filter(user=user)

    def perform_destroy(self, instance):
        # Only unpaid orders can be deleted by customers (based on payment status)
        has_payment = hasattr(instance, 'payment') and instance.payment and instance.payment.status == 'success'
        if has_payment and getattr(self.request.user, "role", None) != 'admin':
            raise PermissionDenied("You cannot delete an order that has already been paid.")
        instance.delete()


class OrderStatusUpdateView(generics.UpdateAPIView):
    serializer_class = OrderStatusUpdateSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "role", None) == 'admin':
            return Order.objects.all()
        raise PermissionDenied("Only admins can update order status.")

    def perform_update(self, serializer):
        order = serializer.instance
        serializer.save()
        # Create notification when status updates (except Pending)
        if order.status != 'Pending':
            OrderNotification.objects.create(
                order=order,
                message=f"Order status updated to {order.status}"
            )


# ------------------------
# NOTIFICATIONS
# ------------------------
class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "role", None) == "admin":
            # Admin sees all notifications, fetch order and order.user
            return OrderNotification.objects.select_related('order', 'order__user').all()
        return OrderNotification.objects.filter(order__user=user)


class NotificationMarkSeenView(generics.UpdateAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "role", None) == "admin":
            return OrderNotification.objects.select_related('order', 'order__user').all()
        return OrderNotification.objects.filter(order__user=user)

    def perform_update(self, serializer):
        serializer.save(seen=True)

# ------------------------
# PAYMENT INITIALIZATION
# ------------------------
class InitializePaymentView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, *args, **kwargs):
        """
        Initialize a Paystack transaction.
        Expects: total_amount in request.data
        """
        total_amount = request.data.get("total_amount")
        if not total_amount:
            return Response({"error": "total_amount is required"}, status=status.HTTP_400_BAD_REQUEST)

        amount_kobo = int(float(total_amount) * 100)  # ✅ Paystack expects amount in kobo
        
        # Debug logging
        print(f'=== PAYMENT INITIALIZATION ===')
        print(f'Total amount received: {total_amount}')
        print(f'Amount in kobo: {amount_kobo}')
        print(f'Amount in NGN: ₦{amount_kobo / 100:,.2f}')
        print(f'=== END PAYMENT INITIALIZATION ===')

        # Make reference unique by appending timestamp
        import time
        reference = f"PAY-{request.user.id}-{int(time.time())}"

        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }
        data = {
            "email": request.user.email,
            "amount": amount_kobo,
            "reference": reference,
            "callback_url": "http://localhost:8000/payment/success/",  # redirect to our payment success page
        }

        try:
            response = requests.post("https://api.paystack.co/transaction/initialize", json=data, headers=headers, timeout=30)
            res_data = response.json()
        except requests.exceptions.ConnectionError as e:
            return Response({
                "error": "Unable to connect to payment service. Please check your internet connection and try again.",
                "details": str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except requests.exceptions.Timeout as e:
            return Response({
                "error": "Payment service request timed out. Please try again.",
                "details": str(e)
            }, status=status.HTTP_504_GATEWAY_TIMEOUT)
        except requests.exceptions.RequestException as e:
            return Response({
                "error": "Payment service error. Please try again later.",
                "details": str(e)
            }, status=status.HTTP_502_BAD_GATEWAY)
        except Exception as e:
            return Response({
                "error": "Unexpected error occurred while initializing payment.",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if res_data.get("status") is True:
            # Extract payment type from Paystack response if available
            payment_type = None
            if "data" in res_data and "authorization" in res_data["data"]:
                auth_data = res_data["data"]["authorization"]
                if "channel" in auth_data:
                    channel = auth_data["channel"]
                    # Map Paystack channels to our payment types
                    if channel in ["card"]:
                        payment_type = "card"
                    elif channel in ["bank_transfer", "bank"]:
                        payment_type = "bank_transfer"
                    elif channel in ["ussd"]:
                        payment_type = "ussd"
                    elif channel in ["mobile_money", "mobilemoney"]:
                        payment_type = "mobile_money"
                    elif channel in ["qr"]:
                        payment_type = "qr"
            
            # Save Payment record (no order yet - will be created after successful payment)
            Payment.objects.create(
                user=request.user,
                order=None,  # No order yet
                reference=reference,
                amount=float(total_amount),
                status="pending",
                payment_type=payment_type,
            )
            return Response(res_data["data"], status=status.HTTP_200_OK)
        else:
            return Response(res_data, status=status.HTTP_400_BAD_REQUEST)


# ------------------------
# PAYMENT VERIFICATION
# ------------------------
class VerifyPaymentView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, reference, *args, **kwargs):
        """
        Verify a Paystack transaction.
        Example: GET /api/store/payments/verify/<reference>/
        """
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        }
        url = f"https://api.paystack.co/transaction/verify/{reference}"
        response = requests.get(url, headers=headers)
        res_data = response.json()

        try:
            payment = Payment.objects.get(reference=reference, user=request.user)
        except Payment.DoesNotExist:
            return Response({"error": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)

        if res_data.get("data", {}).get("status") == "success":
            payment.status = "success"
            
            # Update payment type if not already set and available in response
            if not payment.payment_type and "data" in res_data:
                payment_data = res_data["data"]
                if "authorization" in payment_data:
                    auth_data = payment_data["authorization"]
                    if "channel" in auth_data:
                        channel = auth_data["channel"]
                        # Map Paystack channels to our payment types
                        if channel in ["card"]:
                            payment.payment_type = "card"
                        elif channel in ["bank_transfer", "bank"]:
                            payment.payment_type = "bank_transfer"
                        elif channel in ["ussd"]:
                            payment.payment_type = "ussd"
                        elif channel in ["mobile_money", "mobilemoney"]:
                            payment.payment_type = "mobile_money"
                        elif channel in ["qr"]:
                            payment.payment_type = "qr"
            
            payment.save()

            # Mark order as Pending (payment confirmed)
            payment.order.status = "Pending"
            payment.order.save()
            
            # Reduce quantities for all items in the order
            self._reduce_order_quantities(payment.order)
            
            # Create payment notification with customer name
            customer_name = f"{payment.user.first_name} {payment.user.last_name}".strip() or payment.user.phone_number
            OrderNotification.objects.create(
                order=payment.order,
                message=f"New Payment Received: A payment of ₦ {payment.amount} has been received for order #{payment.order.id} from {customer_name}."
            )

            return Response({"message": "Payment verified successfully"}, status=status.HTTP_200_OK)
        else:
            payment.status = "failed"
            payment.save()
            return Response({"message": "Payment failed"}, status=status.HTTP_400_BAD_REQUEST)
    
    def _reduce_order_quantities(self, order):
        """Reduce portions for all food items in the order after successful payment."""
        from django.db import transaction
        
        with transaction.atomic():
            for bag in order.bags.all():
                for bag_item in bag.items.all():
                    if bag_item.food_item:  # Only reduce if food_item still exists
                        try:
                            bag_item.food_item.reduce_portions(bag_item.portions)
                            # Note: availability is now purely based on portions, no need to update it
                                
                        except ValueError as e:
                            # Log the error but don't fail the payment
                            print(f"Warning: Could not reduce portions for {bag_item.food_item.name}: {e}")


# ------------------------
# PAYSTACK WEBHOOK
# ------------------------
class PaystackWebhookView(generics.GenericAPIView):
    """
    Webhook endpoint for Paystack to automatically verify payments.
    This endpoint is called by Paystack when a payment is completed.
    """
    permission_classes = []  # No authentication required for webhooks
    authentication_classes = []  # No authentication required for webhooks

    def post(self, request, *args, **kwargs):
        """
        Handle Paystack webhook events.
        """
        import hashlib
        import hmac
        
        # Get the webhook signature from headers
        signature = request.META.get('HTTP_X_PAYSTACK_SIGNATURE', '')
        
        # Verify webhook signature (optional but recommended for security)
        if signature:
            expected_signature = hmac.new(
                settings.PAYSTACK_SECRET_KEY.encode(),
                request.body,
                hashlib.sha512
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected_signature):
                return Response({"error": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Parse webhook data
        try:
            webhook_data = request.data
            event_type = webhook_data.get('event')
            
            if event_type == 'charge.success':
                # Payment was successful
                data = webhook_data.get('data', {})
                reference = data.get('reference')
                
                if reference:
                    # Find the payment record
                    try:
                        payment = Payment.objects.get(reference=reference)
                        
                        # Update payment status
                        payment.status = 'success'
                        
                        # Update payment type from webhook data
                        if 'authorization' in data:
                            auth_data = data['authorization']
                            channel = auth_data.get('channel', '')
                            
                            # Map Paystack channels to our payment types
                            if channel in ['card']:
                                payment.payment_type = 'card'
                            elif channel in ['bank_transfer', 'bank']:
                                payment.payment_type = 'bank_transfer'
                            elif channel in ['ussd']:
                                payment.payment_type = 'ussd'
                            elif channel in ['mobile_money', 'mobilemoney']:
                                payment.payment_type = 'mobile_money'
                            elif channel in ['qr']:
                                payment.payment_type = 'qr'
                        
                        payment.save()
                        
                        # Mark order as Pending (payment confirmed)
                        payment.order.status = 'Pending'
                        payment.order.save()
                        
                        # Reduce quantities for all items in the order
                        self._reduce_order_quantities(payment.order)
                        
                        # Create payment notification
                        customer_name = f"{payment.user.first_name} {payment.user.last_name}".strip() or payment.user.phone_number
                        OrderNotification.objects.create(
                            order=payment.order,
                            message=f"New Payment Received: A payment of ₦ {payment.amount} has been received for order #{payment.order.id} from {customer_name}."
                        )
                        
                        print(f"✅ Payment verified via webhook: {reference} for order #{payment.order.id}")
                        
                    except Payment.DoesNotExist:
                        print(f"⚠️ Payment not found for reference: {reference}")
                        return Response({"error": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)
                
            elif event_type == 'charge.failed':
                # Payment failed
                data = webhook_data.get('data', {})
                reference = data.get('reference')
                
                if reference:
                    try:
                        payment = Payment.objects.get(reference=reference)
                        payment.status = 'failed'
                        payment.save()
                        print(f"❌ Payment failed via webhook: {reference}")
                    except Payment.DoesNotExist:
                        print(f"⚠️ Payment not found for failed reference: {reference}")
            
            return Response({"status": "success"}, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"❌ Webhook error: {str(e)}")
            return Response({"error": "Webhook processing failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _reduce_order_quantities(self, order):
        """Reduce portions for all food items in the order after successful payment."""
        from django.db import transaction
        
        with transaction.atomic():
            for bag in order.bags.all():
                for bag_item in bag.items.all():
                    if bag_item.food_item:  # Only reduce if food_item still exists
                        try:
                            bag_item.food_item.reduce_portions(bag_item.portions)
                        except ValueError as e:
                            # Log the error but don't fail the payment
                            print(f"Warning: Could not reduce portions for {bag_item.food_item.name}: {e}")


# ------------------------
# CUSTOMER STATISTICS
# ------------------------
class CustomerStatsView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """Get customer statistics."""
        from django.contrib.auth import get_user_model
        from django.db.models import Count, Sum
        from django.utils import timezone
        
        User = get_user_model()
        
        # Get total customers (only those who have made payments)
        total_customers = User.objects.filter(
            role='customer',
            payments__isnull=False
        ).distinct().count()
        
        # Get new customers this month (using id as proxy for creation order)
        # Since we don't have date_joined, we'll use a different approach
        # Get customers who made their first payment this month
        this_month = timezone.now().replace(day=1)
        new_customers_this_month = User.objects.filter(
            role='customer',
            payments__isnull=False,
            payments__created_at__gte=this_month
        ).distinct().count()
        
        # Get active customers (customers with orders in the last 30 days)
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        active_customers = User.objects.filter(
            role='customer',
            payments__isnull=False,
            payments__created_at__gte=thirty_days_ago
        ).distinct().count()
        
        # Get customer with most orders
        top_customer = User.objects.filter(
            role='customer',
            payments__isnull=False,
            payments__status='success'  # Only count successful payments
        ).annotate(
            total_orders=Count('payments'),
            total_spent=Sum('payments__amount')
        ).order_by('-total_orders').first()
        
        stats = {
            'total_customers': total_customers,
            'new_customers_this_month': new_customers_this_month,
            'active_customers': active_customers,
            'top_customer': {
                'name': f"{top_customer.first_name} {top_customer.last_name}".strip() or top_customer.phone_number,
                'total_orders': top_customer.total_orders if top_customer else 0,
                'total_spent': float(top_customer.total_spent) if top_customer and top_customer.total_spent else 0
            } if top_customer else None
        }
        
        return Response(stats, status=status.HTTP_200_OK)


# ------------------------
# INVENTORY ITEM
# ------------------------
class InventoryItemListCreateView(generics.ListCreateAPIView):
    queryset = InventoryItem.objects.all()
    serializer_class = InventoryItemSerializer
    permission_classes = [IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['name', 'description']


class InventoryItemRetrieveUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    queryset = InventoryItem.objects.all()
    serializer_class = InventoryItemSerializer
    permission_classes = [IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    lookup_field = 'id'


# ------------------------
# DELIVERY FEE CALCULATION
# ------------------------
class CalculateDeliveryFeeView(generics.GenericAPIView):
    """
    Calculate delivery fee based on distance from restaurant to customer address.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, *args, **kwargs):
        """
        Calculate delivery fee based on customer address.
        Expects: delivery_address in request.data
        """
        delivery_address = request.data.get("delivery_address")
        if not delivery_address:
            return Response({"error": "delivery_address is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Restaurant address from footer
        restaurant_address = "No 3, Gbotifa Street, Kajola Bus Stop Imota"
        
        try:
            # Calculate distance using Google Maps Distance Matrix API
            distance_km = self.calculate_distance(restaurant_address, delivery_address)
            
            # Calculate delivery fee based on distance
            delivery_fee = self.calculate_delivery_fee(distance_km)
            
            return Response({
                "delivery_fee": int(round(delivery_fee / 100) * 100), # Rounded to nearest 100
                "distance_km": round(distance_km, 2),
                "restaurant_address": restaurant_address,
                "delivery_address": delivery_address
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "error": "Unable to calculate delivery fee. Please try again.",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def calculate_distance(self, origin, destination):
        """
        Calculate distance between two addresses using Google Maps API.
        For now, we'll use a simple calculation based on Lagos coordinates.
        """
        # For development, we'll use a simple distance calculation
        # In production, you'd use Google Maps Distance Matrix API
        
        # Lagos coordinates (approximate center)
        lagos_lat, lagos_lng = 6.5244, 3.3792
        
        # Simple distance calculation based on address similarity
        # This is a placeholder - in production, use proper geocoding
        import random
        
        # Simulate distance calculation (0.5km to 25km range)
        base_distance = random.uniform(0.5, 25.0)
        
        # Add some variation based on address keywords
        if any(keyword in destination.lower() for keyword in ['imota', 'kajola', 'gbotifa']):
            # Same area - lower distance
            base_distance = random.uniform(0.5, 3.0)
        elif any(keyword in destination.lower() for keyword in ['lagos', 'island', 'mainland']):
            # Different area - higher distance
            base_distance = random.uniform(5.0, 25.0)
        
        return base_distance

    def calculate_delivery_fee(self, distance_km):
        """
        Calculate delivery fee based on distance.
        """
        # Base delivery fee
        base_fee = 500  # ₦500 base fee
        
        # Distance-based pricing
        if distance_km <= 2:
            # Within 2km - base fee only
            return base_fee
        elif distance_km <= 5:
            # 2-5km - base fee + ₦100 per km
            return base_fee + (distance_km - 2) * 100
        elif distance_km <= 10:
            # 5-10km - base fee + ₦200 per km
            return base_fee + 300 + (distance_km - 5) * 200
        else:
            # Over 10km - base fee + ₦300 per km
            return base_fee + 1300 + (distance_km - 10) * 300
