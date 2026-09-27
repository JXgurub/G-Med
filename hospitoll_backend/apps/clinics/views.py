from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from django.utils import timezone
from django.core import signing

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

from core.permissions.custom_permissions import IsAdministrator, IsClinicOwner
from apps.users.throttles import LoginScopedRateThrottle
from .models import ReceptionStaff, ReceptionStaffWorkRecord, Clinic, ClinicDepartment, ClinicService, ClinicStaffMessage, ClinicStaffMessageRecipient
from .serializers import (
    ClinicSerializer,
    ClinicCreateSerializer,
    ClinicUpdateSerializer,
    ClinicBannerUpdateSerializer,
    ClinicOwnerUpdateSerializer,
    ClinicStaffMessageCreateSerializer,
    ClinicStaffMessageInboxItemSerializer,
    ClinicDepartmentSerializer,
    ClinicServiceSerializer,
    ReceptionStaffSerializer,
)


class ClinicViewSet(viewsets.ModelViewSet):
    queryset = Clinic.objects.select_related('owner').all()
    serializer_class = ClinicSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        if self.action in ['my', 'my_banner', 'my_update', 'my_staff_messages']:
            return [permissions.IsAuthenticated()]
        # For create, update, delete - require admin
        return [permissions.IsAuthenticated(), IsAdministrator()]

    def get_throttles(self):
        if self.action in {'list', 'retrieve'}:
            return []
        return super().get_throttles()

    def get_serializer_class(self):
        if self.action == 'create':
            return ClinicCreateSerializer
        if self.action in ['update', 'partial_update']:
            return ClinicUpdateSerializer
        return ClinicSerializer

    @action(detail=False, methods=['get'])
    def my(self, request):
        if not request.user.is_authenticated or not request.user.is_clinic:
            return Response({'detail': 'Klinika topilmadi.'}, status=404)
        clinic = Clinic.objects.filter(owner=request.user).first()
        if not clinic:
            return Response({'detail': 'Klinika topilmadi.'}, status=404)
        serializer = self.get_serializer(clinic)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=['patch'],
        url_path='my/banner',
        parser_classes=[MultiPartParser, FormParser],
        permission_classes=[permissions.IsAuthenticated],
    )
    def my_banner(self, request):
        """Clinic owner can upload/update their clinic banner image (фон расм)."""
        if not request.user.is_authenticated or not request.user.is_clinic:
            return Response({'detail': 'Faqat klinika egasi rasm yuklay oladi.'}, status=403)

        clinic = Clinic.objects.filter(owner=request.user).first()
        if not clinic:
            return Response({'detail': 'Klinika topilmadi.'}, status=404)

        serializer = ClinicBannerUpdateSerializer(clinic, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(ClinicSerializer(clinic, context={'request': request}).data)

    @action(detail=False, methods=['patch'], url_path='my/update')
    def my_update(self, request):
        """Clinic owner can update their own clinic profile and password."""
        if not request.user.is_authenticated or not request.user.is_clinic:
            return Response({'detail': 'Faqat klinika egasi o\'zgartira oladi.'}, status=403)

        clinic = Clinic.objects.filter(owner=request.user).first()
        if not clinic:
            return Response({'detail': 'Klinika topilmadi.'}, status=404)

        serializer = ClinicOwnerUpdateSerializer(clinic, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        clinic.refresh_from_db()

        return Response(ClinicSerializer(clinic, context={'request': request}).data)

    @action(detail=False, methods=['post'], url_path='my/staff-messages')
    def my_staff_messages(self, request):
        """Clinic owner broadcasts a message to all doctors in their clinic."""
        if not request.user.is_authenticated or not request.user.is_clinic:
            return Response({'detail': 'Faqat klinika egasi yubora oladi.'}, status=403)

        clinic = Clinic.objects.filter(owner=request.user).first()
        if not clinic:
            return Response({'detail': 'Klinika topilmadi.'}, status=404)

        serializer = ClinicStaffMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        body = serializer.validated_data['body']

        from apps.doctors.models import Doctor

        doctors = Doctor.objects.select_related('user').filter(clinic=clinic, is_active=True, user__is_active=True)
        recipients = [d.user for d in doctors if d.user]

        if not recipients:
            return Response({'detail': 'Klinikada faol xodimlar topilmadi.'}, status=status.HTTP_400_BAD_REQUEST)

        message = ClinicStaffMessage.objects.create(clinic=clinic, sender=request.user, body=body)
        recipient_rows = [
            ClinicStaffMessageRecipient(message=message, recipient=u)
            for u in recipients
        ]
        ClinicStaffMessageRecipient.objects.bulk_create(recipient_rows, ignore_conflicts=True)

        # Real-time push (best-effort)
        channel_layer = get_channel_layer()
        payload = {
            'type': 'clinic_staff_message',
            'message_id': str(message.id),
            'clinic_id': str(clinic.id),
            'clinic_name': clinic.name,
            'sender_id': str(request.user.id),
            'sender_name': f"{request.user.first_name or ''} {request.user.last_name or ''}".strip() or request.user.email,
            'body': body,
            'created_at': message.created_at.isoformat(),
        }
        for u in recipients:
            try:
                async_to_sync(channel_layer.group_send)(
                    f'notifications_{u.id}',
                    {'type': 'notification_message', 'data': payload},
                )
            except Exception:
                # Ignore push errors; inbox polling still works.
                pass

        return Response({'detail': 'Yuborildi', 'sent': len(recipients)})


class ClinicStaffMessageInboxViewSet(viewsets.GenericViewSet):
    """Doctor inbox for clinic staff messages."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ClinicStaffMessageInboxItemSerializer

    def get_queryset(self):
        user = self.request.user
        return ClinicStaffMessageRecipient.objects.select_related('message', 'message__clinic', 'message__sender').filter(recipient=user)

    def list(self, request):
        if not request.user.is_authenticated or not request.user.is_doctor:
            return Response({'detail': 'Faqat doktorlar ko‘ra oladi.'}, status=403)

        qs = self.get_queryset()
        unread = request.query_params.get('unread')
        if unread in ('1', 'true', 'True', 'yes'):
            qs = qs.filter(is_read=False)

        limit = request.query_params.get('limit')
        try:
            limit_int = int(limit) if limit else 30
        except (TypeError, ValueError):
            limit_int = 30
        limit_int = max(1, min(limit_int, 200))

        items = qs.order_by('-message__created_at')[:limit_int]
        return Response(self.get_serializer(items, many=True).data)

    @action(detail=True, methods=['patch'], url_path='read')
    def mark_read(self, request, pk=None):
        if not request.user.is_authenticated or not request.user.is_doctor:
            return Response({'detail': 'Faqat doktorlar.'}, status=403)

        obj = self.get_queryset().filter(id=pk).first()
        if not obj:
            return Response({'detail': 'Topilmadi.'}, status=404)

        if not obj.is_read:
            obj.is_read = True
            obj.read_at = timezone.now()
            obj.save(update_fields=['is_read', 'read_at'])

        return Response({'detail': 'OK'})


class ClinicDepartmentViewSet(viewsets.ModelViewSet):
    queryset = ClinicDepartment.objects.select_related('clinic', 'head_doctor').all()
    serializer_class = ClinicDepartmentSerializer
    filterset_fields = ['clinic', 'is_active']

    def get_permissions(self):
        # Allow anyone to view departments (list, retrieve)
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        # Require authentication for create, update, delete
        return [permissions.IsAuthenticated()]

    def get_throttles(self):
        if self.action in {'list', 'retrieve'}:
            return []
        return super().get_throttles()


class ReceptionStaffViewSet(viewsets.ModelViewSet):
    serializer_class = ReceptionStaffSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ReceptionStaff.objects.filter(clinic__owner=self.request.user).order_by('first_name', 'last_name')

    def check_object_permissions(self, request, obj):
        if not request.user.is_authenticated or obj.clinic.owner_id != request.user.id:
            self.permission_denied(request, message='Siz faqat o\'z klinikangiz xodimini boshqara olasiz.')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['reception_stats_date'] = self.request.query_params.get('date')
        return context

    def perform_create(self, serializer):
        clinic = Clinic.objects.filter(owner=self.request.user).first()
        if not clinic or not clinic.reception_room_enabled:
            raise PermissionDenied('Qabul xonasi funksiyasi yoqilmagan.')
        serializer.save(clinic=clinic)

    def _resolve_staff_from_session(self, request):
        raw_token = str(request.headers.get('X-Reception-Session') or '').strip()
        try:
            payload = signing.loads(raw_token, salt='reception-staff-session', max_age=60 * 60 * 12)
            return ReceptionStaff.objects.get(id=payload['staff_id'], clinic_id=payload['clinic_id'], is_active=True)
        except Exception:
            return None

    @action(
        detail=False,
        methods=['post'],
        url_path='login',
        permission_classes=[permissions.AllowAny],
        throttle_classes=[LoginScopedRateThrottle],
    )
    def login(self, request):
        email = str(request.data.get('email') or '').strip().lower()
        password = str(request.data.get('password') or '')
        staff = ReceptionStaff.objects.select_related('clinic').filter(email__iexact=email, is_active=True).first()
        if not staff or not staff.password_hash:
            return Response({'detail': 'Email yoki parol noto\'g\'ri.'}, status=status.HTTP_401_UNAUTHORIZED)
        from django.contrib.auth.hashers import check_password
        if not check_password(password, staff.password_hash):
            return Response({'detail': 'Email yoki parol noto\'g\'ri.'}, status=status.HTTP_401_UNAUTHORIZED)
        token = signing.dumps({'staff_id': str(staff.id), 'clinic_id': str(staff.clinic_id)}, salt='reception-staff-session')
        return Response({'token': token, 'staff': ReceptionStaffSerializer(staff).data})

    @action(detail=False, methods=['get'], url_path='me', permission_classes=[permissions.AllowAny], throttle_classes=[])
    def me(self, request):
        staff = self._resolve_staff_from_session(request)
        if not staff:
            return Response({'detail': 'Reception sessiyasi yaroqsiz yoki tugagan.'}, status=status.HTTP_401_UNAUTHORIZED)
        serializer = ReceptionStaffSerializer(staff, context={'reception_stats_date': str(timezone.localdate())})
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='check-in', permission_classes=[permissions.AllowAny], throttle_classes=[])
    def check_in(self, request):
        staff = self._resolve_staff_from_session(request)
        if not staff:
            return Response({'detail': 'Reception sessiyasi yaroqsiz yoki tugagan.'}, status=status.HTTP_401_UNAUTHORIZED)

        now_local = timezone.localtime()
        today = timezone.localdate()
        record, _ = ReceptionStaffWorkRecord.objects.get_or_create(staff=staff, date=today)

        if record.checked_in_at and not record.checked_out_at:
            return Response({'detail': 'Siz bugun allaqachon ishga kelgansiz.'}, status=status.HTTP_400_BAD_REQUEST)

        record.checked_in_at = now_local.time().replace(second=0, microsecond=0)
        record.checked_out_at = None
        record.save(update_fields=['checked_in_at', 'checked_out_at', 'updated_at'])

        serializer = ReceptionStaffSerializer(staff, context={'reception_stats_date': str(today)})
        return Response({'detail': 'Ishga kelish vaqti saqlandi.', 'staff': serializer.data})

    @action(detail=False, methods=['post'], url_path='check-out', permission_classes=[permissions.AllowAny], throttle_classes=[])
    def check_out(self, request):
        staff = self._resolve_staff_from_session(request)
        if not staff:
            return Response({'detail': 'Reception sessiyasi yaroqsiz yoki tugagan.'}, status=status.HTTP_401_UNAUTHORIZED)

        now_local = timezone.localtime()
        today = timezone.localdate()
        record = ReceptionStaffWorkRecord.objects.filter(staff=staff, date=today).first()
        if not record or not record.checked_in_at:
            return Response({'detail': 'Avval Ishga keldim tugmasini bosing.'}, status=status.HTTP_400_BAD_REQUEST)
        if record.checked_out_at:
            return Response({'detail': 'Siz bugun allaqachon ishdan ketgansiz.'}, status=status.HTTP_400_BAD_REQUEST)

        record.checked_out_at = now_local.time().replace(second=0, microsecond=0)
        record.save(update_fields=['checked_out_at', 'updated_at'])

        serializer = ReceptionStaffSerializer(staff, context={'reception_stats_date': str(today)})
        return Response({'detail': 'Ishdan ketish vaqti saqlandi.', 'staff': serializer.data})

    @action(detail=False, methods=['get'], url_path='doctors', permission_classes=[permissions.AllowAny], throttle_classes=[])
    def doctors(self, request):
        staff = self._resolve_staff_from_session(request)
        if not staff:
            return Response({'detail': 'Reception sessiyasi yaroqsiz yoki tugagan.'}, status=status.HTTP_401_UNAUTHORIZED)

        from apps.doctors.models import Doctor
        from apps.doctors.serializers import DoctorSerializer
        doctors = Doctor.objects.filter(clinic_id=staff.clinic_id, is_active=True).select_related('user', 'clinic').prefetch_related('specialty_prices__specialization')
        serialized_doctors = DoctorSerializer(doctors, many=True).data
        for doctor_data in serialized_doctors:
            doctor_data['specialty_prices'] = [
                item for item in doctor_data.get('specialty_prices', [])
                if item.get('doctor_custom') is True
            ]
        return Response(serialized_doctors)

    @action(detail=False, methods=['get'], url_path='patients', permission_classes=[permissions.AllowAny], throttle_classes=[])
    def patients(self, request):
        staff = self._resolve_staff_from_session(request)
        if not staff:
            return Response({'detail': 'Reception sessiyasi yaroqsiz yoki tugagan.'}, status=status.HTTP_401_UNAUTHORIZED)

        from apps.patients.models import Patient
        from django.db.models import Q

        query = str(request.query_params.get('q') or '').strip()
        patients = Patient.objects.filter(
            clinics=staff.clinic,
        ).select_related('user').order_by('user__first_name', 'user__last_name')
        if query:
            parts = query.split()
            name_query = Q(user__first_name__icontains=query) | Q(user__last_name__icontains=query)
            if len(parts) > 1:
                name_query |= Q(
                    user__first_name__icontains=parts[0],
                    user__last_name__icontains=' '.join(parts[1:]),
                )
            patients = patients.filter(
                Q(phone_number__icontains=query) | Q(patient_number__icontains=query) | name_query
            )

        return Response([
            {
                'id': str(patient.id),
                'patient_number': patient.patient_number,
                'full_name': patient.user.get_full_name() if patient.user else 'Bemor',
                'phone_number': patient.phone_number or '',
                'date_of_birth': patient.date_of_birth.isoformat() if patient.date_of_birth else None,
            }
            for patient in patients[:50]
        ])

    @action(detail=False, methods=['get'], url_path='online-appointments', permission_classes=[permissions.AllowAny], throttle_classes=[])
    def online_appointments(self, request):
        staff = self._resolve_staff_from_session(request)
        if not staff:
            return Response({'detail': 'Reception sessiyasi yaroqsiz yoki tugagan.'}, status=status.HTTP_401_UNAUTHORIZED)
        from apps.medical.models import Appointment
        appointments = Appointment.objects.filter(
            clinic=staff.clinic,
            status=Appointment.Status.PENDING_TELEGRAM_CONFIRMATION,
        ).select_related('patient__user', 'doctor__user').order_by('scheduled_date', 'created_at')
        return Response([{
            'id': str(item.id),
            'patient_name': item.patient.user.get_full_name() if item.patient and item.patient.user else 'Bemor',
            'patient_number': item.patient.patient_number if item.patient else '',
            'phone': item.patient.phone_number if item.patient else '',
            'date_of_birth': item.patient.date_of_birth.isoformat() if item.patient and item.patient.date_of_birth else None,
            'doctor_id': str(item.doctor_id),
            'doctor_name': item.doctor.user.get_full_name() if item.doctor and item.doctor.user else 'Doktor',
            'selected_specialties': item.selected_specialties or [],
            'amount': float(item.consultation_fee or 0),
            'queue_position': item.queue_position,
            'scheduled_date': item.scheduled_date.isoformat(),
        } for item in appointments[:100]])

    def _resolve_online_appointment(self, request, appointment_id):
        staff = self._resolve_staff_from_session(request)
        if not staff:
            return None, Response({'detail': 'Reception sessiyasi yaroqsiz yoki tugagan.'}, status=status.HTTP_401_UNAUTHORIZED)
        from apps.medical.models import Appointment
        appointment = Appointment.objects.select_related('clinic', 'doctor', 'patient').filter(
            id=appointment_id, clinic=staff.clinic, status=Appointment.Status.PENDING_TELEGRAM_CONFIRMATION,
        ).first()
        if not appointment:
            return None, Response({'detail': 'Onlayn navbat topilmadi yoki allaqachon ko‘rib chiqilgan.'}, status=status.HTTP_404_NOT_FOUND)
        return (staff, appointment), None

    @action(detail=True, methods=['post'], url_path='online-appointments/confirm', permission_classes=[permissions.AllowAny], throttle_classes=[])
    def confirm_online_appointment(self, request, pk=None):
        resolved, error = self._resolve_online_appointment(request, pk)
        if error:
            return error
        staff, appointment = resolved
        from django.utils import timezone
        from apps.medical.models import Appointment
        appointment.status = Appointment.Status.SCHEDULED
        appointment.reception_staff = staff
        appointment.telegram_token = None
        appointment.telegram_token_expires_at = None
        appointment.save(update_fields=['status', 'reception_staff', 'telegram_token', 'telegram_token_expires_at', 'updated_at'])
        from apps.medical.views import AppointmentViewSet
        AppointmentViewSet()._enqueue_reception_print_job(appointment, appointment.clinic, appointment.doctor)
        return Response({'detail': 'Onlayn navbat tasdiqlandi va printerga yuborildi.', 'queue_position': appointment.queue_position})

    @action(detail=True, methods=['post'], url_path='online-appointments/cancel', permission_classes=[permissions.AllowAny], throttle_classes=[])
    def cancel_online_appointment(self, request, pk=None):
        resolved, error = self._resolve_online_appointment(request, pk)
        if error:
            return error
        _, appointment = resolved
        appointment.status = appointment.Status.CANCELLED
        appointment.save(update_fields=['status', 'updated_at'])
        if appointment.slot_id:
            appointment.slot.status = 'available'
            appointment.slot.save(update_fields=['status'])
        return Response({'detail': 'Onlayn navbat bekor qilindi.'})

    @action(detail=False, methods=['get'], url_path='stats', permission_classes=[permissions.AllowAny], throttle_classes=[])
    def stats(self, request):
        staff = self._resolve_staff_from_session(request)
        if not staff:
            return Response({'detail': 'Reception sessiyasi yaroqsiz yoki tugagan.'}, status=status.HTTP_401_UNAUTHORIZED)
        from apps.medical.models import Appointment
        from django.utils import timezone
        from django.db.models import Sum
        selected_date = request.query_params.get('date') or str(timezone.localdate())
        try:
            from datetime import date
            report_date = date.fromisoformat(selected_date)
        except ValueError:
            report_date = timezone.localdate()
        appointments = Appointment.objects.filter(clinic_id=staff.clinic_id, scheduled_date__date=report_date).select_related('patient__user', 'doctor__user').order_by('scheduled_date')
        queue_statuses = [
            Appointment.Status.SCHEDULED,
            Appointment.Status.CONFIRMED,
            Appointment.Status.WAITING,
        ]
        doctor_accepted_statuses = [
            Appointment.Status.IN_PROGRESS,
            Appointment.Status.COMPLETED,
        ]
        accepted_statuses = [
            Appointment.Status.SCHEDULED,
            Appointment.Status.CONFIRMED,
            Appointment.Status.WAITING,
            Appointment.Status.IN_PROGRESS,
            Appointment.Status.COMPLETED,
        ]
        accepted = appointments.filter(status__in=accepted_statuses)
        queue_patients = appointments.filter(status__in=queue_statuses)
        doctor_accepted_patients = appointments.filter(status__in=doctor_accepted_statuses)
        cancelled = appointments.filter(status__in=[Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW])
        month_start = report_date.replace(day=1)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1)

        monthly = Appointment.objects.filter(
            clinic_id=staff.clinic_id,
            scheduled_date__date__gte=month_start,
            scheduled_date__date__lt=month_end,
        ).exclude(status__in=[Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW])
        map_item = lambda item: {
            'id': str(item.id),
            'queue_position': int(item.queue_position or 0),
            'patient_name': item.patient.user.get_full_name() if item.patient and item.patient.user else 'Bemor',
            'phone': item.patient.phone_number if item.patient else '',
            'patient_number': item.patient.patient_number if item.patient else '',
            'date_of_birth': item.patient.date_of_birth.isoformat() if item.patient and item.patient.date_of_birth else None,
            'birth_year': (
                item.patient.birth_year
                if item.patient and item.patient.birth_year
                else (item.patient.date_of_birth.year if item.patient and item.patient.date_of_birth else None)
            ),
            'doctor_name': item.doctor.user.get_full_name() if item.doctor and item.doctor.user else 'Doktor',
            'doctor_id': str(item.doctor_id) if item.doctor_id else None,
            'selected_specialties': item.selected_specialties or [],
            'amount': float(item.consultation_fee or 0),
            'time': timezone.localtime(item.scheduled_date).strftime('%H:%M')
        }
        return Response({'date': str(report_date), 'accepted_count': accepted.count(), 'cancelled_count': cancelled.count(), 'daily_revenue': float(accepted.aggregate(total=Sum('consultation_fee'))['total'] or 0), 'monthly_revenue': float(monthly.aggregate(total=Sum('consultation_fee'))['total'] or 0), 'salary_type': staff.compensation_type, 'salary_value': float(staff.compensation_value or 0), 'accepted_patients': [map_item(item) for item in accepted], 'queue_patients': [map_item(item) for item in queue_patients], 'doctor_accepted_patients': [map_item(item) for item in doctor_accepted_patients], 'cancelled_patients': [map_item(item) for item in cancelled]})


class ClinicServiceViewSet(viewsets.ModelViewSet):
    queryset = ClinicService.objects.select_related('clinic', 'department').all()
    serializer_class = ClinicServiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['clinic', 'is_active']
