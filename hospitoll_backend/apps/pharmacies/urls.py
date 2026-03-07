from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PharmacyViewSet, MedicineViewSet, PharmacyMarchandiseViewSet

router = DefaultRouter()
router.register(r'medicines', MedicineViewSet, basename='medicine')
router.register(r'inventory', PharmacyMarchandiseViewSet, basename='pharmacy-inventory')
router.register(r'', PharmacyViewSet, basename='pharmacy')

urlpatterns = [
    path('', include(router.urls)),
]
