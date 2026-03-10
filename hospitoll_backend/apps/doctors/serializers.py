from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from django.utils.timezone import localdate
from django.db.models import Value
from django.db.models.functions import Upper, Replace
from datetime import datetime, timedelta
import re
from uuid import uuid4

from apps.users.models import CustomUser
from apps.users.serializers import UserSerializer
from .models import Doctor, Specialization, DoctorAvailability, DoctorWorkRecord, DoctorSpecialization
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
    years_of_experience = serializers.SerializerMethodField()
    version = serializers.DateTimeField(source='updated_at', read_only=False, required=False)

    class Meta:
        model = Doctor
        fields = [
            'id',
            'user',
            'clinic',
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
            'created_at',
            'updated_at',
            'version',
        ]

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

    def get_monthly_hours(self, obj):
        """Calculate total hours worked in current month"""
        today = localdate()  # Get today's date in configured timezone
        start_of_month = today.replace(day=1)
        # Get last day of month
        if today.month == 12:
            end_of_month = today.replace(day=31)
        else:
            end_of_month = (today.replace(month=today.month + 1, day=1) - timedelta(days=1))
        
        records = DoctorWorkRecord.objects.filter(
            doctor=obj,
            date__gte=start_of_month,
            date__lte=end_of_month
        )
        
        total_hours = sum(float(r.work_duration) for r in records)
        return round(total_hours, 2)

    def get_today_hours(self, obj):
        """Calculate hours worked today"""
        today = localdate()  # Get today's date in configured timezone
        today_record = DoctorWorkRecord.objects.filter(
            doctor=obj,
            date=today
        ).first()
        
        if today_record:
            return round(float(today_record.work_duration), 2)
        return 0.0

    def get_today_work_record(self, obj):
        """Get today's work record details"""
        today = localdate()  # Get today's date in configured timezone
        today_record = DoctorWorkRecord.objects.filter(
            doctor=obj,
            date=today
        ).first()
        
        if today_record:
            return {
                'date': today_record.date.isoformat(),
                'checked_in_at': today_record.checked_in_at.isoformat() if today_record.checked_in_at else None,
                'checked_out_at': today_record.checked_out_at.isoformat() if today_record.checked_out_at else None,
                'duration': round(float(today_record.work_duration), 2)
            }
        return None

    def get_today_patients(self, obj):
        """Count total patient visits (medical records) created today"""
        today = localdate()  # Get today's date in configured timezone
        return MedicalRecord.objects.filter(
            doctor=obj,
            created_at__date=today
        ).count()

    def get_monthly_patients(self, obj):
        """Count total patient visits (medical records) created in current month"""
        today = localdate()
        start_of_month = today.replace(day=1)
        if today.month == 12:
            end_of_month = today.replace(day=31)
        else:
            end_of_month = (today.replace(month=today.month + 1, day=1) - timedelta(days=1))

        return MedicalRecord.objects.filter(
            doctor=obj,
            created_at__date__gte=start_of_month,
            created_at__date__lte=end_of_month
        ).count()

    def get_today_appointments(self, obj):
        """Count completed appointments today"""
        today = localdate()
        return Appointment.objects.filter(
            doctor=obj,
            status='completed',
            scheduled_date__date=today
        ).count()

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

        return Appointment.objects.filter(
            doctor=obj,
            updated_at__date__gte=start_of_month,
            updated_at__date__lte=today,
            status__in=[Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW]
        ).count()


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
        if normalized and (
            Patient.objects.annotate(
                national_norm=Replace(
                    Replace(Upper('national_id'), Value(' '), Value('')),
                    Value('\t'),
                    Value(''),
                )
            )
            .filter(national_norm=normalized)
            .exists()
        ):
            raise serializers.ValidationError("Bu pasport/ID bazadagi boshqa odamga tegishli.")
        return normalized or None

    def _find_existing_doctor_by_identity(self, pinfl, passport_id):
        existing_by_pinfl = (
            Doctor.objects.select_related('user', 'clinic').filter(pinfl=pinfl).first()
            if pinfl
            else None
        )
        existing_by_passport = (
            Doctor.objects.select_related('user', 'clinic').filter(passport_id=passport_id).first()
            if passport_id
            else None
        )

        if existing_by_pinfl and existing_by_passport and existing_by_pinfl.id != existing_by_passport.id:
            raise serializers.ValidationError({'detail': "Kiritilgan PINFL va pasport ID turli doktorlarga tegishli."})

        return existing_by_pinfl or existing_by_passport

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
        existing_doctor = self._find_existing_doctor_by_identity(pinfl, passport_id)
        clinic = attrs.get('clinic')

        if existing_doctor and clinic and existing_doctor.is_active and existing_doctor.clinic_id and existing_doctor.clinic_id != clinic.id:
            raise serializers.ValidationError({'detail': "Bu hodim boshqa klinikada ham faoliyat yuritadi."})

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

        existing_doctor = getattr(self, '_existing_doctor', None)
        if not existing_doctor:
            existing_doctor = self._find_existing_doctor_by_identity(pinfl, passport_id)

        if existing_doctor:
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
