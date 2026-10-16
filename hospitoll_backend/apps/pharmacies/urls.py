from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    PharmacyViewSet,
    MedicineViewSet,
    PharmacyMarchandiseViewSet,
    medicine_search,
    pharmacy_pos_snapshot,
    pharmacy_pos_printer,
    pharmacy_printer_service_register,
    pharmacy_pos_print_sale,
    pharmacy_pos_devices,
    pharmacy_pos_device_detail,
    pharmacy_pos_activate_device,
    pharmacy_pos_sync_sale,
)

router = DefaultRouter()
router.register(r'medicines', MedicineViewSet, basename='medicine')
router.register(r'inventory', PharmacyMarchandiseViewSet, basename='pharmacy-inventory')
router.register(r'', PharmacyViewSet, basename='pharmacy')

urlpatterns = [
    path('pos/snapshot/', pharmacy_pos_snapshot, name='pharmacy-pos-snapshot'),
    path('pos/printer/', pharmacy_pos_printer, name='pharmacy-pos-printer'),
    path('pos/printer/register-service/', pharmacy_printer_service_register, name='pharmacy-printer-service-register'),
    path('pos/printer/print-sale/', pharmacy_pos_print_sale, name='pharmacy-pos-print-sale'),
    path('pos/devices/', pharmacy_pos_devices, name='pharmacy-pos-devices'),
    path('pos/devices/activate/', pharmacy_pos_activate_device, name='pharmacy-pos-activate-device'),
    path('pos/devices/<uuid:device_id>/', pharmacy_pos_device_detail, name='pharmacy-pos-device-detail'),
    path('pos/sales/sync/', pharmacy_pos_sync_sale, name='pharmacy-pos-sync-sale'),
    path('medicines/search/', medicine_search, name='medicine-search'),
    path('', include(router.urls)),
]

# Note: medicine_search path must come before router.urls so it's matched first
