from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    PatientMedicationReminderAcknowledgeView,
    PatientMedicationReminderViewSet,
    PatientViewSet,
)

router = DefaultRouter()
router.register(
    r'medication-reminders',
    PatientMedicationReminderViewSet,
    basename='patient-medication-reminder',
)
router.register(r'', PatientViewSet, basename='patient')

urlpatterns = [
    path(
        'medication-reminders/acknowledge/',
        PatientMedicationReminderAcknowledgeView.as_view(),
        name='patient-medication-reminder-acknowledge',
    ),
    path('', include(router.urls)),
]
