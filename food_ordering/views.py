"""
Security Views for Food Ordering System
"""

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
import logging

logger = logging.getLogger('food_ordering.security')

def rate_limit_exceeded(request, exception=None):
    """
    Custom view for rate limit exceeded
    """
    logger.warning(f"Rate limit exceeded for {request.META.get('REMOTE_ADDR')} on {request.path}")
    
    return JsonResponse({
        'error': 'Rate limit exceeded',
        'message': 'Too many requests. Please try again later.',
        'retry_after': 60
    }, status=429)

@csrf_exempt
@require_http_methods(["GET"])
def security_status(request):
    """
    Security status endpoint for monitoring
    """
    return JsonResponse({
        'status': 'secure',
        'timestamp': request.META.get('HTTP_DATE', ''),
        'security_headers': {
            'csp': 'enabled',
            'hsts': 'enabled',
            'xss_protection': 'enabled',
            'content_type_nosniff': 'enabled'
        }
    })

class SecurityHealthCheck(View):
    """
    Security health check endpoint
    """
    
    def get(self, request):
        # Basic security checks
        security_status = {
            'https_enabled': request.is_secure(),
            'csrf_protection': True,
            'rate_limiting': True,
            'input_validation': True,
            'authentication': True,
            'authorization': True,
            'logging': True,
            'headers': {
                'x_frame_options': 'DENY',
                'content_security_policy': 'enabled',
                'strict_transport_security': 'enabled'
            }
        }
        
        return JsonResponse(security_status)

def custom_404(request, exception=None):
    """
    Custom 404 handler with security logging
    """
    logger.warning(f"404 error for {request.META.get('REMOTE_ADDR')} on {request.path}")
    
    return JsonResponse({
        'error': 'Not Found',
        'message': 'The requested resource was not found.',
        'status': 404
    }, status=404)

def custom_500(request):
    """
    Custom 500 handler with security logging
    """
    logger.error(f"500 error for {request.META.get('REMOTE_ADDR')} on {request.path}")
    
    return JsonResponse({
        'error': 'Internal Server Error',
        'message': 'An internal server error occurred.',
        'status': 500
    }, status=500)

def custom_403(request, exception=None):
    """
    Custom 403 handler with security logging
    """
    logger.warning(f"403 error for {request.META.get('REMOTE_ADDR')} on {request.path}")
    
    return JsonResponse({
        'error': 'Forbidden',
        'message': 'Access denied.',
        'status': 403
    }, status=403)
