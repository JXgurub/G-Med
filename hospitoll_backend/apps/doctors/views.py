from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.utils.timezone import localdate, localtime
from django.db import transaction
from django.db.models import Q
from django.db.models import Value
from django.db.models.functions import Upper, Replace
from datetime import datetime, timedelta
import re

from .models import Doctor, Specialization, DoctorAvailability, DoctorWorkRecord, DoctorSpecialization, DoctorEmployment
from apps.patients.models import PatientDoctorRating
from .serializers import (
    DoctorSerializer,
    DoctorCreateSerializer,
    DoctorSelfUpdateSerializer,
    SpecializationSerializer,
    DoctorAvailabilitySerializer,
    DoctorRatingSerializer,
    DoctorRatingCreateSerializer,
    DoctorSpecializationSerializer,
)
from core.error_logging import ErrorLogger


DEFAULT_SPECIALIZATIONS = [
    ('Kardiologiya', 'CARDIO'),
    ('Nevrologiya', 'NEURO'),
    ('Pediatriya', 'PEDI'),
    ('Terapiya', 'THERAPY'),
    ('Ginekologiya', 'GYNE'),
    ('Urologiya', 'URO'),
    ('Dermatologiya', 'DERMA'),
    ('Otorinolaringologiya', 'ENT'),
    ('Oftalmologiya', 'OPHTH'),
    ('Travmatologiya', 'TRAUMA'),
    ('Ortopediya', 'ORTHO'),
    ('Endokrinologiya', 'ENDO'),
    ('Gastroenterologiya', 'GASTRO'),
    ('Pulmonologiya', 'PULMO'),
    ('Nefrologiya', 'NEPHRO'),
    ('Reabilitatsiya', 'REHAB'),
    ('Onkologiya', 'ONCO'),
    ('Psixiatriya', 'PSYCH'),
]


class DoctorViewSet(viewsets.ModelViewSet):
    queryset = Doctor.objects.select_related('user', 'clinic').prefetch_related('specializations')
    filterset_fields = ['clinic', 'is_active']

    @staticmethod
    def _is_truthy_query_param(value):
        return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}

    def _include_former_requested(self):
        return self._is_truthy_query_param(self.request.query_params.get('include_former'))

    def _build_schedule_slots_for_date(self, doctor, target_date):
        """Return expected (start_time, end_time) slot tuples for a specific date based on doctor's schedule."""
        day_key = target_date.strftime('%a')
        working_days = [d.strip() for d in (doctor.working_days or '').split(',') if d.strip()]
        if working_days and day_key not in working_days:
            return set()

        start_dt = datetime.combine(target_date, doctor.available_from)
        end_dt = datetime.combine(target_date, doctor.available_until)
        lunch_start_dt = None
        lunch_end_dt = None
        if doctor.lunch_break_start and doctor.lunch_break_end:
            lunch_start_dt = datetime.combine(target_date, doctor.lunch_break_start)
            lunch_end_dt = datetime.combine(target_date, doctor.lunch_break_end)
            if lunch_start_dt >= lunch_end_dt:
                lunch_start_dt = None
                lunch_end_dt = None

        duration_minutes = int(getattr(doctor, 'slot_minutes', 30) or 30)
        if duration_minutes not in (15, 20, 30):
            duration_minutes = 30
        step = timedelta(minutes=duration_minutes)

        if start_dt >= end_dt:
            return set()

        slots = set()
        cursor = start_dt
        while cursor + step <= end_dt:
            slot_end = cursor + step
            if lunch_start_dt and lunch_end_dt and (cursor < lunch_end_dt and slot_end > lunch_start_dt):
                cursor += step
                continue
            slots.add((cursor.time(), slot_end.time()))
            cursor += step
        return slots

    def _sync_doctor_availability_slots(self, doctor, days_ahead=30):
        """Sync future availability slots with doctor's updated schedule.

        - Creates newly needed slots as 'available'.
        - Removes slots outside schedule only when they are still 'available'.
        - Keeps booked/unavailable slots untouched to avoid breaking existing flows.
        """
        today = localdate()

        for day_offset in range(0, days_ahead + 1):
            target_date = today + timedelta(days=day_offset)
            desired_slots = self._build_schedule_slots_for_date(doctor, target_date)

            existing_qs = DoctorAvailability.objects.filter(doctor=doctor, date=target_date)
            existing_pairs = {(slot.start_time, slot.end_time): slot for slot in existing_qs}

            # Add missing slots
            for start_time, end_time in desired_slots:
                if (start_time, end_time) not in existing_pairs:
                    DoctorAvailability.objects.create(
                        doctor=doctor,
                        date=target_date,
                        start_time=start_time,
                        end_time=end_time,
                        status='available'
                    )

            # Remove obsolete available slots
            for pair, slot in existing_pairs.items():
                if pair not in desired_slots and slot.status == 'available':
                    slot.delete()

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        if self.action in ['my', 'check_in', 'check_out', 'terminate']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        scope_clinic_id = self.request.query_params.get('clinic')
        if scope_clinic_id:
            context['scope_clinic_id'] = str(scope_clinic_id)
        return context

    def list(self, request, *args, **kwargs):
        include_former = self._include_former_requested()
        scope_clinic_id = request.query_params.get('clinic')

        if include_former and scope_clinic_id:
            if not request.user.is_authenticated or not request.user.is_clinic:
                return Response({'detail': 'Ruxsat berilmagan.'}, status=status.HTTP_403_FORBIDDEN)

            owner_clinic = getattr(request.user, 'clinic', None)
            if not owner_clinic or str(owner_clinic.id) != str(scope_clinic_id):
                return Response({'detail': 'Faqat o\'z klinikangiz ma\'lumotlarini ko\'rishingiz mumkin.'}, status=status.HTTP_403_FORBIDDEN)

            former_doctor_ids = DoctorEmployment.objects.filter(
                clinic_id=scope_clinic_id,
                ended_at__isnull=False,
            ).values_list('doctor_id', flat=True)

            queryset = self.get_queryset().filter(
                Q(clinic_id=scope_clinic_id) | Q(id__in=former_doctor_ids)
            ).distinct().order_by('-updated_at')

            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)

        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'detail': 'Ruxsat berilmagan.'}, status=status.HTTP_403_FORBIDDEN)
        if not (request.user.is_clinic or request.user.is_superuser or request.user.is_staff):
            return Response({'detail': 'Faqat klinika egasi doktor qo\'sha oladi.'}, status=status.HTTP_403_FORBIDDEN)

        data = request.data.copy()
        if request.user.is_clinic:
            clinic = getattr(request.user, 'clinic', None)
            if not clinic:
                return Response({'detail': 'Klinika topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
            data['clinic'] = str(clinic.id)

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=False, methods=['post'], url_path='identity-check')
    def identity_check(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'Ruxsat berilmagan.'}, status=status.HTTP_403_FORBIDDEN)
        if not (request.user.is_clinic or request.user.is_superuser or request.user.is_staff):
            return Response({'detail': 'Faqat klinika egasi tekshirishi mumkin.'}, status=status.HTTP_403_FORBIDDEN)

        payload = request.data or {}

        pinfl_raw = str(payload.get('pinfl') or '').strip()
        passport_raw = str(payload.get('passport_id') or '').strip()
        first_name = str(payload.get('first_name') or '').strip().lower()
        last_name = str(payload.get('last_name') or '').strip().lower()
        email = str(payload.get('email') or '').strip().lower()
        birth_date = str(payload.get('date_of_birth') or '').strip()

        field_errors = {}

        pinfl = str(pinfl_raw or '')
        if pinfl and not pinfl.isdigit():
            field_errors['pinfl'] = "JSHSHIR faqat raqamlardan iborat bo'lishi kerak."
        if pinfl and len(pinfl) != 14:
            field_errors['pinfl'] = "JSHSHIR 14 ta raqamdan iborat bo'lishi kerak."

        passport_id = re.sub(r"\s+", "", passport_raw).upper() if passport_raw else ''

        if field_errors:
            return Response({
                'status': 'invalid_identity',
                'message': 'JSHSHIR yoki Pasport/ID noto\'g\'ri kiritilgan.',
                'field_errors': field_errors,
                'can_submit': False,
            }, status=status.HTTP_200_OK)

        if not pinfl and not passport_id:
            return Response({
                'status': 'insufficient_identity',
                'message': 'JSHSHIR yoki Pasport/ID kiriting.',
                'can_submit': False,
            }, status=status.HTTP_200_OK)

        clinic = None
        if request.user.is_clinic:
            clinic = getattr(request.user, 'clinic', None)

        existing_by_pinfl = Doctor.objects.select_related('user', 'clinic').filter(pinfl=pinfl).first() if pinfl else None
        existing_by_passport = None
        if passport_id:
            existing_by_passport = (
                Doctor.objects.select_related('user', 'clinic')
                .annotate(
                    passport_norm=Replace(
                        Replace(Upper('passport_id'), Value(' '), Value('')),
                        Value('\t'),
                        Value(''),
                    )
                )
                .filter(passport_norm=passport_id)
                .first()
            )

        if existing_by_pinfl and existing_by_passport and existing_by_pinfl.id != existing_by_passport.id:
            return Response({
                'status': 'identity_conflict',
                'message': "Kiritilgan JSHSHIR va Pasport/ID turli doktorlarga tegishli.",
                'field_errors': {
                    'pinfl': "JSHSHIR boshqa doktorga tegishli.",
                    'passport_id': "Pasport/ID boshqa doktorga tegishli.",
                },
                'can_submit': False,
            }, status=status.HTTP_200_OK)

        existing_doctor = existing_by_pinfl or existing_by_passport
        if not existing_doctor:
            return Response({
                'status': 'new_doctor_allowed',
                'message': 'JSHSHIR/Pasport bazada topilmadi. Yangi doktor qo\'shishingiz mumkin.',
                'can_submit': True,
                'is_existing_doctor': False,
            }, status=status.HTTP_200_OK)

        current_clinic_id = str(clinic.id) if clinic else ''
        doctor_clinic_id = str(existing_doctor.clinic_id) if existing_doctor.clinic_id else ''

        if existing_doctor.is_active and doctor_clinic_id and current_clinic_id and doctor_clinic_id != current_clinic_id:
            return Response({
                'status': 'blocked_other_clinic',
                'message': 'Bu doktor boshqa klinikada ishlayapdi.',
                'can_submit': False,
                'is_existing_doctor': True,
            }, status=status.HTTP_200_OK)

        if existing_doctor.is_active and doctor_clinic_id and current_clinic_id and doctor_clinic_id == current_clinic_id:
            return Response({
                'status': 'already_in_clinic',
                'message': 'Bu doktor sizning klinikangizda allaqachon faol.',
                'can_submit': False,
                'is_existing_doctor': True,
            }, status=status.HTTP_200_OK)

        if (not existing_doctor.is_active) and doctor_clinic_id and current_clinic_id and doctor_clinic_id != current_clinic_id:
            return Response({
                'status': 'blocked_other_clinic',
                'message': 'Bu doktor boshqa klinikaga biriktirilgan, avval bo\'shatilishi kerak.',
                'can_submit': False,
                'is_existing_doctor': True,
            }, status=status.HTTP_200_OK)

        required_profile_fields = {
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'date_of_birth': birth_date,
        }
        missing = [name for name, val in required_profile_fields.items() if not val]
        if missing:
            return Response({
                'status': 'needs_full_profile',
                'message': 'Bazadagi doktorni ishga olish uchun to\'liq ma\'lumot kiriting.',
                'field_errors': {name: 'Ushbu maydonni to\'ldiring.' for name in missing},
                'can_submit': False,
                'is_existing_doctor': True,
            }, status=status.HTTP_200_OK)

        mismatch_errors = {}
        if first_name != str(existing_doctor.user.first_name or '').strip().lower():
            mismatch_errors['first_name'] = "Ism bazadagi doktor ma'lumotiga mos emas."
        if last_name != str(existing_doctor.user.last_name or '').strip().lower():
            mismatch_errors['last_name'] = "Familiya bazadagi doktor ma'lumotiga mos emas."
        if email != str(existing_doctor.user.email or '').strip().lower():
            mismatch_errors['email'] = "Email bazadagi doktor ma'lumotiga mos emas."
        existing_birth_date = existing_doctor.date_of_birth.isoformat() if existing_doctor.date_of_birth else ''
        if existing_birth_date and birth_date != existing_birth_date:
            mismatch_errors['date_of_birth'] = "Tug'ilgan sana bazadagi doktor ma'lumotiga mos emas."

        if mismatch_errors:
            return Response({
                'status': 'identity_mismatch',
                'message': 'Kiritilgan ma\'lumotlar bazadagi doktor bilan mos emas.',
                'field_errors': mismatch_errors,
                'can_submit': False,
                'is_existing_doctor': True,
            }, status=status.HTTP_200_OK)

        return Response({
            'status': 'eligible_rehire',
            'message': 'Doktor bazada topildi va ma\'lumotlar mos. Ishga olish mumkin.',
            'can_submit': True,
            'is_existing_doctor': True,
            'doctor': {
                'id': str(existing_doctor.id),
                'full_name': f"{existing_doctor.user.first_name} {existing_doctor.user.last_name}".strip(),
                'passport_id': existing_doctor.passport_id,
                'pinfl': existing_doctor.pinfl,
            },
        }, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        return Response(
            {'detail': 'Doktor profilini o‘chirish taqiqlangan. Faqat klinikadan bo‘shatish mumkin.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def get_serializer_class(self):
        if self.action == 'create':
            return DoctorCreateSerializer
        return DoctorSerializer
    
    def update(self, request, *args, **kwargs):
        """Update doctor with optimistic locking to prevent concurrent updates"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        is_owner = bool(request.user.is_clinic and instance.clinic_id and instance.clinic.owner_id == request.user.id)
        is_self_doctor = bool(request.user.is_doctor and instance.user_id == request.user.id)
        is_admin = bool(request.user.is_superuser or request.user.is_staff)

        if not (is_owner or is_self_doctor or is_admin):
            return Response({'detail': 'Ruxsat berilmagan.'}, status=status.HTTP_403_FORBIDDEN)

        if is_self_doctor and not (is_owner or is_admin):
            allowed_fields = {'bio', 'profile_image', 'version'}
            incoming_fields = set(request.data.keys())
            if incoming_fields - allowed_fields:
                return Response({'detail': 'Faqat shaxsiy profil ma\'lumotlarini o\'zgartirish mumkin.'}, status=status.HTTP_403_FORBIDDEN)

        old_schedule = {
            'available_from': instance.available_from,
            'available_until': instance.available_until,
            'lunch_break_start': instance.lunch_break_start,
            'lunch_break_end': instance.lunch_break_end,
            'working_days': instance.working_days,
            'slot_minutes': instance.slot_minutes,
        }
        
        # Check version for optimistic locking
        client_version = request.data.get('version')
        if client_version:
            from django.utils.dateparse import parse_datetime
            client_version_dt = parse_datetime(client_version)
            if client_version_dt and instance.updated_at > client_version_dt:
                return Response({
                    'detail': 'Ma\'lumot boshqa foydalanuvchi tomonidan o\'zgartirilgan. Iltimos, sahifani yangilang.',
                    'error_code': 'VERSION_CONFLICT',
                    'current_version': instance.updated_at.isoformat()
                }, status=status.HTTP_409_CONFLICT)
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            self.perform_update(serializer)

            updated_instance = serializer.instance
            compensation_changed = (
                'compensation_type' in serializer.validated_data
                or 'compensation_value' in serializer.validated_data
            )
            schedule_changed = (
                old_schedule['available_from'] != updated_instance.available_from
                or old_schedule['available_until'] != updated_instance.available_until
                or old_schedule['lunch_break_start'] != updated_instance.lunch_break_start
                or old_schedule['lunch_break_end'] != updated_instance.lunch_break_end
                or old_schedule['working_days'] != updated_instance.working_days
                or old_schedule['slot_minutes'] != updated_instance.slot_minutes
            )

            if compensation_changed and updated_instance.clinic_id:
                active_employment = DoctorEmployment.objects.filter(
                    doctor=updated_instance,
                    clinic=updated_instance.clinic,
                    ended_at__isnull=True,
                ).order_by('-started_at').first()

                if active_employment:
                    active_employment.compensation_type = updated_instance.compensation_type or 'salary'
                    active_employment.compensation_value = updated_instance.compensation_value
                    active_employment.save(update_fields=['compensation_type', 'compensation_value', 'updated_at'])

            if schedule_changed:
                try:
                    self._sync_doctor_availability_slots(updated_instance, days_ahead=30)
                except Exception as sync_error:
                    ErrorLogger.log_exception(sync_error, {
                        'source': 'doctor_update_schedule_sync',
                        'doctor_id': str(getattr(updated_instance, 'id', '')),
                        'user_id': str(getattr(request.user, 'id', '')),
                        'path': request.path,
                    })
        
        return Response(serializer.data)
    
    def partial_update(self, request, *args, **kwargs):
        """Partial update with optimistic locking"""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def my(self, request):
        if not request.user.is_authenticated or not request.user.is_doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=404)
        doctor = Doctor.objects.filter(user=request.user).first()
        if not doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=404)
        
        serializer = DoctorSerializer(doctor)
        return Response(serializer.data)

    @action(detail=False, methods=['patch'], url_path='my/update', url_name='my-update')
    def my_update(self, request):
        if not request.user.is_authenticated or not request.user.is_doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=404)

        doctor = Doctor.objects.filter(user=request.user).first()
        if not doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=404)

        forbidden_fields = {
            'available_from',
            'available_until',
            'lunch_break_start',
            'lunch_break_end',
            'working_days',
        }
        if any(field in request.data for field in forbidden_fields):
            return Response(
                {'detail': 'Ish vaqti va ish kunlarini doktor o\'zi o\'zgartira olmaydi.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DoctorSelfUpdateSerializer(doctor, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        old_slot_minutes = int(getattr(doctor, 'slot_minutes', 30) or 30)
        updated_doctor = serializer.save()

        new_slot_minutes = int(getattr(updated_doctor, 'slot_minutes', 30) or 30)
        if old_slot_minutes != new_slot_minutes:
            try:
                self._sync_doctor_availability_slots(updated_doctor, days_ahead=30)
            except Exception as sync_error:
                ErrorLogger.log_exception(sync_error, {
                    'source': 'doctor_my_update_slot_sync',
                    'doctor_id': str(getattr(updated_doctor, 'id', '')),
                    'user_id': str(getattr(request.user, 'id', '')),
                    'path': request.path,
                    'old_slot_minutes': old_slot_minutes,
                    'new_slot_minutes': new_slot_minutes,
                })

        return Response(DoctorSerializer(updated_doctor).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def check_in(self, request):
        """Doctor check-in endpoint"""
        if not request.user.is_authenticated or not request.user.is_doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=404)
        
        doctor = Doctor.objects.filter(user=request.user).first()
        if not doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=404)

        if not doctor.clinic_id:
            return Response({
                'detail': 'Siz hozircha klinikaga biriktirilmagansiz. Faqat profilingizni tahrirlashingiz mumkin.'
            }, status=403)
        
        # Check if doctor is suspended/inactive
        if not doctor.is_active:
            return Response({
                'detail': 'Sizning hisobingiz vaqtincha to\'xtatilgan. Klinika egasi bilan bog\'laning.'
            }, status=403)
        
        if doctor.is_checked_in:
            return Response({
                'detail': 'Siz allaqachon ishga kelgansiz.',
                'is_checked_in': True,
                'checked_in_at': doctor.checked_in_at.isoformat() if doctor.checked_in_at else None
            }, status=400)
        
        now = timezone.now()
        doctor.is_checked_in = True
        doctor.checked_in_at = now
        doctor.checked_out_at = None
        doctor.save()
        
        # Create work record for today using local timezone
        today = localdate()  # Get today's date in Asia/Tashkent timezone
        checked_in_time = localtime(now).time()  # Get time in Asia/Tashkent timezone
        work_record, created = DoctorWorkRecord.objects.get_or_create(
            doctor=doctor,
            date=today,
            defaults={'checked_in_at': checked_in_time}
        )
        if not created:
            work_record.checked_in_at = checked_in_time
            work_record.checked_out_at = None
            work_record.save()
        
        serializer = DoctorSerializer(doctor)
        return Response({
            'detail': 'Siz muvaffaqiyatli ishga keldiniz.',
            'doctor': serializer.data
        }, status=200)

    @action(detail=False, methods=['post'])
    def check_out(self, request):
        """Doctor check-out endpoint"""
        if not request.user.is_authenticated or not request.user.is_doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=404)
        
        doctor = Doctor.objects.filter(user=request.user).first()
        if not doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=404)

        if not doctor.clinic_id:
            return Response({
                'detail': 'Siz hozircha klinikaga biriktirilmagansiz. Faqat profilingizni tahrirlashingiz mumkin.'
            }, status=403)
        
        # Check if doctor is suspended/inactive
        if not doctor.is_active:
            return Response({
                'detail': 'Sizning hisobingiz vaqtincha to\'xtatilgan. Klinika egasi bilan bog\'laning.'
            }, status=403)
        
        if not doctor.is_checked_in:
            return Response({
                'detail': 'Siz ishga kelmagansiz.',
                'is_checked_in': False
            }, status=400)
        
        now = timezone.now()
        doctor.is_checked_in = False
        doctor.checked_out_at = now
        doctor.save()
        
        # Update work record for today using local timezone
        today = localdate()  # Get today's date in Asia/Tashkent timezone
        checked_out_time = localtime(now).time()  # Get time in Asia/Tashkent timezone
        work_record, created = DoctorWorkRecord.objects.get_or_create(
            doctor=doctor,
            date=today,
            defaults={'checked_out_at': checked_out_time}
        )
        if not created:
            work_record.checked_out_at = checked_out_time
            if not work_record.checked_in_at and doctor.checked_in_at:
                work_record.checked_in_at = localtime(doctor.checked_in_at).time()
            work_record.save()
        elif doctor.checked_in_at:
            work_record.checked_in_at = localtime(doctor.checked_in_at).time()
            work_record.save()
        
        serializer = DoctorSerializer(doctor)
        return Response({
            'detail': 'Siz muvaffaqiyatli ishdan chiqib kettingiz.',
            'doctor': serializer.data
        }, status=200)

    @action(detail=True, methods=['post'])
    def terminate(self, request, pk=None):
        """Clinic owner can only fire doctor from their clinic, without deleting profile."""
        if not request.user.is_authenticated or not request.user.is_clinic:
            return Response({'detail': 'Ruxsat berilmagan.'}, status=status.HTTP_403_FORBIDDEN)

        doctor = self.get_object()
        if not doctor.clinic_id or doctor.clinic.owner_id != request.user.id:
            return Response({'detail': 'Faqat o\'z klinikangiz doktorini bo\'shata olasiz.'}, status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        clinic = doctor.clinic

        active_employment = DoctorEmployment.objects.filter(
            doctor=doctor,
            clinic=clinic,
            ended_at__isnull=True,
        ).order_by('-started_at').first()

        if active_employment:
            active_employment.ended_at = now
            active_employment.terminated_by = request.user
            active_employment.compensation_type = doctor.compensation_type or 'salary'
            active_employment.compensation_value = doctor.compensation_value
            active_employment.save(update_fields=['ended_at', 'terminated_by', 'compensation_type', 'compensation_value', 'updated_at'])
        else:
            DoctorEmployment.objects.create(
                doctor=doctor,
                clinic=clinic,
                started_at=doctor.created_at or now,
                ended_at=now,
                terminated_by=request.user,
                compensation_type=doctor.compensation_type or 'salary',
                compensation_value=doctor.compensation_value,
            )

        doctor.is_checked_in = False
        doctor.checked_out_at = now
        doctor.is_active = False
        doctor.clinic = None
        doctor.save(update_fields=['is_checked_in', 'checked_out_at', 'is_active', 'clinic', 'updated_at'])

        return Response({'detail': 'Doktor klinikadan bo\'shatildi. Profil saqlandi.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def work_stats(self, request):
        """Get doctor work statistics for current month"""
        if not request.user.is_authenticated or not request.user.is_doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=404)
        
        doctor = Doctor.objects.filter(user=request.user).first()
        if not doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=404)
        
        # Check if doctor is suspended/inactive
        if not doctor.is_active:
            return Response({
                'detail': 'Sizning hisobingiz vaqtincha to\'xtatilgan. Klinika egasi bilan bog\'laning.'
            }, status=403)
        
        # Get current month records using local timezone
        today = localdate()
        start_of_month = today.replace(day=1)
        # Get last day of month
        if today.month == 12:
            end_of_month = today.replace(day=31)
        else:
            end_of_month = (today.replace(month=today.month + 1, day=1) - timedelta(days=1))
        
        records = DoctorWorkRecord.objects.filter(
            doctor=doctor,
            date__gte=start_of_month,
            date__lte=end_of_month
        ).order_by('-date')
        
        total_hours = sum(float(r.work_duration) for r in records)
        today_record = DoctorWorkRecord.objects.filter(
            doctor=doctor,
            date=today
        ).first()
        
        today_hours = float(today_record.work_duration) if today_record else 0
        today_checked_in = today_record.checked_in_at if today_record else None
        today_checked_out = today_record.checked_out_at if today_record else None
        
        return Response({
            'current_month': f"{today.year}-{today.month:02d}",
            'total_hours_this_month': round(total_hours, 2),
            'work_days_this_month': len(records),
            'today_hours': round(today_hours, 2),
            'today_checked_in': today_checked_in,
            'today_checked_out': today_checked_out,
            'is_checked_in_now': doctor.is_checked_in,
            'checked_in_at': doctor.checked_in_at.isoformat() if doctor.checked_in_at else None,
            'recent_records': [
                {
                    'date': r.date.isoformat(),
                    'checked_in': r.checked_in_at.isoformat() if r.checked_in_at else None,
                    'checked_out': r.checked_out_at.isoformat() if r.checked_out_at else None,
                    'hours': float(r.work_duration)
                } for r in records[:7]
            ]
        }, status=200)


class SpecializationViewSet(viewsets.ModelViewSet):
    queryset = Specialization.objects.filter(is_active=True).order_by('name')
    serializer_class = SpecializationSerializer

    def _ensure_default_specializations(self):
        if Specialization.objects.exists():
            return

        for name, code in DEFAULT_SPECIALIZATIONS:
            Specialization.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'description': 'Auto-seeded default specialization',
                    'is_active': True,
                }
            )

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def list(self, request, *args, **kwargs):
        self._ensure_default_specializations()
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'detail': 'Ruxsat berilmagan.'}, status=status.HTTP_403_FORBIDDEN)
        if not (request.user.is_clinic or request.user.is_superuser or request.user.is_staff):
            return Response({'detail': 'Faqat klinika yoki admin ixtisoslik qo\'sha oladi.'}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)


class DoctorAvailabilityViewSet(viewsets.ModelViewSet):
    queryset = DoctorAvailability.objects.select_related('doctor').all()
    serializer_class = DoctorAvailabilitySerializer
    filterset_fields = ['doctor', 'date', 'status']

    @staticmethod
    def _ranges_overlap(start_a, end_a, start_b, end_b):
        return start_a < end_b and end_a > start_b

    def get_permissions(self):
        if self.action == 'available':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def available(self, request):
        doctor_id = request.query_params.get('doctor')
        date_str = request.query_params.get('date')
        requested_duration = request.query_params.get('duration_minutes')

        if not doctor_id or not date_str:
            return Response({'detail': 'doctor va date parametrlari kerak.'}, status=status.HTTP_400_BAD_REQUEST)
        # Slot duration is configured per doctor; ignore arbitrary durations to keep a consistent grid.

        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        doctor = Doctor.objects.select_related('clinic').filter(id=doctor_id).first()
        if not doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        if not doctor.is_active or not doctor.clinic or not doctor.clinic.is_active_status:
            return Response({'detail': 'Doktor yoki klinika faol emas.'}, status=status.HTTP_400_BAD_REQUEST)
        if not doctor.is_checked_in:
            return Response([], status=status.HTTP_200_OK)

        duration_minutes = int(getattr(doctor, 'slot_minutes', 30) or 30)
        if requested_duration is not None:
            try:
                if int(requested_duration) != duration_minutes:
                    return Response({'detail': 'duration_minutes ushbu doktor uchun ruxsat etilmagan.'}, status=status.HTTP_400_BAD_REQUEST)
            except Exception:
                return Response({'detail': 'duration_minutes noto‘g‘ri.'}, status=status.HTTP_400_BAD_REQUEST)
        if duration_minutes not in (15, 20, 30):
            duration_minutes = 30

        day_key = target_date.strftime('%a')
        working_days = [d.strip() for d in (doctor.working_days or '').split(',') if d.strip()]
        if working_days and day_key not in working_days:
            return Response([], status=status.HTTP_200_OK)

        start_dt = datetime.combine(target_date, doctor.available_from)
        end_dt = datetime.combine(target_date, doctor.available_until)
        lunch_start_dt = None
        lunch_end_dt = None
        if doctor.lunch_break_start and doctor.lunch_break_end:
            lunch_start_dt = datetime.combine(target_date, doctor.lunch_break_start)
            lunch_end_dt = datetime.combine(target_date, doctor.lunch_break_end)
            if lunch_start_dt >= lunch_end_dt:
                lunch_start_dt = None
                lunch_end_dt = None
        step = timedelta(minutes=duration_minutes)
        slot_cursor = start_dt

        if start_dt >= end_dt:
            return Response([], status=status.HTTP_200_OK)

        existing_slots = list(
            DoctorAvailability.objects.filter(
                doctor=doctor,
                date=target_date,
            ).order_by('start_time', 'created_at')
        )
        blocked_ranges = [
            (
                datetime.combine(target_date, slot.start_time),
                datetime.combine(target_date, slot.end_time),
            )
            for slot in existing_slots
            if slot.status != 'available'
        ]

        desired_slots = []
        while slot_cursor + step <= end_dt:
            slot_end_dt = slot_cursor + step
            if lunch_start_dt and lunch_end_dt and (slot_cursor < lunch_end_dt and slot_end_dt > lunch_start_dt):
                slot_cursor += step
                continue

            overlaps_blocked = any(
                self._ranges_overlap(slot_cursor, slot_end_dt, blocked_start, blocked_end)
                for blocked_start, blocked_end in blocked_ranges
            )
            if not overlaps_blocked:
                desired_slots.append((slot_cursor.time(), slot_end_dt.time()))

            slot_cursor += step

        desired_by_start = {start_time: end_time for start_time, end_time in desired_slots}

        for slot in existing_slots:
            if slot.status != 'available':
                continue

            target_end = desired_by_start.get(slot.start_time)
            if not target_end:
                slot.delete()
                continue

            if slot.end_time != target_end:
                slot.end_time = target_end
                slot.save(update_fields=['end_time'])

        existing_available_starts = set(
            DoctorAvailability.objects.filter(
                doctor=doctor,
                date=target_date,
                status='available',
            ).values_list('start_time', flat=True)
        )
        for start_time, end_time in desired_slots:
            if start_time in existing_available_starts:
                continue
            DoctorAvailability.objects.create(
                doctor=doctor,
                date=target_date,
                start_time=start_time,
                end_time=end_time,
                status='available',
            )

        slots = DoctorAvailability.objects.filter(
            doctor=doctor,
            date=target_date,
            status='available'
        ).order_by('start_time')

        if target_date == localdate():
            now = localtime()
            open_time = (start_dt + timedelta(minutes=10)).time()
            close_time = (end_dt - timedelta(minutes=30)).time()
            if now.time() > close_time:
                return Response([], status=status.HTTP_200_OK)
            min_time = open_time if now.time() < open_time else now.time()
            slots = slots.filter(start_time__gte=min_time, start_time__lte=close_time)

        serializer = DoctorAvailabilitySerializer(slots, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DoctorRatingViewSet(viewsets.ModelViewSet):
    queryset = PatientDoctorRating.objects.select_related('doctor', 'patient').all()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['doctor', 'patient', 'rating']
    ordering = ['-created_at']
    ordering_fields = ['created_at', 'rating']
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return DoctorRatingCreateSerializer
        return DoctorRatingSerializer
    
    def create(self, request, *args, **kwargs):
        """Create a new rating with error handling"""
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    def update(self, request, *args, **kwargs):
        """Update an existing rating"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(serializer.data)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def by_doctor(self, request):
        """Get all ratings for a specific doctor"""
        doctor_id = request.query_params.get('doctor_id')
        if not doctor_id:
            return Response({'detail': 'doctor_id parametri kerak.'}, status=status.HTTP_400_BAD_REQUEST)
        
        ratings = PatientDoctorRating.objects.filter(doctor_id=doctor_id).order_by('-created_at')
        serializer = DoctorRatingSerializer(ratings, many=True)
        return Response(serializer.data)

