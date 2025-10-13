from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib import messages
from django.db.models import Count, Sum, Q
from django.db import models
from django.db.models.deletion import ProtectedError
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
import random
import string
from store.models import Category, FoodItem, Order, Payment, OrderNotification, InventoryItem, Bag, SystemSettings
from accounts.models import User, OTP
from .utils import send_otp_sms


# --- Centralized Payment Validation Functions ---
def is_legitimate_payment(payment):
    """
    Check if a payment is legitimately successful (not just marked as 'success').
    A legitimate payment must have either access_code or authorization_url from a real gateway.
    """
    if not payment or payment.status != 'success':
        return False
    
    # A legitimate payment should have either access_code or authorization_url
    # This indicates it went through a real payment gateway
    has_access_code = payment.access_code and payment.access_code.strip()
    has_auth_url = payment.authorization_url and payment.authorization_url.strip()
    
    return has_access_code or has_auth_url

def get_legitimate_payment_filter():
    """
    Get a Q filter for orders with legitimate successful payments.
    This ensures we only count orders that were actually paid for.
    """
    from django.db.models import Q
    return Q(
        payment__isnull=False,
        payment__status='success',
        payment__access_code__isnull=False
    ) | Q(
        payment__isnull=False,
        payment__status='success',
        payment__authorization_url__isnull=False
    )

def get_legitimate_payments_queryset():
    """
    Get a queryset of legitimate successful payments.
    This ensures we only count payments that were actually processed.
    """
    return Payment.objects.filter(
        status='success'
    ).filter(
        Q(access_code__isnull=False) | Q(authorization_url__isnull=False)
    )

# --- Centralized Order Count Functions ---
def get_active_orders_count():
    """
    Centralized function to get count of active orders (Pending + On the Way).
    This ensures consistency across dashboard home and orders page.
    Only counts orders with LEGITIMATE payments.
    """
    return Order.objects.filter(
        payment__status='success',
        status__in=['Pending', 'On the Way']
    ).count()

def get_pending_orders_count():
    """
    Centralized function to get count of pending orders only.
    Only counts orders with LEGITIMATE payments.
    """
    return Order.objects.filter(
        payment__status='success',
        status='Pending'
    ).count()

def get_on_the_way_orders_count():
    """
    Centralized function to get count of on-the-way orders only.
    Only counts orders with LEGITIMATE payments.
    """
    return Order.objects.filter(
        payment__status='success',
        status='On the Way'
    ).count()

def get_todays_delivered_count():
    """
    Centralized function to get count of today's delivered orders.
    Only counts orders that were actually delivered today (using delivered_at field).
    """
    today = timezone.now().date()
    return Order.objects.filter(
        payment__status='success',
        status='Delivered',
        delivered_at__date=today
    ).count()


# --- Permission Decorators ---
def admin_required(view_func):
    """Decorator to require admin role."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('dashboard:login')
        if getattr(request.user, "role", None) != "admin":
            return HttpResponseForbidden("Admin access required.")
        return view_func(request, *args, **kwargs)
    return wrapper

def admin_or_manager_required(view_func):
    """Decorator to require admin or manager role."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('dashboard:login')
        user_role = getattr(request.user, "role", None)
        if user_role not in ["admin", "manager"]:
            return HttpResponseForbidden("Admin or Manager access required.")
        return view_func(request, *args, **kwargs)
    return wrapper

def admin_or_accountant_required(view_func):
    """Decorator to require admin or accountant role."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('dashboard:login')
        user_role = getattr(request.user, "role", None)
        if user_role not in ["admin", "accountant"]:
            return HttpResponseForbidden("Admin or Accountant access required.")
        return view_func(request, *args, **kwargs)
    return wrapper

def view_only_required(view_func):
    """Decorator to allow admin or accountant (view-only access)."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('dashboard:login')
        user_role = getattr(request.user, "role", None)
        if user_role not in ["admin", "accountant"]:
            return HttpResponseForbidden("Admin or Accountant access required.")
        return view_func(request, *args, **kwargs)
    return wrapper

def admin_manager_or_accountant_required(view_func):
    """Decorator to allow admin (full access), manager (edit access), or accountant (view-only access)."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('dashboard:login')
        user_role = getattr(request.user, "role", None)
        if user_role not in ["admin", "manager", "accountant"]:
            return HttpResponseForbidden("Admin, Manager, or Accountant access required.")
        return view_func(request, *args, **kwargs)
    return wrapper

def get_user_permissions(user):
    """Get user permissions based on role."""
    role = getattr(user, "role", None)
    if role == "admin":
        return {
            "can_manage_users": True,
            "can_manage_items": True,
            "can_manage_categories": True,
            "can_manage_inventory": True,
            "can_manage_orders": True,
            "can_manage_payments": True,
            "can_view_analytics": True,
            "can_delete_orders": True,
            "can_manage_system": True,
        }
    elif role == "manager":
        return {
            "can_manage_users": False,
            "can_manage_items": True,
            "can_manage_categories": True,
            "can_manage_inventory": True,
            "can_manage_orders": True,
            "can_manage_payments": False,
            "can_view_analytics": True,  # Allow managers to view customer analytics
            "can_delete_orders": False,
            "can_manage_system": False,
        }
    elif role == "accountant":
        return {
            "can_manage_users": False,
            "can_manage_items": False,
            "can_manage_categories": False,
            "can_manage_inventory": False,
            "can_manage_orders": False,
            "can_manage_payments": False,
            "can_view_analytics": True,
            "can_delete_orders": False,
            "can_manage_system": False,
            "can_view_all": True,  # View-only access to everything
        }
    else:
        return {
            "can_manage_users": False,
            "can_manage_items": False,
            "can_manage_categories": False,
            "can_manage_inventory": False,
            "can_manage_orders": False,
            "can_manage_payments": False,
            "can_view_analytics": False,
            "can_delete_orders": False,
            "can_manage_system": False,
        }


# --- Login / Logout / Home ---

def dashboard_login(request):
    if request.method == "POST":
        phone_number = request.POST.get("phone_number")
        password = request.POST.get("password")

        user = authenticate(request, username=phone_number, password=password)

        if user and getattr(user, "role", None) in ["admin", "manager", "accountant"]:
            login(request, user)

            # ✅ handle ?next= redirect or fallback
            next_url = request.GET.get("next")
            if next_url:
                return redirect(next_url)
            
            # Redirect based on user role
            if user.role in ["admin", "accountant"]:
                return redirect("dashboard:home")
            else:  # manager
                return redirect("dashboard:items")

        # Redirect to login page with error message to prevent form resubmission
        messages.error(request, "Invalid credentials or not authorized")
        return redirect("dashboard:login")

    return render(request, "dashboard/login.html")


@login_required
def dashboard_logout(request):
    logout(request)
    return redirect("dashboard:login")


def forgot_password(request):
    """Handle forgot password request for admin users."""
    if request.method == "POST":
        phone_number = request.POST.get("phone_number")
        
        try:
            user = User.objects.get(phone_number=phone_number, role='admin')
            
            # Generate OTP
            otp_code = ''.join(random.choices(string.digits, k=5))
            
            # Delete any existing OTPs for this phone number
            OTP.objects.filter(phone_number=phone_number).delete()
            
            # Create new OTP
            OTP.objects.create(
                phone_number=phone_number,
                code=otp_code
            )
            
            # Send OTP via SMS
            sms_sent = send_otp_sms(phone_number, otp_code, "password_reset")
            
            if sms_sent:
                # Store phone number in session for verification
                request.session['reset_phone'] = phone_number
                messages.success(request, f"OTP sent to {phone_number}. Please check your messages.")
                return redirect("dashboard:reset_password")
            else:
                messages.error(request, "Failed to send OTP. Please try again.")
            
        except User.DoesNotExist:
            messages.error(request, "No admin, manager, or accountant account found with this phone number.")
    
    return render(request, "dashboard/forgot_password.html")


def reset_password(request):
    """Handle password reset with OTP verification."""
    phone_number = request.session.get('reset_phone')
    
    if not phone_number:
        messages.error(request, "Invalid reset session. Please try again.")
        return redirect("dashboard:forgot_password")
    
    if request.method == "POST":
        otp_code = request.POST.get("otp")
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")
        
        try:
            # Verify OTP
            otp = OTP.objects.get(phone_number=phone_number, code=otp_code)
            
            if otp.is_expired():
                messages.error(request, "OTP has expired. Please request a new one.")
                return redirect("dashboard:forgot_password")
            
            # Verify passwords match
            if new_password != confirm_password:
                messages.error(request, "Passwords do not match.")
                return render(request, "dashboard/reset_password.html", {"phone_number": phone_number})
            
            if len(new_password) < 6:
                messages.error(request, "Password must be at least 6 characters long.")
                return render(request, "dashboard/reset_password.html", {"phone_number": phone_number})
            
            # Update password
            user = User.objects.get(phone_number=phone_number, role='admin')
            user.set_password(new_password)
            user.save()
            
            # Clean up
            otp.delete()
            del request.session['reset_phone']
            
            messages.success(request, "Password reset successfully! You can now log in with your new password.")
            return redirect("dashboard:login")
            
        except OTP.DoesNotExist:
            messages.error(request, "Invalid OTP code.")
        except User.DoesNotExist:
            messages.error(request, "User not found.")
    
    return render(request, "dashboard/reset_password.html", {"phone_number": phone_number})


def otp_login(request):
    """Handle OTP-based login for admin users."""
    if request.method == "POST":
        phone_number = request.POST.get("phone_number")
        otp_code = request.POST.get("otp")
        
        # If no OTP provided, generate and send one
        if not otp_code:
            try:
                user = User.objects.get(phone_number=phone_number, role__in=['admin', 'manager', 'accountant'])
                
                # Generate OTP
                otp_code = ''.join(random.choices(string.digits, k=5))
                
                # Delete any existing OTPs for this phone number
                OTP.objects.filter(phone_number=phone_number).delete()
                
                # Create new OTP
                OTP.objects.create(
                    phone_number=phone_number,
                    code=otp_code
                )
                
                # Send OTP via SMS
                sms_sent = send_otp_sms(phone_number, otp_code, "login")
                
                if sms_sent:
                    messages.success(request, f"OTP sent to {phone_number}. Please check your messages and enter the code below.")
                    return render(request, "dashboard/otp_login.html", {"phone_number": phone_number, "otp_sent": True})
                else:
                    messages.error(request, "Failed to send OTP. Please try again.")
                    return render(request, "dashboard/otp_login.html")
                
            except User.DoesNotExist:
                messages.error(request, "No admin, manager, or accountant account found with this phone number.")
                return render(request, "dashboard/otp_login.html")
        
        # Verify OTP and log in
        try:
            # Verify OTP
            otp = OTP.objects.get(phone_number=phone_number, code=otp_code)
            
            if otp.is_expired():
                messages.error(request, "OTP has expired. Please request a new one.")
                return render(request, "dashboard/otp_login.html")
            
            # Get user and verify admin or manager role
            user = User.objects.get(phone_number=phone_number, role__in=['admin', 'manager'])
            
            # Log in user
            login(request, user)
            
            # Clean up OTP
            otp.delete()
            
            messages.success(request, "Logged in successfully!")
            
            # Redirect based on user role
            if user.role in ["admin", "accountant"]:
                return redirect("dashboard:home")
            else:  # manager
                return redirect("dashboard:items")
            
        except OTP.DoesNotExist:
            messages.error(request, "Invalid OTP code.")
        except User.DoesNotExist:
            messages.error(request, "No admin, manager, or accountant account found with this phone number.")
    
    return render(request, "dashboard/otp_login.html")


@view_only_required
def dashboard_home(request):
    from django.utils import timezone
    from datetime import timedelta, datetime
    from django.db.models import Q
    
    # Get filter parameters
    revenue_filter = request.GET.get('revenue_filter', 'today')
    products_filter = request.GET.get('products_filter', revenue_filter)  # Default to revenue_filter for backward compatibility
    
    # Use revenue filter as the main filter for backward compatibility
    filter_period = revenue_filter
    
    # Get current date and time
    now = timezone.now()
    today = now.date()
    
    # Calculate date ranges for REVENUE card
    if revenue_filter == 'today':
        revenue_start_date = revenue_end_date = today
        revenue_previous_start = revenue_previous_end = today - timedelta(days=1)
    elif revenue_filter == 'week':
        revenue_start_date = today - timedelta(days=today.weekday())
        revenue_end_date = today
        revenue_previous_start = revenue_start_date - timedelta(days=7)
        revenue_previous_end = revenue_start_date - timedelta(days=1)
    elif revenue_filter == 'month':
        revenue_start_date = today.replace(day=1)
        revenue_end_date = today
        if revenue_start_date.month == 1:
            revenue_previous_start = revenue_start_date.replace(year=revenue_start_date.year-1, month=12)
        else:
            revenue_previous_start = revenue_start_date.replace(month=revenue_start_date.month-1)
        revenue_previous_end = revenue_start_date - timedelta(days=1)
    elif revenue_filter == '3months':
        # Last 3 months
        revenue_start_date = today.replace(day=1) - timedelta(days=90)
        revenue_end_date = today
        # Previous 3 months for comparison
        revenue_previous_start = revenue_start_date - timedelta(days=90)
        revenue_previous_end = revenue_start_date - timedelta(days=1)
    elif revenue_filter == 'year':
        revenue_start_date = today.replace(month=1, day=1)
        revenue_end_date = today
        revenue_previous_start = revenue_start_date.replace(year=revenue_start_date.year-1)
        revenue_previous_end = revenue_start_date - timedelta(days=1)
    elif revenue_filter == 'lifetime':
        # All time data
        revenue_start_date = None  # No start date limit
        revenue_end_date = today
        revenue_previous_start = None  # No comparison for lifetime
        revenue_previous_end = None
    else:  # default to today
        revenue_start_date = revenue_end_date = today
        revenue_previous_start = revenue_previous_end = today - timedelta(days=1)
    
    
    # Get current period data (using revenue filter for orders count)
    if revenue_start_date:
        current_orders = Order.objects.filter(
            payment__status='success',
            payment__created_at__date__range=[revenue_start_date, revenue_end_date],
            status__in=['Pending', 'On the Way', 'Delivered']
        )
        
        # Calculate REVENUE data using revenue filter (from orders, not payments)
        current_revenue = sum(order.total for order in current_orders)
    else:
        # Lifetime data - no date restrictions
        current_orders = Order.objects.filter(
            payment__status='success',
            payment__created_at__date__lte=revenue_end_date,
            status__in=['Pending', 'On the Way', 'Delivered']
        )
        
        current_revenue = sum(order.total for order in current_orders)
    
    # Get previous period data for comparison (using revenue filter)
    if revenue_previous_start and revenue_previous_end:
        previous_orders = Order.objects.filter(
            payment__status='success',
            payment__created_at__date__range=[revenue_previous_start, revenue_previous_end],
            status__in=['Pending', 'On the Way', 'Delivered']
        )
        previous_revenue = sum(order.total for order in previous_orders)
    else:
        # No comparison for lifetime
        previous_revenue = 0
    
    # Calculate growth percentage
    if previous_revenue > 0:
        growth_percentage = ((current_revenue - previous_revenue) / previous_revenue) * 100
    else:
        # If we're showing lifetime data or no previous data, show 0% growth
        growth_percentage = 0
    
    
    # Get active orders count for the badge (uses centralized function)
    active_orders_count = get_active_orders_count()
    
    new_notifications = OrderNotification.objects.filter(seen=False).count()
    
    # Get best selling product(s) for the products filter period
    best_selling_products = []
    
    # Calculate date ranges for PRODUCTS card (separate from revenue)
    if products_filter == 'today':
        products_start_date = products_end_date = today
    elif products_filter == 'week':
        products_start_date = today - timedelta(days=today.weekday())
        products_end_date = today
    elif products_filter == 'month':
        products_start_date = today.replace(day=1)
        products_end_date = today
    elif products_filter == '3months':
        products_start_date = today.replace(day=1) - timedelta(days=90)
        products_end_date = today
    elif products_filter == 'year':
        products_start_date = today.replace(month=1, day=1)
        products_end_date = today
    elif products_filter == 'lifetime':
        products_start_date = None
        products_end_date = today
    else:
        products_start_date = products_end_date = today
    
    # Get orders for products analysis
    if products_start_date:
        products_orders = Order.objects.filter(
            payment__status='success',
            payment__created_at__date__range=[products_start_date, products_end_date],
            status__in=['Pending', 'On the Way', 'Delivered']
        )
    else:
        products_orders = Order.objects.filter(
            payment__status='success',
            payment__created_at__date__lte=products_end_date,
            status__in=['Pending', 'On the Way', 'Delivered']
        )
    
    if products_orders.exists():
        from django.db.models import Count, Sum
        
        # Get all food items with their order counts for the current period
        food_item_counts = {}
        
        for order in products_orders:
            for bag in order.bags.all():
                for bag_item in bag.items.all():
                    if bag_item.food_item:
                        food_item = bag_item.food_item
                        if food_item.id not in food_item_counts:
                            food_item_counts[food_item.id] = {
                                'name': food_item.name,
                                'count': 0,
                                'total_quantity': 0
                            }
                        food_item_counts[food_item.id]['count'] += 1
                        food_item_counts[food_item.id]['total_quantity'] += bag_item.portions
        
        # Find the highest count
        if food_item_counts:
            max_count = max(item['count'] for item in food_item_counts.values())
            
            # Get all products with the highest count (handle ties)
            best_selling_products = [
                {
                    'name': item['name'],
                    'count': item['count'],
                    'total_quantity': item['total_quantity']
                }
                for item in food_item_counts.values()
                if item['count'] == max_count
            ]
    
    # Import json for serialization
    import json
    from django.http import JsonResponse
    
    # Get system settings
    service_charge = SystemSettings.get_setting('service_charge', 100)
    vat_percentage = SystemSettings.get_setting('vat_percentage', 7.5)
    plate_fee = SystemSettings.get_setting('plate_fee', 50)
    
    # Handle system settings form submission
    if request.method == 'POST':
        try:
            if 'service_charge' in request.POST:
                new_value = float(request.POST.get('service_charge', 0))
                if new_value >= 0:
                    SystemSettings.set_setting(
                        'service_charge', 
                        new_value, 
                        'Fixed service charge applied to all orders',
                        request.user
                    )
                    messages.success(request, f"Service charge updated to ₦{new_value}")
                else:
                    messages.error(request, "Service charge must be 0 or greater")
            
            if 'vat_percentage' in request.POST:
                new_value = float(request.POST.get('vat_percentage', 0))
                if 0 <= new_value <= 50:
                    SystemSettings.set_setting(
                        'vat_percentage', 
                        new_value, 
                        'VAT percentage applied to order subtotal',
                        request.user
                    )
                    messages.success(request, f"VAT percentage updated to {new_value}%")
                else:
                    messages.error(request, "VAT percentage must be between 0 and 50%")
            
            
            if 'plate_fee' in request.POST:
                new_value = float(request.POST.get('plate_fee', 0))
                if 0 <= new_value <= 1000:
                    SystemSettings.set_setting(
                        'plate_fee', 
                        new_value, 
                        'Fee per plate for food items',
                        request.user
                    )
                    messages.success(request, f"Plate fee updated to ₦{new_value}")
                else:
                    messages.error(request, "Plate fee must be between 0 and 1,000")
            
            # Refresh settings after update
            service_charge = SystemSettings.get_setting('service_charge', 100)
            vat_percentage = SystemSettings.get_setting('vat_percentage', 7.5)
            plate_fee = SystemSettings.get_setting('plate_fee', 50)
            
        except ValueError as e:
            messages.error(request, f"Invalid input: {str(e)}")
        except Exception as e:
            error_msg = str(e) if str(e) else "Unknown error occurred"
            messages.error(request, f"Error updating setting: {error_msg}")
    
    context = {
        'today_orders': active_orders_count,
        'total_revenue': current_revenue,
        'growth_percentage': growth_percentage,
        'new_notifications': new_notifications,
        'filter_period': filter_period,
        'revenue_filter': revenue_filter,
        'products_filter': products_filter,
        'current_period_orders': current_orders.count(),
        'best_selling_products': best_selling_products,
        'service_charge': service_charge,
        'vat_percentage': vat_percentage,
        'plate_fee': plate_fee,
    }
    
    # Handle AJAX requests with JSON response
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'data': {
                'total_revenue': float(current_revenue),
                'total_revenue_formatted': f'₦{current_revenue:,.0f}',
                'growth_percentage': growth_percentage,
                'best_selling_products': best_selling_products,
            }
        })
    
    return render(request, "dashboard/home.html", context)


# Chart data function removed - no charts displayed
def prepare_chart_data_removed(revenue_filter, products_filter, revenue_start_date, revenue_end_date, products_start_date, products_end_date):
    """Prepare chart data with proper logic for different filter periods"""
    
    chart_data = {
        'revenue_chart': {
            'labels': [],
            'data': [],
            'colors': []
        },
        'products_chart': {
            'labels': [],
            'data': [],
            'colors': []
        }
    }
    
    try:
        from datetime import timedelta
        
        # Revenue chart data based on revenue filter
        if revenue_filter == 'today':
            # Hourly data for today
            revenue_data = []
            labels = []
            
            # Use the revenue_start_date (today) for consistency
            today_date = revenue_start_date
            
            for hour in range(24):
                hour_start = timezone.datetime.combine(today_date, timezone.datetime.min.time())
                hour_start = hour_start.replace(hour=hour)
                hour_end = hour_start + timedelta(hours=1)
                
                hourly_orders = Order.objects.filter(
                    payment__status='success',
                    payment__created_at__gte=hour_start,
                    payment__created_at__lt=hour_end,
                    status__in=['Pending', 'On the Way', 'Delivered']
                )
                hourly_revenue = sum(order.total for order in hourly_orders)
                
                revenue_data.append(float(hourly_revenue))
                labels.append(f"{hour:02d}:00")
            
            chart_data['revenue_chart']['labels'] = labels
            chart_data['revenue_chart']['data'] = revenue_data
            chart_data['revenue_chart']['colors'] = ['#C41115'] * len(revenue_data)
            
        elif revenue_filter == 'week':
            # Daily data for the week
            revenue_data = []
            labels = []
            for i in range(7):
                day = revenue_start_date + timedelta(days=i)
                daily_orders = Order.objects.filter(
                    payment__status='success',
                    payment__created_at__date=day,
                    status__in=['Pending', 'On the Way', 'Delivered']
                )
                daily_revenue = sum(order.total for order in daily_orders)
                
                revenue_data.append(float(daily_revenue))
                labels.append(day.strftime('%a'))
            
            chart_data['revenue_chart']['labels'] = labels
            chart_data['revenue_chart']['data'] = revenue_data
            chart_data['revenue_chart']['colors'] = ['#C41115'] * len(revenue_data)
            
        elif revenue_filter == 'month':
            # Weekly data for the month
            revenue_data = []
            labels = []
            current_date = revenue_start_date
            week_num = 1
            while current_date <= revenue_end_date:
                week_end = min(current_date + timedelta(days=6), revenue_end_date)
                weekly_orders = Order.objects.filter(
                    payment__status='success',
                    payment__created_at__date__range=[current_date, week_end],
                    status__in=['Pending', 'On the Way', 'Delivered']
                )
                weekly_revenue = sum(order.total for order in weekly_orders)
                
                revenue_data.append(float(weekly_revenue))
                labels.append(f'Week {week_num}')
                
                current_date += timedelta(days=7)
                week_num += 1
            
            chart_data['revenue_chart']['labels'] = labels
            chart_data['revenue_chart']['data'] = revenue_data
            chart_data['revenue_chart']['colors'] = ['#C41115'] * len(revenue_data)
            
        elif revenue_filter == '3months':
            # Monthly data for last 3 months
            revenue_data = []
            labels = []
            
            # Calculate the last 3 months properly
            current_date = revenue_end_date
            for i in range(3):
                # Go back i months from current date
                if current_date.month - i <= 0:
                    month = 12 + (current_date.month - i)
                    year = current_date.year - 1
                else:
                    month = current_date.month - i
                    year = current_date.year
                
                month_start = current_date.replace(year=year, month=month, day=1)
                
                # Calculate month end
                if month == 12:
                    month_end = current_date.replace(year=year + 1, month=1, day=1) - timedelta(days=1)
                else:
                    month_end = current_date.replace(year=year, month=month + 1, day=1) - timedelta(days=1)
                
                # For the current month, use revenue_end_date as the limit
                if i == 0:
                    month_end = min(month_end, revenue_end_date)
                
                monthly_orders = Order.objects.filter(
                    payment__status='success',
                    payment__created_at__date__range=[month_start, month_end],
                    status__in=['Pending', 'On the Way', 'Delivered']
                )
                monthly_revenue = sum(order.total for order in monthly_orders)
                
                revenue_data.append(float(monthly_revenue))
                labels.append(month_start.strftime('%b %Y'))
            
            # Reverse to show oldest to newest
            revenue_data.reverse()
            labels.reverse()
            
            chart_data['revenue_chart']['labels'] = labels
            chart_data['revenue_chart']['data'] = revenue_data
            chart_data['revenue_chart']['colors'] = ['#C41115'] * len(revenue_data)
            
        elif revenue_filter == 'year':
            # Monthly data for the year
            revenue_data = []
            labels = []
            for month in range(1, 13):
                month_start = revenue_start_date.replace(month=month, day=1)
                if month == 12:
                    month_end = revenue_start_date.replace(year=revenue_start_date.year + 1, month=1, day=1) - timedelta(days=1)
                else:
                    month_end = revenue_start_date.replace(month=month + 1, day=1) - timedelta(days=1)
                
                monthly_orders = Order.objects.filter(
                    payment__status='success',
                    payment__created_at__date__range=[month_start, month_end],
                    status__in=['Pending', 'On the Way', 'Delivered']
                )
                monthly_revenue = sum(order.total for order in monthly_orders)
                
                revenue_data.append(float(monthly_revenue))
                labels.append(month_start.strftime('%b'))
            
            chart_data['revenue_chart']['labels'] = labels
            chart_data['revenue_chart']['data'] = revenue_data
            chart_data['revenue_chart']['colors'] = ['#C41115'] * len(revenue_data)
            
        elif revenue_filter == 'lifetime':
            # Yearly data for lifetime
            revenue_data = []
            labels = []
            current_year = revenue_start_date.year if revenue_start_date else 2020
            end_year = revenue_end_date.year
            
            for year in range(current_year, end_year + 1):
                year_start = timezone.datetime(year, 1, 1).date()
                year_end = timezone.datetime(year, 12, 31).date()
                
                yearly_orders = Order.objects.filter(
                    payment__status='success',
                    payment__created_at__date__range=[year_start, year_end],
                    status__in=['Pending', 'On the Way', 'Delivered']
                )
                yearly_revenue = sum(order.total for order in yearly_orders)
                
                revenue_data.append(float(yearly_revenue))
                labels.append(str(year))
            
            chart_data['revenue_chart']['labels'] = labels
            chart_data['revenue_chart']['data'] = revenue_data
            chart_data['revenue_chart']['colors'] = ['#C41115'] * len(revenue_data)
        
        # Products chart data - improved logic using products filter
        if products_start_date:
            successful_orders = Order.objects.filter(
                payment__status='success',
                payment__created_at__date__range=[products_start_date, products_end_date]
            )
        else:
            successful_orders = Order.objects.filter(
                payment__status='success',
                payment__created_at__date__lte=products_end_date
            )
        
        successful_bags = Bag.objects.filter(orders__in=successful_orders)
        
        # Get top 4 products only, then add "Others" category
        top_products = FoodItem.objects.filter(
            bagitem__bag__in=successful_bags
        ).annotate(
            total_orders=Count('bagitem__bag__orders', distinct=True)
        ).order_by('-total_orders')[:4]
        
        if top_products.exists():
            # Use consistent colors that match the template indicators
            colors = ['#C41115', '#10b981', '#f59e0b', '#ef4444', '#6b7280']
            
            # Add top 4 products
            for i, product in enumerate(top_products):
                chart_data['products_chart']['labels'].append(product.name[:12] + '...' if len(product.name) > 12 else product.name)
                chart_data['products_chart']['data'].append(product.total_orders)
                chart_data['products_chart']['colors'].append(colors[i])
            
            # Calculate total orders for all products (correct way)
            all_products_with_orders = FoodItem.objects.filter(
                bagitem__bag__in=successful_bags
            ).annotate(
                total_orders=Count('bagitem__bag__orders', distinct=True)
            )
            
            all_products_total = sum(product.total_orders for product in all_products_with_orders)
            
            # Calculate top 4 total
            top_4_total = sum(product.total_orders for product in top_products)
            
            # Add "Others" category if there are more products
            if all_products_total > top_4_total:
                others_count = all_products_total - top_4_total
                chart_data['products_chart']['labels'].append('Others')
                chart_data['products_chart']['data'].append(others_count)
                chart_data['products_chart']['colors'].append('#6b7280')
    
    except Exception as e:
        # If anything fails, use fallback data
        print(f"Chart data generation failed, using fallback: {e}")
        chart_data = {
            'revenue_chart': {
                'labels': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                'data': [1000, 1500, 2000, 1800, 2200, 2500, 3000],
                'colors': ['#C41115'] * 7
            },
            'products_chart': {
                'labels': ['Cheeseburger', 'Chicken Wings', 'Beef Stew', 'Margherita Pizza', 'Others'],
                'data': [8, 7, 7, 4, 3],
                'colors': ['#C41115', '#10b981', '#f59e0b', '#ef4444', '#6b7280']
            }
        }
    
    return chart_data




# --- Extra Pages ---

@admin_manager_or_accountant_required
def dashboard_categories(request):
    
    categories = Category.objects.exclude(name__iexact='All').order_by('id')
    context = {'categories': categories}
    return render(request, "dashboard/categories.html", context)


@admin_manager_or_accountant_required
def dashboard_items(request):
    
    # Get search and category filter parameters
    search_query = request.GET.get('search', '')
    category_filter = request.GET.get('category', '')
    
    items = FoodItem.objects.select_related('category').all()
    
    # Apply search filter if provided
    if search_query:
        items = items.filter(name__icontains=search_query)
    
    # Apply category filter if provided
    if category_filter:
        # If "All" is selected, show items from all categories (excluding "All" category)
        if category_filter == 'all':
            items = items.exclude(category__name__iexact='All')
        else:
            items = items.filter(category_id=category_filter)
    else:
        # Default to showing all items (excluding "All" category)
        items = items.exclude(category__name__iexact='All')
    
    categories = Category.objects.exclude(name__iexact='All').order_by('id')
    
    # Calculate inventory stats
    total_items = items.count()
    available_items = items.filter(portions__gt=0).count()
    out_of_stock_items = items.filter(portions=0).count()
    low_stock_items = items.filter(portions__gt=0, portions__lte=5).count()
    
    context = {
        'items': items, 
        'categories': categories,
        'search_query': search_query,
        'category_filter': category_filter,
        'total_items': total_items,
        'available_items': available_items,
        'out_of_stock_items': out_of_stock_items,
        'low_stock_items': low_stock_items,
    }
    return render(request, "dashboard/items.html", context)


@admin_manager_or_accountant_required
def dashboard_orders(request):
    
    # Get filter parameters
    sort_by = request.GET.get('sort', 'newest')
    
    # Determine ordering
    if sort_by == 'oldest':
        order_by = 'created_at'
    else:  # newest (default)
        order_by = '-created_at'
    
    # Base queryset for all orders
    base_orders = Order.objects.filter(
        payment__status='success'
    ).select_related('user', 'payment').prefetch_related('bags')
    
    # Get pending orders (paid, ready for preparation) - orders with successful payment and 'Pending' status
    pending_orders = base_orders.filter(
        status='Pending'  # Only show orders that are explicitly 'Pending' status
    ).order_by(order_by)
    
    # Processing orders (unpaid) are not shown - they're just cart items
    processing_orders = Order.objects.none()
    
    # Get on-the-way orders (currently out for delivery) - only orders that have been paid for
    on_the_way_orders = base_orders.filter(
        status='On the Way'
    ).order_by(order_by)
    
    # Get count of today's delivered orders (uses centralized function)
    todays_delivered_count = get_todays_delivered_count()
    
    # Get today's delivered orders for the tab
    from django.utils import timezone
    today = timezone.now().date()
    todays_delivered_orders = base_orders.filter(
        status='Delivered',
        delivered_at__date=today
    ).order_by(order_by)
    
    context = {
        'pending_orders': pending_orders,
        'processing_orders': processing_orders,
        'on_the_way_orders': on_the_way_orders,
        'todays_delivered_orders': todays_delivered_orders,
        'todays_delivered_count': todays_delivered_count,
        'current_sort': sort_by,
        # Centralized counts for consistency
        'active_orders_count': get_active_orders_count(),
        'pending_orders_count': get_pending_orders_count(),
        'on_the_way_orders_count': get_on_the_way_orders_count(),
    }
    return render(request, "dashboard/orders.html", context)


@login_required
def dashboard_notifications(request):
    if getattr(request.user, "role", None) != "admin":
        return HttpResponseForbidden("Not authorized.")
    
    notifications = OrderNotification.objects.select_related('order').all().order_by('-created_at')
    context = {'notifications': notifications}
    return render(request, "dashboard/notifications.html", context)


@view_only_required
def dashboard_payments(request):

    # Get filter parameters
    sort_by = request.GET.get('sort', 'newest')
    time_filter = request.GET.get('time', 'today')
    search_query = request.GET.get('search', '')
    
    # Determine ordering
    if sort_by == 'oldest':
        order_by = 'created_at'
    else:  # newest (default)
        order_by = '-created_at'
    
    # Apply time-based filtering - ONLY show successful payments that have orders
    payments = Payment.objects.filter(status='success', order__isnull=False).select_related('order', 'user')
    
    if time_filter == 'today':
        payments = payments.filter(created_at__date=timezone.now().date())
    elif time_filter == '7days':
        from datetime import timedelta
        payments = payments.filter(created_at__gte=timezone.now() - timedelta(days=7))
    elif time_filter == '28days':
        from datetime import timedelta
        payments = payments.filter(created_at__gte=timezone.now() - timedelta(days=28))
    elif time_filter == '3months':
        from datetime import timedelta
        payments = payments.filter(created_at__gte=timezone.now() - timedelta(days=90))
    
    
    # Apply search filter if provided
    if search_query:
        payments = payments.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query)
        )
    # 'lifetime' shows all payments (no additional filter)
    
    payments = payments.order_by(order_by)
    
    context = {
        'payments': payments, 
        'current_sort': sort_by,
        'current_time_filter': time_filter,
        'search_query': search_query
    }
    return render(request, "dashboard/payments.html", context)


@admin_manager_or_accountant_required
def dashboard_users(request):
    
    # Get search and sort parameters
    search_query = request.GET.get('search', '')
    sort_by = request.GET.get('sort', 'newest')  # Default to newest
    
    # Show only customers who have made payments (i.e., have ordered before)
    customers = User.objects.filter(
        role='customer',
        payments__isnull=False
    ).distinct()
    
    # Apply search filter if provided
    if search_query:
        customers = customers.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(phone_number__icontains=search_query)
        )
    
    # Add total spent for each customer
    customers_with_totals = []
    for customer in customers:
        # Count all successful payments for accurate calculations
        successful_payments = customer.payments.filter(status='success')
        total_spent = sum(payment.amount for payment in successful_payments)
        customers_with_totals.append({
            'customer': customer,
            'total_spent': total_spent,
            'orders_count': successful_payments.count(),
            'last_order_date': successful_payments.first().created_at if successful_payments.exists() else None
        })
    
    # Apply sorting
    if sort_by == 'top_spenders':
        customers_with_totals.sort(key=lambda x: x['total_spent'], reverse=True)
    elif sort_by == 'most_orders':
        customers_with_totals.sort(key=lambda x: x['orders_count'], reverse=True)
    elif sort_by == 'newest':
        customers_with_totals.sort(key=lambda x: x['customer'].id, reverse=True)
    elif sort_by == 'oldest':
        customers_with_totals.sort(key=lambda x: x['customer'].id)
    elif sort_by == 'name_asc':
        customers_with_totals.sort(key=lambda x: (x['customer'].first_name or '') + (x['customer'].last_name or ''))
    elif sort_by == 'name_desc':
        customers_with_totals.sort(key=lambda x: (x['customer'].first_name or '') + (x['customer'].last_name or ''), reverse=True)
    
    context = {
        'customers_data': customers_with_totals,
        'search_query': search_query,
        'current_sort': sort_by
    }
    return render(request, "dashboard/users.html", context)


@admin_manager_or_accountant_required
def customer_orders(request, customer_id):
    """Display order history for a specific customer."""
    
    try:
        customer = User.objects.get(id=customer_id, role='customer')
    except User.DoesNotExist:
        messages.error(request, "Customer not found.")
        return redirect('dashboard:users')
    
    # Get all orders for this customer
    orders = Order.objects.filter(
        user=customer,
        payment__status='success'  # Only show successful orders
    ).select_related('payment').prefetch_related('bags__items__food_item').order_by('-created_at')
    
    # Get customer statistics
    total_orders = orders.count()
    total_spent = sum(order.payment.amount for order in orders if order.payment)
    last_order_date = orders.first().created_at if orders.exists() else None
    
    context = {
        'customer': customer,
        'orders': orders,
        'total_orders': total_orders,
        'total_spent': total_spent,
        'last_order_date': last_order_date,
    }
    return render(request, "dashboard/customer_orders.html", context)


@admin_manager_or_accountant_required
def dashboard_inventory(request):
    """Display physical inventory items in the store."""
    
    # Get search parameter
    search_query = request.GET.get('search', '')
    
    # Get all inventory items with user information
    items = InventoryItem.objects.select_related('created_by', 'updated_by').all()
    
    # Apply search filter if provided
    if search_query:
        items = items.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Order by name
    items = items.order_by('name')
    
    context = {
        'inventory_items': items,
        'search_query': search_query,
    }
    return render(request, "dashboard/inventory.html", context)


# --- CRUD Operations ---

@login_required
def add_inventory_item(request):
    """Add a new inventory item."""
    if getattr(request.user, "role", None) not in ["admin", "manager"]:
        return HttpResponseForbidden("Not authorized.")
    
    if request.method == "POST":
        name = request.POST.get("name")
        quantity = request.POST.get("quantity", 0)
        description = request.POST.get("description", "")
        
        # VALIDATION: Ensure we're using the correct field name
        if "portions" in request.POST:
            messages.error(request, "ERROR: Field name mismatch detected. Please use 'quantity' field for inventory items.")
            return render(request, "dashboard/add_inventory_item.html")
        
        if name:
            try:
                # VALIDATION: Ensure quantity is a valid positive integer
                quantity_value = int(quantity) if quantity and quantity.isdigit() else 0
                if quantity_value < 0:
                    quantity_value = 0
                
                # Create inventory item with correct field name
                InventoryItem.objects.create(
                    name=name,
                    quantity=quantity_value,  # CORRECT FIELD NAME
                    description=description,
                    created_by=request.user,
                    updated_by=request.user
                )
                messages.success(request, f"Inventory item '{name}' added successfully!")
                return redirect("dashboard:inventory")
            except ValueError:
                messages.error(request, "Invalid quantity value. Please enter a valid number.")
            except Exception as e:
                if "UNIQUE constraint failed" in str(e) and "name" in str(e):
                    messages.error(request, f"The item '{name}' already exists. Please choose a different name.")
                else:
                    messages.error(request, f"Error adding inventory item: {str(e)}")
        else:
            messages.error(request, "Name is required.")
    
    return render(request, "dashboard/add_inventory_item.html")

@login_required
def edit_inventory_item(request, item_id):
    """Edit an inventory item."""
    if getattr(request.user, "role", None) not in ["admin", "manager"]:
        return HttpResponseForbidden("Not authorized.")
    
    item = get_object_or_404(InventoryItem, id=item_id)
    
    if request.method == "POST":
        name = request.POST.get("name")
        quantity = request.POST.get("quantity", 0)
        description = request.POST.get("description", "")
        
        # VALIDATION: Ensure we're using the correct field name
        if "portions" in request.POST:
            messages.error(request, "ERROR: Field name mismatch detected. Please use 'quantity' field for inventory items.")
            context = {'item': item}
            return render(request, "dashboard/edit_inventory_item.html", context)
        
        if name:
            try:
                # VALIDATION: Ensure quantity is a valid positive integer
                quantity_value = int(quantity) if quantity and quantity.isdigit() else 0
                if quantity_value < 0:
                    quantity_value = 0
                
                # Update inventory item with correct field name
                item.name = name
                item.quantity = quantity_value  # CORRECT FIELD NAME
                item.description = description
                item.updated_by = request.user
                item.save()
                messages.success(request, f"Inventory item '{name}' updated successfully!")
                return redirect("dashboard:inventory")
            except ValueError:
                messages.error(request, "Invalid quantity value. Please enter a valid number.")
            except Exception as e:
                if "UNIQUE constraint failed" in str(e) and "name" in str(e):
                    messages.error(request, f"The item '{name}' already exists. Please choose a different name.")
                else:
                    messages.error(request, f"Error updating inventory item: {str(e)}")
        else:
            messages.error(request, "Name is required.")
    
    context = {'item': item}
    return render(request, "dashboard/edit_inventory_item.html", context)

@login_required
def delete_inventory_item(request, item_id):
    """Delete an inventory item."""
    if getattr(request.user, "role", None) != "admin":
        return HttpResponseForbidden("Not authorized.")
    
    item = get_object_or_404(InventoryItem, id=item_id)
    item_name = item.name
    
    try:
        item.delete()
        messages.success(request, f"Inventory item '{item_name}' deleted successfully!")
    except Exception as e:
        messages.error(request, f"Error deleting inventory item: {str(e)}")
    
    return redirect("dashboard:inventory")

@login_required
def add_category(request):
    if getattr(request.user, "role", None) not in ["admin", "manager"]:
        return HttpResponseForbidden("Not authorized.")
    
    if request.method == "POST":
        name = request.POST.get("name")
        if name:
            try:
                Category.objects.create(name=name)
                messages.success(request, f"Category '{name}' added successfully!")
                return redirect("dashboard:categories")
            except Exception as e:
                if "UNIQUE constraint failed" in str(e) and "name" in str(e):
                    messages.error(request, f"The category '{name}' already exists. Please choose a different name.")
                else:
                    messages.error(request, f"Error adding category: {str(e)}")
        else:
            messages.error(request, "Category name is required.")
    
    return render(request, "dashboard/add_category.html")


@login_required
def edit_category(request, category_id):
    if getattr(request.user, "role", None) not in ["admin", "manager"]:
        return HttpResponseForbidden("Not authorized.")
    
    category = get_object_or_404(Category, id=category_id)
    
    if request.method == "POST":
        name = request.POST.get("name")
        if name:
            try:
                category.name = name
                category.save()
                messages.success(request, f"Category updated successfully!")
                return redirect("dashboard:categories")
            except Exception as e:
                if "UNIQUE constraint failed" in str(e) and "name" in str(e):
                    messages.error(request, f"The category '{name}' already exists. Please choose a different name.")
                else:
                    messages.error(request, f"Error updating category: {str(e)}")
        else:
            messages.error(request, "Category name is required.")
    
    context = {'category': category}
    return render(request, "dashboard/edit_category.html", context)


@login_required
@require_POST
def delete_category(request, category_id):
    if getattr(request.user, "role", None) not in ["admin", "manager"]:
        return HttpResponseForbidden("Not authorized.")
    
    category = get_object_or_404(Category, id=category_id)
    category_name = category.name
    
    try:
        # Store category and its food items data for potential undo
        food_items_data = []
        for item in category.food_items.all():
            food_items_data.append({
                'id': item.id,
                'name': item.name,
                'price': float(item.price),
                'image_url': item.image_url,
                'image': item.image.name if item.image else None,
                'availability': item.availability,
            })
        
        category_data = {
            'id': category.id,
            'name': category.name,
            'food_items': food_items_data,
            'deleted_at': timezone.now().isoformat()
        }
        
        category.delete()
        
        # Store in session for undo (expires in 30 seconds)
        request.session['deleted_category'] = category_data
        request.session['deleted_category_expires'] = timezone.now().timestamp() + 30
        
        # Create undo URL for the success message
        undo_url = f"/dashboard/categories/undo-delete/"
        success_message = f"Category '{category_name}' deleted successfully! <a href='{undo_url}' onclick='return confirmUndo(this)' style='color: #3498db; text-decoration: underline; margin-left: 10px;'>Undo</a>"
        messages.success(request, success_message)
    except ProtectedError:
        messages.error(request, f"Cannot delete category '{category_name}' because it contains food items that are referenced in existing orders. To delete this category, first delete all food items in it, or mark them as out of stock instead.")
    
    return redirect("dashboard:categories")


@login_required
def add_item(request):
    if getattr(request.user, "role", None) not in ["admin", "manager"]:
        return HttpResponseForbidden("Not authorized.")
    
    categories = Category.objects.exclude(name__iexact='All').order_by('id')
    
    if request.method == "POST":
        name = request.POST.get("name")
        price = request.POST.get("price")
        category_id = request.POST.get("category")
        image_url = request.POST.get("image_url", "")
        out_of_stock = request.POST.get("out_of_stock") == "on"
        portions = request.POST.get("portions", 0)
        image_file = request.FILES.get("image")
        
        if name and price and category_id:
            try:
                category = Category.objects.get(id=category_id)
                
                # Handle out of stock toggle
                if out_of_stock:
                    final_portions = 0
                    availability = False
                else:
                    final_portions = int(portions) if portions else 0
                    availability = True
                
                # Create the food item with validation
                food_item = FoodItem(
                    name=name,
                    price=float(price),
                    category=category,
                    image_url=image_url,
                    image=image_file,
                    availability=availability,
                    portions=final_portions,
                    created_by=request.user,
                    updated_by=request.user
                )
                # Validate the food item before saving
                food_item.full_clean()
                food_item.save()
                messages.success(request, f"Item '{name}' added successfully!")
                return redirect("dashboard:items")
            except Exception as e:
                if "UNIQUE constraint failed" in str(e) and "name" in str(e):
                    messages.error(request, f"The item '{name}' already exists. Please choose a different name.")
                elif isinstance(e, (ValueError, Category.DoesNotExist)):
                    messages.error(request, f"Invalid data provided: {str(e)}")
                else:
                    messages.error(request, f"Error adding item: {str(e)}")
        else:
            messages.error(request, "Name, price, and category are required.")
    
    context = {'categories': categories}
    return render(request, "dashboard/add_item.html", context)


@login_required
def edit_item(request, item_id):
    if getattr(request.user, "role", None) not in ["admin", "manager"]:
        return HttpResponseForbidden("Not authorized.")
    
    item = get_object_or_404(FoodItem, id=item_id)
    categories = Category.objects.exclude(name__iexact='All').order_by('id')
    
    if request.method == "POST":
        name = request.POST.get("name")
        price = request.POST.get("price")
        category_id = request.POST.get("category")
        image_url = request.POST.get("image_url", "")
        out_of_stock = request.POST.get("out_of_stock") == "on"
        portions = request.POST.get("portions", 0)
        remove_image = request.POST.get("remove_image") == "1"
        
        if name and price and category_id:
            try:
                category = Category.objects.get(id=category_id)
                item.name = name
                item.price = float(price)
                item.category = category
                item.image_url = image_url
                
                # Handle image removal
                if remove_image:
                    if item.image:
                        item.image.delete(save=False)  # Delete the file
                    item.image = None
                elif 'image' in request.FILES:
                    # If uploading new image, delete old one first
                    if item.image:
                        item.image.delete(save=False)
                    item.image = request.FILES['image']
                
                # Handle out of stock toggle
                if out_of_stock:
                    item.portions = 0
                    item.availability = False
                else:
                    item.portions = int(portions) if portions else 0
                    item.availability = True
                
                # Set updated_by field
                item.updated_by = request.user
                
                # Validate the food item before saving
                item.full_clean()
                item.save()
                messages.success(request, f"Item '{name}' updated successfully!")
                return redirect("dashboard:items")
            except Exception as e:
                if "UNIQUE constraint failed" in str(e) and "name" in str(e):
                    messages.error(request, f"The item '{name}' already exists. Please choose a different name.")
                elif isinstance(e, (ValueError, Category.DoesNotExist)):
                    messages.error(request, "Invalid data provided.")
                else:
                    messages.error(request, f"Error updating item: {str(e)}")
        else:
            messages.error(request, "Name, price, and category are required.")
    
    context = {'item': item, 'categories': categories}
    return render(request, "dashboard/edit_item.html", context)


@login_required
@require_POST
def delete_item(request, item_id):
    if getattr(request.user, "role", None) not in ["admin", "manager"]:
        return HttpResponseForbidden("Not authorized.")
    
    item = get_object_or_404(FoodItem, id=item_id)
    item_name = item.name
    
    try:
        # Store item data for potential undo
        item_data = {
            'id': item.id,
            'name': item.name,
            'price': float(item.price),
            'image_url': item.image_url,
            'image': item.image.name if item.image else None,
            'category_id': item.category.id,
            'availability': item.availability,
            'deleted_at': timezone.now().isoformat()
        }
        
        item.delete()
        
        # Store in session for undo (expires in 30 seconds)
        request.session['deleted_item'] = item_data
        request.session['deleted_item_expires'] = timezone.now().timestamp() + 30
        
        # Create undo URL for the success message
        undo_url = f"/dashboard/items/undo-delete/"
        success_message = f"Item '{item_name}' deleted successfully! <a href='{undo_url}' onclick='return confirmUndo(this)' style='color: #3498db; text-decoration: underline; margin-left: 10px;'>Undo</a>"
        messages.success(request, success_message)
    except ProtectedError:
        messages.error(request, f"Cannot delete item '{item_name}' because it is referenced in existing orders. To remove this item from the menu, mark it as 'Out of Stock' instead of deleting it.")
    
    return redirect("dashboard:items")


@login_required
@require_POST
def undo_delete_item(request):
    """Undo the deletion of a food item."""
    if getattr(request.user, "role", None) not in ["admin", "manager"]:
        return HttpResponseForbidden("Not authorized.")
    
    # Check if there's a deleted item in session and it hasn't expired
    if 'deleted_item' not in request.session:
        messages.error(request, "No item to undo.")
        return redirect("dashboard:items")
    
    if 'deleted_item_expires' not in request.session:
        messages.error(request, "Undo period has expired.")
        return redirect("dashboard:items")
    
    if timezone.now().timestamp() > request.session['deleted_item_expires']:
        messages.error(request, "Undo period has expired.")
        # Clean up expired session data
        del request.session['deleted_item']
        del request.session['deleted_item_expires']
        return redirect("dashboard:items")
    
    try:
        item_data = request.session['deleted_item']
        
        # Check if category still exists
        try:
            category = Category.objects.get(id=item_data['category_id'])
        except Category.DoesNotExist:
            messages.error(request, "Cannot undo: The category for this item no longer exists.")
            del request.session['deleted_item']
            del request.session['deleted_item_expires']
            return redirect("dashboard:items")
        
        # Recreate the food item with the original ID
        food_item = FoodItem(
            id=item_data['id'],  # Preserve original ID
            name=item_data['name'],
            price=item_data['price'],
            image_url=item_data['image_url'],
            category=category,
            availability=item_data['availability']
        )
        food_item.save()
        
        # Clean up session data
        del request.session['deleted_item']
        del request.session['deleted_item_expires']
        
        messages.success(request, f"Item '{item_data['name']}' has been restored successfully!")
        
    except Exception as e:
        messages.error(request, f"Failed to restore item: {str(e)}")
    
    return redirect("dashboard:items")


@login_required
@require_POST
def undo_delete_category(request):
    """Undo the deletion of a category and its food items."""
    if getattr(request.user, "role", None) not in ["admin", "manager"]:
        return HttpResponseForbidden("Not authorized.")
    
    # Check if there's a deleted category in session and it hasn't expired
    if 'deleted_category' not in request.session:
        messages.error(request, "No category to undo.")
        return redirect("dashboard:categories")
    
    if 'deleted_category_expires' not in request.session:
        messages.error(request, "Undo period has expired.")
        return redirect("dashboard:categories")
    
    if timezone.now().timestamp() > request.session['deleted_category_expires']:
        messages.error(request, "Undo period has expired.")
        # Clean up expired session data
        del request.session['deleted_category']
        del request.session['deleted_category_expires']
        return redirect("dashboard:categories")
    
    try:
        category_data = request.session['deleted_category']
        
        # Recreate the category with the original ID
        category = Category(
            id=category_data['id'],  # Preserve original ID
            name=category_data['name']
        )
        category.save()
        
        # Recreate all food items with their original IDs
        for item_data in category_data['food_items']:
            food_item = FoodItem(
                id=item_data['id'],  # Preserve original ID
                name=item_data['name'],
                price=item_data['price'],
                image_url=item_data['image_url'],
                category=category,
                availability=item_data['availability']
            )
            food_item.save()
        
        # Clean up session data
        del request.session['deleted_category']
        del request.session['deleted_category_expires']
        
        messages.success(request, f"Category '{category_data['name']}' and its items have been restored successfully!")
        
    except Exception as e:
        messages.error(request, f"Failed to restore category: {str(e)}")
    
    return redirect("dashboard:categories")


@login_required
@require_POST
def update_order_status(request, order_id):
    if getattr(request.user, "role", None) not in ["admin", "manager"]:
        return HttpResponseForbidden("Not authorized.")
    
    order = get_object_or_404(Order, id=order_id)
    new_status = request.POST.get("status")
    
    if new_status in [choice[0] for choice in Order.STATUS_CHOICES]:
        old_status = order.status
        order.status = new_status
        order.save()
        
        # Create notification for status change
        customer_name = f"{order.user.first_name} {order.user.last_name}".strip() or order.user.phone_number
        OrderNotification.objects.create(
            order=order,
            message=f"Order #{order.id} for {customer_name}: Status changed from {old_status} to {new_status}"
        )
        
        messages.success(request, f"Order #{order.id} status updated to {new_status}")
    else:
        messages.error(request, "Invalid status provided.")
    
    # Preserve tab state when redirecting
    tab = request.GET.get('tab', 'pending')
    return redirect(f"{reverse('dashboard:orders')}?tab={tab}")


@login_required
@require_POST
def bulk_send_for_delivery(request):
    if getattr(request.user, "role", None) not in ["admin", "manager"]:
        return HttpResponseForbidden("Not authorized.")
    
    order_ids = request.POST.getlist('order_ids')
    if not order_ids:
        messages.error(request, "No orders selected.")
        tab = request.GET.get('tab', 'pending')
        return redirect(f"{reverse('dashboard:orders')}?tab={tab}")
    
    updated_count = 0
    for order_id in order_ids:
        try:
            # Only process orders that are legitimately paid and ready for delivery
            order = Order.objects.filter(
                id=order_id, 
                payment__status='success'
            ).first()
            
            if not order:
                continue
            order.status = 'On the Way'
            order.save()
            
            # Create notification
            customer_name = f"{order.user.first_name} {order.user.last_name}".strip() or order.user.phone_number
            OrderNotification.objects.create(
                order=order,
                message=f"Order #{order.id} for {customer_name}: Status changed from Accepted to On the Way"
            )
            updated_count += 1
        except Order.DoesNotExist:
            continue
    
    if updated_count > 0:
        messages.success(request, f"{updated_count} order(s) sent for delivery successfully!")
    else:
        messages.error(request, "No valid orders found to send for delivery.")
    
    # Preserve tab state when redirecting
    tab = request.GET.get('tab', 'pending')
    return redirect(f"{reverse('dashboard:orders')}?tab={tab}")


@login_required
@require_POST
def bulk_mark_delivered(request):
    if getattr(request.user, "role", None) not in ["admin", "manager"]:
        return HttpResponseForbidden("Not authorized.")
    
    order_ids = request.POST.getlist('order_ids')
    if not order_ids:
        messages.error(request, "No orders selected.")
        tab = request.GET.get('tab', 'pending')
        return redirect(f"{reverse('dashboard:orders')}?tab={tab}")
    
    updated_count = 0
    for order_id in order_ids:
        try:
            # Only process orders that are on the way and legitimately paid
            order = Order.objects.filter(
                id=order_id, 
                status='On the Way',
                payment__status='success'
            ).first()
            
            if not order:
                continue
            order.status = 'Delivered'
            order.save()
            
            # Create notification
            customer_name = f"{order.user.first_name} {order.user.last_name}".strip() or order.user.phone_number
            OrderNotification.objects.create(
                order=order,
                message=f"Order #{order.id} for {customer_name}: Status changed from On the Way to Delivered"
            )
            updated_count += 1
        except Order.DoesNotExist:
            continue
    
    if updated_count > 0:
        messages.success(request, f"{updated_count} order(s) marked as delivered successfully!")
    else:
        messages.error(request, "No valid orders found to mark as delivered.")
    
    # Preserve tab state when redirecting
    tab = request.GET.get('tab', 'pending')
    return redirect(f"{reverse('dashboard:orders')}?tab={tab}")


@login_required
def delivered_orders(request):
    if getattr(request.user, "role", None) not in ["admin", "manager", "accountant"]:
        return HttpResponseForbidden("Not authorized.")
    
    # Get sort parameter
    sort_by = request.GET.get('sort', 'newest')
    
    # Determine ordering - use delivered_at for delivered orders
    if sort_by == 'oldest':
        order_by = 'delivered_at'
    else:  # newest (default)
        order_by = '-delivered_at'
    
    # Get only today's delivered orders
    from django.utils import timezone
    today = timezone.now().date()
    delivered_orders = Order.objects.filter(
        payment__status='success',
        status='Delivered',
        delivered_at__date=today
    ).select_related('user').prefetch_related('bags').order_by(order_by)
    
    context = {
        'delivered_orders': delivered_orders,
        'current_sort': sort_by
    }
    return render(request, "dashboard/delivered_orders.html", context)


@login_required
def order_details(request, order_id):
    if getattr(request.user, "role", None) not in ["admin", "manager", "accountant"]:
        return HttpResponseForbidden("Not authorized.")
    
    order = get_object_or_404(Order.objects.prefetch_related('bags__items__food_item__category'), id=order_id)
    context = {'order': order}
    return render(request, "dashboard/order_details.html", context)


# --- Staff Management ---

@admin_required
def dashboard_staff(request):
    """Display all staff members (admin, manager, accountant) for admin to manage."""
    
    # Get all staff users (excluding customers)
    staff_users = User.objects.filter(
        role__in=['admin', 'manager', 'accountant']
    ).order_by('role', 'first_name', 'last_name')
    
    # Group staff by role for better organization
    staff_by_role = {
        'admin': staff_users.filter(role='admin'),
        'manager': staff_users.filter(role='manager'),
        'accountant': staff_users.filter(role='accountant'),
    }
    
    context = {
        'staff_users': staff_users,
        'staff_by_role': staff_by_role,
    }
    return render(request, "dashboard/staff.html", context)


@admin_required
@csrf_exempt
def edit_staff(request, user_id):
    """Edit staff login details (phone number and password)."""
    
    staff_user = get_object_or_404(User, id=user_id, role__in=['admin', 'manager', 'accountant'])
    
    if request.method == "POST":
        phone_number = request.POST.get("phone_number")
        email = request.POST.get("email", "").strip()
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")
        
        # Validate phone number
        if not phone_number or len(phone_number.strip()) < 10:
            messages.error(request, "Valid phone number is required (minimum 10 characters).")
            context = {'staff_user': staff_user}
            return render(request, "dashboard/edit_staff.html", context)
        
        # Check if phone number is already taken by another user
        existing_user = User.objects.filter(phone_number=phone_number).exclude(id=user_id)
        if existing_user.exists():
            messages.error(request, f"Phone number '{phone_number}' is already taken by another user.")
            context = {'staff_user': staff_user}
            return render(request, "dashboard/edit_staff.html", context)
        
        # Check if email is already taken by another user (if email is provided)
        if email:
            existing_email_user = User.objects.filter(email=email).exclude(id=user_id)
            if existing_email_user.exists():
                messages.error(request, f"Email '{email}' is already taken by another user.")
                context = {'staff_user': staff_user}
                return render(request, "dashboard/edit_staff.html", context)
        
        # Update phone number
        old_phone = staff_user.phone_number
        staff_user.phone_number = phone_number.strip()
        
        # Update email
        staff_user.email = email if email else None
        
        # Update password if provided
        if new_password:
            if new_password != confirm_password:
                messages.error(request, "New password and confirmation password do not match.")
                context = {'staff_user': staff_user}
                return render(request, "dashboard/edit_staff.html", context)
            
            if len(new_password) < 6:
                messages.error(request, "Password must be at least 6 characters long.")
                context = {'staff_user': staff_user}
                return render(request, "dashboard/edit_staff.html", context)
            
            # Set the hashed password (for authentication)
            staff_user.set_password(new_password)
        
        try:
            staff_user.save()
            
            # Create success message
            updated_fields = []
            if old_phone != phone_number:
                updated_fields.append(f"Phone: {phone_number}")
            if email:
                updated_fields.append(f"Email: {email}")
            if new_password:
                updated_fields.append("Password updated")
            
            # Always show success message
            if updated_fields:
                fields_text = ", ".join(updated_fields)
                messages.success(request, f"Staff member '{staff_user.get_full_name() or staff_user.phone_number}' updated successfully! {fields_text}")
            else:
                messages.success(request, f"Staff member '{staff_user.get_full_name() or staff_user.phone_number}' details updated successfully!")
            
            return redirect("dashboard:staff")
            
        except Exception as e:
            messages.error(request, f"Error updating staff member: {str(e)}")
    
    context = {'staff_user': staff_user}
    return render(request, "dashboard/edit_staff.html", context)


@login_required
def system_settings(request):
    """System settings management page for admins."""
    # Check if user is admin
    if request.user.role != 'admin':
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect("dashboard:home")
    
    # Get current settings
    service_charge = SystemSettings.get_setting('service_charge', 100)
    vat_percentage = SystemSettings.get_setting('vat_percentage', 7.5)
    delivery_fee_base = SystemSettings.get_setting('delivery_fee_base', 500)
    plate_fee = SystemSettings.get_setting('plate_fee', 50)
    
    if request.method == 'POST':
        try:
            if 'update_service_charge' in request.POST:
                new_value = float(request.POST.get('service_charge', 0))
                if 0 <= new_value <= 5000:
                    SystemSettings.set_setting(
                        'service_charge', 
                        new_value, 
                        'Fixed service charge applied to all orders',
                        request.user
                    )
                    messages.success(request, f"Service charge updated to ₦{new_value}")
                else:
                    messages.error(request, "Service charge must be between 0 and 5,000")
            
            elif 'update_vat_percentage' in request.POST:
                new_value = float(request.POST.get('vat_percentage', 0))
                if 0 <= new_value <= 50:
                    SystemSettings.set_setting(
                        'vat_percentage', 
                        new_value, 
                        'VAT percentage applied to order subtotal',
                        request.user
                    )
                    messages.success(request, f"VAT percentage updated to {new_value}%")
                else:
                    messages.error(request, "VAT percentage must be between 0 and 50%")
            
            elif 'update_delivery_fee_base' in request.POST:
                new_value = float(request.POST.get('delivery_fee_base', 0))
                if 0 <= new_value <= 10000:
                    SystemSettings.set_setting(
                        'delivery_fee_base', 
                        new_value, 
                        'Base delivery fee (can be adjusted based on location)',
                        request.user
                    )
                    messages.success(request, f"Base delivery fee updated to ₦{new_value}")
                else:
                    messages.error(request, "Base delivery fee must be between 0 and 10,000")
            
            elif 'update_plate_fee' in request.POST:
                new_value = float(request.POST.get('plate_fee', 0))
                if 0 <= new_value <= 1000:
                    SystemSettings.set_setting(
                        'plate_fee', 
                        new_value, 
                        'Fee per plate for food items',
                        request.user
                    )
                    messages.success(request, f"Plate fee updated to ₦{new_value}")
                else:
                    messages.error(request, "Plate fee must be between 0 and 1,000")
            
            # Refresh settings after update
            service_charge = SystemSettings.get_setting('service_charge', 100)
            vat_percentage = SystemSettings.get_setting('vat_percentage', 7.5)
            plate_fee = SystemSettings.get_setting('plate_fee', 50)
            
        except ValueError:
            messages.error(request, "Invalid input. Please enter valid numbers.")
        except Exception as e:
            messages.error(request, f"Error updating setting: {str(e)}")
    
    context = {
        'service_charge': service_charge,
        'vat_percentage': vat_percentage,
        'plate_fee': plate_fee,
    }
    
    return render(request, "dashboard/system_settings.html", context)
