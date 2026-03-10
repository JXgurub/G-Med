import secrets

from datetime import timedelta
import logging
import re
from typing import Any, cast

from django.conf import settings
from django.core import signing
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from django.db.models import Value
from django.db.models.functions import Upper, Replace

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    EmailTokenObtainPairSerializer,
    PatientTokenObtainSerializer,
    UserSerializer,
    PasswordResetRequestSerializer,
    PasswordResetVerifySerializer,
    PasswordResetConfirmSerializer,
    ChangePasswordSerializer,
    DoctorPasswordResetRequestSerializer,
    DoctorPasswordResetVerifySerializer,
    DoctorPasswordResetConfirmSerializer,
)
from .models import CustomUser, PasswordResetCode
from .throttles import (
    LoginScopedRateThrottle,
    PasswordResetConfirmThrottle,
    PasswordResetRequestThrottle,
    PasswordResetVerifyThrottle,
)

logger = logging.getLogger(__name__)


def _normalize_passport_id(value: str) -> str:
    """Normalize passport id by removing all whitespace and uppercasing."""
    if not value:
        return ''
    value = value.strip().upper()
    return re.sub(r"\s+", "", value)


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

    return len(provided_norm) >= 9 and len(stored_norm) >= 9 and provided_norm[-9:] == stored_norm[-9:]


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer
    throttle_scope = 'auth'
    throttle_classes = [LoginScopedRateThrottle]


class PatientTokenObtainView(TokenObtainPairView):
    serializer_class = PatientTokenObtainSerializer
    throttle_scope = 'auth'
    throttle_classes = [LoginScopedRateThrottle]


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        validated_data = cast(dict[str, Any], serializer.validated_data)

        request.user.set_password(str(validated_data['new_password']))
        request.user.save(update_fields=['password'])

        return Response({'detail': 'Parol muvaffaqiyatli yangilandi.'}, status=status.HTTP_200_OK)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetRequestThrottle]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = cast(dict[str, Any], serializer.validated_data)

        passport_id = _normalize_passport_id(str(validated_data.get('passport_id') or ''))
        phone_number = str(validated_data.get('phone_number') or '')

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

        if not patient or not user or not user.is_active or user.role != 'patient':
            logger.warning("Password reset not found for provided passport/phone pair")
            return Response({'detail': "Bunday foydalanuvchi bazada yo'q."}, status=status.HTTP_404_NOT_FOUND)

        stored_phone = (patient.phone_number or user.phone_number or '').strip()
        if not _phones_match(phone_number, stored_phone):
            return Response({'detail': "Pasport ID va telefon raqam mos emas."}, status=status.HTTP_400_BAD_REQUEST)

        # Generate 6-digit one-time code and store hashed version.
        code = f"{secrets.randbelow(1000000):06d}"
        expires_at = timezone.now() + timedelta(minutes=10)
        PasswordResetCode.objects.create(
            user=user,
            code_hash=make_password(code),
            expires_at=expires_at,
        )

        # Deliver OTP via Telegram chat linked by previous Telegram-confirmed appointment.
        try:
            from apps.medical.models import Appointment
            from apps.medical.telegram_bot_service import TelegramBotService

            chat_id = (
                Appointment.objects.filter(patient=patient, telegram_chat_id__isnull=False)
                .exclude(telegram_chat_id=0)
                .order_by('-telegram_confirmed_at', '-updated_at')
                .values_list('telegram_chat_id', flat=True)
                .first()
            )
            if not chat_id:
                return Response(
                    {'detail': "Bu bemor Telegram botga ulanmagan. Avval bot orqali tasdiqlangan navbat bo'lishi kerak."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            bot = TelegramBotService()
            client = bot._require_client()
            client.send_message(
                int(chat_id),
                "🔐 G-MED parolni tiklash kodi\n\n"
                f"Kod: <b>{code}</b>\n"
                "Kod 10 daqiqa amal qiladi.\n"
                "Agar bu so'rov sizniki bo'lmasa, xabarni e'tiborsiz qoldiring.",
            )
        except Exception:
            logger.exception('Password reset OTP could not be sent to Telegram')
            return Response({'detail': 'Kodni Telegram orqali yuborib bo`lmadi. Keyinroq urinib ko`ring.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        response_data = {'detail': "Kod Telegram botga yuborildi."}
        if getattr(settings, 'DEBUG', False):
            response_data['debug_code'] = code
        return Response(response_data, status=status.HTTP_200_OK)


class PasswordResetVerifyView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetVerifyThrottle]

    def post(self, request):
        serializer = PasswordResetVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = cast(dict[str, Any], serializer.validated_data)
        reset = cast(PasswordResetCode, validated_data['reset'])

        token = signing.dumps(
            {'reset_id': str(reset.id)},
            salt='gmed-password-reset',
        )

        return Response({'token': token, 'expires_in': 600}, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetConfirmThrottle]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = cast(dict[str, Any], serializer.validated_data)

        token = str(validated_data['token'])
        new_password = str(validated_data['new_password'])

        try:
            payload = signing.loads(token, salt='gmed-password-reset', max_age=600)
        except signing.SignatureExpired:
            return Response({'detail': 'Kod muddati tugagan. Qayta so\u2018rov yuboring.'}, status=status.HTTP_400_BAD_REQUEST)
        except signing.BadSignature:
            return Response({'detail': 'Token noto\u2018g\u2018ri.'}, status=status.HTTP_400_BAD_REQUEST)

        reset_id = payload.get('reset_id')
        reset = PasswordResetCode.objects.select_related('user').filter(id=reset_id).first()
        if not reset:
            return Response({'detail': 'Kod topilmadi.'}, status=status.HTTP_400_BAD_REQUEST)
        if reset.used_at is not None:
            return Response({'detail': 'Kod allaqachon ishlatilgan.'}, status=status.HTTP_400_BAD_REQUEST)
        if reset.is_expired:
            return Response({'detail': 'Kod muddati tugagan.'}, status=status.HTTP_400_BAD_REQUEST)

        user = reset.user
        user.set_password(new_password)
        user.save(update_fields=['password'])
        reset.used_at = timezone.now()
        reset.save(update_fields=['used_at'])

        return Response({'detail': 'Parol muvaffaqiyatli yangilandi.'}, status=status.HTTP_200_OK)


class DoctorPasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetRequestThrottle]

    def post(self, request):
        serializer = DoctorPasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = cast(dict[str, Any], serializer.validated_data)

        doctor = validated_data['doctor']
        user = validated_data['user']

        code = f"{secrets.randbelow(1000000):06d}"
        expires_at = timezone.now() + timedelta(minutes=2)
        PasswordResetCode.objects.create(
            user=user,
            code_hash=make_password(code),
            expires_at=expires_at,
        )

        chat_id = getattr(doctor, 'telegram_chat_id', None)
        if not chat_id:
            bot_username = getattr(settings, 'TELEGRAM_BOT_USERNAME', '') or 'hosptol_bot'
            return Response(
                {
                    'detail': (
                        "Doktor Telegram botga ulanmagan. Avval botda /doctorlink buyrug'i bilan ulanib oling."
                    ),
                    'bot_link': f"https://t.me/{bot_username}",
                    'link_hint': "Botga kirib: /doctorlink <tel> <passport> <pinfl> yuboring.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from apps.medical.telegram_bot_service import TelegramBotService

            bot = TelegramBotService()
            client = bot._require_client()
            client.send_message(
                int(chat_id),
                "🔐 G-MED doktor parol tiklash kodi\n\n"
                f"Kod: <b>{code}</b>\n"
                "Kod 2 daqiqa amal qiladi.\n"
                "Agar bu so'rov sizniki bo'lmasa, xabarni e'tiborsiz qoldiring.",
            )
        except Exception:
            logger.exception('Doctor password reset OTP could not be sent to Telegram')
            return Response({'detail': 'Kodni Telegram orqali yuborib bo`lmadi. Keyinroq urinib ko`ring.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        response_data = {'detail': "Kod Telegram botga yuborildi.", 'expires_in': 120}
        if getattr(settings, 'DEBUG', False):
            response_data['debug_code'] = code
        return Response(response_data, status=status.HTTP_200_OK)


class DoctorPasswordResetVerifyView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetVerifyThrottle]

    def post(self, request):
        serializer = DoctorPasswordResetVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = cast(dict[str, Any], serializer.validated_data)
        reset = cast(PasswordResetCode, validated_data['reset'])

        token = signing.dumps(
            {'reset_id': str(reset.id)},
            salt='gmed-doctor-password-reset',
        )

        return Response({'token': token, 'expires_in': 120}, status=status.HTTP_200_OK)


class DoctorPasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetConfirmThrottle]

    def post(self, request):
        serializer = DoctorPasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = cast(dict[str, Any], serializer.validated_data)

        token = str(validated_data['token'])
        new_password = str(validated_data['new_password'])
        new_email = str(validated_data.get('new_email') or '').strip().lower()

        try:
            payload = signing.loads(token, salt='gmed-doctor-password-reset', max_age=120)
        except signing.SignatureExpired:
            return Response({'detail': 'Kod muddati tugagan. Qayta so\'rov yuboring.'}, status=status.HTTP_400_BAD_REQUEST)
        except signing.BadSignature:
            return Response({'detail': 'Token noto\'g\'ri.'}, status=status.HTTP_400_BAD_REQUEST)

        reset_id = payload.get('reset_id')
        reset = PasswordResetCode.objects.select_related('user').filter(id=reset_id).first()
        if not reset:
            return Response({'detail': 'Kod topilmadi.'}, status=status.HTTP_400_BAD_REQUEST)
        if reset.used_at is not None:
            return Response({'detail': 'Kod allaqachon ishlatilgan.'}, status=status.HTTP_400_BAD_REQUEST)
        if reset.is_expired:
            return Response({'detail': 'Kod muddati tugagan.'}, status=status.HTTP_400_BAD_REQUEST)

        user = reset.user
        if user.role != 'doctor':
            return Response({'detail': 'Faqat doktor uchun.'}, status=status.HTTP_400_BAD_REQUEST)

        if new_email and CustomUser.objects.filter(email__iexact=new_email).exclude(id=user.id).exists():
            return Response({'detail': 'Ushbu email band.'}, status=status.HTTP_400_BAD_REQUEST)

        update_fields = ['password']
        if new_email and user.email != new_email:
            user.email = new_email
            update_fields.append('email')

        user.set_password(new_password)
        user.save(update_fields=update_fields)
        reset.used_at = timezone.now()
        reset.save(update_fields=['used_at'])

        return Response({'detail': 'Email va parol muvaffaqiyatli yangilandi.'}, status=status.HTTP_200_OK)
