from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AppointmentViewSet, MedicalRecordViewSet, DiagnosisViewSet, PrescriptionViewSet, LabTestViewSet
from .telegram_views import TelegramWebhookView

router = DefaultRouter()
router.register(r'appointments', AppointmentViewSet, basename='appointment')
router.register(r'records', MedicalRecordViewSet, basename='medical-record')
router.register(r'diagnoses', DiagnosisViewSet, basename='diagnosis')
router.register(r'prescriptions', PrescriptionViewSet, basename='prescription')
router.register(r'lab-tests', LabTestViewSet, basename='lab-test')

urlpatterns = [
    path('', include(router.urls)),
    path('telegram/webhook/<str:secret>/', TelegramWebhookView.as_view(), name='telegram-webhook'),
]
