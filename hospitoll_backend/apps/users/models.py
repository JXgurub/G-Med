from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from uuid import uuid4


class CustomUser(AbstractUser):
    """
    Custom user model with UUID primary key and role-based access control.
    Supports multiple roles: Administrator, Clinic, Doctor, Patient, Pharmacy
    """
    
    ROLE_CHOICES = (
        ('admin', _('Administrator')),
        ('clinic', _('Clinic')),
        ('doctor', _('Doctor')),
        ('patient', _('Patient')),
        ('pharmacy', _('Pharmacy')),
    )
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False,
        help_text=_("Unique identifier for user")
    )
    email = models.EmailField(
        _('email address'),
        max_length=255,
        unique=True,
        error_messages={
            'unique': _("Bu email allaqachon ro'yxatdan o'tgan."),
        }
    )
    phone_number = models.CharField(
        _('phone number'),
        max_length=20,
        blank=True,
        null=True
    )
    role = models.CharField(
        _('role'),
        max_length=20,
        choices=ROLE_CHOICES,
        default='patient'
    )
    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_("Foydalanuvchi aktiv bo'lsa belgi qo'ying.")
    )
    is_verified = models.BooleanField(
        _('verified'),
        default=False,
        help_text=_("Email tasdiqlangan bo'lsa belgi qo'ying.")
    )
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['role']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"
    
    def get_role_display(self):
        return dict(self.ROLE_CHOICES).get(self.role, self.role)
    
    @property
    def is_administrator(self):
        return self.role == 'admin'
    
    @property
    def is_clinic(self):
        return self.role == 'clinic'
    
    @property
    def is_doctor(self):
        return self.role == 'doctor'
    
    @property
    def is_patient(self):
        return self.role == 'patient'
    
    @property
    def is_pharmacy(self):
        return self.role == 'pharmacy'


class PasswordResetCode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='password_reset_codes')
    code_hash = models.CharField(max_length=255)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['used_at']),
        ]

    @property
    def is_used(self):
        return self.used_at is not None

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at


class CodeVerificationLockState(models.Model):
    CHANNEL_PATIENT_RESET = 'patient_password_reset'
    CHANNEL_DOCTOR_RESET = 'doctor_password_reset'
    CHANNEL_CLINIC_RESET = 'clinic_password_reset'

    CHANNEL_CHOICES = (
        (CHANNEL_PATIENT_RESET, 'Patient password reset'),
        (CHANNEL_DOCTOR_RESET, 'Doctor password reset'),
        (CHANNEL_CLINIC_RESET, 'Clinic password reset'),
    )

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='code_verification_lock_states')
    channel = models.CharField(max_length=64, choices=CHANNEL_CHOICES)
    lock_stage = models.PositiveSmallIntegerField(default=1)
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    blocked_until = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'channel')
        indexes = [
            models.Index(fields=['channel', 'blocked_until']),
            models.Index(fields=['user', 'channel']),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.channel}:stage={self.lock_stage}"


class DoctorResetTelegramSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    token = models.UUIDField(default=uuid4, unique=True, db_index=True)
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='doctor_reset_telegram_sessions')
    doctor = models.ForeignKey('doctors.Doctor', on_delete=models.CASCADE, related_name='reset_telegram_sessions')
    telegram_user_id = models.BigIntegerField(blank=True, null=True, db_index=True)
    telegram_chat_id = models.BigIntegerField(blank=True, null=True)
    linked_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'expires_at']),
            models.Index(fields=['doctor', 'expires_at']),
        ]

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at


class ClinicResetTelegramSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    token = models.UUIDField(default=uuid4, unique=True, db_index=True)
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='clinic_reset_telegram_sessions')
    clinic = models.ForeignKey('clinics.Clinic', on_delete=models.CASCADE, related_name='reset_telegram_sessions')
    telegram_user_id = models.BigIntegerField(blank=True, null=True, db_index=True)
    telegram_chat_id = models.BigIntegerField(blank=True, null=True)
    linked_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'expires_at']),
            models.Index(fields=['clinic', 'expires_at']),
        ]

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at


class PatientResetTelegramSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    token = models.UUIDField(default=uuid4, unique=True, db_index=True)
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='patient_reset_telegram_sessions')
    patient = models.ForeignKey('patients.Patient', on_delete=models.CASCADE, related_name='reset_telegram_sessions')
    telegram_user_id = models.BigIntegerField(blank=True, null=True, db_index=True)
    telegram_chat_id = models.BigIntegerField(blank=True, null=True)
    linked_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'expires_at']),
            models.Index(fields=['patient', 'expires_at']),
        ]

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at


class PharmacyResetTelegramSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    token = models.UUIDField(default=uuid4, unique=True, db_index=True)
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='pharmacy_reset_telegram_sessions')
    pharmacy = models.ForeignKey('pharmacies.Pharmacy', on_delete=models.CASCADE, related_name='reset_telegram_sessions')
    telegram_user_id = models.BigIntegerField(blank=True, null=True, db_index=True)
    telegram_chat_id = models.BigIntegerField(blank=True, null=True)
    linked_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'expires_at']),
            models.Index(fields=['pharmacy', 'expires_at']),
        ]

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at
