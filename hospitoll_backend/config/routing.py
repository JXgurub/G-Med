"""
WebSocket URL routing configuration for Django Channels.
"""

from django.urls import re_path
from core.consumers import (
    NotificationConsumer,
    DoctorStatusConsumer,
    AppointmentStatusConsumer,
)

websocket_urlpatterns = [
    # General notifications
    re_path(r'ws/notifications/(?P<user_id>[0-9a-f\-]{32,36})/$', NotificationConsumer.as_asgi()),
    
    # Doctor real-time updates (check-in/check-out, status changes)
    re_path(r'ws/doctor/status/(?P<doctor_id>[0-9a-f\-]{32,36})/$', DoctorStatusConsumer.as_asgi()),
    
    # Appointment status updates
    re_path(r'ws/appointment/(?P<appointment_id>[0-9a-f\-]{32,36})/$', AppointmentStatusConsumer.as_asgi()),
]
