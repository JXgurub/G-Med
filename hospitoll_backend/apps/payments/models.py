from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from uuid import uuid4


class Payment(models.Model):
    """
    General payment model for consultation fees, services, etc.
    """
    
    PAYMENT_TYPE_CHOICES = (
        ('consultation', _('Maslahat')),
        ('service', _('Xizmat')),
        ('medicine', _('Dori')),
        ('test', _('Sinov')),
        ('subscription', _('Obuna')),
    )
    
    PAYMENT_STATUS_CHOICES = (
        ('pending', _('Kutilmoqda')),
        ('confirmed', _('Tasdiqlangan')),
        ('failed', _('Muvaffaqiyatsiz')),
        ('cancelled', _('Bekor qilingan')),
        ('refunded', _('Qaytarilgan')),
    )
    
    PAYMENT_METHOD_CHOICES = (
        ('card', _('Bank kartalipsi')),
        ('bank_transfer', _('Bank o\'tkazmasi')),
        ('cash', _('Naqd pul')),
        ('online_wallet', _('Elektron hamyon')),
    )
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    payment_type = models.CharField(
        _('payment type'),
        max_length=50,
        choices=PAYMENT_TYPE_CHOICES
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending'
    )
    clinic = models.ForeignKey(
        'clinics.Clinic',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments_received'
    )
    pharmacy = models.ForeignKey(
        'pharmacies.Pharmacy',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments_received'
    )
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments'
    )
    appointment = models.OneToOneField(
        'medical.Appointment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment'
    )
    description = models.CharField(
        _('description'),
        max_length=500
    )
    amount = models.DecimalField(
        _('amount'),
        max_digits=15,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text=_("So'm da hisob qilinadi")
    )
    payment_method = models.CharField(
        _('payment method'),
        max_length=50,
        choices=PAYMENT_METHOD_CHOICES
    )
    transaction_id = models.CharField(
        _('transaction ID'),
        max_length=255,
        blank=True,
        help_text=_("Xarij to'lovni ID")
    )
    reference_number = models.CharField(
        _('reference number'),
        max_length=255,
        blank=True
    )
    notes = models.TextField(
        _('notes'),
        blank=True
    )
    paid_date = models.DateTimeField(
        _('paid date'),
        null=True,
        blank=True
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
        verbose_name = _('Payment')
        verbose_name_plural = _('Payments')
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['clinic', 'status']),
            models.Index(fields=['patient', 'status']),
        ]
    
    def __str__(self):
        return f"{self.get_payment_type_display()} - {self.amount} SUM ({self.get_status_display()})"
    
    def confirm_payment(self):
        """Mark payment as confirmed"""
        from django.utils import timezone
        self.status = 'confirmed'
        self.paid_date = timezone.now()
        self.save()
        return self


class Invoice(models.Model):
    """
    Invoice model for billing records
    """
    
    STATUS_CHOICES = (
        ('draft', _('Qoralama')),
        ('issued', _('Chiqarilgan')),
        ('paid', _('To\'landi')),
        ('overdue', _('Muddatidan o\'tgan')),
        ('cancelled', _('Bekor qilingan')),
    )
    
    PAYMENT_STATUS_CHOICES = (
        ('not_initiated', _('Boshlangani yo\'q')),
        ('initiated', _('Boshlangan')),
        ('pending_payment', _('To\'lov kutilmoqda')),
        ('completed', _('Yakunlangan')),
        ('failed', _('Muvaffaqiyatsiz')),
        ('cancelled', _('Bekor qilingan')),
        ('paid', _('To\'landi')),
    )
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    invoice_number = models.CharField(
        _('invoice number'),
        max_length=100,
        unique=True
    )
    clinic = models.ForeignKey(
        'clinics.Clinic',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices_issued'
    )
    pharmacy = models.ForeignKey(
        'pharmacies.Pharmacy',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices_issued'
    )
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices'
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    total_amount = models.DecimalField(
        _('total amount'),
        max_digits=15,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )
    tax_amount = models.DecimalField(
        _('tax amount'),
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )
    discount_amount = models.DecimalField(
        _('discount amount'),
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )
    net_amount = models.DecimalField(
        _('net amount'),
        max_digits=15,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )
    paid_amount = models.DecimalField(
        _('paid amount'),
        max_digits=15,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )
    payment_terms = models.CharField(
        _('payment terms'),
        max_length=255,
        blank=True
    )
    due_date = models.DateField(
        _('due date'),
        blank=True,
        null=True
    )
    issued_date = models.DateField(
        _('issued date'),
        auto_now_add=True
    )
    paid_date = models.DateField(
        _('paid date'),
        null=True,
        blank=True
    )
    notes = models.TextField(
        _('notes'),
        blank=True
    )
    # Payment processing fields
    payment_status = models.CharField(
        _('payment status'),
        max_length=50,
        choices=PAYMENT_STATUS_CHOICES,
        default='not_initiated'
    )
    payment_order_id = models.CharField(
        _('payment order ID'),
        max_length=255,
        blank=True,
        help_text=_("Click to'lov buyurtmasi ID")
    )
    payment_transaction_id = models.CharField(
        _('payment transaction ID'),
        max_length=255,
        blank=True,
        help_text=_("Click operatsiya ID")
    )
    payment_initiated_at = models.DateTimeField(
        _('payment initiated at'),
        null=True,
        blank=True,
        help_text=_("To'lov jarayoni boshlangan vaqti")
    )
    payment_confirmed_at = models.DateTimeField(
        _('payment confirmed at'),
        null=True,
        blank=True,
        help_text=_("To'lov tasdiqlangan vaqti")
    )
    payment_cancelled_at = models.DateTimeField(
        _('payment cancelled at'),
        null=True,
        blank=True,
        help_text=_("To'lov bekor qilingan vaqti")
    )
    payment_method = models.CharField(
        _('payment method'),
        max_length=50,
        choices=[
            ('click', _('Click')),
            ('stripe', _('Stripe')),
            ('cash', _('Naqd pul')),
            ('transfer', _('Bank o\'tkazmasi')),
        ],
        blank=True,
        help_text=_("To'lov usuli")
    )
    amount = models.DecimalField(
        _('amount'),
        max_digits=15,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text=_("So'm da hisob qilinadi")
    )
    description = models.TextField(
        _('description'),
        blank=True,
        help_text=_("To'lov tavsifi")
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
        verbose_name = _('Invoice')
        verbose_name_plural = _('Invoices')
        indexes = [
            models.Index(fields=['invoice_number']),
            models.Index(fields=['status']),
            models.Index(fields=['patient', 'status']),
        ]
    
    def __str__(self):
        return f"Invoice {self.invoice_number}"
    
    def calculate_total_with_tax(self):
        """Calculate total amount including tax"""
        return self.total_amount + self.tax_amount - self.discount_amount
