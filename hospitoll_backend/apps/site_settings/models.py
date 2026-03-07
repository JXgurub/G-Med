from uuid import uuid4

from django.db import models
from django.utils.translation import gettext_lazy as _


class HomeContactSettings(models.Model):
    """Singleton-like settings for the Home page contact (Bog'lanish) section."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)

    text = models.TextField(_('text'), blank=True, default='')

    telegram_link = models.URLField(_('telegram link'), blank=True, default='')
    phone_number = models.CharField(_('phone number'), max_length=50, blank=True, default='')
    instagram_link = models.URLField(_('instagram link'), blank=True, default='')
    email = models.EmailField(_('email'), blank=True, default='')
    email_display = models.CharField(
        _('email display'),
        max_length=255,
        blank=True,
        default='',
        help_text=_('Frontendda ko‘rinadigan email. Ixtiyoriy (masalan: support@yourdomain.uz).')
    )

    image = models.ImageField(
        _('contact image'),
        upload_to='home_contact/%Y/%m/%d/',
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('Home Contact Settings')
        verbose_name_plural = _('Home Contact Settings')
        ordering = ['-updated_at']

    def __str__(self):
        return 'HomeContactSettings'

    @classmethod
    def get_solo(cls):
        obj = cls.objects.first()
        if obj:
            return obj
        return cls.objects.create()


class ContactLead(models.Model):
    """Lead capture from Contact page."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)

    name = models.CharField(_('name'), max_length=255, blank=True, default='')
    phone_number = models.CharField(_('phone number'), max_length=50, blank=True, default='')
    email = models.EmailField(_('email'), blank=True, default='')
    message = models.TextField(_('message'), blank=True, default='')

    is_read = models.BooleanField(_('is read'), default=False)
    read_at = models.DateTimeField(_('read at'), blank=True, null=True)

    created_at = models.DateTimeField(_('created at'), auto_now_add=True)

    class Meta:
        verbose_name = _('Contact Lead')
        verbose_name_plural = _('Contact Leads')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.name or 'Lead'} ({self.created_at:%Y-%m-%d %H:%M})"


class SystemAlert(models.Model):
    """Centralized technical alerts for admins (errors, warnings, predicted risks)."""

    class Severity(models.TextChoices):
        WARNING = 'warning', _('Warning')
        ERROR = 'error', _('Error')
        CRITICAL = 'critical', _('Critical')

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    alert_type = models.CharField(_('alert type'), max_length=120, db_index=True)
    message = models.TextField(_('message'))
    severity = models.CharField(
        _('severity'),
        max_length=20,
        choices=Severity.choices,
        default=Severity.ERROR,
        db_index=True,
    )
    context = models.JSONField(_('context'), blank=True, default=dict)
    traceback = models.TextField(_('traceback'), blank=True, default='')

    is_resolved = models.BooleanField(_('is resolved'), default=False, db_index=True)
    resolved_at = models.DateTimeField(_('resolved at'), blank=True, null=True)
    resolved_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_system_alerts',
        verbose_name=_('resolved by'),
    )

    created_at = models.DateTimeField(_('created at'), auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _('System Alert')
        verbose_name_plural = _('System Alerts')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_resolved', '-created_at']),
            models.Index(fields=['severity', '-created_at']),
            models.Index(fields=['alert_type', '-created_at']),
        ]

    def __str__(self):
        return f"[{self.severity}] {self.alert_type}: {self.message[:80]}"
