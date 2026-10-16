from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, URLValidator
from uuid import uuid4


class Pharmacy(models.Model):
    """
    Pharmacy model representing medicine dispensaries.
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
        related_name='pharmacy',
        limit_choices_to={'role': 'pharmacy'},
        help_text=_("Dorixona egasi")
    )
    owner_passport_id = models.CharField(
        _('owner passport id'),
        max_length=32,
        blank=True,
        default='',
        help_text=_("Dorixona egasining pasport IDsi")
    )
    name = models.CharField(
        _('pharmacy name'),
        max_length=255,
        unique=True
    )
    slug = models.SlugField(
        _('slug'),
        unique=True
    )
    description = models.TextField(
        _('description'),
        blank=True
    )
    registration_number = models.CharField(
        _('registration number'),
        max_length=100,
        unique=True,
        help_text=_("Noyob ro'yxatdan o'tish raqami")
    )
    license_document = models.FileField(
        _('license document'),
        upload_to='pharmacy_licenses/%Y/%m/%d/',
        blank=True,
        null=True
    )
    address = models.CharField(
        _('address'),
        max_length=500
    )
    phone_number = models.CharField(
        _('phone number'),
        max_length=20
    )
    email = models.EmailField(
        _('email')
    )
    website = models.URLField(
        _('website'),
        blank=True,
        null=True,
        validators=[URLValidator()]
    )
    receipt_show_address = models.BooleanField(
        _('show address on receipt'),
        default=True,
        help_text=_('Dorixona chekida manzilni chiqarish')
    )
    receipt_show_phone = models.BooleanField(
        _('show phone on receipt'),
        default=True,
        help_text=_('Dorixona chekida telefon raqamini chiqarish')
    )
    receipt_show_website = models.BooleanField(
        _('show website on receipt'),
        default=False,
        help_text=_('Dorixona chekida sayt havolasini chiqarish')
    )
    receipt_instagram_url = models.CharField(
        _('receipt Instagram URL'),
        max_length=255,
        blank=True,
        default='',
        help_text=_('Chekda chiqariladigan Instagram manzili yoki nomi')
    )
    receipt_show_instagram = models.BooleanField(
        _('show Instagram on receipt'),
        default=False,
        help_text=_('Dorixona chekida Instagram manzilini chiqarish')
    )
    logo = models.ImageField(
        _('logo'),
        upload_to='pharmacy_logos/%Y/%m/%d/',
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
        default=False
    )
    is_blocked = models.BooleanField(
        _('blocked'),
        default=False
    )
    rating = models.FloatField(
        _('rating'),
        default=0.0,
        validators=[MinValueValidator(0.0)]
    )
    total_ratings = models.PositiveIntegerField(
        _('total ratings'),
        default=0
    )
    working_hours = models.CharField(
        _('working hours'),
        max_length=100,
        default='09:00 - 20:00',
        help_text=_("Masalan: 09:00 - 20:00")
    )
    established_date = models.DateField(
        _('established date'),
        blank=True,
        null=True
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
        verbose_name = _('Pharmacy')
        verbose_name_plural = _('Pharmacies')
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return self.name
    
    @property
    def is_active_status(self):
        return self.status == 'active' and not self.is_blocked


class Medicine(models.Model):
    """
    Medicine/Drug model
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    name = models.CharField(
        _('medicine name'),
        max_length=255
    )
    generic_name = models.CharField(
        _('generic name'),
        max_length=255,
        blank=True
    )
    atc_code = models.CharField(
        _('ATC code'),
        max_length=100,
        blank=True,
        help_text=_("Anatomical Therapeutic Chemical kod")
    )
    description = models.TextField(
        _('description'),
        blank=True
    )
    category = models.CharField(
        _('category'),
        max_length=120,
        default='Boshqa',
        blank=True,
        help_text=_('Dori kategoriyasi')
    )
    dosage_form = models.CharField(
        _('dosage form'),
        max_length=100,
        blank=True,
        help_text=_("masalan, tabletka, suyuqlik, injeksiya")
    )
    strength = models.CharField(
        _('strength'),
        max_length=100,
        blank=True,
        help_text=_("masalan, 500mg, 2%")
    )
    manufacturer = models.CharField(
        _('manufacturer'),
        max_length=255,
        blank=True
    )
    country_of_origin = models.CharField(
        _('country of origin'),
        max_length=120,
        blank=True,
        help_text=_('Dori ishlab chiqarilgan davlat')
    )
    is_prescription_required = models.BooleanField(
        _('prescription required'),
        default=False,
        help_text=_("Retseptli dori shahar qo'yilsa belgi qo'ying")
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
        verbose_name = _('Medicine')
        verbose_name_plural = _('Medicines')
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['atc_code']),
            models.Index(fields=['category']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.strength})" if self.strength else self.name


class PharmacyMarchandise(models.Model):
    """
    Medicines available at each pharmacy
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.CASCADE,
        related_name='medicines'
    )
    medicine = models.ForeignKey(
        Medicine,
        on_delete=models.CASCADE,
        related_name='pharmacy_stocks'
    )
    batch_number = models.CharField(
        _('batch number'),
        max_length=100,
        blank=True
    )
    expiry_date = models.DateField(
        _('expiry date')
    )
    quantity_in_stock = models.PositiveIntegerField(
        _('quantity in stock'),
        default=0
    )
    unit_price = models.DecimalField(
        _('unit price'),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text=_("So'm da hisob qilinadi")
    )
    is_available = models.BooleanField(
        _('available'),
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
        unique_together = ('pharmacy', 'medicine', 'batch_number')
        verbose_name = _('Pharmacy Merchandise')
        verbose_name_plural = _('Pharmacy Merchandise')
        indexes = [
            models.Index(fields=['pharmacy', 'is_available']),
            models.Index(fields=['expiry_date']),
        ]
    
    def __str__(self):
        return f"{self.pharmacy.name} - {self.medicine.name}"


class PharmacyPosDevice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.CASCADE,
        related_name='pos_devices',
    )
    name = models.CharField(max_length=120)
    activation_code_hash = models.CharField(max_length=64, blank=True)
    activation_code_created_at = models.DateTimeField(null=True, blank=True)
    client_id = models.UUIDField(null=True, blank=True, unique=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.pharmacy.name} - {self.name}"


class PharmacySale(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.CASCADE,
        related_name='pos_sales',
    )
    device = models.ForeignKey(
        PharmacyPosDevice,
        on_delete=models.PROTECT,
        related_name='sales',
    )
    sold_at = models.DateTimeField()
    total = models.DecimalField(max_digits=12, decimal_places=2)
    synced_at = models.DateTimeField(auto_now_add=True)
    has_stock_discrepancy = models.BooleanField(default=False)

    class Meta:
        ordering = ['-sold_at']
        indexes = [
            models.Index(fields=['pharmacy', 'sold_at']),
            models.Index(fields=['device', 'sold_at']),
        ]


class PharmacySaleLine(models.Model):
    sale = models.ForeignKey(
        PharmacySale,
        on_delete=models.CASCADE,
        related_name='lines',
    )
    inventory = models.ForeignKey(
        PharmacyMarchandise,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pos_sale_lines',
    )
    medicine = models.ForeignKey(
        Medicine,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pos_sale_lines',
    )
    medicine_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    stock_shortfall = models.PositiveIntegerField(default=0)
    stock_mismatch = models.BooleanField(default=False)
