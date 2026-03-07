from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DoctorViewSet, SpecializationViewSet, DoctorAvailabilityViewSet, DoctorRatingViewSet
from .doctor_specialty_viewset import DoctorSpecializationViewSet

router = DefaultRouter()
router.register(r'specializations', SpecializationViewSet, basename='specialization')
router.register(r'specialty-prices', DoctorSpecializationViewSet, basename='doctor-specialization')
router.register(r'availability', DoctorAvailabilityViewSet, basename='doctor-availability')
router.register(r'ratings', DoctorRatingViewSet, basename='doctor-rating')
router.register(r'', DoctorViewSet, basename='doctor')

urlpatterns = [
    path('', include(router.urls)),
]
