from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from uuid import uuid4
from django.utils import timezone


class Appointment(models.Model):
    """
    Doctor appointment booking
    """

    class Status(models.TextChoices):
        # New telegram-first flow
        PENDING_TELEGRAM_CONFIRMATION = 'pending_telegram_confirmation', _('Telegram tasdiqi kutilmoqda')
        CONFIRMED = 'confirmed', _('Tasdiqlangan')

        # Doctor panel workflow
        WAITING = 'waiting', _('Kutilmoqda')
        IN_PROGRESS = 'in_progress', _('Jarayonda')

        # Legacy / general
        SCHEDULED = 'scheduled', _('Rejalashtirilgan')
        COMPLETED = 'completed', _('Bajarilgan')
        CANCELLED = 'cancelled', _('Bekor qilingan')
        NO_SHOW = 'no_show', _('Kelmagandi')
    
    APPOINTMENT_TYPE_CHOICES = (
        ('consultation', _('Maslahat')),
        ('follow_up', _('Tekshiruv')),
        ('procedure', _('Operatsiya')),
        ('test', _('Sinov')),
    )
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.CASCADE,
        related_name='appointments'
    )
    slot = models.ForeignKey(
        'doctors.DoctorAvailability',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointments',
        help_text=_('Booked availability slot (used to free slot on cancellation)')
    )
    doctor = models.ForeignKey(
        'doctors.Doctor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointments'
    )
    doctor_name = models.CharField(
        _('doctor name'),
        max_length=255,
        blank=True,
        help_text=_("Doktor nomi (arxiv uchun)")
    )
    clinic = models.ForeignKey(
        'clinics.Clinic',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointments'
    )
    clinic_name = models.CharField(
        _('clinic name'),
        max_length=255,
        blank=True,
        help_text=_("Klinika nomi (arxiv uchun)")
    )
    appointment_type = models.CharField(
        _('appointment type'),
        max_length=20,
        choices=APPOINTMENT_TYPE_CHOICES,
        default='consultation'
    )
    status = models.CharField(
        _('status'),
        max_length=40,
        choices=Status.choices,
        default=Status.SCHEDULED
    )
    scheduled_date = models.DateTimeField(
        _('scheduled date')
    )
    duration_minutes = models.PositiveIntegerField(
        _('duration in minutes'),
        default=30
    )
    reason = models.TextField(
        _('reason for visit'),
        blank=True
    )
    notes = models.TextField(
        _('notes'),
        blank=True
    )
    consultation_fee = models.DecimalField(
        _('consultation fee'),
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )
    is_paid = models.BooleanField(
        _('paid'),
        default=False
    )

    queue_position = models.PositiveIntegerField(
        _('queue position'),
        default=0,
        help_text=_('Ordering position for doctor queue on the given day')
    )

    telegram_token = models.UUIDField(
        _('telegram token'),
        null=True,
        blank=True,
        unique=True,
        help_text=_('One-time token used for Telegram /start linking')
    )
    telegram_token_expires_at = models.DateTimeField(
        _('telegram token expires at'),
        null=True,
        blank=True
    )
    telegram_user_id = models.BigIntegerField(
        _('telegram user id'),
        null=True,
        blank=True,
        db_index=True
    )
    telegram_chat_id = models.BigIntegerField(
        _('telegram chat id'),
        null=True,
        blank=True
    )
    telegram_confirmed_at = models.DateTimeField(
        _('telegram confirmed at'),
        null=True,
        blank=True
    )
    telegram_reminder_sent_at = models.DateTimeField(
        _('telegram reminder sent at'),
        null=True,
        blank=True
    )

    telegram_15min_prompt_sent_at = models.DateTimeField(
        _('telegram 15min prompt sent at'),
        null=True,
        blank=True
    )

    telegram_two_left_notified_at = models.DateTimeField(
        _('telegram two left notified at'),
        null=True,
        blank=True,
        help_text=_('Set when patient is notified that only 2 people are ahead in queue')
    )

    telegram_one_left_notified_at = models.DateTimeField(
        _('telegram one left notified at'),
        null=True,
        blank=True,
        help_text=_('Set when patient is notified that only 1 person is ahead in queue')
    )

    patient_arrival_confirmed_at = models.DateTimeField(
        _('patient arrival confirmed at'),
        null=True,
        blank=True,
        help_text=_('Set when patient taps "Boraman" on the 15-minute Telegram prompt')
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
        ordering = ['-scheduled_date']
        verbose_name = _('Appointment')
        verbose_name_plural = _('Appointments')
        indexes = [
            models.Index(fields=['patient', 'scheduled_date']),
            models.Index(fields=['doctor', 'scheduled_date']),
            models.Index(fields=['status']),
            models.Index(fields=['telegram_user_id', 'scheduled_date']),
            models.Index(fields=['telegram_token']),
        ]

    @property
    def telegram_token_is_expired(self) -> bool:
        if not self.telegram_token or not self.telegram_token_expires_at:
            return True
        return timezone.now() >= self.telegram_token_expires_at
    
    def save(self, *args, **kwargs):
        # Avtomatik ravishda doctor va clinic nomlarini saqlash
        if self.doctor and not self.doctor_name:
            self.doctor_name = self.doctor.user.get_full_name()
        if self.clinic and not self.clinic_name:
            self.clinic_name = self.clinic.name
        super().save(*args, **kwargs)
    
    def __str__(self):
        doctor_name = self.doctor_name if self.doctor_name else (self.doctor.user.get_full_name() if self.doctor else "O'chirilgan doktor")
        return f"{self.patient.user.get_full_name()} - Dr. {doctor_name} ({self.scheduled_date})"


class MedicalRecord(models.Model):
    """
    Medical record/encounter for each appointment
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.CASCADE,
        related_name='medical_records'
    )
    doctor = models.ForeignKey(
        'doctors.Doctor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='medical_records'
    )
    doctor_name = models.CharField(
        _('doctor name'),
        max_length=255,
        blank=True,
        help_text=_("Doktor nomi (arxiv uchun)")
    )
    clinic = models.ForeignKey(
        'clinics.Clinic',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='medical_records'
    )
    clinic_name = models.CharField(
        _('clinic name'),
        max_length=255,
        blank=True,
        help_text=_("Klinika nomi (arxiv uchun)")
    )
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='medical_record'
    )
    chief_complaint = models.TextField(
        _('chief complaint'),
        blank=True,
        help_text=_("Bemorning asosiy shikoyati")
    )
    vital_signs = models.JSONField(
        _('vital signs'),
        blank=True,
        null=True,
        help_text=_("Harorat, bosim, duch-dumi va xokazo")
    )
    examination_findings = models.TextField(
        _('examination findings'),
        blank=True,
        help_text=_("Jismoniy tekshiruv natijasi")
    )
    assessment = models.TextField(
        _('assessment'),
        blank=True,
        help_text=_("Doktorning baholash va tashxisi")
    )
    plan = models.TextField(
        _('plan'),
        blank=True,
        help_text=_("Davolash rejasi va tavsiyalar")
    )
    is_locked = models.BooleanField(
        _('locked'),
        default=False,
        help_text=_("Yozuv yakuniy bo'lsa belgi qo'ying")
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
        verbose_name = _('Medical Record')
        verbose_name_plural = _('Medical Records')
        indexes = [
            models.Index(fields=['patient', '-created_at']),
            models.Index(fields=['doctor', '-created_at']),
        ]
    
    def save(self, *args, **kwargs):
        # Avtomatik ravishda doctor va clinic nomlarini saqlash
        if self.doctor and not self.doctor_name:
            self.doctor_name = self.doctor.user.get_full_name()
        if self.clinic and not self.clinic_name:
            self.clinic_name = self.clinic.name
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Medical Record - {self.patient.user.get_full_name()} ({self.created_at.date()})"


class TelegramConversationState(models.Model):
    """Small state machine for Telegram bot interactions (e.g., reschedule flow)."""

    class Action(models.TextChoices):
        RESCHEDULE_AWAITING_DATETIME = 'reschedule_awaiting_datetime', _('Reschedule awaiting datetime')
        RATING_AWAITING_COMMENT = 'rating_awaiting_comment', _('Rating awaiting comment')

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    telegram_user_id = models.BigIntegerField(_('telegram user id'), db_index=True)
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name='telegram_states'
    )
    action = models.CharField(_('action'), max_length=64, choices=Action.choices)
    expires_at = models.DateTimeField(_('expires at'))
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['telegram_user_id', 'expires_at']),
            models.Index(fields=['appointment', 'expires_at']),
        ]

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at


class Diagnosis(models.Model):
    """
    Diagnosis information
    """
    
    CERTAINTY_CHOICES = (
        ('confirmed', _('Tasdiqlangan')),
        ('probable', _('Ehtimol')),
        ('provisional', _('Vaqtiy')),
    )
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    medical_record = models.ForeignKey(
        MedicalRecord,
        on_delete=models.CASCADE,
        related_name='diagnoses'
    )
    diagnosis_code = models.CharField(
        _('diagnosis code'),
        max_length=100,
        blank=True,
        help_text=_("ICD-10 kodi")
    )
    diagnosis_name = models.CharField(
        _('diagnosis name'),
        max_length=500
    )
    certainty = models.CharField(
        _('certainty'),
        max_length=20,
        choices=CERTAINTY_CHOICES,
        default='confirmed'
    )
    notes = models.TextField(
        _('notes'),
        blank=True
    )
    is_primary = models.BooleanField(
        _('primary diagnosis'),
        default=False,
        help_text=_("Asosiy tashxis bo'lsa belgi qo'ying")
    )
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True
    )
    
    class Meta:
        verbose_name = _('Diagnosis')
        verbose_name_plural = _('Diagnoses')
        ordering = ['-is_primary', '-created_at']
    
    def __str__(self):
        return self.diagnosis_name


class Prescription(models.Model):
    """
    Medicine prescription
    """
    
    STATUS_CHOICES = (
        ('active', _('Aktiv')),
        ('completed', _('Bajarilgan')),
        ('expired', _('Muddati tugagan')),
        ('cancelled', _('Bekor qilingan')),
    )
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    medical_record = models.ForeignKey(
        MedicalRecord,
        on_delete=models.CASCADE,
        related_name='prescriptions'
    )
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.CASCADE,
        related_name='prescriptions'
    )
    doctor = models.ForeignKey(
        'doctors.Doctor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prescriptions',
        help_text=_("Retsept bergan doktor (o'chirilgan bo'lsa NULL)")
    )
    doctor_name = models.CharField(
        _('doctor name'),
        max_length=255,
        blank=True,
        help_text=_("Doktor nomi (arxiv uchun)")
    )
    medicine = models.ForeignKey(
        'pharmacies.Medicine',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prescriptions'
    )
    dosage = models.CharField(
        _('dosage'),
        max_length=200,
        help_text=_("masalan, 1 tabletka, kun 3 marta")
    )
    frequency = models.CharField(
        _('frequency'),
        max_length=200,
        help_text=_("qancha muddat davomida")
    )
    duration_days = models.PositiveIntegerField(
        _('duration in days'),
        default=7
    )
    instructions = models.TextField(
        _('special instructions'),
        blank=True,
        help_text=_("Qo'shimcha ko'rsatmalar")
    )
    quantity = models.PositiveIntegerField(
        _('quantity'),
        default=1
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
    issued_date = models.DateTimeField(
        _('issued date'),
        auto_now_add=True
    )
    expiry_date = models.DateField(
        _('expiry date'),
        blank=True,
        null=True,
        help_text=_("Retsept qancha vaqtgacha haqiqiy")
    )
    filled_at_pharmacy = models.ForeignKey(
        'pharmacies.Pharmacy',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prescriptions'
    )
    is_filled = models.BooleanField(
        _('filled'),
        default=False
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
        ordering = ['-issued_date']
        verbose_name = _('Prescription')
        verbose_name_plural = _('Prescriptions')
        indexes = [
            models.Index(fields=['patient', 'status']),
            models.Index(fields=['doctor', '-issued_date']),
            models.Index(fields=['expiry_date']),
        ]
    
    def save(self, *args, **kwargs):
        """Auto-populate archive fields"""
        if self.doctor and not self.doctor_name:
            self.doctor_name = self.doctor.user.get_full_name()
        super().save(*args, **kwargs)
    
    def __str__(self):
        medicine_name = self.medicine.name if self.medicine else "Unknown"
        doctor_name = self.doctor_name if self.doctor_name else (
            self.doctor.user.get_full_name() if self.doctor else "O'chirilgan doktor"
        )
        return f"{self.patient.user.get_full_name()} - {medicine_name} (Dr. {doctor_name})"


class LabTest(models.Model):
    """
    Laboratory test orders and results
    """
    
    STATUS_CHOICES = (
        ('ordered', _('Muddaao etilgan')),
        ('in_progress', _('Davom etayotgan')),
        ('completed', _('Bajarilgan')),
        ('cancelled', _('Bekor qilingan')),
    )
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    medical_record = models.ForeignKey(
        MedicalRecord,
        on_delete=models.CASCADE,
        related_name='lab_tests'
    )
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.CASCADE,
        related_name='lab_tests'
    )
    doctor = models.ForeignKey(
        'doctors.Doctor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lab_tests',
        help_text=_("Laboratoriya testini buyurgan doktor (o'chirilgan bo'lsa NULL)")
    )
    doctor_name = models.CharField(
        _('doctor name'),
        max_length=255,
        blank=True,
        help_text=_("Doktor nomi (arxiv uchun)")
    )
    test_name = models.CharField(
        _('test name'),
        max_length=255
    )
    test_code = models.CharField(
        _('test code'),
        max_length=100,
        blank=True
    )
    description = models.TextField(
        _('description'),
        blank=True
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='ordered'
    )
    ordered_date = models.DateTimeField(
        _('ordered date'),
        auto_now_add=True
    )
    scheduled_date = models.DateField(
        _('scheduled date'),
        blank=True,
        null=True
    )
    completed_date = models.DateTimeField(
        _('completed date'),
        blank=True,
        null=True
    )
    results = models.JSONField(
        _('test results'),
        blank=True,
        null=True,
        help_text=_("Sinov natijalarini JSON formatida")
    )
    normal_range = models.CharField(
        _('normal range'),
        max_length=255,
        blank=True
    )
    notes = models.TextField(
        _('notes'),
        blank=True
    )
    
    class Meta:
        ordering = ['-ordered_date']
        verbose_name = _('Lab Test')
        verbose_name_plural = _('Lab Tests')
        indexes = [
            models.Index(fields=['patient', 'status']),
            models.Index(fields=['ordered_date']),
        ]
    
    def save(self, *args, **kwargs):
        """Auto-populate archive fields"""
        if self.doctor and not self.doctor_name:
            self.doctor_name = self.doctor.user.get_full_name()
        super().save(*args, **kwargs)
    
    def __str__(self):
        doctor_name = self.doctor_name if self.doctor_name else (
            self.doctor.user.get_full_name() if self.doctor else "O'chirilgan doktor"
        )
        return f"{self.patient.user.get_full_name()} - {self.test_name} (Dr. {doctor_name})"
