from django.urls import path

from .views import (
    ContactLeadAdminListView,
    ContactLeadCreateView,
    ContactLeadMarkReadView,
    AdminBroadcastView,
    BroadcastNotificationInboxView,
    WebPushConfigView,
    WebPushSubscriptionView,
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
    path('broadcast/admin/', AdminBroadcastView.as_view(), name='admin-broadcast'),
    path('broadcast/inbox/', BroadcastNotificationInboxView.as_view(), name='broadcast-inbox'),
    path('broadcast/inbox/<uuid:pk>/read/', BroadcastNotificationInboxView.as_view(), name='broadcast-inbox-read'),
    path('push/config/', WebPushConfigView.as_view(), name='web-push-config'),
    path('push/subscriptions/', WebPushSubscriptionView.as_view(), name='web-push-subscriptions'),
    path('system-alerts/<uuid:pk>/resolve/', SystemAlertResolveView.as_view(), name='system-alerts-resolve'),
]
