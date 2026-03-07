from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta
from uuid import uuid4


class SubscriptionPlan(models.Model):
    """
    Available subscription plans
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    name = models.CharField(
        _('plan name'),
        max_length=255,
        unique=True
    )
    description = models.TextField(
        _('description'),
        blank=True
    )
    price = models.DecimalField(
        _('monthly price'),
        max_digits=10,
        decimal_places=2,
        help_text=_("So'm da hisob qilinadi")
    )
    duration_days = models.PositiveIntegerField(
        _('duration in days'),
        default=30,
        help_text=_("Obuna muddat kunlarda")
    )
    max_doctors = models.PositiveIntegerField(
        _('max doctors'),
        null=True,
        blank=True,
        help_text=_("Ortiqcha doktorlar soni (bo'sh = cheksiz)")
    )
    max_patients = models.PositiveIntegerField(
        _('max patients'),
        null=True,
        blank=True,
        help_text=_("Ortiqcha bemorlar soni (bo'sh = cheksiz)")
    )
    features = models.JSONField(
        _('features'),
        blank=True,
        null=True,
        help_text=_("Rejaning xususiyatlari")
    )
    is_active = models.BooleanField(
        _('active'),
        default=True
    )
    sort_order = models.PositiveIntegerField(
        _('sort order'),
        default=0
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
        ordering = ['sort_order']
        verbose_name = _('Subscription Plan')
        verbose_name_plural = _('Subscription Plans')
    
    def __str__(self):
        return f"{self.name} - {self.price} SUM"


class Subscription(models.Model):
    """
    Subscription model for clinics and pharmacies.
    Handles subscription lifecycle and payment confirmation.
    """
    
    SUBSCRIBER_TYPE_CHOICES = (
        ('clinic', _('Klinika')),
        ('pharmacy', _('Dorixona')),
    )
    
    STATUS_CHOICES = (
        ('trial', _('Sinov davri')),
        ('pending_payment', _('To\'lov kutilmoqda')),
        ('active', _('Aktiv')),
        ('expired', _('Muddati tugagan')),
        ('cancelled', _('Bekor qilingan')),
        ('suspended', _('To\'xtatilgan')),
    )
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    subscriber_type = models.CharField(
        _('subscriber type'),
        max_length=20,
        choices=SUBSCRIBER_TYPE_CHOICES
    )
    clinic = models.OneToOneField(
        'clinics.Clinic',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subscription'
    )
    pharmacy = models.OneToOneField(
        'pharmacies.Pharmacy',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subscription'
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name='subscriptions'
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='trial'
    )
    start_date = models.DateTimeField(
        _('start date'),
        auto_now_add=True
    )
    end_date = models.DateTimeField(
        _('end date'),
        null=True,
        blank=True
    )
    trial_period_days = models.PositiveIntegerField(
        _('trial period days'),
        default=7,
        help_text=_("Sinov davri kunlarda")
    )
    trial_end_date = models.DateTimeField(
        _('trial end date'),
        null=True,
        blank=True
    )
    payment_confirmation_date = models.DateTimeField(
        _('payment confirmation date'),
        null=True,
        blank=True,
        help_text=_("To'lov tasdiqlangan sana")
    )
    auto_renewal = models.BooleanField(
        _('auto renewal'),
        default=True,
        help_text=_("Obuna avtomatik yangilansin mi")
    )
    days_until_expiry = models.IntegerField(
        _('days until expiry'),
        default=30,
        help_text=_("Qancha kundan keyin obuna tugaydi")
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
        verbose_name = _('Subscription')
        verbose_name_plural = _('Subscriptions')
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['end_date']),
        ]
    
    def __str__(self):
        subscriber_name = self.clinic.name if self.clinic else self.pharmacy.name
        return f"{subscriber_name} - {self.plan.name}"
    
    def get_subscriber(self):
        """Get the clinic or pharmacy this subscription belongs to"""
        return self.clinic or self.pharmacy
    
    def activate_by_payment(self):
        """
        Activate subscription when payment is confirmed.
        Sets active status and adds 30 days to subscription.
        """
        now = timezone.now()
        self.status = 'active'
        self.payment_confirmation_date = now
        self.end_date = now + timedelta(days=30)
        self.save()
        return self
    
    def is_expired(self):
        """Check if subscription has expired"""
        if self.end_date:
            return timezone.now() > self.end_date
        return False
    
    def days_remaining(self):
        """Calculate days remaining until expiry"""
        if self.end_date:
            delta = self.end_date - timezone.now()
            return max(0, delta.days)
        return None
    
    def auto_deactivate_if_expired(self):
        """
        Automatically deactivate subscription if expired.
        Updates related clinic/pharmacy status to inactive.
        """
        if self.is_expired() and self.status == 'active':
            self.status = 'expired'
            subscriber = self.get_subscriber()
            if subscriber:
                subscriber.status = 'inactive'
                subscriber.save()
            self.save()
            return True
        return False


class SubscriptionPayment(models.Model):
    """
    Track subscription payments
    """
    
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
        ('check', _('Chek')),
    )
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    amount = models.DecimalField(
        _('amount'),
        max_digits=15,
        decimal_places=2,
        help_text=_("So'm da hisob qilinadi")
    )
    payment_method = models.CharField(
        _('payment method'),
        max_length=50,
        choices=PAYMENT_METHOD_CHOICES
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending'
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
        blank=True,
        help_text=_("Bank referenciya raqami")
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
        verbose_name = _('Subscription Payment')
        verbose_name_plural = _('Subscription Payments')
        indexes = [
            models.Index(fields=['subscription', 'status']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.subscription} - {self.amount} SUM ({self.get_status_display()})"
    
    def confirm_payment(self):
        """
        Confirm payment and activate subscription
        """
        self.status = 'confirmed'
        self.paid_date = timezone.now()
        self.save()
        self.subscription.activate_by_payment()
        return self
