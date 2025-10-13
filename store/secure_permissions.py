"""
Secure Permissions for Food Ordering System
"""

from rest_framework import permissions
from django.contrib.auth import get_user_model
import logging

User = get_user_model()
logger = logging.getLogger('food_ordering.security')

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner of the object.
        return obj.owner == request.user

class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow admins to edit objects.
    """
    
    def has_permission(self, request, view):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to admin users.
        return request.user.is_authenticated and request.user.role == 'admin'

class IsAdminOrManager(permissions.BasePermission):
    """
    Custom permission to only allow admins and managers.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return request.user.role in ['admin', 'manager']

class IsAdminManagerOrAccountant(permissions.BasePermission):
    """
    Custom permission to only allow admins, managers, and accountants.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return request.user.role in ['admin', 'manager', 'accountant']

class IsCustomerOnly(permissions.BasePermission):
    """
    Custom permission to only allow customers.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return request.user.role == 'customer'

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to allow owners or admins.
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin can do anything
        if request.user.role == 'admin':
            return True
        
        # Owner can do anything with their objects
        if hasattr(obj, 'user') and obj.user == request.user:
            return True
        
        if hasattr(obj, 'owner') and obj.owner == request.user:
            return True
        
        return False

class SecureAPIPermission(permissions.BasePermission):
    """
    Comprehensive security permission for API endpoints.
    """
    
    def has_permission(self, request, view):
        # Log all API access attempts
        logger.info(f"API access attempt: {request.method} {request.path} by user {request.user.id if request.user.is_authenticated else 'anonymous'}")
        
        # Check if user is authenticated
        if not request.user.is_authenticated:
            # Allow only safe methods for anonymous users
            if request.method in permissions.SAFE_METHODS:
                return True
            return False
        
        # Check for suspicious activity
        if self._is_suspicious_request(request):
            logger.warning(f"Suspicious API request from user {request.user.id}: {request.method} {request.path}")
            return False
        
        # Check rate limiting (basic check)
        if self._is_rate_limited(request):
            logger.warning(f"Rate limited API request from user {request.user.id}: {request.method} {request.path}")
            return False
        
        return True
    
    def has_object_permission(self, request, view, obj):
        # Admin can do anything
        if request.user.role == 'admin':
            return True
        
        # Check ownership
        if hasattr(obj, 'user') and obj.user == request.user:
            return True
        
        if hasattr(obj, 'owner') and obj.owner == request.user:
            return True
        
        # For read-only access, allow if user has appropriate role
        if request.method in permissions.SAFE_METHODS:
            if hasattr(obj, 'user') and obj.user.role in ['admin', 'manager']:
                return True
        
        return False
    
    def _is_suspicious_request(self, request):
        """Check for suspicious request patterns"""
        # Check for SQL injection patterns in query parameters
        for param, value in request.GET.items():
            if self._contains_sql_injection(value):
                return True
        
        # Check for SQL injection patterns in POST data
        if request.method == 'POST':
            for param, value in request.POST.items():
                if self._contains_sql_injection(value):
                    return True
        
        # Check for path traversal
        if '../' in request.path or '..\\' in request.path:
            return True
        
        return False
    
    def _contains_sql_injection(self, value):
        """Check if value contains SQL injection patterns"""
        if not isinstance(value, str):
            return False
        
        sql_patterns = [
            'union', 'select', 'insert', 'delete', 'update', 'drop',
            'script', 'javascript:', 'vbscript:', 'onload=', 'onerror=',
            'or 1=1', 'and 1=1', '--', '/*', '*/'
        ]
        
        value_lower = value.lower()
        return any(pattern in value_lower for pattern in sql_patterns)
    
    def _is_rate_limited(self, request):
        """Basic rate limiting check"""
        # This is a simplified check - in production, use proper rate limiting
        from django.core.cache import cache
        
        cache_key = f"api_rate_limit_{request.user.id}_{request.path}"
        requests = cache.get(cache_key, 0)
        
        if requests > 100:  # 100 requests per minute
            return True
        
        cache.set(cache_key, requests + 1, 60)  # 1 minute
        return False

class PaymentPermission(permissions.BasePermission):
    """
    Special permission for payment-related operations.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Only customers can make payments
        if request.user.role != 'customer':
            return False
        
        # Log payment attempts
        logger.info(f"Payment attempt by user {request.user.id}: {request.method} {request.path}")
        
        return True
    
    def has_object_permission(self, request, view, obj):
        # Users can only access their own payments
        if hasattr(obj, 'user') and obj.user == request.user:
            return True
        
        # Admins can access all payments
        if request.user.role == 'admin':
            return True
        
        return False

class OrderPermission(permissions.BasePermission):
    """
    Special permission for order-related operations.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Log order operations
        logger.info(f"Order operation by user {request.user.id}: {request.method} {request.path}")
        
        return True
    
    def has_object_permission(self, request, view, obj):
        # Users can only access their own orders
        if hasattr(obj, 'user') and obj.user == request.user:
            return True
        
        # Staff can access all orders
        if request.user.role in ['admin', 'manager', 'accountant']:
            return True
        
        return False
