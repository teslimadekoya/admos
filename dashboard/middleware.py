from django.shortcuts import redirect
from django.urls import reverse
from django.http import HttpResponseForbidden


class CashierAccessMiddleware:
    """
    Middleware to restrict cashiers from accessing admin dashboard URLs.
    Cashiers should only access POS dashboard.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check if user is authenticated and is a cashier
        if (request.user.is_authenticated and 
            hasattr(request.user, 'role') and 
            request.user.role == 'cashier'):
            
            # Check if trying to access admin dashboard URLs
            if request.path.startswith('/dashboard/'):
                # Redirect cashiers to POS dashboard
                return redirect('http://localhost:3000/login')  # POS frontend URL
        
        response = self.get_response(request)
        return response
