from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ClinicViewSet, ClinicDepartmentViewSet, ClinicServiceViewSet, ClinicStaffMessageInboxViewSet, ReceptionStaffViewSet

router = DefaultRouter()
router.register(r'departments', ClinicDepartmentViewSet, basename='clinic-department')
router.register(r'services', ClinicServiceViewSet, basename='clinic-service')  
router.register(r'staff-messages', ClinicStaffMessageInboxViewSet, basename='clinic-staff-messages')
router.register(r'reception-staff', ReceptionStaffViewSet, basename='reception-staff')
router.register(r'', ClinicViewSet, basename='clinic')

urlpatterns = [
    path('', include(router.urls)),
]
