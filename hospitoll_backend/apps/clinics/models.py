from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import URLValidator, MinValueValidator
from django.utils import timezone
from uuid import uuid4
import uuid as uuid_lib


class Clinic(models.Model):
    """
    Clinic model representing healthcare facilities.
    Each clinic can have multiple doctors and patients.
    """
    
    STATUS_CHOICES = (
        ('active', _('Aktiv')),
        ('inactive', _('Faolsiz')),
        ('suspended', _('To\'xtatilgan')),
        ('trial', _('Sinov davri')),
    )
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    owner = models.OneToOneField(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='clinic',
        limit_choices_to={'role': 'clinic'},
        help_text=_("Klinika egasi")
    )
    owner_passport_id = models.CharField(
        _('owner passport id'),
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
        help_text=_("Klinika egasining pasport yoki ID raqami")
    )
    name = models.CharField(
        _('clinic name'),
        max_length=255,
        unique=True
    )
    slug = models.SlugField(
        _('slug'),
        unique=True,
        help_text=_("URL uchun noyob identifikator")
    )
    description = models.TextField(
        _('description'),
        blank=True,
        help_text=_("Klinika haqida qisqacha ma'lumot")
    )
    address = models.CharField(
        _('address'),
        max_length=500,
        help_text=_("Klinikaning manzili")
    )
    phone_number = models.CharField(
        _('phone number'),
        max_length=20,
        help_text=_("Klinikaning telefon raqami")
    )
    email = models.EmailField(
        _('email'),
        help_text=_("Klinikaning email manzili")
    )
    website = models.URLField(
        _('website'),
        blank=True,
        null=True,
        validators=[URLValidator()]
    )
    registration_number = models.CharField(
        _('registration number'),
        max_length=100,
        unique=True,
        help_text=_("Noyob ro'yxatdan o'tish raqami")
    )
    license_document = models.FileField(
        _('license document'),
        upload_to='clinic_licenses/%Y/%m/%d/',
        blank=True,
        null=True
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='trial'
    )
    is_verified = models.BooleanField(
        _('verified'),
        default=False,
        help_text=_("Administrator tomonidan tasdiqlangan")
    )
    is_blocked = models.BooleanField(
        _('blocked'),
        default=False,
        help_text=_("Administratorning to'saxalini")
    )
    logo = models.ImageField(
        _('logo'),
        upload_to='clinic_logos/%Y/%m/%d/',
        blank=True,
        null=True
    )
    banner_image = models.ImageField(
        _('banner image'),
        upload_to='clinic_banners/%Y/%m/%d/',
        blank=True,
        null=True
    )
    established_date = models.DateField(
        _('established date'),
        blank=True,
        null=True
    )
    rating = models.FloatField(
        _('rating'),
        default=0.0,
        validators=[MinValueValidator(0.0)],
        help_text=_("Foydalanuvchilar bergan o'rtacha reytingi (0-5)")
    )
    total_ratings = models.PositiveIntegerField(
        _('total ratings'),
        default=0,
        help_text=_("Jami reytingi bergan foydalanuvchilar soni")
    )
    working_hours = models.CharField(
        _('working hours'),
        max_length=100,
        default='09:00 - 18:00',
        help_text=_("Masalan: 09:00 - 18:00")
    )
    attendance_enabled = models.BooleanField(
        _('doctor attendance enabled'),
        default=False,
        help_text=_("Doktor ishga kelish va ketishini belgilashi mumkin")
    )
    diagnosis_entry_enabled = models.BooleanField(
        _('diagnosis entry enabled'),
        default=False,
        help_text=_("Bemor qabul qilinganda tashxis formasini avtomatik ochish")
    )
    reception_room_enabled = models.BooleanField(
        _('reception room enabled'),
        default=False,
        help_text=_("Qabul xonasi navbat logikasini yoqish")
    )
    queue_ticket_clinic_name = models.CharField(
        _('queue ticket clinic name'),
        max_length=255,
        blank=True,
        default='',
        help_text=_("Navbat qog'ozida ko'rsatiladigan klinika nomi")
    )
    queue_ticket_clinic_address = models.CharField(
        _('queue ticket clinic address'),
        max_length=500,
        blank=True,
        default='',
        help_text=_("Navbat qog'ozida ko'rsatiladigan klinika manzili")
    )
    queue_ticket_contact_url = models.CharField(
        _('queue ticket contact url'),
        max_length=255,
        blank=True,
        default='',
        help_text=_("Navbat qog'ozida ko'rsatiladigan Telegram/Instagram/yoki URL")
    )
    QUEUE_TICKET_NUMBER_SIZE_CHOICES = (
        ('small', _('Kichik')),
        ('medium', _('O‘rta')),
        ('large', _('Katta')),
    )
    queue_ticket_number_size = models.CharField(
        _('queue ticket number size'),
        max_length=10,
        choices=QUEUE_TICKET_NUMBER_SIZE_CHOICES,
        default='large',
        help_text=_('Navbat raqamining qog‘ozdagi shrift o‘lchami')
    )
    amount = models.DecimalField(
        _('payment amount'),
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text=_("To'lov miqdori")
    )
    payment_description = models.TextField(
        _('payment description'),
        blank=True,
        help_text=_("To'lov haqida ta'rif")
    )
    payment_date = models.DateTimeField(
        _('payment date'),
        null=True,
        blank=True,
        help_text=_("To'lov miqdori o'rnatilgan sana")
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
        verbose_name = _('Clinic')
        verbose_name_plural = _('Clinics')
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['registration_number']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"
    
    @property
    def is_active_status(self):
        return self.status == 'active' and not self.is_blocked
    
    @property
    def doctors_count(self):
        return self.doctors.filter(is_active=True).count()
    
    @property
    def patients_count(self):
        return self.patients.filter(is_active=True).count()


class ReceptionStaff(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='reception_staff')
    pinfl = models.CharField(max_length=14)
    passport_id = models.CharField(max_length=50)
    date_of_birth = models.DateField()
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    password_hash = models.CharField(max_length=128, blank=True)
    compensation_type = models.CharField(max_length=20, default='salary', choices=(('salary', 'Ish haqi'), ('percent', 'Foiz')))
    compensation_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    available_from = models.TimeField(default='09:00')
    available_until = models.TimeField(default='18:00')
    lunch_break_start = models.TimeField(null=True, blank=True)
    lunch_break_end = models.TimeField(null=True, blank=True)
    working_days = models.CharField(max_length=100, default='Mon,Tue,Wed,Thu,Fri')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['first_name', 'last_name']
        indexes = [models.Index(fields=['clinic', 'is_active'])]

    def __str__(self):
        return f'{self.first_name} {self.last_name}'


class ReceptionStaffWorkRecord(models.Model):
    staff = models.ForeignKey(ReceptionStaff, on_delete=models.CASCADE, related_name='work_records')
    date = models.DateField()
    checked_in_at = models.TimeField(null=True, blank=True)
    checked_out_at = models.TimeField(null=True, blank=True)
    patients_count = models.PositiveIntegerField(default=0)
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['staff', 'date'], name='unique_reception_staff_work_day')]
        ordering = ['-date']

    def __str__(self):
        return f'{self.staff} - {self.date}'


class ClinicDepartment(models.Model):
    """
    Department within a clinic (e.g., Cardiology, Pediatrics, etc.)
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name='departments'
    )
    name = models.CharField(
        _('department name'),
        max_length=255
    )
    description = models.TextField(
        _('description'),
        blank=True
    )
    head_doctor = models.ForeignKey(
        'doctors.Doctor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='headed_departments'
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
        unique_together = ('clinic', 'name')
        verbose_name = _('Department')
        verbose_name_plural = _('Departments')
    
    def __str__(self):
        return f"{self.clinic.name} - {self.name}"


class ClinicService(models.Model):
    """
    Services offered by a clinic (e.g., Consultation, Surgery, Lab Tests, etc.)
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name='services'
    )
    department = models.ForeignKey(
        ClinicDepartment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='services'
    )
    name = models.CharField(
        _('service name'),
        max_length=255
    )
    description = models.TextField(
        _('description'),
        blank=True
    )
    price = models.DecimalField(
        _('price'),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text=_("So'm da hisob qilinadi")
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
        verbose_name = _('Service')
        verbose_name_plural = _('Services')
        indexes = [
            models.Index(fields=['clinic', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.clinic.name} - {self.name}"


class ClinicStaffMessage(models.Model):
    """A message from a clinic owner to clinic staff (doctors)."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    clinic = models.ForeignKey('clinics.Clinic', on_delete=models.CASCADE, related_name='staff_messages')
    sender = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='sent_clinic_staff_messages')
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['clinic', '-created_at'], name='clinics_cli_clinic__08aa05_idx'),
            models.Index(fields=['sender', '-created_at'], name='clinics_cli_sender__f3df0c_idx'),
        ]

    def __str__(self):
        return f"ClinicStaffMessage({self.clinic_id}, {self.sender_id}, {self.created_at})"


class ClinicStaffMessageRecipient(models.Model):
    """Per-recipient delivery status for clinic staff messages."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    message = models.ForeignKey('clinics.ClinicStaffMessage', on_delete=models.CASCADE, related_name='recipients')
    recipient = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='clinic_staff_message_recipients')
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-delivered_at']
        constraints = [
            models.UniqueConstraint(fields=['message', 'recipient'], name='uniq_clinic_staff_message_recipient'),
        ]
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-delivered_at'], name='clinics_cli_recipie_8fd2b9_idx'),
            models.Index(fields=['message', '-delivered_at'], name='clinics_cli_message_9d252f_idx'),
        ]

    def __str__(self):
        return f"ClinicStaffMessageRecipient({self.recipient_id}, read={self.is_read})"
