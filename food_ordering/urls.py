from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from store.admin import admin_site
from food_ordering.views import security_status, SecurityHealthCheck, custom_404, custom_500, custom_403

urlpatterns = [
    path("admin/", admin.site.urls),  # Use default Django admin
    path("custom-admin/", admin_site.urls),  # Use custom admin site
    path("api/accounts/", include("accounts.urls")),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("api/store/", include("store.urls")),
    path("dashboard/", include("dashboard.urls")),  # 👈 clean include
    path("", include("customer_site.urls")),  # Customer-facing website
    
    # Security endpoints
    path('security/status/', security_status, name='security_status'),
    path('security/health/', SecurityHealthCheck.as_view(), name='security_health'),
]

# Custom error handlers
handler404 = custom_404
handler500 = custom_500
handler403 = custom_403

# Serve media and static files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # Serve static files from STATICFILES_DIRS in development
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
