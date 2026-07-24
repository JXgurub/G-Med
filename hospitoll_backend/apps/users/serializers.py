from rest_framework import serializers
from django.utils import timezone
from django.contrib.auth.hashers import check_password
from django.db.models import Q, CharField, F, Value
from django.db.models.functions import Coalesce
import re
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import AuthenticationFailed

from .code_lockout import clear_lock_state, ensure_not_blocked, register_failed_code_attempt
from .models import CodeVerificationLockState, CustomUser, PasswordResetCode


def _normalize_phone_number(value: str) -> str:
    if not value:
        return ''
    return re.sub(r"\D+", "", str(value))


def _phones_match(provided: str, stored: str) -> bool:
    provided_norm = _normalize_phone_number(provided)
    stored_norm = _normalize_phone_number(stored)

    if not provided_norm or not stored_norm:
        return False

    if provided_norm == stored_norm:
        return True

    # Be tolerant to country code formatting (+998xxxxxxxxx vs xxxxxxxxx).
    return len(provided_norm) >= 9 and len(stored_norm) >= 9 and provided_norm[-9:] == stored_norm[-9:]


def _digits_only(value: str) -> str:
    if not value:
        return ''
    return re.sub(r"\D+", "", str(value))


def _normalize_compact_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or '').strip().upper())


def _is_digits_only(value: str) -> bool:
    return bool(str(value or '').strip()) and str(value or '').strip().isdigit()


def _doctor_identity_matches(*, passport_id: str, birth_date, pinfl: str, doctor) -> bool:
    provided_passport = _digits_only(passport_id)
    provided_pinfl = _digits_only(pinfl)

    if not provided_passport or not provided_pinfl or not birth_date:
        return False

    stored_passport = _digits_only((doctor.passport_id or '').strip())
    stored_pinfl = _digits_only((doctor.pinfl or '').strip())
    stored_birth_date = doctor.date_of_birth

    if not stored_passport or not stored_pinfl or not stored_birth_date:
        return False

    passport_ok = provided_passport == stored_passport
    pinfl_ok = provided_pinfl == stored_pinfl
    birth_date_ok = birth_date == stored_birth_date
    return passport_ok and pinfl_ok and birth_date_ok


def _find_doctor_for_reset(passport_id: str, birth_date, pinfl: str):
    # Import here to avoid circular imports
    from apps.doctors.models import Doctor

    candidates = (
        Doctor.objects.select_related('user')
        .filter(user__is_active=True, user__role='doctor', is_active=True)
    )
    for doctor in candidates:
        if _doctor_identity_matches(
            passport_id=passport_id,
            birth_date=birth_date,
            pinfl=pinfl,
            doctor=doctor,
        ):
            return doctor
    return None


def _find_clinic_for_reset(clinic_number: str, passport_id: str, phone_number: str):
    # Import here to avoid circular imports
    from apps.clinics.models import Clinic

    normalized_clinic_number = _normalize_compact_text(clinic_number)
    normalized_passport_id = _normalize_compact_text(passport_id)

    if not normalized_clinic_number or not normalized_passport_id or not phone_number:
        return None

    clinics = Clinic.objects.select_related('owner').filter(owner__is_active=True, owner__role='clinic')
    for clinic in clinics:
        stored_clinic_number = _normalize_compact_text(clinic.registration_number)
        stored_passport_id = _normalize_compact_text(clinic.owner_passport_id)
        stored_phone = (clinic.owner.phone_number or clinic.phone_number or '').strip()

        if not stored_clinic_number or not stored_passport_id or not stored_phone:
            continue

        if (
            stored_clinic_number == normalized_clinic_number
            and stored_passport_id == normalized_passport_id
            and _phones_match(phone_number, stored_phone)
        ):
            return clinic

    return None


def _find_pharmacy_for_reset(pharmacy_number: str, passport_id: str, phone_number: str):
    # Import here to avoid circular imports
    from apps.pharmacies.models import Pharmacy

    normalized_pharmacy_number = _normalize_compact_text(pharmacy_number)
    normalized_passport_id = _normalize_compact_text(passport_id)

    if not normalized_pharmacy_number or not normalized_passport_id or not phone_number:
        return None

    pharmacies = Pharmacy.objects.select_related('owner').filter(owner__is_active=True, owner__role='pharmacy')
    for pharmacy in pharmacies:
        stored_pharmacy_number = _normalize_compact_text(pharmacy.registration_number)
        stored_passport_id = _normalize_compact_text(pharmacy.owner_passport_id)
        stored_phone = (pharmacy.owner.phone_number or pharmacy.phone_number or '').strip()

        if not stored_pharmacy_number or not stored_passport_id or not stored_phone:
            continue

        if (
            stored_pharmacy_number == normalized_pharmacy_number
            and stored_passport_id == normalized_passport_id
            and _phones_match(phone_number, stored_phone)
        ):
            return pharmacy

    return None


def _find_patient_for_reset(phone_number: str):
    # Import here to avoid circular imports
    from apps.patients.models import Patient

    if not phone_number:
        return None

    tail = _normalize_phone_number(phone_number)
    tail = tail[-9:] if len(tail) >= 9 else tail
    if not tail:
        return None

    patient = (
        Patient.objects.select_related('user')
        .annotate(
            patient_phone_norm=Coalesce(F('phone_number'), Value('', output_field=CharField())),
            user_phone_norm=Coalesce(F('user__phone_number'), Value('', output_field=CharField())),
        )
        .filter(Q(patient_phone_norm__endswith=tail) | Q(user_phone_norm__endswith=tail))
        .first()
    )

    if not patient or not patient.user:
        return None

    stored_phone = (patient.phone_number or patient.user.phone_number or '').strip()
    if not _phones_match(phone_number, stored_phone):
        return None

    return patient


class UserSerializer(serializers.ModelSerializer):
    has_usable_password = serializers.SerializerMethodField()

    def get_has_usable_password(self, obj):
        return obj.has_usable_password()

    class Meta:
        model = CustomUser
        fields = [
            'id',
            'email',
            'username',
            'first_name',
            'last_name',
            'role',
            'phone_number',
            'has_usable_password',
            'is_superuser',
            'is_staff',
            'is_active',
            'is_verified',
            'created_at',
            'updated_at',
        ]


class EmailTokenObtainPairSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        user = CustomUser.objects.filter(email__iexact=email).first()
        if not user:
            # Allow login via clinic/pharmacy contact email by mapping to owner.
            from apps.clinics.models import Clinic
            from apps.pharmacies.models import Pharmacy

            clinic = Clinic.objects.select_related('owner').filter(email__iexact=email).first()
            if clinic and clinic.owner:
                user = clinic.owner
            else:
                pharmacy = Pharmacy.objects.select_related('owner').filter(email__iexact=email).first()
                if pharmacy and pharmacy.owner:
                    user = pharmacy.owner
        if not user:
            raise AuthenticationFailed("Email yoki parol noto'g'ri.")

        if not user.is_active:
            raise AuthenticationFailed("Foydalanuvchi faol emas.")

        if not user.check_password(password):
            raise AuthenticationFailed("Email yoki parol noto'g'ri.")

        # Check subscription status for clinic/pharmacy owners
        subscription_data = None
        is_subscription_expired = False
        if user.is_clinic or user.is_pharmacy:
            from apps.clinics.models import Clinic
            from apps.pharmacies.models import Pharmacy
            
            subscriber = None
            if user.is_clinic:
                subscriber = Clinic.objects.filter(owner=user).first()
            elif user.is_pharmacy:
                subscriber = Pharmacy.objects.filter(owner=user).first()
            
            if subscriber and hasattr(subscriber, 'subscription'):
                subscription = subscriber.subscription
                # Check and auto-update expired status
                subscription.auto_deactivate_if_expired()
                subscription.refresh_from_db()
                
                is_subscription_expired = subscription.is_expired()
                subscription_data = {
                    'status': subscription.status,
                    'is_expired': is_subscription_expired,
                    'end_date': subscription.end_date.isoformat() if subscription.end_date else None,
                    'days_remaining': subscription.days_remaining(),
                }
                
                # Block login if subscription expired
                if is_subscription_expired:
                    raise AuthenticationFailed(
                        "Obunangiz muddati tugagan. Iltimos admin bilan bog'laning. "
                        f"Telefon: {subscriber.phone_number or 'mavjud emas'}"
                    )

        refresh = RefreshToken.for_user(user)
        response_data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data,
        }
        
        if subscription_data:
            response_data['subscription'] = subscription_data
        
        return response_data


class PatientTokenObtainSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        phone_number_raw = attrs.get('phone_number') or ''
        phone_number = _normalize_phone_number(phone_number_raw)
        password = attrs.get('password')

        # Import here to avoid circular imports
        from apps.patients.models import Patient

        if not phone_number:
            raise AuthenticationFailed("Telefon raqam yoki parol noto'g'ri.")

        # Normalize common formatting characters to compare phone values safely.
        def _phone_expr(field_name: str):
            expr = Coalesce(F(field_name), Value(''), output_field=CharField())
            for token in (' ', '\t', '\n', '\r', '+', '-', '(', ')'):
                expr = Replace(expr, Value(token), Value(''))
            return expr

        tail = phone_number[-9:] if len(phone_number) >= 9 else phone_number
        candidates = (
            Patient.objects.select_related('user')
            .annotate(
                patient_phone_norm=_phone_expr('phone_number'),
                user_phone_norm=_phone_expr('user__phone_number'),
            )
            .filter(
                Q(patient_phone_norm__endswith=tail)
                | Q(user_phone_norm__endswith=tail)
            )
        )

        patient = next(
            (
                item
                for item in candidates
                if _phones_match(phone_number_raw, (item.phone_number or item.user.phone_number or '').strip())
            ),
            None,
        )

        if not patient:
            raise AuthenticationFailed("Telefon raqam yoki parol noto'g'ri.")

        user = patient.user
        if not user:
            raise AuthenticationFailed("Telefon raqam yoki parol noto'g'ri.")

        if not user.is_active:
            raise AuthenticationFailed("Foydalanuvchi faol emas.")

        if not user.check_password(password):
            raise AuthenticationFailed("Telefon raqam yoki parol noto'g'ri.")

        if user.role != 'patient':
            raise AuthenticationFailed("Bu hisob bemor hisobi emas.")

        refresh = RefreshToken.for_user(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data,
        }


class PasswordResetRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField()

    def validate(self, attrs):
        phone_number = str(attrs.get('phone_number') or '')

        if len(_normalize_phone_number(phone_number)) < 9:
            raise serializers.ValidationError({'phone_number': 'Telefon raqam noto\'g\'ri.'})

        patient = _find_patient_for_reset(phone_number)
        if not patient or not patient.user or not patient.user.is_active or patient.user.role != 'patient':
            raise serializers.ValidationError({'detail': "Kiritilgan ma'lumotlar bo'yicha bemor topilmadi."})

        attrs['patient'] = patient
        attrs['user'] = patient.user
        return attrs


class PasswordResetVerifySerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    code = serializers.CharField()

    def validate(self, attrs):
        base = PasswordResetRequestSerializer(
            data={
                'phone_number': attrs.get('phone_number'),
            }
        )
        base.is_valid(raise_exception=True)

        patient = base.validated_data['patient']
        user = base.validated_data['user']
        code = (attrs.get('code') or '').strip()

        reset = PasswordResetCode.objects.filter(user=user, used_at__isnull=True, expires_at__gt=timezone.now()).first()
        if not reset:
            raise serializers.ValidationError({'detail': "Kod eskirgan yoki topilmadi."})

        blocked_payload = ensure_not_blocked(user, CodeVerificationLockState.CHANNEL_PATIENT_RESET)
        if blocked_payload:
            raise serializers.ValidationError(blocked_payload)

        if not check_password(code, reset.code_hash):
            failure_payload = register_failed_code_attempt(user, CodeVerificationLockState.CHANNEL_PATIENT_RESET)
            raise serializers.ValidationError(failure_payload)

        clear_lock_state(user, CodeVerificationLockState.CHANNEL_PATIENT_RESET)

        attrs['patient'] = patient
        attrs['user'] = user
        attrs['reset'] = reset
        return attrs


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        if not value or len(value) < 6:
            raise serializers.ValidationError('Parol kamida 6 ta belgidan iborat bo\u2018lishi kerak.')
        return value


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = self.context['request'].user
        current_password = attrs.get('current_password')
        new_password = attrs.get('new_password')

        if not user.check_password(current_password):
            raise serializers.ValidationError({'current_password': 'Joriy parol noto\'g\'ri.'})

        if not new_password or len(new_password) < 6:
            raise serializers.ValidationError({'new_password': 'Yangi parol kamida 6 ta belgidan iborat bo\'lishi kerak.'})

        if current_password == new_password:
            raise serializers.ValidationError({'new_password': 'Yangi parol joriy parol bilan bir xil bo\'lmasligi kerak.'})

        return attrs


class DoctorPasswordResetRequestSerializer(serializers.Serializer):
    passport_id = serializers.CharField()
    birth_date = serializers.DateField(input_formats=['%Y-%m-%d', '%d.%m.%Y'])
    pinfl = serializers.CharField()

    def validate(self, attrs):
        passport_id = str(attrs.get('passport_id') or '')
        birth_date = attrs.get('birth_date')
        pinfl = attrs.get('pinfl') or ''
        pinfl_digits = _digits_only(pinfl)

        if len(_digits_only(passport_id)) < 5:
            raise serializers.ValidationError({'passport_id': 'Pasport ID noto\'g\'ri.'})
        if not birth_date:
            raise serializers.ValidationError({'birth_date': "Tug'ilgan sana kiritilishi kerak."})
        if len(pinfl_digits) != 14:
            raise serializers.ValidationError({'pinfl': 'PINFL/JSHSHIR 14 ta raqamdan iborat bo\'lishi kerak.'})

        doctor = _find_doctor_for_reset(passport_id, birth_date, pinfl_digits)
        if not doctor or not doctor.user or not doctor.user.is_active or doctor.user.role != 'doctor':
            raise serializers.ValidationError({'detail': "Kiritilgan ma'lumotlar bo'yicha doktor topilmadi."})

        attrs['pinfl'] = pinfl_digits
        attrs['doctor'] = doctor
        attrs['user'] = doctor.user
        return attrs


class DoctorPasswordResetVerifySerializer(serializers.Serializer):
    passport_id = serializers.CharField()
    birth_date = serializers.DateField(input_formats=['%Y-%m-%d', '%d.%m.%Y'])
    pinfl = serializers.CharField()
    code = serializers.CharField()

    def validate(self, attrs):
        base = DoctorPasswordResetRequestSerializer(
            data={
                'passport_id': attrs.get('passport_id'),
                'birth_date': attrs.get('birth_date'),
                'pinfl': attrs.get('pinfl'),
            }
        )
        base.is_valid(raise_exception=True)

        doctor = base.validated_data['doctor']
        user = base.validated_data['user']
        code = (attrs.get('code') or '').strip()

        reset = PasswordResetCode.objects.filter(user=user, used_at__isnull=True, expires_at__gt=timezone.now()).first()
        if not reset:
            raise serializers.ValidationError({'detail': "Kod eskirgan yoki topilmadi."})

        blocked_payload = ensure_not_blocked(user, CodeVerificationLockState.CHANNEL_DOCTOR_RESET)
        if blocked_payload:
            raise serializers.ValidationError(blocked_payload)

        if not check_password(code, reset.code_hash):
            failure_payload = register_failed_code_attempt(user, CodeVerificationLockState.CHANNEL_DOCTOR_RESET)
            raise serializers.ValidationError(failure_payload)

        clear_lock_state(user, CodeVerificationLockState.CHANNEL_DOCTOR_RESET)

        attrs['doctor'] = doctor
        attrs['user'] = user
        attrs['reset'] = reset
        return attrs


class DoctorPasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    new_email = serializers.EmailField(required=False, allow_blank=True)

    def validate_new_password(self, value):
        if not value or len(value) < 6:
            raise serializers.ValidationError('Parol kamida 6 ta belgidan iborat bo\'lishi kerak.')
        return value

    def validate_new_email(self, value):
        clean = (value or '').strip()
        if not clean:
            return ''
        return clean.lower()


class ClinicPasswordResetRequestSerializer(serializers.Serializer):
    clinic_number = serializers.CharField()
    passport_id = serializers.CharField()
    phone_number = serializers.CharField()

    def validate(self, attrs):
        clinic_number = str(attrs.get('clinic_number') or '')
        passport_id = str(attrs.get('passport_id') or '')
        phone_number = str(attrs.get('phone_number') or '')

        if len(_normalize_compact_text(clinic_number)) < 3:
            raise serializers.ValidationError({'clinic_number': 'Klinika raqami noto\'g\'ri.'})
        if len(_normalize_compact_text(passport_id)) < 5:
            raise serializers.ValidationError({'passport_id': 'Pasport ID noto\'g\'ri.'})
        if len(_normalize_phone_number(phone_number)) < 9:
            raise serializers.ValidationError({'phone_number': 'Telefon raqam noto\'g\'ri.'})

        clinic = _find_clinic_for_reset(clinic_number, passport_id, phone_number)
        if not clinic or not clinic.owner or not clinic.owner.is_active or clinic.owner.role != 'clinic':
            raise serializers.ValidationError({'detail': "Kiritilgan ma'lumotlar bo'yicha klinika topilmadi."})

        attrs['clinic_number'] = _normalize_compact_text(clinic_number)
        attrs['passport_id'] = _normalize_compact_text(passport_id)
        attrs['clinic'] = clinic
        attrs['user'] = clinic.owner
        return attrs


class ClinicPasswordResetVerifySerializer(serializers.Serializer):
    clinic_number = serializers.CharField()
    passport_id = serializers.CharField()
    phone_number = serializers.CharField()
    code = serializers.CharField()

    def validate(self, attrs):
        base = ClinicPasswordResetRequestSerializer(
            data={
                'clinic_number': attrs.get('clinic_number'),
                'passport_id': attrs.get('passport_id'),
                'phone_number': attrs.get('phone_number'),
            }
        )
        base.is_valid(raise_exception=True)

        clinic = base.validated_data['clinic']
        user = base.validated_data['user']
        code = (attrs.get('code') or '').strip()

        reset = PasswordResetCode.objects.filter(user=user, used_at__isnull=True, expires_at__gt=timezone.now()).first()
        if not reset:
            raise serializers.ValidationError({'detail': "Kod eskirgan yoki topilmadi."})

        blocked_payload = ensure_not_blocked(user, CodeVerificationLockState.CHANNEL_CLINIC_RESET)
        if blocked_payload:
            raise serializers.ValidationError(blocked_payload)

        if not check_password(code, reset.code_hash):
            failure_payload = register_failed_code_attempt(user, CodeVerificationLockState.CHANNEL_CLINIC_RESET)
            raise serializers.ValidationError(failure_payload)

        clear_lock_state(user, CodeVerificationLockState.CHANNEL_CLINIC_RESET)

        attrs['clinic'] = clinic
        attrs['user'] = user
        attrs['reset'] = reset
        return attrs


class ClinicPasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    new_email = serializers.EmailField(required=False, allow_blank=True)

    def validate_new_password(self, value):
        if not value or len(value) < 6:
            raise serializers.ValidationError('Parol kamida 6 ta belgidan iborat bo\'lishi kerak.')
        return value

    def validate_new_email(self, value):
        clean = (value or '').strip()
        if not clean:
            return ''
        return clean.lower()


class PharmacyPasswordResetRequestSerializer(serializers.Serializer):
    pharmacy_number = serializers.CharField()
    passport_id = serializers.CharField()
    phone_number = serializers.CharField()

    def validate(self, attrs):
        pharmacy_number = str(attrs.get('pharmacy_number') or '')
        passport_id = str(attrs.get('passport_id') or '')
        phone_number = str(attrs.get('phone_number') or '')

        if len(_normalize_compact_text(pharmacy_number)) < 3:
            raise serializers.ValidationError({'pharmacy_number': 'Dorixona raqami noto\'g\'ri.'})
        if len(_normalize_compact_text(passport_id)) < 5:
            raise serializers.ValidationError({'passport_id': 'Pasport ID noto\'g\'ri.'})
        if len(_normalize_phone_number(phone_number)) < 9:
            raise serializers.ValidationError({'phone_number': 'Telefon raqam noto\'g\'ri.'})

        pharmacy = _find_pharmacy_for_reset(pharmacy_number, passport_id, phone_number)
        if not pharmacy or not pharmacy.owner or not pharmacy.owner.is_active or pharmacy.owner.role != 'pharmacy':
            raise serializers.ValidationError({'detail': "Kiritilgan ma'lumotlar bo'yicha dorixona topilmadi."})

        attrs['pharmacy_number'] = _normalize_compact_text(pharmacy_number)
        attrs['passport_id'] = _normalize_compact_text(passport_id)
        attrs['pharmacy'] = pharmacy
        attrs['user'] = pharmacy.owner
        return attrs


class PharmacyPasswordResetVerifySerializer(serializers.Serializer):
    pharmacy_number = serializers.CharField()
    passport_id = serializers.CharField()
    phone_number = serializers.CharField()
    code = serializers.CharField()

    def validate(self, attrs):
        base = PharmacyPasswordResetRequestSerializer(
            data={
                'pharmacy_number': attrs.get('pharmacy_number'),
                'passport_id': attrs.get('passport_id'),
                'phone_number': attrs.get('phone_number'),
            }
        )
        base.is_valid(raise_exception=True)

        pharmacy = base.validated_data['pharmacy']
        user = base.validated_data['user']
        code = (attrs.get('code') or '').strip()

        reset = PasswordResetCode.objects.filter(user=user, used_at__isnull=True, expires_at__gt=timezone.now()).first()
        if not reset:
            raise serializers.ValidationError({'detail': "Kod eskirgan yoki topilmadi."})

        pharmacy_channel = 'pharmacy_password_reset'
        blocked_payload = ensure_not_blocked(user, pharmacy_channel)
        if blocked_payload:
            raise serializers.ValidationError(blocked_payload)

        if not check_password(code, reset.code_hash):
            failure_payload = register_failed_code_attempt(user, pharmacy_channel)
            raise serializers.ValidationError(failure_payload)

        clear_lock_state(user, pharmacy_channel)

        attrs['pharmacy'] = pharmacy
        attrs['user'] = user
        attrs['reset'] = reset
        return attrs


class PharmacyPasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    new_email = serializers.EmailField(required=False, allow_blank=True)

    def validate_new_password(self, value):
        if not value or len(value) < 6:
            raise serializers.ValidationError('Parol kamida 6 ta belgidan iborat bo\'lishi kerak.')
        return value

    def validate_new_email(self, value):
        clean = (value or '').strip()
        if not clean:
            return ''
        return clean.lower()
