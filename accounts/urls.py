from django.urls import path
from .views import RequestOTPView, VerifyOTPView, LoginView, ProfileView, SetupSessionView, LogoutView, RequestPasswordResetView, VerifyPasswordResetView

app_name = "accounts"

urlpatterns = [
    path('request-otp/', RequestOTPView.as_view(), name='request-otp'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('login/', LoginView.as_view(), name='login'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('setup-session/', SetupSessionView.as_view(), name='setup-session'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('request-password-reset/', RequestPasswordResetView.as_view(), name='request-password-reset'),
    path('verify-password-reset/', VerifyPasswordResetView.as_view(), name='verify-password-reset'),
]
