from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

ADMIN_PATH = settings.ADMIN_URL
if not ADMIN_PATH.endswith('/'):
    ADMIN_PATH = f'{ADMIN_PATH}/'

urlpatterns = [
    path(ADMIN_PATH, admin.site.urls),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # API endpoints
    path('api/v1/users/', include('apps.users.urls')),
    path('api/v1/clinics/', include('apps.clinics.urls')),
    path('api/v1/doctors/', include('apps.doctors.urls')),
    path('api/v1/patients/', include('apps.patients.urls')),
    path('api/v1/pharmacies/', include('apps.pharmacies.urls')),
    path('api/v1/medical/', include('apps.medical.urls')),
    path('api/v1/subscriptions/', include('apps.subscriptions.urls')),
    path('api/v1/payments/', include('apps.payments.urls')),
    path('api/v1/analytics/', include('apps.analytics.urls')),
    path('api/v1/site-settings/', include('apps.site_settings.urls')),
    path('api/v1/', include('apps.search.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
