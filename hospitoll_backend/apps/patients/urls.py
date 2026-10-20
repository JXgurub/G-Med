from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    HealthAlertViewSet,
    PatientHealthReadingViewSet,
    PatientLiverJournalEntryViewSet,
    PatientMedicationReminderAcknowledgeView,
    PatientMedicationReminderViewSet,
    PatientTreatmentPlanViewSet,
    PatientTreatmentStepViewSet,
    PatientViewSet,
)

router = DefaultRouter()
router.register(
    r'medication-reminders',
    PatientMedicationReminderViewSet,
    basename='patient-medication-reminder',
)
router.register(
    r'treatment-plans',
    PatientTreatmentPlanViewSet,
    basename='patient-treatment-plan',
)
router.register(
    r'treatment-steps',
    PatientTreatmentStepViewSet,
    basename='patient-treatment-step',
)
router.register(
    r'health-readings',
    PatientHealthReadingViewSet,
    basename='patient-health-reading',
)
router.register(
    r'liver-journal',
    PatientLiverJournalEntryViewSet,
    basename='patient-liver-journal',
)
router.register(
    r'health-alerts',
    HealthAlertViewSet,
    basename='patient-health-alert',
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
