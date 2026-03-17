from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from uuid import uuid4


class Specialization(models.Model):
    """
    Medical specializations (Cardiology, Neurology, etc.)
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    name = models.CharField(
        _('specialization name'),
        max_length=255,
        unique=True
    )
    code = models.CharField(
        _('code'),
        max_length=50,
        unique=True,
        help_text=_("Noyob kodi (masalan, CARD)")
    )
    description = models.TextField(
        _('description'),
        blank=True
    )
    is_active = models.BooleanField(
        _('active'),
        default=True
    )
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True
    )
    
    class Meta:
        ordering = ['name']
        verbose_name = _('Specialization')
        verbose_name_plural = _('Specializations')
    
    def __str__(self):
        return self.name


class Doctor(models.Model):
    """
    Doctor model linked to CustomUser and Clinic.
    Each doctor can have multiple specializations.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    user = models.OneToOneField(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='doctor',
        limit_choices_to={'role': 'doctor'}
    )
    clinic = models.ForeignKey(
        'clinics.Clinic',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='doctors',
        help_text=_("Doktor tegishli klinika")
    )
    pinfl = models.CharField(
        _('pinfl'),
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text=_("Doktorning yagona PINFL raqami")
    )
    specializations = models.ManyToManyField(
        Specialization,
        related_name='doctors',
        blank=True,
        help_text=_("Doktor ixtisosliklari")
    )
    license_number = models.CharField(
        _('license number'),
        max_length=100,
        unique=True,
        help_text=_("Tibbiy litsenziya raqami")
    )
    license_document = models.FileField(
        _('license document'),
        upload_to='doctor_licenses/%Y/%m/%d/',
        blank=True,
        null=True
    )
    certificate_document = models.FileField(
        _('certificate document'),
        upload_to='doctor_certificates/%Y/%m/%d/',
        blank=True,
        null=True
    )
    diploma_number = models.CharField(
        _('diploma number'),
        max_length=100,
        blank=True,
        help_text=_("Doktorning diplom raqami")
    )
    first_work_year = models.PositiveSmallIntegerField(
        _('first work year'),
        null=True,
        blank=True,
        validators=[MinValueValidator(1950), MaxValueValidator(2100)],
        help_text=_("Doktor ish boshlagan birinchi yil")
    )
    first_work_month = models.PositiveSmallIntegerField(
        _('first work month'),
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text=_("Doktor ish boshlagan birinchi oy (1-12)")
    )
    date_of_birth = models.DateField(
        _('date of birth'),
        null=True,
        blank=True,
        help_text=_("Doktor tug'ilgan sanasi")
    )
    passport_id = models.CharField(
        _('passport id'),
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
        help_text=_("Doktorning pasport yoki ID raqami")
    )
    telegram_user_id = models.BigIntegerField(
        _('telegram user id'),
        null=True,
        blank=True,
        db_index=True,
        help_text=_('Doktor Telegram user id (password reset OTP uchun)')
    )
    telegram_chat_id = models.BigIntegerField(
        _('telegram chat id'),
        null=True,
        blank=True,
        help_text=_('Doktor Telegram chat id (password reset OTP uchun)')
    )
    COMPENSATION_TYPE_CHOICES = (
        ('salary', _('Salary')),
        ('percent', _('Percent')),
    )
    compensation_type = models.CharField(
        _('compensation type'),
        max_length=20,
        choices=COMPENSATION_TYPE_CHOICES,
        default='salary',
        help_text=_("Ish haqi turi: salary yoki percent")
    )
    compensation_value = models.DecimalField(
        _('compensation value'),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text=_("Ish haqi summasi yoki foiz qiymati")
    )
    bio = models.TextField(
        _('biography'),
        blank=True,
        help_text=_("Doktor haqida qisqacha ma'lumot")
    )
    profile_image = models.ImageField(
        _('profile image'),
        upload_to='doctor_profiles/%Y/%m/%d/',
        blank=True,
        null=True
    )
    years_of_experience = models.PositiveIntegerField(
        _('years of experience'),
        default=0,
        validators=[MinValueValidator(0)]
    )
    consultation_fee = models.DecimalField(
        _('consultation fee'),
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text=_("So'm da hisob qilinadi")
    )
    available_from = models.TimeField(
        _('available from'),
        default='09:00'
    )
    available_until = models.TimeField(
        _('available until'),
        default='17:00'
    )
    lunch_break_start = models.TimeField(
        _('lunch break start'),
        null=True,
        blank=True,
        help_text=_('Abet (tanaffus) boshlanish vaqti')
    )
    lunch_break_end = models.TimeField(
        _('lunch break end'),
        null=True,
        blank=True,
        help_text=_('Abet (tanaffus) tugash vaqti')
    )
    SLOT_MINUTES_CHOICES = (
        (15, '15'),
        (20, '20'),
        (30, '30'),
    )
    slot_minutes = models.PositiveSmallIntegerField(
        _('slot minutes'),
        choices=SLOT_MINUTES_CHOICES,
        default=30,
        validators=[MinValueValidator(15), MaxValueValidator(30)],
        help_text=_('Appointment slot duration in minutes (15/20/30)')
    )
    working_days = models.CharField(
        _('working days'),
        max_length=100,
        default='Mon,Tue,Wed,Thu,Fri',
        help_text=_("Kun nomlari comma bilan ajratilgan")
    )
    is_active = models.BooleanField(
        _('active'),
        default=True
    )
    is_verified = models.BooleanField(
        _('verified'),
        default=False,
        help_text=_("Administrator tomonidan tasdiqlangan")
    )
    rating = models.FloatField(
        _('rating'),
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(5.0)]
    )
    total_ratings = models.PositiveIntegerField(
        _('total ratings'),
        default=0
    )
    total_patients = models.PositiveIntegerField(
        _('total patients'),
        default=0
    )
    consultation_count = models.PositiveIntegerField(
        _('consultation count'),
        default=0
    )
    is_checked_in = models.BooleanField(
        _('is checked in'),
        default=False,
        help_text=_("Doktor hozir ishda ekanligini ko'rsatadi")
    )
    checked_in_at = models.DateTimeField(
        _('checked in at'),
        null=True,
        blank=True,
        help_text=_("Doktor ishga kelgan vaqti")
    )
    checked_out_at = models.DateTimeField(
        _('checked out at'),
        null=True,
        blank=True,
        help_text=_("Doktor ishdan chiqgan vaqti")
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
        verbose_name = _('Doctor')
        verbose_name_plural = _('Doctors')
        indexes = [
            models.Index(fields=['clinic', 'is_active']),
            models.Index(fields=['-rating']),
        ]
    
    def __str__(self):
        clinic_name = self.clinic.name if self.clinic else 'Klinikasiz'
        return f"Dr. {self.user.get_full_name()} ({clinic_name})"
    
    @property
    def specializations_display(self):
        return ", ".join([s.name for s in self.specializations.all()])
    
    @property
    def can_login(self):
        """Doctor can login even if currently not assigned to a clinic."""
        if not self.user.is_active:
            return False
        if not self.clinic:
            return True
        return self.clinic.is_active_status

    def save(self, *args, **kwargs):
        if self.first_work_year:
            today = timezone.localdate()
            current_year = today.year
            normalized_year = min(self.first_work_year, current_year)
            self.first_work_year = normalized_year
            start_month = self.first_work_month or 1
            if start_month < 1:
                start_month = 1
            if start_month > 12:
                start_month = 12
            self.first_work_month = start_month

            years = current_year - normalized_year
            if today.month < start_month:
                years -= 1
            self.years_of_experience = max(0, years)
        super().save(*args, **kwargs)


class DoctorEmployment(models.Model):
    """Tracks which clinic a doctor worked at and when the employment ended."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name='employment_history'
    )
    clinic = models.ForeignKey(
        'clinics.Clinic',
        on_delete=models.CASCADE,
        related_name='doctor_employments'
    )
    started_at = models.DateTimeField(
        _('started at'),
        default=timezone.now,
        db_index=True
    )
    ended_at = models.DateTimeField(
        _('ended at'),
        null=True,
        blank=True,
        db_index=True
    )
    terminated_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='terminated_doctor_employments'
    )
    compensation_type = models.CharField(
        _('compensation type'),
        max_length=20,
        choices=Doctor.COMPENSATION_TYPE_CHOICES,
        default='salary',
        help_text=_('Employment pay model snapshot for historical reporting')
    )
    compensation_value = models.DecimalField(
        _('compensation value'),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text=_('Employment pay value snapshot for historical reporting')
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
        ordering = ['-started_at']
        verbose_name = _('Doctor Employment')
        verbose_name_plural = _('Doctor Employments')
        constraints = [
            models.UniqueConstraint(
                fields=['doctor'],
                condition=models.Q(ended_at__isnull=True),
                name='unique_active_employment_per_doctor'
            )
        ]
        indexes = [
            models.Index(fields=['doctor', 'clinic']),
            models.Index(fields=['clinic', '-started_at']),
            models.Index(fields=['doctor', 'ended_at']),
        ]

    def __str__(self):
        status = 'active' if self.ended_at is None else f"ended {self.ended_at.date()}"
        return f"{self.doctor.user.get_full_name()} @ {self.clinic.name} ({status})"


class DoctorSpecialization(models.Model):
    """
    Junction model for Doctor and Specialization with pricing
    Allows each doctor to have different prices for different specialties
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name='specialty_prices'
    )
    specialization = models.ForeignKey(
        Specialization,
        on_delete=models.CASCADE,
        related_name='doctor_prices'
    )
    consultation_fee = models.DecimalField(
        _('consultation fee'),
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text=_("Ushbu ixtisoslik uchun konsultatsiya narxi (So'm)")
    )
    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_("Bu ixtisoslik faol yoki faol emas")
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
        unique_together = ('doctor', 'specialization')
        ordering = ['specialization__name']
        verbose_name = _('Doctor Specialization')
        verbose_name_plural = _('Doctor Specializations')
        indexes = [
            models.Index(fields=['doctor', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.doctor.user.get_full_name()} - {self.specialization.name} ({self.consultation_fee} So'm)"


class DoctorAvailability(models.Model):
    """
    Doctor's appointment availability slots
    """
    
    SLOT_STATUS_CHOICES = (
        ('available', _('Mavjud')),
        ('booked', _('Band qilingan')),
        ('unavailable', _('Mavjud emas')),
    )
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name='availability_slots'
    )
    date = models.DateField(
        _('date')
    )
    start_time = models.TimeField(
        _('start time')
    )
    end_time = models.TimeField(
        _('end time')
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=SLOT_STATUS_CHOICES,
        default='available'
    )
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True
    )
    
    class Meta:
        unique_together = ('doctor', 'date', 'start_time')
        verbose_name = _('Doctor Availability')
        verbose_name_plural = _('Doctor Availabilities')
    
    def __str__(self):
        return f"{self.doctor.user.get_full_name()} - {self.date} ({self.start_time}-{self.end_time})"


class DoctorWorkRecord(models.Model):
    """
    Doctor's daily work log - tracks check-in and check-out times
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name='work_records',
        help_text=_("Doktor")
    )
    date = models.DateField(
        _('date'),
        help_text=_("Ish kunining sanasi")
    )
    checked_in_at = models.TimeField(
        _('checked in at'),
        null=True,
        blank=True,
        help_text=_("Ishga kelgan vaqti")
    )
    checked_out_at = models.TimeField(
        _('checked out at'),
        null=True,
        blank=True,
        help_text=_("Ishdan chiqgan vaqti")
    )
    work_duration = models.DecimalField(
        _('work duration'),
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text=_("Ish vaqti (soat)")
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
        unique_together = ('doctor', 'date')
        ordering = ['-date']
        verbose_name = _('Doctor Work Record')
        verbose_name_plural = _('Doctor Work Records')
        indexes = [
            models.Index(fields=['doctor', 'date']),
            models.Index(fields=['doctor', '-date']),
        ]
    
    def __str__(self):
        return f"{self.doctor.user.get_full_name()} - {self.date}"
    
    def calculate_duration(self):
        """Calculate work duration in hours"""
        if self.checked_in_at and self.checked_out_at:
            # Create datetime objects for proper time difference calculation
            from datetime import datetime, timedelta
            
            # Convert times to datetime for calculation
            in_time = datetime.combine(self.date, self.checked_in_at)
            out_time = datetime.combine(self.date, self.checked_out_at)
            
            # Handle case where checkout is next day (shouldn't happen but safe)
            if out_time < in_time:
                out_time += timedelta(days=1)
            
            duration = (out_time - in_time).total_seconds() / 3600
            self.work_duration = round(duration, 2)
        return self.work_duration
    
    def save(self, *args, **kwargs):
        """Auto-calculate duration before saving"""
        self.calculate_duration()
        super().save(*args, **kwargs)

