from store.models import Order
from django.db.models import Q

def active_orders_count(request):
    """Add active orders count to all template contexts using all successful payments."""
    if hasattr(request, 'user') and request.user.is_authenticated and getattr(request.user, 'role', None) in ['admin', 'manager', 'accountant']:
        # Use all successful payments for consistency
        return {
            'active_orders_count': Order.objects.filter(
                payment__status='success',
                status__in=['Pending', 'On the Way']  # Only count active orders
            ).count()
        }
    return {'active_orders_count': 0}
