from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import PrinterDeviceViewSet, PrintJobViewSet, printer_heartbeat

router = DefaultRouter()
router.register(r'devices', PrinterDeviceViewSet, basename='printer-device')
router.register(r'jobs', PrintJobViewSet, basename='print-job')

urlpatterns = [
    path('heartbeat/', printer_heartbeat, name='printer-heartbeat'),
    path('register/', PrinterDeviceViewSet.as_view({'post': 'register'}), name='printer-register-legacy'),
    path('my-status/', PrinterDeviceViewSet.as_view({'get': 'my_status'}), name='printer-my-status-legacy'),
    path('jobs/test-print/', PrintJobViewSet.as_view({'post': 'test_print'}), name='printer-test-print-legacy'),
    *router.urls,
]
