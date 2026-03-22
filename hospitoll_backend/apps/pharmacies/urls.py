from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PharmacyViewSet, MedicineViewSet, PharmacyMarchandiseViewSet, medicine_search

router = DefaultRouter()
router.register(r'medicines', MedicineViewSet, basename='medicine')
router.register(r'inventory', PharmacyMarchandiseViewSet, basename='pharmacy-inventory')
router.register(r'', PharmacyViewSet, basename='pharmacy')

urlpatterns = [
    path('medicines/search/', medicine_search, name='medicine-search'),
    path('', include(router.urls)),
]

# Note: medicine_search path must come before router.urls so it's matched first
