import secrets

from datetime import timedelta
import logging
import re
from typing import Any, cast

from django.conf import settings
from django.core import signing
from django.utils import timezone
from django.contrib.auth.hashers import make_password

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
    ClinicPasswordResetRequestSerializer,
    ClinicPasswordResetVerifySerializer,
    ClinicPasswordResetConfirmSerializer,
    PharmacyPasswordResetRequestSerializer,
    PharmacyPasswordResetVerifySerializer,
    PharmacyPasswordResetConfirmSerializer,
)
from .models import CustomUser, PasswordResetCode
from .models import DoctorResetTelegramSession, ClinicResetTelegramSession, PharmacyResetTelegramSession
from .models import PatientResetTelegramSession
from .throttles import (
    LoginScopedRateThrottle,
    PasswordResetConfirmThrottle,
    PasswordResetRequestThrottle,
    PasswordResetVerifyThrottle,
)

logger = logging.getLogger(__name__)

PATIENT_RESET_CODE_SECONDS = 120
PATIENT_RESET_SESSION_SECONDS = 3600
DOCTOR_RESET_CODE_SECONDS = 120
DOCTOR_RESET_SESSION_SECONDS = 3600
CLINIC_RESET_CODE_SECONDS = 120
CLINIC_RESET_SESSION_SECONDS = 3600
PHARMACY_RESET_CODE_SECONDS = 120
PHARMACY_RESET_SESSION_SECONDS = 3600


def _doctor_bot_username() -> str:
    return str(getattr(settings, 'TELEGRAM_BOT_USERNAME', '') or 'hosptol_bot').strip().lstrip('@') or 'hosptol_bot'


def _doctor_reset_bot_link(token) -> str:
    return f"https://t.me/{_doctor_bot_username()}?start=dr_{token}"


def _clinic_reset_bot_link(token) -> str:
    return f"https://t.me/{_doctor_bot_username()}?start=cl_{token}"


def _pharmacy_reset_bot_link(token) -> str:
    return f"https://t.me/{_doctor_bot_username()}?start=ph_{token}"


def _patient_reset_bot_link(token) -> str:
    return f"https://t.me/{_doctor_bot_username()}?start=pt_{token}"


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

        patient = validated_data['patient']
        user = validated_data['user']
        now = timezone.now()

        code = f"{secrets.randbelow(1000000):06d}"
        PasswordResetCode.objects.create(
            user=user,
            code_hash=make_password(code),
            expires_at=now + timedelta(seconds=PATIENT_RESET_CODE_SECONDS),
        )

        session = (
            PatientResetTelegramSession.objects.filter(user=user, expires_at__gt=now)
            .order_by('-created_at')
            .first()
        )
        if session:
            session.patient = patient
            session.expires_at = now + timedelta(seconds=PATIENT_RESET_SESSION_SECONDS)
            session.save(update_fields=['patient', 'telegram_user_id', 'telegram_chat_id', 'linked_at', 'expires_at', 'updated_at'])
        else:
            session = PatientResetTelegramSession.objects.create(
                user=user,
                patient=patient,
                expires_at=now + timedelta(seconds=PATIENT_RESET_SESSION_SECONDS),
            )

        bot_link = _patient_reset_bot_link(session.token)
        chat_id = session.telegram_chat_id
        delivered_to_bot = bool(chat_id)

        if delivered_to_bot:
            try:
                from apps.medical.telegram_bot_service import TelegramBotService

                bot = TelegramBotService()
                client = bot._require_client()
                client.send_message(
                    int(chat_id),
                    "🔐 G-MED bemor parol tiklash kodi\n\n"
                    f"Kod: <b>{code}</b>\n"
                    "Kod 2 daqiqa amal qiladi.\n"
                    "Agar bu so'rov sizniki bo'lmasa, xabarni e'tiborsiz qoldiring.",
                )
            except Exception:
                logger.exception('Patient password reset OTP could not be sent to Telegram')
                return Response({'detail': 'Kodni Telegram orqali yuborib bo`lmadi. Keyinroq urinib ko`ring.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        response_data = {
            'detail': (
                "Kod Telegram botga yuborildi."
                if delivered_to_bot
                else "Token yaratildi. Botga o'tib Start bosing, kod botga yuboriladi."
            ),
            'expires_in': PATIENT_RESET_CODE_SECONDS,
            'bot_link': bot_link,
            'session_expires_in': PATIENT_RESET_SESSION_SECONDS,
            'bot_note': "Eslatma: bu bot sizga 1 soat davomida yordam beradi.",
        }
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
            salt='gmed-patient-password-reset',
        )

        return Response({'token': token, 'expires_in': PATIENT_RESET_SESSION_SECONDS}, status=status.HTTP_200_OK)


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
            payload = signing.loads(token, salt='gmed-patient-password-reset', max_age=PATIENT_RESET_SESSION_SECONDS)
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
        if user.role != 'patient':
            return Response({'detail': 'Faqat bemor uchun.'}, status=status.HTTP_400_BAD_REQUEST)

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
        now = timezone.now()

        code = f"{secrets.randbelow(1000000):06d}"
        expires_at = now + timedelta(seconds=DOCTOR_RESET_CODE_SECONDS)
        PasswordResetCode.objects.create(
            user=user,
            code_hash=make_password(code),
            expires_at=expires_at,
        )

        session = (
            DoctorResetTelegramSession.objects.filter(user=user, expires_at__gt=now)
            .order_by('-created_at')
            .first()
        )
        if session:
            session.doctor = doctor
            session.expires_at = now + timedelta(seconds=DOCTOR_RESET_SESSION_SECONDS)
            session.save(update_fields=['doctor', 'telegram_user_id', 'telegram_chat_id', 'linked_at', 'expires_at', 'updated_at'])
        else:
            session = DoctorResetTelegramSession.objects.create(
                user=user,
                doctor=doctor,
                expires_at=now + timedelta(seconds=DOCTOR_RESET_SESSION_SECONDS),
            )

        bot_link = _doctor_reset_bot_link(session.token)
        chat_id = session.telegram_chat_id
        delivered_to_bot = bool(chat_id)

        if delivered_to_bot:
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

        response_data = {
            'detail': (
                "Kod Telegram botga yuborildi."
                if delivered_to_bot
                else "Token yaratildi. Botga o'tib Start bosing, kod botga yuboriladi."
            ),
            'expires_in': DOCTOR_RESET_CODE_SECONDS,
            'bot_link': bot_link,
            'session_expires_in': DOCTOR_RESET_SESSION_SECONDS,
            'bot_note': "Eslatma: bu bot sizga 1 soat davomida yordam beradi.",
        }
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

        return Response({'token': token, 'expires_in': DOCTOR_RESET_SESSION_SECONDS}, status=status.HTTP_200_OK)


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
            payload = signing.loads(token, salt='gmed-doctor-password-reset', max_age=DOCTOR_RESET_SESSION_SECONDS)
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


class ClinicPasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetRequestThrottle]

    def post(self, request):
        serializer = ClinicPasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = cast(dict[str, Any], serializer.validated_data)

        clinic = validated_data['clinic']
        user = validated_data['user']
        now = timezone.now()

        code = f"{secrets.randbelow(1000000):06d}"
        expires_at = now + timedelta(seconds=CLINIC_RESET_CODE_SECONDS)
        PasswordResetCode.objects.create(
            user=user,
            code_hash=make_password(code),
            expires_at=expires_at,
        )

        session = (
            ClinicResetTelegramSession.objects.filter(user=user, expires_at__gt=now)
            .order_by('-created_at')
            .first()
        )
        if session:
            session.clinic = clinic
            session.expires_at = now + timedelta(seconds=CLINIC_RESET_SESSION_SECONDS)
            session.save(update_fields=['clinic', 'telegram_user_id', 'telegram_chat_id', 'linked_at', 'expires_at', 'updated_at'])
        else:
            session = ClinicResetTelegramSession.objects.create(
                user=user,
                clinic=clinic,
                expires_at=now + timedelta(seconds=CLINIC_RESET_SESSION_SECONDS),
            )

        bot_link = _clinic_reset_bot_link(session.token)
        chat_id = session.telegram_chat_id
        delivered_to_bot = bool(chat_id)

        if delivered_to_bot:
            try:
                from apps.medical.telegram_bot_service import TelegramBotService

                bot = TelegramBotService()
                client = bot._require_client()
                client.send_message(
                    int(chat_id),
                    "🔐 G-MED klinika parol tiklash kodi\n\n"
                    f"Kod: <b>{code}</b>\n"
                    "Kod 2 daqiqa amal qiladi.\n"
                    "Agar bu so'rov sizniki bo'lmasa, xabarni e'tiborsiz qoldiring.",
                )
            except Exception:
                logger.exception('Clinic owner password reset OTP could not be sent to Telegram')
                return Response({'detail': 'Kodni Telegram orqali yuborib bo`lmadi. Keyinroq urinib ko`ring.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        response_data = {
            'detail': (
                "Kod Telegram botga yuborildi."
                if delivered_to_bot
                else "Token yaratildi. Botga o'tib Start bosing, kod botga yuboriladi."
            ),
            'expires_in': CLINIC_RESET_CODE_SECONDS,
            'bot_link': bot_link,
            'session_expires_in': CLINIC_RESET_SESSION_SECONDS,
            'bot_note': "Eslatma: bu bot sizga 1 soat davomida yordam beradi.",
        }
        if getattr(settings, 'DEBUG', False):
            response_data['debug_code'] = code
        return Response(response_data, status=status.HTTP_200_OK)


class ClinicPasswordResetVerifyView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetVerifyThrottle]

    def post(self, request):
        serializer = ClinicPasswordResetVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = cast(dict[str, Any], serializer.validated_data)
        reset = cast(PasswordResetCode, validated_data['reset'])

        token = signing.dumps(
            {'reset_id': str(reset.id)},
            salt='gmed-clinic-password-reset',
        )

        return Response({'token': token, 'expires_in': CLINIC_RESET_SESSION_SECONDS}, status=status.HTTP_200_OK)


class ClinicPasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetConfirmThrottle]

    def post(self, request):
        serializer = ClinicPasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = cast(dict[str, Any], serializer.validated_data)

        token = str(validated_data['token'])
        new_password = str(validated_data['new_password'])
        new_email = str(validated_data.get('new_email') or '').strip().lower()

        try:
            payload = signing.loads(token, salt='gmed-clinic-password-reset', max_age=CLINIC_RESET_SESSION_SECONDS)
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
        if user.role != 'clinic':
            return Response({'detail': 'Faqat klinika egasi uchun.'}, status=status.HTTP_400_BAD_REQUEST)

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


class PharmacyPasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetRequestThrottle]

    def post(self, request):
        serializer = PharmacyPasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = cast(dict[str, Any], serializer.validated_data)

        pharmacy = validated_data['pharmacy']
        user = validated_data['user']
        now = timezone.now()

        code = f"{secrets.randbelow(1000000):06d}"
        expires_at = now + timedelta(seconds=PHARMACY_RESET_CODE_SECONDS)
        PasswordResetCode.objects.create(
            user=user,
            code_hash=make_password(code),
            expires_at=expires_at,
        )

        session = (
            PharmacyResetTelegramSession.objects.filter(user=user, expires_at__gt=now)
            .order_by('-created_at')
            .first()
        )
        if session:
            session.pharmacy = pharmacy
            session.expires_at = now + timedelta(seconds=PHARMACY_RESET_SESSION_SECONDS)
            session.save(update_fields=['pharmacy', 'telegram_user_id', 'telegram_chat_id', 'linked_at', 'expires_at', 'updated_at'])
        else:
            session = PharmacyResetTelegramSession.objects.create(
                user=user,
                pharmacy=pharmacy,
                expires_at=now + timedelta(seconds=PHARMACY_RESET_SESSION_SECONDS),
            )

        bot_link = _pharmacy_reset_bot_link(session.token)
        chat_id = session.telegram_chat_id
        delivered_to_bot = bool(chat_id)

        if delivered_to_bot:
            try:
                from apps.medical.telegram_bot_service import TelegramBotService

                bot = TelegramBotService()
                client = bot._require_client()
                client.send_message(
                    int(chat_id),
                    "🔐 G-MED dorixona parol tiklash kodi\n\n"
                    f"Kod: <b>{code}</b>\n"
                    "Kod 2 daqiqa amal qiladi.\n"
                    "Agar bu so'rov sizniki bo'lmasa, xabarni e'tiborsiz qoldiring.",
                )
            except Exception:
                logger.exception('Pharmacy owner password reset OTP could not be sent to Telegram')
                return Response({'detail': 'Kodni Telegram orqali yuborib bo`lmadi. Keyinroq urinib ko`ring.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        response_data = {
            'detail': (
                "Kod Telegram botga yuborildi."
                if delivered_to_bot
                else "Token yaratildi. Botga o'tib Start bosing, kod botga yuboriladi."
            ),
            'expires_in': PHARMACY_RESET_CODE_SECONDS,
            'bot_link': bot_link,
            'session_expires_in': PHARMACY_RESET_SESSION_SECONDS,
            'bot_note': "Eslatma: bu bot sizga 1 soat davomida yordam beradi.",
        }
        if getattr(settings, 'DEBUG', False):
            response_data['debug_code'] = code
        return Response(response_data, status=status.HTTP_200_OK)


class PharmacyPasswordResetVerifyView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetVerifyThrottle]

    def post(self, request):
        serializer = PharmacyPasswordResetVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = cast(dict[str, Any], serializer.validated_data)
        reset = cast(PasswordResetCode, validated_data['reset'])

        token = signing.dumps(
            {'reset_id': str(reset.id)},
            salt='gmed-pharmacy-password-reset',
        )

        return Response({'token': token, 'expires_in': PHARMACY_RESET_SESSION_SECONDS}, status=status.HTTP_200_OK)


class PharmacyPasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetConfirmThrottle]

    def post(self, request):
        serializer = PharmacyPasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = cast(dict[str, Any], serializer.validated_data)

        token = str(validated_data['token'])
        new_password = str(validated_data['new_password'])
        new_email = str(validated_data.get('new_email') or '').strip().lower()

        try:
            payload = signing.loads(token, salt='gmed-pharmacy-password-reset', max_age=PHARMACY_RESET_SESSION_SECONDS)
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
        if user.role != 'pharmacy':
            return Response({'detail': 'Faqat dorixona egasi uchun.'}, status=status.HTTP_400_BAD_REQUEST)

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
