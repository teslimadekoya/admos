"""
Customer-facing website views for Admos Place food ordering.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
import json
import requests
from datetime import datetime
from django.conf import settings
from store.models import FoodItem, Category, Order, SystemSettings


def homepage(request):
    """Homepage with featured items and restaurant info."""
    print("=== HOMEPAGE VIEW DEBUG ===")
    
    # Get all available food items from database, ordered alphabetically by name
    food_items = FoodItem.objects.filter(availability=True).select_related('category').order_by('name')
    print(f"DEBUG: Found {food_items.count()} food items")
    
    # Get all categories except 'All' (which is a special category)
    # Order by ID so new categories appear at the end
    categories = list(Category.objects.exclude(name='All').order_by('id'))
    print(f"DEBUG: Found {len(categories)} categories")
    for cat in categories:
        print(f"DEBUG: Category - {cat.name}")
    
    # Convert to list of dictionaries for template
    featured_items = []
    for item in food_items:
        # Get the best available image (uploaded image takes priority over URL)
        image_url = None
        if item.image:
            image_url = item.image.url
        elif item.image_url:
            image_url = item.image_url
            
        featured_items.append({
            'id': item.id,
            'name': item.name,
            'description': f"Delicious {item.name.lower()}",  # Generate description since field doesn't exist
            'price': float(item.price),
            'image': image_url,
            'category': {
                'id': item.category.id if item.category else None,
                'name': item.category.name if item.category else 'Other'
            }
        })
    
    # Get dynamic plate fee from system settings
    plate_fee = int(float(SystemSettings.get_setting('plate_fee', 50)))
    
    context = {
        'featured_items': featured_items,
        'categories': categories,
        'restaurant_name': 'Admos Place',
        'restaurant_tagline': 'Delicious Food, Delivered Fast',
        'plate_fee': plate_fee,
    }
    
    print(f"DEBUG: Context has {len(context['categories'])} categories")
    print("=== END HOMEPAGE VIEW DEBUG ===")
    
    return render(request, 'customer_site/homepage.html', context)


def search(request):
    """Search page for food items."""
    query = request.GET.get('q', '').strip()
    results = []
    
    if query:
        # Search in food items and categories using Q objects
        from django.db.models import Q
        
        all_items = FoodItem.objects.filter(
            availability=True
        ).filter(
            Q(name__icontains=query) | Q(category__name__icontains=query)
        ).select_related('category').distinct().order_by('name')
        
        # Convert to list of dictionaries
        for item in all_items:
            # Get the best available image (uploaded image takes priority over URL)
            image_url = None
            if item.image:
                image_url = item.image.url
            elif item.image_url:
                image_url = item.image_url
                
            results.append({
                'id': item.id,
                'name': item.name,
                'description': f"Delicious {item.name.lower()}",
                'price': float(item.price),
                'image': image_url,
                'category': {
                    'name': item.category.name if item.category else 'Other'
                }
            })
    
    # Get dynamic plate fee from system settings
    plate_fee = int(float(SystemSettings.get_setting('plate_fee', 50)))
    
    context = {
        'query': query,
        'results': results,
        'restaurant_name': 'Admos Place',
        'plate_fee': plate_fee,
    }
    return render(request, 'customer_site/search.html', context)


def cart(request):
    """Shopping cart page."""
    print("=== CART VIEW CALLED ===")
    
    # Initialize bags if not exists
    if 'bags' not in request.session:
        default_bag = {
            'id': 'bag_1',
            'name': 'Bag 1',
            'items': [],
            'created_at': str(datetime.now())
        }
        request.session['bags'] = [default_bag]
        request.session['current_bag'] = 'bag_1'
        request.session.modified = True
    
    # Get current bag
    current_bag_id = request.session.get('current_bag', 'bag_1')
    bags = request.session.get('bags', [])
    current_bag = next((b for b in bags if b['id'] == current_bag_id), bags[0] if bags else None)
    
    # Debug: Check for old cart data
    old_cart = request.session.get('cart', [])
    if old_cart:
        print(f"WARNING: Old cart data found: {old_cart}")
        # Clear old cart data
        if 'cart' in request.session:
            del request.session['cart']
            request.session.modified = True
    
    # TEMPORARY: Clear all session data to fix duplicates
    if request.GET.get('clear') == 'true':
        print("CLEARING ALL SESSION DATA")
        request.session.flush()
        return redirect('customer_site:cart')
    
    # Get items from current bag (for backward compatibility)
    cart_items = current_bag.get('items', []) if current_bag else []
    
    # Update existing plate items with current system setting
    plate_fee = float(SystemSettings.get_setting('plate_fee', 50))
    for bag in bags:
        for item in bag.get('items', []):
            if item.get('is_plates'):
                item['price'] = plate_fee
                print(f"Updated plate price to {plate_fee} for item: {item.get('name')}")
    
    # Save updated bags to session
    request.session['bags'] = bags
    request.session.modified = True
    
    print("Cart view - loaded cart from current bag:", cart_items)
    print("Cart view - all bags:", bags)
    for i, bag in enumerate(bags):
        print(f"Bag {i+1} ({bag.get('id', 'unknown')}): {len(bag.get('items', []))} items")
        for item in bag.get('items', []):
            print(f"  - {item.get('name', 'unknown')} (ID: {item.get('id', 'unknown')})")
    
    # Calculate total from ALL bags and individual bag totals
    cart_total = 0
    all_items = []
    
    for bag in bags:
        bag_items = bag.get('items', [])
        bag_total = 0
        
        for item in bag_items:
            item_total = item.get('price', 0) * item.get('quantity', 0)
            item['total_price'] = item_total
            bag_total += item_total
            cart_total += item_total
            all_items.append(item)
        
        # Add bag total to bag data
        bag['total'] = bag_total
    
    # Keep cart_items empty since we're using bags for display
    cart_items = []
    
    # Check if any bag has items
    has_items = any(bag.get('items') for bag in bags)
    
    # Get dynamic plate fee from system settings
    plate_fee = int(float(SystemSettings.get_setting('plate_fee', 50)))
    
    context = {
        'cart_items': cart_items,
        'cart_total': cart_total,
        'delivery_fee': 500,  # Default delivery fee (will be calculated dynamically on checkout)
        'service_charge': 100,  # Default service charge
        'restaurant_name': 'Admos Place',
        'bags': bags,
        'current_bag': current_bag,
        'has_items': has_items,
        'user': request.user,  # Add user to context
        'plate_fee': plate_fee,
    }
    return render(request, 'customer_site/cart.html', context)


def validate_cart_plates(cart_items):
    """Ensure that food items in cart have plates."""
    # Check if there are food items
    food_items = [item for item in cart_items if item.get('category', '').lower() == 'food']
    
    if food_items:
        # Check if there's a separate plates item
        has_plates_item = any(item.get('is_plates') for item in cart_items)
        
        if not has_plates_item:
            # Add a separate plates item
            # Get dynamic plate fee from system settings
            plate_fee = float(SystemSettings.get_setting('plate_fee', 50))
            plates_item = {
                'id': 'plates',
                'name': 'Plates',
                'price': plate_fee,  # Dynamic plate fee
                'quantity': 1,
                'image': '',
                'category': 'Service',
                'is_plates': True
            }
            cart_items.append(plates_item)
    else:
        # No food items, remove any plates items
        cart_items = [item for item in cart_items if not item.get('is_plates')]
    
    return cart_items


def checkout(request):
    """Checkout page for logged-in users."""
    # Check if user is authenticated via session OR JWT token
    is_authenticated = request.user.is_authenticated
    authenticated_user = None
    
    # If not authenticated via session, check for JWT token in GET parameter or Authorization header
    if not is_authenticated:
        token = None
        
        # Check GET parameter first (from form submission)
        jwt_token = request.GET.get('jwt_token')
        if jwt_token:
            token = jwt_token
        
        # Check Authorization header (from AJAX requests)
        if not token:
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if token:
            try:
                from rest_framework_simplejwt.tokens import AccessToken
                from accounts.models import User
                
                # Decode the JWT token
                access_token = AccessToken(token)
                user_id = access_token['user_id']
                user = User.objects.get(id=user_id)
                
                # Set the user in the request
                request.user = user
                authenticated_user = user
                is_authenticated = True
            except Exception as e:
                pass  # JWT authentication failed
    
    if not is_authenticated:
        messages.info(request, 'Please log in to proceed with checkout.')
        return redirect('customer_site:cart')
    
    # Use the authenticated user (either from session or JWT)
    user = authenticated_user or request.user
    
    # Get bags from session
    bags = request.session.get('bags', [])
    
    # Check if any bag has items
    has_items = any(bag.get('items') for bag in bags)
    
    if not has_items:
        messages.warning(request, 'Your cart is empty!')
        return redirect('customer_site:homepage')
    
    # Calculate totals from all bags
    subtotal = 0
    for bag in bags:
        bag_total = 0
        for item in bag.get('items', []):
            bag_total += item.get('price', 0) * item.get('quantity', 0)
        bag['total'] = bag_total
        subtotal += bag_total
    
    # Get dynamic system settings
    service_charge = float(SystemSettings.get_setting('service_charge', 100))
    vat_percentage = float(SystemSettings.get_setting('vat_percentage', 7.5))
    plate_fee = float(SystemSettings.get_setting('plate_fee', 50))
    vat_amount = subtotal * (vat_percentage / 100)  # VAT on subtotal only
    delivery_fee = 0      # Start with 0 delivery fee (will be calculated when user enters address)
    total = subtotal + service_charge + vat_amount + delivery_fee
    
    context = {
        'bags': bags,
        'subtotal': subtotal,
        'service_charge': service_charge,
        'vat_percentage': vat_percentage,
        'vat_amount': vat_amount,
        'delivery_fee': delivery_fee,
        'total': total,
        'user': user,
        'restaurant_name': 'Admos Place',
        'plate_fee': plate_fee,
    }
    
    # Add cache control headers to prevent caching
    response = render(request, 'customer_site/checkout.html', context)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


def order_history(request):
    """User's order history."""
    # Try to authenticate user via JWT token first, then fall back to session
    user = None
    
    # Try JWT authentication first
    try:
        from rest_framework_simplejwt.authentication import JWTAuthentication
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
        from rest_framework_simplejwt.tokens import AccessToken
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Check for JWT token in URL parameter first (like checkout view)
        jwt_token = request.GET.get('jwt_token')
        if jwt_token:
            try:
                token = AccessToken(jwt_token)
                user_id = token['user_id']
                user = User.objects.get(id=user_id)
                print(f"JWT Authentication from URL successful for user: {user.id}")
            except Exception as e:
                print(f"JWT token from URL validation failed: {e}")
                user = None
        
        # If no user found from URL token, check Authorization header
        if not user:
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if auth_header.startswith('Bearer '):
                token_string = auth_header.split(' ')[1]
                try:
                    token = AccessToken(token_string)
                    user_id = token['user_id']
                    user = User.objects.get(id=user_id)
                    print(f"JWT Authentication from header successful for user: {user.id}")
                except Exception as e:
                    print(f"JWT token from header validation failed: {e}")
                    user = None
        
        # If still no user, try the standard JWT authentication
        if not user:
            jwt_auth = JWTAuthentication()
            auth_result = jwt_auth.authenticate(request)
            if auth_result:
                user, token = auth_result
                print(f"JWT Authentication standard successful for user: {user.id}")
            else:
                user = None
    except Exception as e:
        print(f"JWT Authentication failed: {e}")
        user = None
    
    # Fallback to session authentication
    if not user and request.user.is_authenticated:
        user = request.user
        print(f"Session authentication successful for user: {user.id}")
    
    # If still no user, try to get from session data
    if not user:
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user_id = request.session.get('user_id')
            if user_id:
                user = User.objects.get(id=user_id)
                print(f"Session user_id authentication successful for user: {user.id}")
        except Exception as e:
            print(f"Session user_id authentication failed: {e}")
            user = None
    
    orders_list = []
    if user:
        try:
            # Query directly from database - only orders with successful payments
            orders_qs = Order.objects.filter(
                user=user,
                payment__status='success'
            ).order_by('-created_at').select_related('user').prefetch_related('bags__items')
            print(f"Found {orders_qs.count()} orders for user {user.id}")
            for order in orders_qs:
                # Get the actual payment amount instead of calculated order total
                actual_payment_amount = None
                try:
                    # Try different ways to get the payment
                    payment = order.payment_set.filter(status='success').first()
                    if not payment:
                        # Try getting any payment for this order
                        payment = order.payment_set.first()
                    
                    if payment:
                        actual_payment_amount = float(payment.amount)
                        print(f"Order {order.id}: Found payment {payment.id} with amount ₦{actual_payment_amount}")
                        print(f"Order {order.id}: Payment status: {payment.status}")
                        print(f"Order {order.id}: Payment reference: {payment.reference}")
                        print(f"Order {order.id}: Order total: ₦{order.total}")
                    else:
                        print(f"Order {order.id}: No payment found")
                        actual_payment_amount = float(order.total)  # Fallback to order total
                except Exception as e:
                    print(f"Error getting payment amount for order {order.id}: {e}")
                    actual_payment_amount = float(order.total)  # Fallback to order total
                
                order_dict = {
                    'id': order.id,
                    'status': order.status,
                    'created_at': order.created_at,
                    'total': actual_payment_amount if actual_payment_amount is not None else float(order.total),  # Use actual payment amount
                    'delivery_address': order.delivery_address,
                    'bags': []
                }
                for bag in order.bags.all():
                    bag_dict = {
                        'id': bag.id,
                        'name': getattr(bag, 'name', f'Bag {bag.id}'),
                        'items': []
                    }
                    for item in bag.items.all():
                        bag_dict['items'].append({
                            'name': item.item_name or (item.food_item.name if item.food_item else ''),
                            'price': float(item.item_price) if item.item_price is not None else (float(item.food_item.price) if item.food_item else 0),
                            'portions': item.portions,
                            'plates': item.plates,
                            'category': item.item_category or (item.food_item.category.name if item.food_item and item.food_item.category else ''),
                        })
                    order_dict['bags'].append(bag_dict)
                orders_list.append(order_dict)
        except Exception as e:
            print(f"Error building order history from DB: {e}")
            orders_list = []
    else:
        # Not authenticated in session; attempt API (may still be unauthenticated)
        try:
            api_url = f"{request.scheme}://{request.get_host()}/api/store/secure/user-orders/"
            headers = {
                'Authorization': f'Bearer {request.session.get("access_token", "")}',
                'Content-Type': 'application/json'
            }
            response = requests.get(api_url, headers=headers)
            if response.status_code == 200:
                data = response.json() or {}
                orders_list = data.get('orders', [])
            else:
                orders_list = []
        except Exception as e:
            print(f"Error fetching order history via API: {e}")
            orders_list = []

    print(f"=== ORDER HISTORY DEBUG ===")
    print(f"User found: {user}")
    print(f"Orders found: {len(orders_list)}")
    print(f"Request user: {request.user}")
    print(f"Request user authenticated: {request.user.is_authenticated}")
    print(f"=== END ORDER HISTORY DEBUG ===")
    
    # Get dynamic plate fee from system settings
    plate_fee = int(float(SystemSettings.get_setting('plate_fee', 50)))
    
    from django.conf import settings
    
    context = {
        'orders': orders_list,
        'user': user or request.user,
        'restaurant_name': 'Admos Place',
        'plate_fee': plate_fee,
        'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY,
    }
    return render(request, 'customer_site/order_history.html', context)


@csrf_exempt
@require_http_methods(["GET"])
def get_user_orders_api(request):
    """API endpoint to get user orders for the order history page."""
    try:
        from rest_framework_simplejwt.authentication import JWTAuthentication
        from rest_framework_simplejwt.tokens import AccessToken
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Try to authenticate user
        user = None
        
        # Check for JWT token in Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            token_string = auth_header.split(' ')[1]
            try:
                token = AccessToken(token_string)
                user_id = token['user_id']
                user = User.objects.get(id=user_id)
                print(f"JWT Authentication successful for user: {user.id}")
            except Exception as e:
                print(f"JWT token validation failed: {e}")
                return JsonResponse({'error': 'Invalid token'}, status=401)
        else:
            return JsonResponse({'error': 'No authorization header'}, status=401)
        
        if not user:
            return JsonResponse({'error': 'User not found'}, status=404)
        
        # Get orders for the user - only orders with successful payments
        orders_qs = Order.objects.filter(
            user=user,
            payment__status='success'
        ).order_by('-created_at').select_related('user').prefetch_related('bags__items')
        orders_list = []
        
        for order in orders_qs:
            order_dict = {
                'id': order.id,
                'status': order.status,
                'created_at': order.created_at.isoformat(),
                'total': float(order.total),
                'delivery_address': order.delivery_address,
                'bags': []
            }
            for bag in order.bags.all():
                bag_dict = {
                    'id': bag.id,
                    'name': getattr(bag, 'name', f'Bag {bag.id}'),
                    'items': []
                }
                for item in bag.items.all():
                    bag_dict['items'].append({
                        'name': item.item_name or (item.food_item.name if item.food_item else ''),
                        'price': float(item.item_price) if item.item_price is not None else (float(item.food_item.price) if item.food_item else 0),
                        'portions': item.portions,
                        'plates': item.plates,
                        'category': item.item_category or (item.food_item.category.name if item.food_item and item.food_item.category else ''),
                    })
                order_dict['bags'].append(bag_dict)
            orders_list.append(order_dict)
        
        return JsonResponse({
            'success': True,
            'orders': orders_list,
            'count': len(orders_list)
        })
        
    except Exception as e:
        print(f"Error in get_user_orders_api: {e}")
        return JsonResponse({'error': str(e)}, status=500)


def order_tracking(request, order_id):
    """Order tracking page."""
    # Check if user is authenticated via session OR JWT token
    is_authenticated = request.user.is_authenticated
    authenticated_user = None
    
    # If not authenticated via session, check for JWT token in GET parameter or Authorization header
    if not is_authenticated:
        token = None
        
        # Check GET parameter first (from form submission)
        jwt_token = request.GET.get('jwt_token')
        if jwt_token:
            token = jwt_token
        
        # Check Authorization header (from AJAX requests)
        if not token:
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if token:
            try:
                from rest_framework_simplejwt.tokens import AccessToken
                from accounts.models import User
                
                # Decode the JWT token
                access_token = AccessToken(token)
                user_id = access_token['user_id']
                user = User.objects.get(id=user_id)
                
                # Set the user in the request
                request.user = user
                authenticated_user = user
                is_authenticated = True
            except Exception as e:
                pass  # JWT authentication failed
    
    # Use the authenticated user (either from session or JWT)
    user = authenticated_user or request.user
    
    try:
        # Fetch order directly from database
        from store.models import Order
        order_obj = Order.objects.select_related('user', 'payment').prefetch_related('bags__items__food_item').get(id=order_id)
        
        # If no user is authenticated, show a message and redirect
        if not user:
            messages.error(request, 'Please log in to view order details.')
            return redirect('customer_site:order_history')
        
        # Check if the order belongs to the authenticated user
        if order_obj.user != user:
            return redirect('customer_site:order_history')
        
        # Convert to dictionary format for template
        order = {
            'id': order_obj.id,
            'status': order_obj.status,
            'created_at': order_obj.created_at,
            'total': float(order_obj.total),
            'subtotal': float(order_obj.subtotal),
            'delivery_fee': float(order_obj.delivery_fee),
            'service_charge': float(order_obj.service_charge),
            'delivery_address': order_obj.delivery_address,
            'contact_phone': order_obj.contact_phone,
            'bags': [],
            'payment': None
        }
        
        # Add payment info if exists
        if hasattr(order_obj, 'payment') and order_obj.payment:
            order['payment'] = {
                'status': order_obj.payment.status,
                'payment_type': order_obj.payment.payment_type,
                'amount': float(order_obj.payment.amount),
                'reference': order_obj.payment.reference
            }
        
        # Add bags and items
        for bag in order_obj.bags.all():
            bag_dict = {
                'id': bag.id,
                'name': getattr(bag, 'name', f'Bag {bag.id}'),
                'items': []
            }
            for item in bag.items.all():
                bag_dict['items'].append({
                    'id': item.id,
                    'name': item.item_name or (item.food_item.name if item.food_item else 'Unknown Item'),
                    'price': float(item.item_price) if item.item_price is not None else (float(item.food_item.price) if item.food_item else 0),
                    'total_price': float(item.total_price) if item.total_price is not None else 0,
                    'portions': item.portions,
                    'plates': item.plates,
                    'category': item.item_category or (item.food_item.category.name if item.food_item and item.food_item.category else ''),
                    'image': item.food_item.image if item.food_item and item.food_item.image else ''
                })
            order['bags'].append(bag_dict)
            
    except Order.DoesNotExist:
        messages.error(request, 'Order not found!')
        return redirect('customer_site:order_history')
    except Exception as e:
        print(f"Error fetching order: {e}")
        messages.error(request, 'Error loading order details!')
        return redirect('customer_site:order_history')
    
    # Get dynamic plate fee from system settings
    plate_fee = int(float(SystemSettings.get_setting('plate_fee', 50)))
    
    from django.conf import settings
    
    context = {
        'order': order,
        'user': user or request.user,
        'restaurant_name': 'Admos Place',
        'plate_fee': plate_fee,
        'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY,
    }
    return render(request, 'customer_site/order_tracking.html', context)


# API Views for AJAX calls
@csrf_exempt
@require_http_methods(["POST"])
def add_to_cart(request):
    """Add item to cart via AJAX."""
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        quantity = int(data.get('quantity', 1))
        plates = int(data.get('plates', 0))
        
        # Get item directly from database
        try:
            item = FoodItem.objects.get(id=item_id, availability=True)
        except FoodItem.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Item not found or not available!'
            })
        
        # Check if requested quantity exceeds available portions
        if not item.can_order_portions(quantity):
            portion_text = item.quantity_display.split(" ", 1)[1] if item.quantity_display else "portions"
            if item.portions == 1:
                message = f'Sorry, only 1 {portion_text} of {item.name} available. Look for something else to eat!'
            else:
                message = f'Sorry, only {item.portions} {portion_text} of {item.name} available. Look for something else to eat!'
            return JsonResponse({
                'success': False,
                'message': message
            })
        
        # Get current bags
        bags = request.session.get('bags', [])
        
        # Initialize bags if not exists
        if not bags:
            default_bag = {
                'id': 'bag_1',
                'name': 'Bag 1',
                'items': [],
                'created_at': str(datetime.now())
            }
            bags = [default_bag]
            request.session['bags'] = bags
            request.session['current_bag'] = 'bag_1'
        
        # Get current bag
        current_bag_id = request.session.get('current_bag', 'bag_1')
        current_bag = next((b for b in bags if b['id'] == current_bag_id), bags[0])
        
        # Get current cart items from current bag
        cart = current_bag.get('items', [])
        
        # Check if this is a food category item and if plates are required
        is_food_category = item.category and item.category.name.lower() == 'food'
        is_plate_item = item.name and item.name.lower() == 'plate'
        
        # Check if current bag already has food items
        has_food_items = any(
            cart_item.get('category', '').lower() == 'food' 
            for cart_item in cart
        )
        
        # Handle plate requirements for food items
        if is_food_category and not is_plate_item:
            if not has_food_items and plates == 0:
                return JsonResponse({
                    'success': False,
                    'message': 'At least one plate is required for food items!'
                })
            # For subsequent food items, don't add plates to the item
            elif has_food_items and plates > 0:
                plates = 0
        
        # Check if item already in cart
        item_in_cart = False
        for cart_item in cart:
            if cart_item['id'] == item_id:
                new_total_quantity = cart_item['quantity'] + quantity
                # Check if the new total quantity exceeds available portions
                if not item.can_order_portions(new_total_quantity):
                    portion_text = item.quantity_display.split(" ", 1)[1] if item.quantity_display else "portions"
                    if item.portions == 1:
                        message = f'Sorry, only 1 {portion_text} of {item.name} available and you\'ve already added it to your cart. Look for something else to eat!'
                    else:
                        message = f'Sorry, only {item.portions} {portion_text} of {item.name} available and you\'ve already added them to your cart. Look for something else to eat!'
                    return JsonResponse({
                        'success': False,
                        'message': message
                    })
                
                # Additional check: if cart already has max available quantity, don't allow adding more
                if cart_item['quantity'] >= item.portions:
                    return JsonResponse({
                        'success': False,
                        'message': f'You already have the maximum available quantity ({item.portions} {item.quantity_display.split(" ", 1)[1] if item.quantity_display else "portions"}) of {item.name} in your cart. You can only reduce the quantity.'
                    })
                
                cart_item['quantity'] = new_total_quantity
                # Update plates if this is the first food item
                if is_food_category and not is_plate_item and not has_food_items:
                    cart_item['plates'] = plates
                item_in_cart = True
                break
        
        # Add new item if not in cart
        if not item_in_cart:
            cart_item_data = {
                'id': item_id,
                'name': item.name,
                'price': float(item.price),
                'quantity': quantity,
                'image': item.image.url if item.image else item.image_url or '',
                'category': item.category.name if item.category else '',
            }
            
            cart.append(cart_item_data)
            
            # If this is the first food item with plates, add a separate "Plates" item
            if is_food_category and not is_plate_item and plates > 0:
                # Get dynamic plate fee from system settings
                plate_fee = float(SystemSettings.get_setting('plate_fee', 50))
                plates_item = {
                    'id': f'plates_{current_bag_id}',  # Make plate ID unique per bag
                    'name': 'Plates',
                    'price': plate_fee,  # Dynamic plate fee
                    'quantity': plates,
                    'image': '',
                    'category': 'Service',
                    'is_plates': True
                }
                cart.append(plates_item)
        
        # Update current bag with new cart items
        current_bag['items'] = cart
        
        # Save bags to session
        request.session['bags'] = bags
        request.session.modified = True
        
        # Calculate total cart count from all bags
        total_cart_count = sum(len(bag.get('items', [])) for bag in bags)
        
        return JsonResponse({
            'success': True,
            'message': f'{item.name} added to cart!',
            'cart_count': total_cart_count
        })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })


@csrf_exempt
@require_http_methods(["POST"])
def update_cart_item(request):
    """Update cart item quantity or plates via AJAX."""
    print("=== UPDATE CART ITEM CALLED ===")
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        quantity = data.get('quantity')
        plates = data.get('plates')
        bag_id = data.get('bag_id')
        
        # Handle plates parameter - if plates is provided, use it as quantity
        if plates is not None:
            quantity = int(plates)
            print(f"Using plates as quantity: {quantity}")
        elif quantity is not None:
            quantity = int(quantity)
        else:
            return JsonResponse({
                'success': False,
                'message': 'No quantity or plates provided'
            })
        
        print(f"Update request - item_id: {item_id}, quantity: {quantity}, plates: {plates}, bag_id: {bag_id}")
        
        # Get current bags
        bags = request.session.get('bags', [])
        
        # Find the item in the specified bag or any bag
        item_found = False
        print(f"Looking for item_id: {item_id} (type: {type(item_id)})")
        
        # Search for the item, prioritizing the current bag first
        current_bag_id = request.session.get('current_bag')
        bags_to_search = bags
        
        # If we have a current bag, prioritize it by putting it first in the search order
        if current_bag_id:
            current_bag = next((b for b in bags if b.get('id') == current_bag_id), None)
            if current_bag:
                # Put current bag first, then other bags
                other_bags = [b for b in bags if b.get('id') != current_bag_id]
                bags_to_search = [current_bag] + other_bags
                print(f"Searching for item_id: {item_id}, prioritizing current bag: {current_bag_id}")
            else:
                print(f"Searching across all bags for item_id: {item_id}")
        else:
            print(f"Searching across all bags for item_id: {item_id}")
        
        for bag in bags_to_search:
            cart = bag.get('items', [])
            print(f"Checking bag {bag.get('id')} with {len(cart)} items")
            for cart_item in cart:
                print(f"  Comparing cart_item['id']: {cart_item['id']} (type: {type(cart_item['id'])}) with item_id: {item_id}")
                # Compare both as strings to handle type mismatches
                if str(cart_item['id']) == str(item_id):
                    print(f"  MATCH FOUND! Updating item: {cart_item.get('name', 'Unknown')}")
                    # Update quantity (now handles both quantity and plates)
                    old_quantity = cart_item['quantity']
                    print(f"  Updating quantity from {old_quantity} to {quantity}")
                    
                    if quantity <= 0:
                        cart.remove(cart_item)
                        print(f"  Removed item (quantity <= 0)")
                    else:
                        # Check if this is a plate item (has string ID starting with 'plates_')
                        if cart_item.get('is_plates') or str(item_id).startswith('plates_'):
                            # For plate items, just update the quantity without validation
                            cart_item['quantity'] = quantity
                            print(f"  Updated plate quantity to {cart_item['quantity']}")
                            print(f"  Plate item after update: {cart_item}")
                        else:
                            # Check if the new quantity exceeds available portions (for regular food items)
                            try:
                                item = FoodItem.objects.get(id=item_id, availability=True)
                                if not item.can_order_portions(quantity):
                                    portion_text = item.quantity_display.split(" ", 1)[1] if item.quantity_display else "portions"
                                    if item.portions == 1:
                                        message = f'Sorry, only 1 {portion_text} of {item.name} available. Look for something else to eat!'
                                    else:
                                        message = f'Sorry, only {item.portions} {portion_text} of {item.name} available. Look for something else to eat!'
                                    return JsonResponse({
                                        'success': False,
                                        'message': message
                                    })
                                
                                # Additional check: prevent increasing quantity if already at maximum
                                if quantity > old_quantity and old_quantity >= item.portions:
                                    return JsonResponse({
                                        'success': False,
                                        'message': f'You already have the maximum available quantity ({item.portions} {item.quantity_display.split(" ", 1)[1] if item.quantity_display else "portions"}) of {item.name} in your cart. You can only reduce the quantity.'
                                    })
                                    
                            except FoodItem.DoesNotExist:
                                return JsonResponse({
                                    'success': False,
                                    'message': 'Item not found or not available!'
                                })
                            
                            cart_item['quantity'] = quantity
                            print(f"  Updated quantity to {cart_item['quantity']}")
                            print(f"  Item after update: {cart_item}")
                    
                    item_found = True
                    break
            if item_found:
                break
        
        # Save bags to session
        request.session['bags'] = bags
        request.session.modified = True
        request.session.save()  # Force persist to database
        
        # Calculate total cart count from all bags
        total_cart_count = sum(len(bag.get('items', [])) for bag in bags)
        
        return JsonResponse({
            'success': True,
            'cart_count': total_cart_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })


@csrf_exempt
@require_http_methods(["POST"])
def remove_from_cart(request):
    """Remove item from cart via AJAX."""
    print("=== REMOVE FROM CART CALLED ===")
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        print(f"Request data: {data}")
        print(f"Item ID to remove: {item_id}")
        
        # Fix type mismatch - convert to int if numeric, keep as string if not
        try:
            item_id = int(item_id)
        except (TypeError, ValueError):
            pass  # leave it as string if not numeric (like 'plates')
        
        print(f"Item ID after type conversion: {item_id} (type: {type(item_id)})")
        
        # Get current bags
        bags = request.session.get('bags', [])
        print(f"Initial bags: {bags}")
        
        # Find the item being removed in any bag
        item_to_remove = None
        bag_with_item = None
        for bag in bags:
            cart = bag.get('items', [])
            for item in cart:
                print(f"Comparing item['id'] ({item['id']}, type: {type(item['id'])}) with item_id ({item_id}, type: {type(item_id)})")
                if item['id'] == item_id:
                    item_to_remove = item
                    bag_with_item = bag
                    print(f"Found item to remove: {item}")
                    break
            if item_to_remove:
                break
        
        # Check if trying to remove plates when there are food items
        if item_to_remove and item_to_remove.get('is_plates'):
            # Get list of food items that need plates from the same bag
            food_items = [
                item.get('name', 'Unknown item') 
                for item in bag_with_item.get('items', []) 
                if item.get('category', '').lower() == 'food'
            ]
            
            if food_items:
                if len(food_items) == 1:
                    message = f'You have {food_items[0]} that requires a plate to serve. Remove the food item first.'
                else:
                    items_text = ', '.join(food_items[:-1]) + f' and {food_items[-1]}'
                    message = f'You have {items_text} that require plates to serve. Remove the food items first.'
                
                return JsonResponse({
                    'success': False,
                    'message': message
                })
        
        # Remove the item from the bag
        if bag_with_item:
            bag_with_item['items'] = [item for item in bag_with_item['items'] if item['id'] != item_id]
        
        # If we removed a food item, check if we need to remove plates too
        if item_to_remove and item_to_remove.get('category', '').lower() == 'food':
            # Check if there are any remaining food items in the same bag
            has_remaining_food = any(
                item.get('category', '').lower() == 'food' 
                for item in bag_with_item.get('items', [])
            )
            
            # If no food items left, remove plates too
            if not has_remaining_food:
                bag_with_item['items'] = [item for item in bag_with_item['items'] if not item.get('is_plates')]
        
        # If any bag becomes empty, delete it and renumber remaining bags
        if bag_with_item and not bag_with_item.get('items'):
            # Remove the empty bag
            bags = [bag for bag in bags if bag.get('id') != bag_with_item.get('id')]
            
            # Renumber all remaining bags
            for i, bag in enumerate(bags):
                new_bag_number = i + 1
                old_id = bag.get('id')
                new_id = f'bag_{new_bag_number}'
                new_name = f'Bag {new_bag_number}'
                
                # Update bag ID and name
                bag['id'] = new_id
                bag['name'] = new_name
                
                # Update current_bag if it was pointing to the old ID
                if request.session.get('current_bag') == old_id:
                    request.session['current_bag'] = new_id
            
            # If no bags left, create a new Bag 1
            if not bags:
                new_bag_1 = {
                    'id': 'bag_1',
                    'name': 'Bag 1',
                    'items': [],
                    'created_at': str(datetime.now())
                }
                bags = [new_bag_1]
                request.session['current_bag'] = 'bag_1'
        
        # Save bags to session
        request.session['bags'] = bags
        request.session.modified = True
        request.session.save()  # Force persist to database
        
        print("Updated bags:", bags)
        print("=== REMOVE FROM CART COMPLETED ===")
        
        # Calculate total cart count from all bags
        total_cart_count = sum(len(bag.get('items', [])) for bag in bags)
        
        return JsonResponse({
            'success': True,
            'cart_count': total_cart_count
        })
        
    except Exception as e:
        print(f"ERROR in remove_from_cart: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })


@require_http_methods(["GET"])
def get_cart(request):
    """Get current cart contents via AJAX."""
    try:
        # Get bags from session
        bags = request.session.get('bags', [])
        
        # If no bags exist, create a default one
        if not bags:
            default_bag = {
                'id': 'bag_1',
                'name': 'Bag 1',
                'items': [],
                'created_at': str(datetime.now())
            }
            request.session['bags'] = [default_bag]
            request.session.modified = True
            bags = [default_bag]
        
        # Update existing plate items with current system setting
        plate_fee = float(SystemSettings.get_setting('plate_fee', 50))
        for bag in bags:
            for item in bag.get('items', []):
                if item.get('is_plates'):
                    item['price'] = plate_fee
        
        # Save updated bags to session
        request.session['bags'] = bags
        request.session.modified = True
        
        # Get all items from all bags and calculate bag totals
        all_items = []
        print(f"=== GET_CART DEBUG ===")
        print(f"Total bags: {len(bags)}")
        for bag in bags:
            bag_items = bag.get('items', [])
            bag_total = 0
            print(f"Bag {bag.get('id')} has {len(bag_items)} items")
            
            for item in bag_items:
                price = float(item.get('price', 0))
                quantity = int(item.get('quantity', 0))
                total_price = price * quantity
                item['total_price'] = total_price
                bag_total += total_price
                print(f"Item: {item.get('name')} (ID: {item.get('id')}), Price: {price}, Quantity: {quantity}, Total: {total_price}")
                all_items.append(item)
            
            # Add bag total to bag data
            bag['total'] = bag_total
        
        # Get current bag information
        current_bag_id = request.session.get('current_bag', 'bag_1')
        current_bag = next((b for b in bags if b['id'] == current_bag_id), bags[0] if bags else None)
        
        return JsonResponse({
            'success': True,
            'cart_items': all_items,
            'cart_count': len(all_items),
            'bags': bags,
            'current_bag': current_bag,
            'current_bag_id': current_bag_id
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })


@csrf_exempt
@require_http_methods(["POST"])
def create_order_from_cart(request):
    """Prepare order data for payment - DO NOT create order until payment is successful."""
    try:
        # Get user from JWT token
        from rest_framework_simplejwt.authentication import JWTAuthentication
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
        
        # Authenticate user using JWT token
        jwt_auth = JWTAuthentication()
        try:
            auth_result = jwt_auth.authenticate(request)
            if auth_result is None:
                return JsonResponse({
                    'success': False,
                    'error': 'Authentication required'
                }, status=401)
            user, token = auth_result
        except (InvalidToken, TokenError):
            return JsonResponse({
                'success': False,
                'error': 'Invalid or expired token'
            }, status=401)
        
        data = json.loads(request.body)
        cart_items = data.get('cart_items', [])
        delivery_address = data.get('delivery_address', '')
        contact_phone = data.get('contact_phone', '')
        from decimal import Decimal
        delivery_fee = Decimal(str(data.get('delivery_fee', 500)))
        # Use dynamic system settings with fallbacks
        service_charge = Decimal(str(data.get('service_charge', SystemSettings.get_setting('service_charge', 100))))
        vat_percentage = Decimal(str(data.get('vat_percentage', SystemSettings.get_setting('vat_percentage', 7.5))))
        vat_amount = Decimal(str(data.get('vat_amount', 0)))
        
        # Validate required fields
        if not delivery_address or len(delivery_address.strip()) < 10:
            return JsonResponse({
                'success': False,
                'error': 'Valid delivery address is required (minimum 10 characters)'
            }, status=400)
        
        if not contact_phone or len(contact_phone.strip()) < 10:
            return JsonResponse({
                'success': False,
                'error': 'Valid contact phone is required'
            }, status=400)
        
        if not cart_items:
            return JsonResponse({
                'success': False,
                'error': 'No items in cart'
            }, status=400)
        
        # Get bags from session to maintain the cart structure
        session_bags = request.session.get('bags', [])
        if not session_bags:
            return JsonResponse({
                'success': False,
                'error': 'No cart data found in session'
            }, status=400)
        
        # Calculate order total without creating the order
        from store.models import FoodItem
        from django.db import transaction
        
        total_amount = Decimal('0')
        valid_items = []
        
        for session_bag in session_bags:
            bag_items = session_bag.get('items', [])
            if not bag_items:
                continue  # Skip empty bags
            
            for cart_item in bag_items:
                # Handle plate items separately
                if cart_item.get('is_plates'):
                    # Add plate costs to total
                    plate_total = cart_item.get('price', 0) * cart_item.get('quantity', 1)
                    total_amount += Decimal(str(plate_total))
                    continue
                
                # Get food item
                try:
                    food_item = FoodItem.objects.get(id=cart_item['id'])
                except FoodItem.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'error': f'Food item with ID {cart_item["id"]} not found'
                    }, status=400)
                
                # Calculate item total
                item_total = food_item.price * cart_item.get('quantity', 1)
                total_amount += item_total
                
                valid_items.append({
                    'food_item': food_item,
                    'quantity': cart_item.get('quantity', 1),
                    'session_bag': session_bag,
                    'bag_items': bag_items
                })
        
        # Add delivery fee, service charge, and VAT
        total_amount += delivery_fee + service_charge + vat_amount
        
        # Debug logging
        print(f'=== ORDER TOTAL CALCULATION ===')
        print(f'Items subtotal: {total_amount - delivery_fee - service_charge - vat_amount}')
        print(f'Delivery fee: {delivery_fee}')
        print(f'Service charge: {service_charge}')
        print(f'VAT amount: {vat_amount}')
        print(f'Total amount: {total_amount}')
        print(f'Cart items count: {len(session_bags)}')
        for bag in session_bags:
            print(f'  Bag {bag["id"]}: {len(bag["items"])} items')
            for item in bag["items"]:
                print(f'    - {item["name"]}: {item["quantity"]} × ₦{item["price"]} = ₦{item["quantity"] * item["price"]}')
        print(f'=== END ORDER TOTAL CALCULATION ===')
        
        # Store order data in session for payment success callback
        order_data = {
            'user_id': user.id,
            'delivery_address': delivery_address,
            'contact_phone': contact_phone,
            'delivery_fee': float(delivery_fee),
            'service_charge': float(service_charge),
            'vat_percentage': float(vat_percentage),
            'vat_amount': float(vat_amount),
            'session_bags': session_bags,
            'valid_items': [
                {
                    'food_item_id': item['food_item'].id,
                    'quantity': item['quantity'],
                    'session_bag': item['session_bag'],
                    'bag_items': item['bag_items']
                }
                for item in valid_items
            ]
        }
        
        # Store in session for payment success callback
        request.session['pending_order_data'] = order_data
        request.session.modified = True
        request.session.save()
        
        print(f"=== ORDER PREPARATION DEBUG ===")
        print(f"User: {user.email}")
        print(f"Total amount: {total_amount}")
        print(f"Number of items: {len(valid_items)}")
        print(f"Order data stored in session")
        print(f"=== END ORDER PREPARATION DEBUG ===")
        
        return JsonResponse({
            'success': True,
            'total_amount': float(total_amount),
            'message': 'Order data prepared for payment'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error preparing order: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def clear_cart(request):
    """Clear entire cart via AJAX."""
    print("=== CLEAR CART CALLED ===")
    try:
        # Clear all bags from session
        request.session['bags'] = []
        request.session['current_bag'] = 'bag_1'
        request.session.modified = True
        request.session.save()  # Force persist to database
        
        print("Cart cleared successfully")
        
        return JsonResponse({
            'success': True,
            'message': 'Cart cleared successfully',
            'cart_count': 0
        })
        
    except Exception as e:
        print(f"Error clearing cart: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })


def create_bag(request):
    """Create a new bag via AJAX."""
    try:
        # Initialize bags in session if not exists
        if 'bags' not in request.session:
            request.session['bags'] = []
        
        # Check if there are existing bags and if the last one is empty
        existing_bags = request.session['bags']
        if existing_bags:
            last_bag = existing_bags[-1]
            if not last_bag.get('items', []):
                return JsonResponse({
                    'success': False,
                    'message': f'Please add items to {last_bag["name"]} before creating a new bag.'
                })
        
        # Auto-generate bag name
        bag_number = len(request.session['bags']) + 1
        bag_name = f'Bag {bag_number}'
        
        # Create new bag
        new_bag = {
            'id': f'bag_{bag_number}',
            'name': bag_name,
            'items': [],
            'created_at': str(datetime.now())
        }
        
        request.session['bags'].append(new_bag)
        # Switch to the newly created bag
        request.session['current_bag'] = new_bag['id']
        request.session.modified = True
        
        return JsonResponse({
            'success': True,
            'bag': new_bag,
            'message': f'{bag_name} created successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })


def get_bags(request):
    """Get all bags via AJAX."""
    try:
        bags = request.session.get('bags', [])
        
        # If no bags exist, create a default one
        if not bags:
            default_bag = {
                'id': 'bag_1',
                'name': 'Bag 1',
                'items': [],
                'created_at': str(datetime.now())
            }
            request.session['bags'] = [default_bag]
            request.session.modified = True
            bags = [default_bag]
        
        return JsonResponse({
            'success': True,
            'bags': bags
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })


def switch_bag(request):
    """Switch to a different bag via AJAX."""
    try:
        data = json.loads(request.body)
        bag_id = data.get('bag_id')
        
        bags = request.session.get('bags', [])
        bag = next((b for b in bags if b['id'] == bag_id), None)
        
        if not bag:
            return JsonResponse({
                'success': False,
                'message': 'Bag not found'
            })
        
        # Set current bag in session
        request.session['current_bag'] = bag_id
        request.session.modified = True
        
        return JsonResponse({
            'success': True,
            'current_bag': bag,
            'bag_name': bag['name'],
            'message': f'Switched to {bag["name"]}'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })


def delete_bag(request):
    """Delete a bag via AJAX."""
    try:
        data = json.loads(request.body)
        bag_id = data.get('bag_id')
        
        print(f"=== DELETE BAG CALLED ===")
        print(f"Bag ID to delete: {bag_id}")
        
        bags = request.session.get('bags', [])
        current_bag_id = request.session.get('current_bag')
        
        print(f"Current bags: {[b['id'] for b in bags]}")
        print(f"Current bag ID: {current_bag_id}")
        
        # Find the bag to delete
        bag_to_delete = next((b for b in bags if b['id'] == bag_id), None)
        if not bag_to_delete:
            return JsonResponse({
                'success': False,
                'message': 'Bag not found'
            })
        
        print(f"Deleting bag: {bag_to_delete['name']} ({bag_to_delete['id']})")
        
        # If this is the last bag, clear the entire cart
        if len(bags) <= 1:
            request.session['bags'] = []
            request.session['current_bag'] = None
            request.session.modified = True
            
            return JsonResponse({
                'success': True,
                'message': 'Cart cleared successfully',
                'bags': [],
                'current_bag': None
            })
        
        # Remove the bag
        bags = [b for b in bags if b['id'] != bag_id]
        
        # Renumber all remaining bags
        for i, bag in enumerate(bags):
            new_bag_number = i + 1
            old_id = bag.get('id')
            new_id = f'bag_{new_bag_number}'
            new_name = f'Bag {new_bag_number}'
            
            # Update bag ID and name
            bag['id'] = new_id
            bag['name'] = new_name
            
            # Update current_bag if it was pointing to the old ID
            if request.session.get('current_bag') == old_id:
                request.session['current_bag'] = new_id
        
        request.session['bags'] = bags
        request.session.modified = True
        
        # If we deleted the current bag, switch to the first remaining bag
        if current_bag_id == bag_id:
            if bags:
                new_current_bag = bags[0]['id']
                request.session['current_bag'] = new_current_bag
                request.session.modified = True
                print(f"Switched current bag to: {new_current_bag}")
            else:
                request.session['current_bag'] = None
                request.session.modified = True
                print("No bags remaining, set current_bag to None")
        
        print(f"Remaining bags: {[b['id'] for b in bags]}")
        print(f"New current bag: {request.session.get('current_bag')}")
        print(f"=== DELETE BAG COMPLETED ===")
        
        return JsonResponse({
            'success': True,
            'bags': bags,
            'current_bag': request.session.get('current_bag'),
            'message': f'{bag_to_delete["name"]} deleted successfully'
        })
        
    except Exception as e:
        print(f"Delete bag error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })


def payment_success(request):
    """Payment success page - handles Paystack callback and creates order only after successful payment."""
    reference = request.GET.get('reference')
    trxref = request.GET.get('trxref')  # Paystack sometimes uses this parameter
    
    # Use either reference or trxref
    payment_reference = reference or trxref
    
    if not payment_reference:
        # No reference provided, show error
        # Get dynamic plate fee from system settings
        plate_fee = float(SystemSettings.get_setting('plate_fee', 50))
        
        return render(request, 'customer_site/payment_success.html', {
            'success': False,
            'message': 'No payment reference provided',
            'order': None,
            'plate_fee': plate_fee,
        })
    
    try:
        print(f"=== PAYMENT SUCCESS DEBUG ===")
        print(f"Payment reference: {payment_reference}")
        
        # Get the payment record
        from store.models import Payment, Order, Bag, BagItem, FoodItem
        from django.contrib.auth import get_user_model
        from django.db import transaction
        from decimal import Decimal
        
        User = get_user_model()
        
        payment = Payment.objects.get(reference=payment_reference)
        print(f"Payment found: {payment.id}, Status: {payment.status}, Order: {payment.order}")
        
        # Verify payment with Paystack
        import requests
        from django.conf import settings
        
        print(f"Verifying payment with Paystack...")
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        }
        url = f"https://api.paystack.co/transaction/verify/{payment_reference}"
        response = requests.get(url, headers=headers)
        res_data = response.json()
        
        print(f"Paystack response: {res_data}")
        
        if res_data.get("data", {}).get("status") == "success":
            # Payment is successful
            payment.status = "success"
            
            # Get the actual amount paid from Paystack and update payment record
            actual_payment_amount = res_data.get("data", {}).get("amount", 0) / 100  # Convert from kobo to NGN
            payment.amount = actual_payment_amount  # Update with actual Paystack amount
            
            try:
                payment.save()
                print(f"Actual payment amount from Paystack: ₦{actual_payment_amount:,.2f}")
            except Exception as e:
                print(f"Error saving payment: {e}")
                # Get dynamic plate fee from system settings
                plate_fee = float(SystemSettings.get_setting('plate_fee', 50))
                
                return render(request, 'customer_site/payment_success.html', {
                    'success': False,
                    'message': f'Error processing payment: {str(e)}',
                    'order': None,
                    'plate_fee': plate_fee,
                })
            
            # Check if order already exists (in case of page refresh)
            if payment.order:
                print(f"Order already exists: {payment.order.id}")
                order = payment.order
            else:
                # Get order data from session to create new order
                order_data = request.session.get('pending_order_data')
                print(f"Order data from session: {order_data}")
                if not order_data:
                    print("No order data found in session")
                    # Get dynamic plate fee from system settings
                    plate_fee = float(SystemSettings.get_setting('plate_fee', 50))
                    
                    return render(request, 'customer_site/payment_success.html', {
                        'success': False,
                        'message': 'Order data not found. Please contact support.',
                        'order': None,
                        'plate_fee': plate_fee,
                    })
            
                # Get user
                try:
                    user = User.objects.get(id=order_data['user_id'])
                except User.DoesNotExist:
                    # Get dynamic plate fee from system settings
                    plate_fee = float(SystemSettings.get_setting('plate_fee', 50))
                    
                    return render(request, 'customer_site/payment_success.html', {
                        'success': False,
                        'message': 'User not found. Please contact support.',
                        'order': None,
                        'plate_fee': plate_fee,
                    })
                
                # Create order only after successful payment
                with transaction.atomic():
                    # Create the order
                    order = Order.objects.create(
                        user=user,
                        delivery_address=order_data['delivery_address'],
                        contact_phone=order_data['contact_phone'],
                        delivery_fee=Decimal(str(order_data['delivery_fee'])),
                        service_charge=Decimal(str(order_data['service_charge'])),
                        vat_percentage=Decimal(str(order_data.get('vat_percentage', 7.5))),
                        vat_amount=Decimal(str(order_data.get('vat_amount', 0))),
                        status="Pending"  # Order is confirmed after payment
                    )
                    
                    # Create bags and bag items from session data
                    bags = []
                    session_bags = order_data['session_bags']
                    
                    for session_bag in session_bags:
                        bag_items = session_bag.get('items', [])
                        if not bag_items:
                            continue  # Skip empty bags
                        
                        # Create bag
                        bag = Bag.objects.create(owner=user)
                        bags.append(bag)
                        
                        # Process items in this bag
                        for cart_item in bag_items:
                            # Skip plate items as they're handled separately
                            if cart_item.get('is_plates'):
                                continue
                            
                            # Get food item
                            try:
                                food_item = FoodItem.objects.get(id=cart_item['id'])
                            except FoodItem.DoesNotExist:
                                continue  # Skip invalid items
                            
                            # Calculate plates needed for this food item
                            plates_needed = 1  # Default
                            if cart_item.get('category', '').lower() == 'food':
                                # Look for plates item in the same bag
                                for plate_item in bag_items:
                                    if plate_item.get('is_plates') and plate_item.get('id', '').endswith(session_bag.get('id', '')):
                                        plates_needed = plate_item.get('quantity', 1)
                                        break
                            
                            # Create bag item with correct quantity and plates
                            BagItem.objects.create(
                                bag=bag,
                                food_item=food_item,
                                portions=cart_item.get('quantity', 1),
                                plates=plates_needed
                            )
                    
                    # Link bags to order
                    order.bags.set(bags)
                    
                    # Link payment to order
                    payment.order = order
                    payment.save()
                    
                    print(f"=== ORDER CREATED AFTER PAYMENT SUCCESS ===")
                    print(f"Order ID: {order.id}")
                    print(f"Payment Reference: {payment_reference}")
                    print(f"User: {user.email}")
                    print(f"Total: {order.total}")
                    print(f"=== END ORDER CREATION ===")
                
                # Reduce quantities for all items in the order
                _reduce_order_quantities(order)
                
                # Clear the user's cart and pending order data after successful payment
                request.session['bags'] = []
                request.session['current_bag'] = 'bag_1'
                if 'pending_order_data' in request.session:
                    del request.session['pending_order_data']
                request.session.modified = True
                request.session.save()  # Force persist to database
            
            # Get dynamic plate fee from system settings
            plate_fee = float(SystemSettings.get_setting('plate_fee', 50))
            
            return render(request, 'customer_site/payment_success.html', {
                'success': True,
                'message': 'Payment successful! Your order has been confirmed.',
                'order': order,
                'payment': payment,
                'actual_payment_amount': actual_payment_amount,  # Amount actually paid from Paystack
                'plate_fee': plate_fee,
            })
        else:
            # Payment failed
            payment.status = "failed"
            payment.save()
            
            # Clear pending order data on payment failure
            if 'pending_order_data' in request.session:
                del request.session['pending_order_data']
            request.session.modified = True
            request.session.save()
            
            # Get dynamic plate fee from system settings
            plate_fee = float(SystemSettings.get_setting('plate_fee', 50))
            
            return render(request, 'customer_site/payment_success.html', {
                'success': False,
                'message': 'Payment verification failed. Please contact support.',
                'order': None,
                'payment': payment,
                'plate_fee': plate_fee,
            })
            
    except Payment.DoesNotExist:
        # Get dynamic plate fee from system settings
        plate_fee = float(SystemSettings.get_setting('plate_fee', 50))
        
        return render(request, 'customer_site/payment_success.html', {
            'success': False,
            'message': 'Payment record not found',
            'order': None,
            'plate_fee': plate_fee,
        })
    except Exception as e:
        import traceback
        print(f"Payment verification error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        # Get dynamic plate fee from system settings
        plate_fee = float(SystemSettings.get_setting('plate_fee', 50))
        
        return render(request, 'customer_site/payment_success.html', {
            'success': False,
            'message': 'An error occurred while verifying payment. Please contact support.',
            'order': None,
            'plate_fee': plate_fee,
        })


def _reduce_order_quantities(order):
    """Reduce portions for all food items in the order after successful payment."""
    from django.db import transaction
    
    # Check if quantities have already been reduced by looking at the order status
    # We'll use a simple approach: check if the order has been processed
    if hasattr(order, '_quantities_reduced'):
        print(f"Quantities already reduced for order {order.id}")
        return
    
    with transaction.atomic():
        for bag in order.bags.all():
            for bag_item in bag.items.all():
                if bag_item.food_item:  # Only reduce if food_item still exists
                    try:
                        bag_item.food_item.reduce_portions(bag_item.portions)
                        print(f"Reduced {bag_item.portions} portions of {bag_item.food_item.name}")
                    except ValueError as e:
                        # Log the error but don't fail the payment
                        print(f"Warning: Could not reduce portions for {bag_item.food_item.name}: {e}")
        
        # Mark that quantities have been reduced for this order
        order._quantities_reduced = True


def manual_clear_cart(request):
    """Manual cart clearing for debugging purposes."""
    print("=== MANUAL CART CLEAR CALLED ===")
    try:
        # Clear all session data
        request.session.flush()
        print("All session data cleared")
        
        return JsonResponse({
            'success': True,
            'message': 'Cart and all session data cleared successfully'
        })
        
    except Exception as e:
        print(f"Error clearing cart: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })


def profile(request):
    """Profile page for authenticated users to view and edit their information."""
    # For JWT-authenticated users, we'll let the frontend handle authentication
    # The profile page will check for JWT tokens and redirect if needed
    
    # Get dynamic plate fee from system settings
    plate_fee = int(float(SystemSettings.get_setting('plate_fee', 50)))
    
    return render(request, 'customer_site/profile.html', {
        'user': request.user if request.user.is_authenticated else None,
        'plate_fee': plate_fee,
    })

@csrf_exempt
@require_http_methods(["GET"])
def debug_session(request):
    """Debug session data"""
    bags = request.session.get('bags', [])
    current_bag = request.session.get('current_bag')
    
    debug_info = {
        'session_key': request.session.session_key,
        'current_bag': current_bag,
        'bags_count': len(bags),
        'bags': []
    }
    
    for bag in bags:
        bag_info = {
            'id': bag.get('id'),
            'items_count': len(bag.get('items', [])),
            'items': []
        }
        for item in bag.get('items', []):
            bag_info['items'].append({
                'id': item.get('id'),
                'name': item.get('name'),
                'quantity': item.get('quantity')
            })
        debug_info['bags'].append(bag_info)
    
    return JsonResponse(debug_info)