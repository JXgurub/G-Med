import secrets

from datetime import timedelta
import logging
import sys
import re

from django.conf import settings
from django.core.mail import send_mail
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
)
from .models import CustomUser, PasswordResetCode

logger = logging.getLogger(__name__)


def _normalize_passport_id(value: str) -> str:
    """Normalize passport id by removing all whitespace and uppercasing."""
    if not value:
        return ''
    value = value.strip().upper()
    return re.sub(r"\s+", "", value)


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer
    throttle_scope = 'auth'


class PatientTokenObtainView(TokenObtainPairView):
    serializer_class = PatientTokenObtainSerializer
    throttle_scope = 'auth'


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save(update_fields=['password'])

        return Response({'detail': 'Parol muvaffaqiyatli yangilandi.'}, status=status.HTTP_200_OK)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'password_reset'

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        passport_id_raw = serializer.validated_data.get('passport_id') or ''
        passport_id = _normalize_passport_id(passport_id_raw)
        email = serializer.validated_data['email']
        user = None

        if passport_id:
            from apps.patients.models import Patient

            # Compare normalized forms (ignore whitespace and case).
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
            maybe_user = patient.user if patient else None

            if maybe_user:
                # Email must match the patient's account email.
                if ((maybe_user.email or '').strip().lower() != (email or '').strip().lower()):
                    return Response({'detail': "Pasport ID va email mos emas."}, status=status.HTTP_400_BAD_REQUEST)
                user = maybe_user
        else:
            user = CustomUser.objects.filter(email__iexact=email).first()

        if user and (not user.is_active or user.role != 'patient'):
            user = None

        # If passport_id is provided, we can safely be explicit about "not found" because
        # the caller is providing multiple identifiers.
        if passport_id and not user:
            logger.warning("Password reset not found for provided passport/email pair")
            return Response({'detail': "Bunday foydalanuvchi bazada yo'q."}, status=status.HTTP_404_NOT_FOUND)

        # Always return success-ish response to avoid user enumeration.
        if not user:
            return Response({'detail': "Agar email to'g'ri bo'lsa, tasdiqlash kodi yuborildi."}, status=status.HTTP_200_OK)

        # Generate 6-digit one-time code.
        code = f"{secrets.randbelow(1000000):06d}"
        expires_at = timezone.now() + timedelta(minutes=10)
        reset = PasswordResetCode.objects.create(
            user=user,
            code_hash=make_password(code),
            expires_at=expires_at,
        )

        if getattr(settings, 'DEBUG', False):
            banner = (
                "\n" + ("=" * 72) +
                "\nG-MED | PASSWORD RESET OTP" +
                (f"\nPASSPORT: {passport_id}" if passport_id else "") +
                f"\nEMAIL   : {user.email}" +
                f"\nCODE    : {code}" +
                f"\nEXPIRES : {expires_at.isoformat()}" +
                "\n" + ("=" * 72) + "\n"
            )
            print(banner, flush=True)
            try:
                sys.stderr.write(banner)
                sys.stderr.flush()
            except Exception:
                pass
            logger.warning(banner)
        else:
            logger.info('Password reset OTP generated and emailed')

        subject = 'G-MED: Parolni tiklash kodi'
        message = (
            f"Assalomu alaykum!\n\n"
            f"Parolni tiklash uchun bir martalik kod: {code}\n"
            f"Kod 10 daqiqa amal qiladi.\n\n"
            f"Agar siz bu so'rovni yubormagan bo'lsangiz, xabarni e'tiborsiz qoldiring."
        )
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'noreply@gmed.uz'
        try:
            send_mail(subject, message, from_email, [user.email], fail_silently=False)
        except Exception as e:
            # Email might not be configured in dev/staging. Keep the reset code so the user
            # can continue using the OTP shown in the server console.
            detail = "Email yuborilmadi, kod server terminaliga chiqarildi."
            if getattr(settings, 'DEBUG', False):
                detail = f"{detail} ({type(e).__name__}: {str(e)})"
            response_data = {'detail': detail}
            if getattr(settings, 'DEBUG', False):
                response_data['debug_code'] = code
            return Response(response_data, status=status.HTTP_200_OK)

        response_data = {'detail': "Kod emailingizga yuborildi."}
        if getattr(settings, 'DEBUG', False):
            response_data['debug_code'] = code
        return Response(response_data, status=status.HTTP_200_OK)


class PasswordResetVerifyView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'password_reset'

    def post(self, request):
        serializer = PasswordResetVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reset = serializer.validated_data['reset']

        token = signing.dumps(
            {'reset_id': str(reset.id)},
            salt='gmed-password-reset',
        )

        return Response({'token': token, 'expires_in': 600}, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'password_reset'

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']

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
