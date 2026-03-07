from rest_framework import serializers
from django.utils import timezone
from django.contrib.auth.hashers import check_password
from django.db.models import Value
from django.db.models.functions import Upper, Replace
import re
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import AuthenticationFailed

from .models import CustomUser, PasswordResetCode


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
    passport_id = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        passport_id_raw = attrs.get('passport_id')
        passport_id = re.sub(r"\s+", "", (passport_id_raw or '').strip().upper())
        password = attrs.get('password')

        # Import here to avoid circular imports
        from apps.patients.models import Patient

        # Find patient by passport ID (ignore whitespace + case)
        patient = (
            Patient.objects.select_related('user')
            .annotate(
                national_norm=Replace(
                    Replace(Upper('national_id'), Value(' '), Value('')),
                    Value('\t'),
                    Value(''),
                )
            )
            .filter(national_norm=passport_id)
            .first()
        )

        if not patient:
            raise AuthenticationFailed("Pasport ID yoki parol noto'g'ri.")

        user = patient.user
        if not user:
            raise AuthenticationFailed("Pasport ID yoki parol noto'g'ri.")

        if not user.is_active:
            raise AuthenticationFailed("Foydalanuvchi faol emas.")

        if not user.check_password(password):
            raise AuthenticationFailed("Pasport ID yoki parol noto'g'ri.")

        if user.role != 'patient':
            raise AuthenticationFailed("Bu hisob bemor hisobi emas.")

        refresh = RefreshToken.for_user(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data,
        }


class PasswordResetRequestSerializer(serializers.Serializer):
    passport_id = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField()


class PasswordResetVerifySerializer(serializers.Serializer):
    passport_id = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField()
    code = serializers.CharField()

    def validate(self, attrs):
        passport_id_raw = (attrs.get('passport_id') or '')
        passport_id = re.sub(r"\s+", "", passport_id_raw.strip().upper())
        email = attrs.get('email')
        code = (attrs.get('code') or '').strip()

        user = None

        if passport_id:
            from apps.patients.models import Patient

            patient = (
                Patient.objects.select_related('user')
                .annotate(
                    national_norm=Replace(
                        Replace(Upper('national_id'), Value(' '), Value('')),
                        Value('\t'),
                        Value(''),
                    )
                )
                .filter(national_norm=passport_id)
                .first()
            )
            user = patient.user if patient else None
            if not user:
                raise serializers.ValidationError({'detail': "Bunday foydalanuvchi bazada yo'q."})
            if (user.email or '').strip().lower() != (email or '').strip().lower():
                raise serializers.ValidationError({'detail': "Pasport ID va email mos emas."})
        else:
            user = CustomUser.objects.filter(email__iexact=email).first()

        if not user or not user.is_active or user.role != 'patient':
            raise serializers.ValidationError({'detail': "Email yoki kod noto'g'ri."})

        reset = PasswordResetCode.objects.filter(user=user, used_at__isnull=True, expires_at__gt=timezone.now()).first()
        if not reset:
            raise serializers.ValidationError({'detail': "Kod eskirgan yoki topilmadi."})

        if not check_password(code, reset.code_hash):
            raise serializers.ValidationError({'detail': "Email yoki kod noto'g'ri."})

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
