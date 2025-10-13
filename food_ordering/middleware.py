"""
Custom Security Middleware for Food Ordering System
Comprehensive security hardening middleware
"""

import logging
import time
from django.http import HttpResponse, JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
import hashlib
import ipaddress

logger = logging.getLogger('food_ordering.security')

class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Add comprehensive security headers to all responses
    """
    
    def process_response(self, request, response):
        # Content Security Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdnjs.cloudflare.com https://code.jquery.com; "
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https://api.paystack.co https://api.twilio.com; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "object-src 'none'; "
            "upgrade-insecure-requests;"
        )
        response['Content-Security-Policy'] = csp
        
        # Additional Security Headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = (
            'geolocation=(), microphone=(), camera=(), '
            'payment=(), usb=(), magnetometer=(), gyroscope=(), '
            'accelerometer=(), ambient-light-sensor=()'
        )
        response['Cross-Origin-Embedder-Policy'] = 'require-corp'
        response['Cross-Origin-Opener-Policy'] = 'same-origin'
        response['Cross-Origin-Resource-Policy'] = 'same-origin'
        
        # Remove server information
        if 'Server' in response:
            del response['Server']
        
        return response

class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Log security-relevant requests and detect suspicious activity
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        # Start timing
        request._start_time = time.time()
        
        # Log suspicious patterns
        self._check_suspicious_patterns(request)
        
        # Rate limiting for sensitive endpoints
        self._check_rate_limits(request)
        
        return None
    
    def process_response(self, request, response):
        # Calculate request time
        if hasattr(request, '_start_time'):
            duration = time.time() - request._start_time
            
            # Log slow requests
            if duration > 5.0:  # 5 seconds
                logger.warning(
                    f"Slow request detected: {request.method} {request.path} "
                    f"took {duration:.2f}s from {self._get_client_ip(request)}"
                )
        
        # Log security-relevant responses
        if response.status_code in [400, 401, 403, 404, 429, 500]:
            logger.warning(
                f"Security response: {response.status_code} for "
                f"{request.method} {request.path} from {self._get_client_ip(request)}"
            )
        
        return response
    
    def _get_client_ip(self, request):
        """Get real client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _check_suspicious_patterns(self, request):
        """Check for suspicious request patterns"""
        ip = self._get_client_ip(request)
        path = request.path.lower()
        
        # SQL Injection patterns
        sql_patterns = [
            'union', 'select', 'insert', 'delete', 'update', 'drop',
            'script', 'javascript:', 'vbscript:', 'onload=', 'onerror='
        ]
        
        # Check query parameters
        for param, value in request.GET.items():
            if any(pattern in str(value).lower() for pattern in sql_patterns):
                logger.warning(
                    f"Potential SQL injection attempt from {ip}: "
                    f"{param}={value} in {request.path}"
                )
                self._block_ip_temporarily(ip, "SQL injection attempt")
        
        # Check POST data
        if request.method == 'POST':
            for param, value in request.POST.items():
                if any(pattern in str(value).lower() for pattern in sql_patterns):
                    logger.warning(
                        f"Potential SQL injection attempt from {ip}: "
                        f"{param}={value} in {request.path}"
                    )
                    self._block_ip_temporarily(ip, "SQL injection attempt")
        
        # Check for path traversal
        if '../' in path or '..\\' in path:
            logger.warning(f"Path traversal attempt from {ip}: {request.path}")
            self._block_ip_temporarily(ip, "Path traversal attempt")
        
        # Check for admin brute force
        if '/admin/' in path or '/dashboard/login/' in path:
            self._check_admin_brute_force(ip)
    
    def _check_rate_limits(self, request):
        """Check rate limits for sensitive endpoints"""
        ip = self._get_client_ip(request)
        path = request.path
        
        # Rate limiting for login endpoints
        if '/login/' in path or '/api/auth/' in path:
            cache_key = f"rate_limit_login_{ip}"
            attempts = cache.get(cache_key, 0)
            if attempts >= 5:  # 5 attempts per minute
                logger.warning(f"Rate limit exceeded for login from {ip}")
                self._block_ip_temporarily(ip, "Rate limit exceeded")
                return HttpResponse("Rate limit exceeded", status=429)
            cache.set(cache_key, attempts + 1, 60)  # 1 minute
    
    def _check_admin_brute_force(self, ip):
        """Check for admin brute force attempts"""
        cache_key = f"admin_attempts_{ip}"
        attempts = cache.get(cache_key, 0)
        if attempts >= 10:  # 10 attempts per hour
            logger.warning(f"Admin brute force detected from {ip}")
            self._block_ip_temporarily(ip, "Admin brute force", 3600)  # 1 hour block
        cache.set(cache_key, attempts + 1, 3600)  # 1 hour
    
    def _block_ip_temporarily(self, ip, reason, duration=300):
        """Temporarily block an IP address"""
        cache_key = f"blocked_ip_{ip}"
        cache.set(cache_key, {
            'reason': reason,
            'blocked_at': timezone.now().isoformat()
        }, duration)
        logger.warning(f"IP {ip} blocked for {duration}s: {reason}")

class IPWhitelistMiddleware(MiddlewareMixin):
    """
    IP whitelist middleware for admin access
    """
    
    def process_request(self, request):
        # Only apply to admin and dashboard
        if not (request.path.startswith('/admin/') or request.path.startswith('/dashboard/')):
            return None
        
        ip = self._get_client_ip(request)
        
        # Check if IP is blocked
        if cache.get(f"blocked_ip_{ip}"):
            logger.warning(f"Blocked IP {ip} attempted to access {request.path}")
            return HttpResponse("Access denied", status=403)
        
        # Allow localhost and internal IPs
        try:
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj.is_loopback or ip_obj.is_private:
                return None
        except ValueError:
            pass
        
        # For production, you might want to implement IP whitelisting here
        # For now, we'll allow all IPs but log access
        logger.info(f"Admin access from {ip} to {request.path}")
        return None
    
    def _get_client_ip(self, request):
        """Get real client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
