from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from django.utils.timezone import localdate
from django.db.models import Q, Value
from django.db.models.functions import Upper, Replace
from datetime import datetime, timedelta
from decimal import Decimal
import re
from uuid import uuid4

from apps.users.models import CustomUser
from apps.users.serializers import UserSerializer
from .models import Doctor, Specialization, DoctorAvailability, DoctorWorkRecord, DoctorSpecialization, DoctorEmployment
from apps.medical.models import Appointment, MedicalRecord
from apps.patients.models import Patient
from apps.patients.models import PatientDoctorRating


class SpecializationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialization
        fields = ['id', 'name', 'code', 'description', 'is_active', 'created_at']


class DoctorSpecializationSerializer(serializers.ModelSerializer):
    specialization = SpecializationSerializer(read_only=True)
    specialization_id = serializers.PrimaryKeyRelatedField(
        queryset=Specialization.objects.all(),
        write_only=True,
        source='specialization'
    )
    
    class Meta:
        model = DoctorSpecialization
        fields = ['id', 'specialization', 'specialization_id', 'consultation_fee', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class DoctorSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    specializations = SpecializationSerializer(many=True, read_only=True)
    specialty_prices = DoctorSpecializationSerializer(many=True, read_only=True)
    monthly_hours = serializers.SerializerMethodField()
    today_hours = serializers.SerializerMethodField()
    today_work_record = serializers.SerializerMethodField()
    today_patients = serializers.SerializerMethodField()
    monthly_patients = serializers.SerializerMethodField()
    today_appointments = serializers.SerializerMethodField()
    monthly_cancelled_appointments = serializers.SerializerMethodField()
    monthly_effective_revenue = serializers.SerializerMethodField()
    monthly_estimated_salary = serializers.SerializerMethodField()
    years_of_experience = serializers.SerializerMethodField()
    is_former_for_scope_clinic = serializers.SerializerMethodField()
    scoped_clinic_id = serializers.SerializerMethodField()
    scoped_employment_started_at = serializers.SerializerMethodField()
    scoped_employment_ended_at = serializers.SerializerMethodField()
    clinic_association_status = serializers.SerializerMethodField()
    version = serializers.DateTimeField(source='updated_at', read_only=False, required=False)

    class Meta:
        model = Doctor
        fields = [
            'id',
            'user',
            'clinic',
            'display_order',
            'pinfl',
            'specializations',
            'specialty_prices',
            'license_number',
            'license_document',
            'certificate_document',
            'diploma_number',
            'first_work_year',
            'first_work_month',
            'date_of_birth',
            'passport_id',
            'compensation_type',
            'compensation_value',
            'bio',
            'profile_image',
            'years_of_experience',
            'consultation_fee',
            'available_from',
            'available_until',
            'lunch_break_start',
            'lunch_break_end',
            'slot_minutes',
            'working_days',
            'is_active',
            'is_verified',
            'rating',
            'total_ratings',
            'total_patients',
            'consultation_count',
            'is_checked_in',
            'checked_in_at',
            'checked_out_at',
            'monthly_hours',
            'today_hours',
            'today_work_record',
            'today_patients',
            'monthly_patients',
            'today_appointments',
            'monthly_cancelled_appointments',
            'monthly_effective_revenue',
            'monthly_estimated_salary',
            'is_former_for_scope_clinic',
            'scoped_clinic_id',
            'scoped_employment_started_at',
            'scoped_employment_ended_at',
            'clinic_association_status',
            'created_at',
            'updated_at',
            'version',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'display_order']

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        available_from = attrs.get('available_from', getattr(instance, 'available_from', None))
        available_until = attrs.get('available_until', getattr(instance, 'available_until', None))
        lunch_break_start = attrs.get('lunch_break_start', getattr(instance, 'lunch_break_start', None))
        lunch_break_end = attrs.get('lunch_break_end', getattr(instance, 'lunch_break_end', None))

        if lunch_break_start and lunch_break_end:
            if lunch_break_start >= lunch_break_end:
                raise serializers.ValidationError({'lunch_break_end': 'Abet tugash vaqti boshlanish vaqtidan keyin bo\'lishi kerak.'})
            if available_from and lunch_break_start <= available_from:
                raise serializers.ValidationError({'lunch_break_start': 'Abet boshlanishi ish boshlanishidan keyin bo\'lishi kerak.'})
            if available_until and lunch_break_end >= available_until:
                raise serializers.ValidationError({'lunch_break_end': 'Abet tugashi ish tugashidan oldin bo\'lishi kerak.'})
        return attrs

    def _get_scope_clinic_id(self):
        scope_clinic_id = self.context.get('scope_clinic_id')
        if not scope_clinic_id:
            return None
        return str(scope_clinic_id)

    def _get_scope_employments(self, obj):
        scope_clinic_id = self._get_scope_clinic_id()
        if not scope_clinic_id:
            return []

        cache_key = f'_scope_employments_{scope_clinic_id}'
        cached = getattr(obj, cache_key, None)
        if cached is not None:
            return cached

        employments = list(
            DoctorEmployment.objects.filter(
                doctor=obj,
                clinic_id=scope_clinic_id,
            ).order_by('started_at')
        )
        setattr(obj, cache_key, employments)
        return employments

    @staticmethod
    def _to_local_date(value):
        if not value:
            return None
        localized = timezone.localtime(value) if timezone.is_aware(value) else value
        return localized.date()

    def _get_scope_date_windows(self, obj, start_date, end_date):
        scope_clinic_id = self._get_scope_clinic_id()
        if not scope_clinic_id:
            return [(start_date, end_date)]

        now = timezone.now()
        windows = []
        employments = self._get_scope_employments(obj)

        for employment in employments:
            employment_start = self._to_local_date(employment.started_at)
            employment_end = self._to_local_date(employment.ended_at or now)
            if not employment_start or not employment_end:
                continue
            overlap_start = max(start_date, employment_start)
            overlap_end = min(end_date, employment_end)
            if overlap_start <= overlap_end:
                windows.append((overlap_start, overlap_end))

        if windows:
            return windows

        if str(getattr(obj, 'clinic_id', '')) == scope_clinic_id:
            fallback_start = self._to_local_date(getattr(obj, 'created_at', None)) or start_date
            overlap_start = max(start_date, fallback_start)
            if overlap_start <= end_date:
                return [(overlap_start, end_date)]

        return []

    def _build_work_record_range_filter(self, obj, start_date, end_date):
        scope_clinic_id = self._get_scope_clinic_id()
        if not scope_clinic_id:
            return Q(date__gte=start_date, date__lte=end_date)

        employments = self._get_scope_employments(obj)
        if not employments:
            if str(getattr(obj, 'clinic_id', '')) != scope_clinic_id:
                return None
            fallback_start = self._to_local_date(getattr(obj, 'created_at', None)) or start_date
            overlap_start = max(start_date, fallback_start)
            if overlap_start > end_date:
                return None
            return Q(date__gte=overlap_start, date__lte=end_date)

        window_filter = Q()
        now = timezone.now()
        for employment in employments:
            employment_start_date = self._to_local_date(employment.started_at)
            employment_end_date = self._to_local_date(employment.ended_at or now)
            if not employment_start_date or not employment_end_date:
                continue

            overlap_start = max(start_date, employment_start_date)
            overlap_end = min(end_date, employment_end_date)
            if overlap_start > overlap_end:
                continue

            clause = Q(date__gte=overlap_start, date__lte=overlap_end)
            if employment.started_at:
                clause &= Q(created_at__gte=employment.started_at)
            if employment.ended_at:
                clause &= Q(created_at__lte=employment.ended_at)
            window_filter |= clause

        return window_filter if window_filter else None

    def _scope_filter_queryset(self, queryset):
        scope_clinic_id = self._get_scope_clinic_id()
        if not scope_clinic_id:
            return queryset
        return queryset.filter(clinic_id=scope_clinic_id)

    def _resolve_default_consultation_fee_for_doctor(self, obj):
        default_fee = Decimal(getattr(obj, 'consultation_fee', 0) or 0)
        if default_fee > 0:
            return default_fee

        specialty_fees = [
            Decimal(fee or 0)
            for fee in DoctorSpecialization.objects.filter(
                doctor=obj,
                is_active=True,
            ).values_list('consultation_fee', flat=True).distinct()
        ]
        positive_fees = [fee for fee in specialty_fees if fee > 0]
        if len(set(positive_fees)) == 1:
            return positive_fees[0]

        return default_fee

    @staticmethod
    def _accepted_appointment_statuses():
        return [Appointment.Status.IN_PROGRESS, Appointment.Status.COMPLETED]

    def _get_monthly_effective_revenue_decimal(self, obj):
        scope_key = self._get_scope_clinic_id() or 'all'
        cache_key = f'_monthly_effective_revenue_{scope_key}'
        cached_value = getattr(obj, cache_key, None)
        if cached_value is not None:
            return cached_value

        today = localdate()
        start_of_month = today.replace(day=1)
        if today.month == 12:
            end_of_month = today.replace(day=31)
        else:
            end_of_month = (today.replace(month=today.month + 1, day=1) - timedelta(days=1))

        accepted_statuses = self._accepted_appointment_statuses()

        appointments = Appointment.objects.filter(
            doctor=obj,
            scheduled_date__date__gte=start_of_month,
            scheduled_date__date__lte=end_of_month,
            status__in=accepted_statuses,
        )
        appointments = self._scope_filter_queryset(appointments)

        records_without_appointment = MedicalRecord.objects.filter(
            doctor=obj,
            created_at__date__gte=start_of_month,
            created_at__date__lte=end_of_month,
            appointment__isnull=True,
        )
        records_without_appointment = self._scope_filter_queryset(records_without_appointment)

        doctor_default_fee = self._resolve_default_consultation_fee_for_doctor(obj)
        total_revenue = Decimal('0')

        for appointment in appointments:
            appointment_fee = Decimal(appointment.consultation_fee or 0)
            effective_fee = appointment_fee if appointment_fee > 0 else doctor_default_fee
            total_revenue += effective_fee

        total_revenue += doctor_default_fee * records_without_appointment.count()

        setattr(obj, cache_key, total_revenue)
        return total_revenue

    def _get_scope_compensation_snapshot(self, obj):
        default_type = getattr(obj, 'compensation_type', None) or 'salary'
        default_value = getattr(obj, 'compensation_value', None)

        scope_clinic_id = self._get_scope_clinic_id()
        if not scope_clinic_id:
            return default_type, default_value

        employments = self._get_scope_employments(obj)
        if not employments:
            if str(getattr(obj, 'clinic_id', '')) == scope_clinic_id:
                return default_type, default_value
            return 'salary', None

        active_employment = next((item for item in reversed(employments) if item.ended_at is None), None)
        scoped_employment = active_employment or employments[-1]

        snapshot_type = scoped_employment.compensation_type or default_type
        snapshot_value = scoped_employment.compensation_value
        if snapshot_value is None:
            snapshot_value = default_value
        return snapshot_type, snapshot_value

    def get_monthly_hours(self, obj):
        """Calculate total hours worked in current month"""
        today = localdate()  # Get today's date in configured timezone
        start_of_month = today.replace(day=1)
        # Get last day of month
        if today.month == 12:
            end_of_month = today.replace(day=31)
        else:
            end_of_month = (today.replace(month=today.month + 1, day=1) - timedelta(days=1))
        
        records = DoctorWorkRecord.objects.filter(doctor=obj)
        range_filter = self._build_work_record_range_filter(obj, start_of_month, end_of_month)
        if range_filter is None:
            return 0.0
        records = records.filter(range_filter)
        
        total_hours = sum(float(r.work_duration) for r in records)
        return round(total_hours, 2)

    def get_today_hours(self, obj):
        """Calculate hours worked today"""
        today = localdate()  # Get today's date in configured timezone
        range_filter = self._build_work_record_range_filter(obj, today, today)
        if range_filter is None:
            return 0.0
        today_record = DoctorWorkRecord.objects.filter(
            doctor=obj,
            date=today
        ).filter(range_filter).first()
        
        if today_record:
            return round(float(today_record.work_duration), 2)
        return 0.0

    def get_today_work_record(self, obj):
        """Get today's work record details"""
        today = localdate()  # Get today's date in configured timezone
        range_filter = self._build_work_record_range_filter(obj, today, today)
        if range_filter is None:
            return None
        today_record = DoctorWorkRecord.objects.filter(
            doctor=obj,
            date=today
        ).filter(range_filter).first()
        
        if today_record:
            return {
                'date': today_record.date.isoformat(),
                'checked_in_at': today_record.checked_in_at.isoformat() if today_record.checked_in_at else None,
                'checked_out_at': today_record.checked_out_at.isoformat() if today_record.checked_out_at else None,
                'duration': round(float(today_record.work_duration), 2)
            }
        return None

    def get_today_patients(self, obj):
        """Count today's accepted appointments + standalone medical records."""
        today = localdate()  # Get today's date in configured timezone
        accepted_statuses = self._accepted_appointment_statuses()

        appointments_qs = Appointment.objects.filter(
            doctor=obj,
            scheduled_date__date=today,
            status__in=accepted_statuses,
        )
        appointments_qs = self._scope_filter_queryset(appointments_qs)

        standalone_records_qs = MedicalRecord.objects.filter(
            doctor=obj,
            created_at__date=today,
            appointment__isnull=True,
        )
        standalone_records_qs = self._scope_filter_queryset(standalone_records_qs)

        return appointments_qs.count() + standalone_records_qs.count()

    def get_monthly_patients(self, obj):
        """Count monthly accepted appointments + standalone medical records."""
        today = localdate()
        start_of_month = today.replace(day=1)
        if today.month == 12:
            end_of_month = today.replace(day=31)
        else:
            end_of_month = (today.replace(month=today.month + 1, day=1) - timedelta(days=1))

        accepted_statuses = self._accepted_appointment_statuses()

        appointments_qs = Appointment.objects.filter(
            doctor=obj,
            scheduled_date__date__gte=start_of_month,
            scheduled_date__date__lte=end_of_month,
            status__in=accepted_statuses,
        )
        appointments_qs = self._scope_filter_queryset(appointments_qs)

        standalone_records_qs = MedicalRecord.objects.filter(
            doctor=obj,
            created_at__date__gte=start_of_month,
            created_at__date__lte=end_of_month,
            appointment__isnull=True,
        )
        standalone_records_qs = self._scope_filter_queryset(standalone_records_qs)

        return appointments_qs.count() + standalone_records_qs.count()

    def get_today_appointments(self, obj):
        """Count completed appointments today"""
        today = localdate()
        queryset = Appointment.objects.filter(
            doctor=obj,
            status='completed',
            scheduled_date__date=today
        )
        return self._scope_filter_queryset(queryset).count()

    def get_years_of_experience(self, obj):
        if obj.first_work_year:
            today = timezone.localdate()
            start_month = obj.first_work_month or 1
            years = today.year - obj.first_work_year
            if today.month < start_month:
                years -= 1
            return max(0, years)
        return obj.years_of_experience or 0

    def get_monthly_cancelled_appointments(self, obj):
        """Count cancelled + no_show appointments in current month"""
        today = localdate()
        start_of_month = today.replace(day=1)

        queryset = Appointment.objects.filter(
            doctor=obj,
            updated_at__date__gte=start_of_month,
            updated_at__date__lte=today,
            status__in=[Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW]
        )
        return self._scope_filter_queryset(queryset).count()

    def get_monthly_effective_revenue(self, obj):
        total_revenue = self._get_monthly_effective_revenue_decimal(obj)
        return round(float(total_revenue), 2)

    def get_monthly_estimated_salary(self, obj):
        monthly_revenue = self._get_monthly_effective_revenue_decimal(obj)
        compensation_type, compensation_value = self._get_scope_compensation_snapshot(obj)

        compensation_decimal = Decimal(compensation_value or 0)
        if compensation_type == 'percent':
            estimated_salary = (monthly_revenue * compensation_decimal) / Decimal('100')
        else:
            estimated_salary = compensation_decimal

        if estimated_salary < 0:
            estimated_salary = Decimal('0')
        return round(float(estimated_salary), 2)

    def get_is_former_for_scope_clinic(self, obj):
        scope_clinic_id = self._get_scope_clinic_id()
        if not scope_clinic_id:
            return False
        if str(getattr(obj, 'clinic_id', '')) == scope_clinic_id:
            return False
        return any(employment.ended_at for employment in self._get_scope_employments(obj))

    def get_scoped_clinic_id(self, obj):
        scope_clinic_id = self._get_scope_clinic_id()
        if scope_clinic_id:
            return scope_clinic_id
        return str(obj.clinic_id) if obj.clinic_id else None

    def get_scoped_employment_started_at(self, obj):
        scope_clinic_id = self._get_scope_clinic_id()
        if not scope_clinic_id:
            return None

        employments = self._get_scope_employments(obj)
        if not employments:
            return None

        if str(getattr(obj, 'clinic_id', '')) == scope_clinic_id:
            active_employment = next((item for item in employments if item.ended_at is None), None)
            if active_employment:
                return active_employment.started_at

        return employments[-1].started_at

    def get_scoped_employment_ended_at(self, obj):
        scope_clinic_id = self._get_scope_clinic_id()
        if not scope_clinic_id:
            return None
        if str(getattr(obj, 'clinic_id', '')) == scope_clinic_id:
            return None

        employments = self._get_scope_employments(obj)
        for employment in reversed(employments):
            if employment.ended_at:
                return employment.ended_at
        return None

    def get_clinic_association_status(self, obj):
        scope_clinic_id = self._get_scope_clinic_id()
        if scope_clinic_id:
            if str(getattr(obj, 'clinic_id', '')) == scope_clinic_id:
                return 'current'
            if self.get_is_former_for_scope_clinic(obj):
                return 'former'
            return 'unassigned'

        if getattr(obj, 'clinic_id', None):
            return 'current'
        return 'unassigned'


class DoctorCreateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    first_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    last_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    phone_number = serializers.CharField(write_only=True, required=False, allow_blank=True)
    pinfl = serializers.CharField(required=False, allow_blank=True)
    license_number = serializers.CharField(required=False, allow_blank=True)
    specialization_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        help_text="Doktor ixtisosliklarining ID'lari"
    )
    specialty_prices = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField()),
        write_only=True,
        required=False,
        help_text="Ixtisosliklari uchun narxlar: [{'specialization_id': 'uuid', 'consultation_fee': '50000'}, ...]"
    )

    class Meta:
        model = Doctor
        fields = [
            'id',
            'clinic',
            'pinfl',
            'license_number',
            'diploma_number',
            'first_work_year',
            'first_work_month',
            'date_of_birth',
            'passport_id',
            'compensation_type',
            'compensation_value',
            'bio',
            'years_of_experience',
            'consultation_fee',
            'available_from',
            'available_until',
            'lunch_break_start',
            'lunch_break_end',
            'slot_minutes',
            'working_days',
            'is_active',
            'email',
            'password',
            'first_name',
            'last_name',
            'phone_number',
            'specialization_ids',
            'specialty_prices',
        ]

    def validate_email(self, value):
        return (value or '').strip()

    def validate_pinfl(self, value):
        normalized = str(value or '').strip()
        if not normalized:
            return None
        if not normalized.isdigit():
            raise serializers.ValidationError("PINFL faqat raqamlardan iborat bo'lishi kerak.")
        if len(normalized) != 14:
            raise serializers.ValidationError("JSHSHIR 14 ta raqamdan iborat bo'lishi kerak.")
        return normalized

    def validate_specialization_ids(self, value):
        if value is None:
            return []
        return value

    def validate_passport_id(self, value):
        if value is None:
            return None
        normalized = re.sub(r"\s+", "", str(value).strip().upper())
        return normalized or None

    def _find_existing_doctors_by_identity(self, pinfl, passport_id):
        existing_by_pinfl = (
            Doctor.objects.select_related('user', 'clinic').filter(pinfl=pinfl).first()
            if pinfl
            else None
        )
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
            raise serializers.ValidationError({
                'pinfl': "Kiritilgan JSHSHIR boshqa doktorga tegishli.",
                'passport_id': "Kiritilgan pasport/ID boshqa doktorga tegishli.",
            })

        return existing_by_pinfl, existing_by_passport

    @staticmethod
    def _normalize_text(value):
        return str(value or '').strip().lower()

    def _validate_existing_doctor_rehire_data(self, existing_doctor, attrs):
        required_for_rehire = ['pinfl', 'passport_id', 'date_of_birth', 'first_name', 'last_name', 'email']
        missing = [field for field in required_for_rehire if not attrs.get(field)]
        if missing:
            raise serializers.ValidationError({
                field: "Bazadagi doktorni qayta ishga olish uchun ushbu maydon majburiy." for field in missing
            })

        errors = {}

        provided_pinfl = attrs.get('pinfl')
        expected_pinfl = existing_doctor.pinfl
        if expected_pinfl and provided_pinfl != expected_pinfl:
            errors['pinfl'] = "JSHSHIR bazadagi doktor ma'lumotiga mos emas."

        provided_passport = attrs.get('passport_id')
        expected_passport = re.sub(r"\s+", "", str(existing_doctor.passport_id or '').strip().upper())
        if expected_passport and provided_passport != expected_passport:
            errors['passport_id'] = "Pasport/ID bazadagi doktor ma'lumotiga mos emas."

        provided_dob = attrs.get('date_of_birth')
        expected_dob = existing_doctor.date_of_birth
        if expected_dob and provided_dob != expected_dob:
            errors['date_of_birth'] = "Tug'ilgan sana bazadagi doktor ma'lumotiga mos emas."

        provided_first_name = self._normalize_text(attrs.get('first_name'))
        expected_first_name = self._normalize_text(existing_doctor.user.first_name)
        if expected_first_name and provided_first_name != expected_first_name:
            errors['first_name'] = "Ism bazadagi doktor ma'lumotiga mos emas."

        provided_last_name = self._normalize_text(attrs.get('last_name'))
        expected_last_name = self._normalize_text(existing_doctor.user.last_name)
        if expected_last_name and provided_last_name != expected_last_name:
            errors['last_name'] = "Familiya bazadagi doktor ma'lumotiga mos emas."

        provided_email = self._normalize_text(attrs.get('email'))
        expected_email = self._normalize_text(existing_doctor.user.email)
        if expected_email and provided_email != expected_email:
            errors['email'] = "Email bazadagi doktor ma'lumotiga mos emas."

        if errors:
            raise serializers.ValidationError(errors)

    def validate(self, attrs):
        compensation_type = attrs.get('compensation_type')
        compensation_value = attrs.get('compensation_value')
        if compensation_type == 'percent' and compensation_value is not None and compensation_value > 100:
            raise serializers.ValidationError({'compensation_value': 'Foiz qiymati 100 dan katta bo\'lmasligi kerak.'})

        available_from = attrs.get('available_from')
        available_until = attrs.get('available_until')
        lunch_break_start = attrs.get('lunch_break_start')
        lunch_break_end = attrs.get('lunch_break_end')
        if lunch_break_start and lunch_break_end:
            if lunch_break_start >= lunch_break_end:
                raise serializers.ValidationError({'lunch_break_end': 'Abet tugash vaqti boshlanish vaqtidan keyin bo\'lishi kerak.'})
            if available_from and lunch_break_start <= available_from:
                raise serializers.ValidationError({'lunch_break_start': 'Abet boshlanishi ish boshlanishidan keyin bo\'lishi kerak.'})
            if available_until and lunch_break_end >= available_until:
                raise serializers.ValidationError({'lunch_break_end': 'Abet tugashi ish tugashidan oldin bo\'lishi kerak.'})

        pinfl = attrs.get('pinfl')
        passport_id = attrs.get('passport_id')
        email = attrs.get('email')
        existing_by_pinfl, existing_by_passport = self._find_existing_doctors_by_identity(pinfl, passport_id)
        existing_doctor = existing_by_pinfl or existing_by_passport
        clinic = attrs.get('clinic')

        if existing_doctor and clinic and existing_doctor.is_active:
            if existing_doctor.clinic_id == clinic.id:
                field_errors = {}
                if existing_by_pinfl:
                    field_errors['pinfl'] = "Bu JSHSHIR bilan doktor allaqachon mavjud."
                if existing_by_passport:
                    field_errors['passport_id'] = "Bu pasport/ID bilan doktor allaqachon mavjud."
                raise serializers.ValidationError(field_errors or {'detail': "Doktor allaqachon mavjud."})

            if existing_doctor.clinic_id and existing_doctor.clinic_id != clinic.id:
                raise serializers.ValidationError({'detail': "Bu hodim boshqa klinikada ham faoliyat yuritadi."})

        if existing_doctor and clinic and (not existing_doctor.is_active) and existing_doctor.clinic_id and existing_doctor.clinic_id != clinic.id:
            raise serializers.ValidationError({'detail': "Bu doktor boshqa klinikaga biriktirilgan, avval bo'shatilishi kerak."})

        if email:
            existing_user = CustomUser.objects.filter(email__iexact=email).first()
            if existing_user:
                email_owner_doctor = Doctor.objects.filter(user=existing_user).first()
                if existing_doctor:
                    if not email_owner_doctor or email_owner_doctor.id != existing_doctor.id:
                        raise serializers.ValidationError({'email': "Bu email boshqa doktorga tegishli."})
                else:
                    if email_owner_doctor:
                        raise serializers.ValidationError({'email': "Bu email boshqa doktorga tegishli."})
                    raise serializers.ValidationError({'email': "Bu email allaqachon ro'yxatdan o'tgan."})

        if existing_doctor:
            if not attrs.get('clinic'):
                raise serializers.ValidationError({'clinic': "Klinika maydoni majburiy."})
            self._validate_existing_doctor_rehire_data(existing_doctor, attrs)
            self._existing_doctor = existing_doctor
            return attrs

        required_for_new = ['email', 'password', 'first_name', 'last_name']
        missing = [field for field in required_for_new if not attrs.get(field)]
        if missing:
            raise serializers.ValidationError({field: "Ushbu maydon majburiy." for field in missing})
        if not attrs.get('specialization_ids'):
            raise serializers.ValidationError({'specialization_ids': "Doktor kamida bitta ixtisoslikka ega bo'lishi kerak."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        email = validated_data.pop('email', '')
        password = validated_data.pop('password', '')
        first_name = validated_data.pop('first_name', '')
        last_name = validated_data.pop('last_name', '')
        phone_number = validated_data.pop('phone_number', '')
        pinfl = validated_data.pop('pinfl', None)
        specialization_ids = validated_data.pop('specialization_ids', [])
        specialty_prices = validated_data.pop('specialty_prices', [])

        clinic = validated_data.get('clinic')
        passport_id = validated_data.get('passport_id')
        now = timezone.now()

        existing_doctor = getattr(self, '_existing_doctor', None)
        if not existing_doctor:
            existing_by_pinfl, existing_by_passport = self._find_existing_doctors_by_identity(pinfl, passport_id)
            existing_doctor = existing_by_pinfl or existing_by_passport

        if existing_doctor:
            if clinic:
                DoctorEmployment.objects.filter(
                    doctor=existing_doctor,
                    ended_at__isnull=True,
                ).exclude(clinic=clinic).update(ended_at=now)

            existing_doctor.clinic = clinic
            existing_doctor.is_active = True
            existing_doctor.is_checked_in = False
            existing_doctor.checked_in_at = None
            existing_doctor.checked_out_at = None
            if pinfl and not existing_doctor.pinfl:
                existing_doctor.pinfl = pinfl
            existing_doctor.consultation_fee = validated_data.get('consultation_fee', existing_doctor.consultation_fee)
            existing_doctor.available_from = validated_data.get('available_from', existing_doctor.available_from)
            existing_doctor.available_until = validated_data.get('available_until', existing_doctor.available_until)
            existing_doctor.lunch_break_start = validated_data.get('lunch_break_start', existing_doctor.lunch_break_start)
            existing_doctor.lunch_break_end = validated_data.get('lunch_break_end', existing_doctor.lunch_break_end)
            existing_doctor.slot_minutes = validated_data.get('slot_minutes', existing_doctor.slot_minutes)
            existing_doctor.working_days = validated_data.get('working_days', existing_doctor.working_days)
            existing_doctor.date_of_birth = validated_data.get('date_of_birth', existing_doctor.date_of_birth)
            existing_doctor.passport_id = validated_data.get('passport_id', existing_doctor.passport_id)
            existing_doctor.compensation_type = validated_data.get('compensation_type', existing_doctor.compensation_type)
            existing_doctor.compensation_value = validated_data.get('compensation_value', existing_doctor.compensation_value)
            existing_doctor.save()

            if clinic:
                has_active_employment = DoctorEmployment.objects.filter(
                    doctor=existing_doctor,
                    clinic=clinic,
                    ended_at__isnull=True,
                ).exists()
                if not has_active_employment:
                    DoctorEmployment.objects.create(
                        doctor=existing_doctor,
                        clinic=clinic,
                        started_at=now,
                        compensation_type=existing_doctor.compensation_type or 'salary',
                        compensation_value=existing_doctor.compensation_value,
                    )

            if specialization_ids:
                existing_doctor.specializations.set(Specialization.objects.filter(id__in=specialization_ids))
                for spec_id in specialization_ids:
                    price = existing_doctor.consultation_fee
                    for spec_price in specialty_prices:
                        if spec_price.get('specialization_id') == str(spec_id):
                            try:
                                price = float(spec_price.get('consultation_fee', price))
                            except (ValueError, TypeError):
                                pass
                            break
                    DoctorSpecialization.objects.update_or_create(
                        doctor=existing_doctor,
                        specialization_id=spec_id,
                        defaults={'consultation_fee': price, 'is_active': True}
                    )

            return existing_doctor

        user = CustomUser.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            role='doctor'
        )

        if not validated_data.get('license_number'):
            auto_license_suffix = (pinfl or str(uuid4()).replace('-', '')[:10]).upper()
            validated_data['license_number'] = f"AUTO-{auto_license_suffix}"

        doctor = Doctor.objects.create(user=user, pinfl=pinfl, **validated_data)

        if clinic:
            DoctorEmployment.objects.create(
                doctor=doctor,
                clinic=clinic,
                started_at=now,
                compensation_type=doctor.compensation_type or 'salary',
                compensation_value=doctor.compensation_value,
            )
        
        # Add specializations
        if specialization_ids:
            doctor.specializations.set(Specialization.objects.filter(id__in=specialization_ids))
            
            # Create DoctorSpecialization records with pricing
            for spec_id in specialization_ids:
                # Find price for this specialization if provided
                price = validated_data.get('consultation_fee', 0)
                
                # Check if specialty_prices has a price for this specialization
                for spec_price in specialty_prices:
                    if spec_price.get('specialization_id') == str(spec_id):
                        try:
                            price = float(spec_price.get('consultation_fee', price))
                        except (ValueError, TypeError):
                            price = validated_data.get('consultation_fee', 0)
                        break
                
                DoctorSpecialization.objects.create(
                    doctor=doctor,
                    specialization_id=spec_id,
                    consultation_fee=price
                )
        
        return doctor


class DoctorSelfUpdateSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Doctor
        fields = [
            'first_name',
            'last_name',
            'email',
            'phone_number',
            'pinfl',
            'license_number',
            'license_document',
            'certificate_document',
            'diploma_number',
            'first_work_year',
            'first_work_month',
            'bio',
            'consultation_fee',
            'slot_minutes',
        ]

    def validate_pinfl(self, value):
        normalized = str(value or '').strip()
        if not normalized:
            return None
        if not normalized.isdigit():
            raise serializers.ValidationError("PINFL faqat raqamlardan iborat bo'lishi kerak.")
        if len(normalized) != 14:
            raise serializers.ValidationError("JSHSHIR 14 ta raqamdan iborat bo'lishi kerak.")
        instance = getattr(self, 'instance', None)
        if instance and instance.pinfl and instance.pinfl != normalized:
            raise serializers.ValidationError("PINFL bir marta saqlangach o'zgartirib bo'lmaydi.")
        qs = Doctor.objects.filter(pinfl=normalized)
        if instance and instance.id:
            qs = qs.exclude(id=instance.id)
        if qs.exists():
            raise serializers.ValidationError("Bu PINFL allaqachon boshqa doktorga biriktirilgan.")
        return normalized

    def validate_first_work_year(self, value):
        if value is None:
            return value
        current_year = timezone.localdate().year
        if value > current_year:
            raise serializers.ValidationError("Birinchi ish yili joriy yildan katta bo'lishi mumkin emas.")
        return value

    def validate_first_work_month(self, value):
        if value is None:
            return value
        if value < 1 or value > 12:
            raise serializers.ValidationError("Birinchi ish oyi 1 dan 12 gacha bo'lishi kerak.")
        return value

    def validate_email(self, value):
        if not value:
            return value
        instance = getattr(self, 'instance', None)
        qs = CustomUser.objects.filter(email__iexact=value)
        if instance and instance.user_id:
            qs = qs.exclude(id=instance.user_id)
        if qs.exists():
            raise serializers.ValidationError("Bu email allaqachon ro'yxatdan o'tgan.")
        return value

    def validate_license_number(self, value):
        if not value:
            return value
        instance = getattr(self, 'instance', None)
        qs = Doctor.objects.filter(license_number=value)
        if instance and instance.id:
            qs = qs.exclude(id=instance.id)
        if qs.exists():
            raise serializers.ValidationError("Bu litsenziya raqami allaqachon mavjud.")
        return value

    def update(self, instance, validated_data):
        user = instance.user

        first_name = validated_data.pop('first_name', None)
        last_name = validated_data.pop('last_name', None)
        email = validated_data.pop('email', None)
        phone_number = validated_data.pop('phone_number', None)

        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name
        if email is not None and email != '':
            user.email = email
            user.username = email
        if phone_number is not None:
            user.phone_number = phone_number
        user.save()

        if 'pinfl' in validated_data and instance.pinfl:
            validated_data.pop('pinfl', None)

        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        return instance


class DoctorWorkRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorWorkRecord
        fields = [
            'id',
            'doctor',
            'date',
            'checked_in_at',
            'checked_out_at',
            'work_duration',
            'created_at',
            'updated_at',
        ]


class DoctorAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorAvailability
        fields = ['id', 'doctor', 'date', 'start_time', 'end_time', 'status', 'created_at']


class DoctorRatingSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    
    class Meta:
        model = PatientDoctorRating
        fields = ['id', 'doctor', 'patient', 'patient_name', 'rating', 'comment', 'is_anonymous', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_patient_name(self, obj):
        if obj.is_anonymous:
            return 'Anonim'
        return obj.patient.user.get_full_name() if obj.patient and obj.patient.user else 'N/A'


class DoctorRatingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientDoctorRating
        fields = ['id', 'doctor', 'patient', 'rating', 'comment', 'is_anonymous', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating 1 dan 5 gacha bo'lishi kerak.")
        return value
    
    def validate(self, data):
        # Check if patient already rated this doctor
        if self.instance is None:  # Only for create
            existing_rating = PatientDoctorRating.objects.filter(
                doctor=data.get('doctor'),
                patient=data.get('patient')
            ).first()
            if existing_rating:
                raise serializers.ValidationError({"detail": "Siz bu doktorga allaqachon baho berdingiz."})
        return data
    
    def create(self, validated_data):
        """Create rating and update doctor's average rating"""
        rating = PatientDoctorRating.objects.create(**validated_data)
        return rating
