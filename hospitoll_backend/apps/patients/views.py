import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import Patient, PatientMedicationReminder
from .reminder_serializers import PatientMedicationReminderSerializer
from .serializers import PatientSerializer, PatientCreateSerializer
from apps.site_settings.models import BroadcastNotification


class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.select_related('user').all()
    filterset_fields = ['gender', 'city', 'is_active']

    def get_queryset(self):
        qs = super().get_queryset()

        query = str(self.request.query_params.get('q') or '').strip()
        if query:
            qs = qs.filter(
                Q(user__first_name__icontains=query)
                | Q(user__last_name__icontains=query)
                | Q(phone_number__icontains=query)
                | Q(user__phone_number__icontains=query)
            )

        return qs

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        if self.action == 'my':
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'create':
            return PatientCreateSerializer
        return PatientSerializer

    @action(detail=False, methods=['get'])
    def my(self, request):
        if not request.user.is_authenticated or not request.user.is_patient:
            return Response({'detail': 'Bemor topilmadi.'}, status=404)
        patient = Patient.objects.filter(user=request.user).first()
        if not patient:
            return Response({'detail': 'Bemor topilmadi.'}, status=404)
        serializer = PatientSerializer(patient)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def set_password(self, request, pk=None):
        if not request.user.is_authenticated:
            return Response({'detail': 'Ruxsat yo‘q.'}, status=status.HTTP_401_UNAUTHORIZED)
        if not (request.user.is_doctor or request.user.is_administrator):
            return Response({'detail': 'Ruxsat yo‘q.'}, status=status.HTTP_403_FORBIDDEN)

        patient = self.get_object()
        password = request.data.get('password')
        if not password or len(password) < 6:
            return Response({'detail': 'Parol kamida 6 ta belgidan iborat bo‘lishi kerak.'}, status=status.HTTP_400_BAD_REQUEST)

        if not patient.user:
            return Response({'detail': 'Bemor foydalanuvchisi topilmadi.'}, status=status.HTTP_400_BAD_REQUEST)

        patient.user.set_password(password)
        patient.user.save(update_fields=['password'])
        return Response({'detail': 'Parol muvaffaqiyatli o‘rnatildi.'}, status=status.HTTP_200_OK)


class PatientMedicationReminderViewSet(viewsets.ModelViewSet):
    serializer_class = PatientMedicationReminderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if not getattr(self.request.user, 'is_patient', False):
            return PatientMedicationReminder.objects.none()
        return PatientMedicationReminder.objects.filter(
            patient__user=self.request.user,
        )

    def perform_create(self, serializer):
        if not getattr(self.request.user, 'is_patient', False):
            raise PermissionDenied('Faqat bemorlar dori eslatmasi qo‘sha oladi.')
        patient = get_object_or_404(Patient, user=self.request.user)
        serializer.save(patient=patient)


class PatientMedicationReminderAcknowledgeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            acknowledgement_token = uuid.UUID(
                str(request.data.get('acknowledgement_token', ''))
            )
        except (ValueError, TypeError, AttributeError):
            return Response(
                {'detail': 'Eslatma tasdiqlash tokeni yaroqsiz.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            reminder = (
                PatientMedicationReminder.objects.select_for_update()
                .select_related('patient__user')
                .filter(
                    acknowledgement_token=acknowledgement_token,
                    is_active=True,
                    pending_dose_at__isnull=False,
                )
                .first()
            )
            if reminder is None:
                return Response({'acknowledged': False}, status=status.HTTP_200_OK)

            now = timezone.now()
            reminder.pending_dose_at = None
            reminder.next_nudge_at = None
            reminder.acknowledgement_token = None
            reminder.save(update_fields=[
                'pending_dose_at',
                'next_nudge_at',
                'acknowledgement_token',
                'updated_at',
            ])
            BroadcastNotification.objects.filter(
                user=reminder.patient.user,
                data__acknowledgement_token=str(acknowledgement_token),
                read_at__isnull=True,
            ).update(read_at=now)

        return Response({'acknowledged': True}, status=status.HTTP_200_OK)
