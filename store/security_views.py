"""
Secure API Views with Enhanced Security
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
import logging
import time

from .models import FoodItem, Bag, BagItem, Order, Payment
from .serializers import FoodItemSerializer, BagSerializer, OrderSerializer
from .permissions import IsAdminOrOwnerOrReadOnly

User = get_user_model()
logger = logging.getLogger('food_ordering.security')

class SecureUserRateThrottle(UserRateThrottle):
    """Custom rate throttle for authenticated users"""
    scope = 'user'

class SecureAnonRateThrottle(AnonRateThrottle):
    """Custom rate throttle for anonymous users"""
    scope = 'anon'

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([SecureUserRateThrottle])
@never_cache
def secure_food_items(request):
    """
    Secure endpoint for food items with enhanced validation
    """
    try:
        # Input validation
        category = request.GET.get('category', '').strip()
        search = request.GET.get('search', '').strip()
        
        # Sanitize inputs
        if category and not category.replace('-', '').replace('_', '').isalnum():
            return Response({
                'error': 'Invalid category parameter'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if search and len(search) > 100:
            return Response({
                'error': 'Search term too long'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get food items with security checks
        queryset = FoodItem.objects.all()
        
        if category:
            queryset = queryset.filter(category__name__iexact=category)
        
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        # Limit results to prevent data exposure
        queryset = queryset[:100]
        
        serializer = FoodItemSerializer(queryset, many=True)
        
        # Log access
        logger.info(f"Food items accessed by user {request.user.id}")
        
        return Response({
            'items': serializer.data,
            'count': len(serializer.data)
        })
        
    except Exception as e:
        logger.error(f"Error in secure_food_items: {str(e)}")
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([SecureUserRateThrottle])
@transaction.atomic
def secure_create_bag_item(request):
    """
    Secure endpoint for creating bag items with validation
    """
    try:
        # Input validation
        food_item_id = request.data.get('food_item_id')
        portions = request.data.get('portions', 1)
        plates = request.data.get('plates', 0)
        
        # Validate food_item_id
        if not food_item_id or not isinstance(food_item_id, int):
            return Response({
                'error': 'Valid food_item_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate portions
        if not isinstance(portions, int) or portions < 1 or portions > 100:
            return Response({
                'error': 'Portions must be between 1 and 100'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate plates
        if not isinstance(plates, int) or plates < 0 or plates > 50:
            return Response({
                'error': 'Plates must be between 0 and 50'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get food item
        try:
            food_item = FoodItem.objects.get(id=food_item_id)
        except FoodItem.DoesNotExist:
            return Response({
                'error': 'Food item not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check availability
        if not food_item.can_order_portions(portions):
            return Response({
                'error': f'Not enough {food_item.name} in stock. Available: {food_item.portions}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get or create bag
        bag, created = Bag.objects.get_or_create(
            owner=request.user,
            defaults={'name': f'Bag for {request.user.get_full_name()}'}
        )
        
        # Create bag item with validation
        try:
            bag_item = BagItem.objects.create(
                bag=bag,
                food_item=food_item,
                portions=portions,
                plates=plates
            )
            
            # Log creation
            logger.info(f"Bag item created by user {request.user.id}: {food_item.name} x{portions}")
            
            return Response({
                'message': 'Item added to bag successfully',
                'bag_item_id': bag_item.id,
                'bag_total': bag.total_cost
            }, status=status.HTTP_201_CREATED)
            
        except ValidationError as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"Error in secure_create_bag_item: {str(e)}")
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([SecureUserRateThrottle])
@transaction.atomic
def secure_create_order(request):
    """
    Secure endpoint for creating orders with comprehensive validation
    """
    try:
        # Input validation
        delivery_address = request.data.get('delivery_address', '').strip()
        contact_phone = request.data.get('contact_phone', '').strip()
        delivery_fee = request.data.get('delivery_fee', 500)
        service_charge = request.data.get('service_charge', 100)
        
        # Validate required fields
        if not delivery_address or len(delivery_address) < 10:
            return Response({
                'error': 'Valid delivery address is required (minimum 10 characters)'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not contact_phone or len(contact_phone) < 10:
            return Response({
                'error': 'Valid contact phone is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate fees
        if not isinstance(delivery_fee, (int, float)) or delivery_fee < 0 or delivery_fee > 10000:
            return Response({
                'error': 'Invalid delivery fee'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not isinstance(service_charge, (int, float)) or service_charge < 0 or service_charge > 5000:
            return Response({
                'error': 'Invalid service charge'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get user's bags
        bags = Bag.objects.filter(owner=request.user)
        if not bags.exists():
            return Response({
                'error': 'No items in bag'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate all bags
        for bag in bags:
            if not bag.items.exists():
                return Response({
                    'error': f'Bag "{bag.name}" is empty'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check availability for all items
            for item in bag.items.all():
                if not item.food_item.can_order_portions(item.portions):
                    return Response({
                        'error': f'Not enough {item.food_item.name} in stock'
                    }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create order
        order = Order.objects.create(
            user=request.user,
            delivery_address=delivery_address,
            contact_phone=contact_phone,
            delivery_fee=delivery_fee,
            service_charge=service_charge
        )
        
        # Add bags to order
        order.bags.set(bags)
        
        # Log order creation
        logger.info(f"Order created by user {request.user.id}: #{order.id}")
        
        return Response({
            'message': 'Order created successfully',
            'order_id': order.id,
            'total': order.total,
            'status': order.status
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Error in secure_create_order: {str(e)}")
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([SecureUserRateThrottle])
@never_cache
def secure_user_orders(request):
    """
    Secure endpoint for user's orders
    """
    try:
        # Get user's orders with security checks
        orders = Order.objects.filter(user=request.user).order_by('-created_at')[:50]
        
        serializer = OrderSerializer(orders, many=True)
        
        # Log access
        logger.info(f"Orders accessed by user {request.user.id}")
        
        return Response({
            'orders': serializer.data,
            'count': len(serializer.data)
        })
        
    except Exception as e:
        logger.error(f"Error in secure_user_orders: {str(e)}")
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([SecureUserRateThrottle])
@ratelimit(key='user', rate='5/m', method='POST', block=False)
def secure_payment_verification(request):
    """
    Secure endpoint for payment verification
    """
    try:
        # Input validation
        order_id = request.data.get('order_id')
        reference = request.data.get('reference', '').strip()
        
        if not order_id or not isinstance(order_id, int):
            return Response({
                'error': 'Valid order_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not reference or len(reference) < 10:
            return Response({
                'error': 'Valid payment reference is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get order
        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            return Response({
                'error': 'Order not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if payment already exists
        if hasattr(order, 'payment') and order.payment:
            return Response({
                'error': 'Payment already exists for this order'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create payment (in real implementation, verify with payment provider)
        payment = Payment.objects.create(
            order=order,
            user=request.user,
            reference=reference,
            amount=order.total,
            status='success'  # In real implementation, verify this
        )
        
        # Log payment
        logger.info(f"Payment created by user {request.user.id}: {reference} for order #{order.id}")
        
        return Response({
            'message': 'Payment verified successfully',
            'payment_id': payment.id,
            'status': payment.status
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Error in secure_payment_verification: {str(e)}")
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
