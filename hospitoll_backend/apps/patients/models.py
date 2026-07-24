from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from uuid import uuid4


class Patient(models.Model):
    """
    Patient model linked to CustomUser.
    Patients can be associated with multiple clinics and doctors.
    """
    
    BLOOD_TYPE_CHOICES = (
        ('O+', 'O+'),
        ('O-', 'O-'),
        ('A+', 'A+'),
        ('A-', 'A-'),
        ('B+', 'B+'),
        ('B-', 'B-'),
        ('AB+', 'AB+'),
        ('AB-', 'AB-'),
    )
    
    GENDER_CHOICES = (
        ('male', _('Erkak')),
        ('female', _('Ayol')),
        ('other', _('Boshqa')),
    )
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    user = models.OneToOneField(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='patient',
        limit_choices_to={'role': 'patient'}
    )
    clinics = models.ManyToManyField(
        'clinics.Clinic',
        related_name='patients',
        blank=True,
        help_text=_("Bemor bog'langan klinikalar")
    )
    gender = models.CharField(
        _('gender'),
        max_length=20,
        choices=GENDER_CHOICES,
        blank=True
    )
    date_of_birth = models.DateField(
        _('date of birth'),
        blank=True,
        null=True
    )
    birth_year = models.PositiveSmallIntegerField(
        _('birth year'),
        blank=True,
        null=True,
        validators=[MinValueValidator(1900), MaxValueValidator(2100)],
        help_text=_('Bemor tug‘ilgan yili (ixtiyoriy).')
    )
    age = models.PositiveSmallIntegerField(
        _('age'),
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(130)],
        help_text=_('Bemor yoshi (ixtiyoriy). Agar date_of_birth bo\'lsa, yosh avtomatik hisoblanadi.')
    )
    blood_type = models.CharField(
        _('blood type'),
        max_length=10,
        choices=BLOOD_TYPE_CHOICES,
        blank=True
    )
    insurance_id = models.CharField(
        _('insurance ID'),
        max_length=100,
        blank=True,
        null=True
    )
    phone_number = models.CharField(
        _('phone number'),
        max_length=20,
        blank=True
    )
    address = models.CharField(
        _('address'),
        max_length=500,
        blank=True
    )
    city = models.CharField(
        _('city'),
        max_length=100,
        blank=True
    )
    country = models.CharField(
        _('country'),
        max_length=100,
        default='Uzbekistan'
    )
    emergency_contact_name = models.CharField(
        _('emergency contact name'),
        max_length=255,
        blank=True
    )
    emergency_contact_phone = models.CharField(
        _('emergency contact phone'),
        max_length=20,
        blank=True
    )
    allergies = models.TextField(
        _('allergies'),
        blank=True,
        help_text=_("Bemor allergialariga haqida ma'lumot")
    )
    drug_allergies = models.TextField(
        _('drug allergies'),
        blank=True,
        help_text=_("Dorilarga allergiya haqida ma'lumot")
    )
    animal_allergies = models.TextField(
        _('animal allergies'),
        blank=True,
        help_text=_("Hayvonlarga allergiya haqida ma'lumot")
    )
    weight_kg = models.DecimalField(
        _('weight (kg)'),
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0.0)],
        help_text=_('Bemor vazni kilogrammda (ixtiyoriy).')
    )
    height_cm = models.DecimalField(
        _('height (cm)'),
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0.0)],
        help_text=_('Bemor bo‘yi santimetrda (ixtiyoriy).')
    )
    chronic_diseases = models.TextField(
        _('chronic diseases'),
        blank=True,
        help_text=_("Surunkali kasalliklari")
    )
    medications = models.TextField(
        _('medications'),
        blank=True,
        help_text=_("Hozirda qabul qilyotgan dorilar")
    )
    no_show_count = models.PositiveSmallIntegerField(
        _('no show count'),
        default=0,
        help_text=_('How many times the patient was marked as NO_SHOW')
    )
    requires_deposit = models.BooleanField(
        _('requires deposit'),
        default=False,
        help_text=_('If true, patient must pay deposit before booking next appointment')
    )
    is_active = models.BooleanField(
        _('active'),
        default=True
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
        verbose_name = _('Patient')
        verbose_name_plural = _('Patients')
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return self.user.get_full_name()
    
    @property
    def calculated_age(self):
        if self.date_of_birth:
            from datetime import date
            today = date.today()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None


class PatientMedicalHistory(models.Model):
    """
    Patient's past medical history and procedures
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name='medical_history'
    )
    condition = models.CharField(
        _('condition'),
        max_length=255
    )
    description = models.TextField(
        _('description'),
        blank=True
    )
    diagnosed_date = models.DateField(
        _('diagnosed date'),
        blank=True,
        null=True
    )
    status = models.CharField(
        _('status'),
        max_length=50,
        default='ongoing',
        choices=(
            ('ongoing', _('Davom etayotgan')),
            ('recovered', _('Tiklab olingan')),
            ('chronic', _('Surunkali')),
        )
    )
    doctor = models.ForeignKey(
        'doctors.Doctor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True
    )
    
    class Meta:
        verbose_name = _('Medical History')
        verbose_name_plural = _('Medical Histories')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.patient.user.get_full_name()} - {self.condition}"


class PatientDoctorRating(models.Model):
    """
    Ratings given by patients to doctors
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name='doctor_ratings'
    )
    doctor = models.ForeignKey(
        'doctors.Doctor',
        on_delete=models.CASCADE,
        related_name='ratings'
    )
    rating = models.IntegerField(
        _('rating'),
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(
        _('comment'),
        blank=True,
        help_text=_("Reytingi ishiga doir izoh")
    )
    is_anonymous = models.BooleanField(
        _('anonymous'),
        default=False
    )
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True
    )
    
    class Meta:
        unique_together = ('patient', 'doctor')
        verbose_name = _('Doctor Rating')
        verbose_name_plural = _('Doctor Ratings')
    
    def __str__(self):
        return f"{self.patient.user.get_full_name()} rated {self.doctor.user.get_full_name()} {self.rating}/5"
    
    def save(self, *args, **kwargs):
        """Update doctor's average rating after saving"""
        super().save(*args, **kwargs)
        
        # Update doctor's rating statistics
        from django.db.models import Avg, Count
        stats = PatientDoctorRating.objects.filter(doctor=self.doctor).aggregate(
            avg_rating=Avg('rating'),
            total_ratings=Count('id')
        )
        
        self.doctor.rating = round(stats['avg_rating'] or 0.0, 1)
        self.doctor.total_ratings = stats['total_ratings'] or 0
        self.doctor.save(update_fields=['rating', 'total_ratings'])
        
        # Update clinic's rating based on all doctors' ratings
        if self.doctor.clinic:
            clinic = self.doctor.clinic
            all_doctors = clinic.doctors.all()
            if all_doctors.exists():
                clinic_stats = PatientDoctorRating.objects.filter(
                    doctor__clinic=clinic
                ).aggregate(
                    avg_rating=Avg('rating'),
                    total_ratings=Count('id')
                )
                clinic.rating = round(clinic_stats['avg_rating'] or 0.0, 1)
                clinic.total_ratings = clinic_stats['total_ratings'] or 0
                clinic.save(update_fields=['rating', 'total_ratings'])

