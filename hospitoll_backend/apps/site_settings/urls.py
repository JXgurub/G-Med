from django.urls import path

from .views import (
    ContactLeadAdminListView,
    ContactLeadCreateView,
    ContactLeadMarkReadView,
    HomeContactSettingsView,
    SystemAlertAdminListView,
    SystemAlertClientCreateView,
    SystemAlertResolveView,
)

urlpatterns = [
    path('home-contact/', HomeContactSettingsView.as_view(), name='home-contact-settings'),
    path('contact-leads/', ContactLeadCreateView.as_view(), name='contact-leads-create'),
    path('contact-leads/admin/', ContactLeadAdminListView.as_view(), name='contact-leads-admin-list'),
    path('contact-leads/<uuid:pk>/read/', ContactLeadMarkReadView.as_view(), name='contact-leads-mark-read'),
    path('system-alerts/client/', SystemAlertClientCreateView.as_view(), name='system-alerts-client-create'),
    path('system-alerts/admin/', SystemAlertAdminListView.as_view(), name='system-alerts-admin-list'),
    path('system-alerts/<uuid:pk>/resolve/', SystemAlertResolveView.as_view(), name='system-alerts-resolve'),
]
