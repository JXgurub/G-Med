from __future__ import annotations

from uuid import uuid4

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class PrinterDevice(models.Model):
    STATUS_CHOICES = (
        ('ready', 'Ulangan va tayyor'),
        ('checking', 'Tekshirilmoqda / band'),
        ('offline', 'Printer Service offline'),
        ('disconnected', 'Ulanmagan'),
    )

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    clinic = models.ForeignKey('clinics.Clinic', on_delete=models.CASCADE, related_name='printer_devices')
    reception_room = models.ForeignKey('clinics.ClinicDepartment', on_delete=models.SET_NULL, null=True, blank=True, related_name='printer_devices')
    device_name = models.CharField(max_length=120, default='G-MED Printer Device', help_text='Lokal qurilma nomi')
    printer_name = models.CharField(max_length=150, blank=True, default='', help_text='Masalan: Xprinter XP-Q200')
    device_token = models.CharField(max_length=200, unique=True, help_text='Printer service uchun maxsus token')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='offline')
    last_seen = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [models.Index(fields=['clinic', 'status']), models.Index(fields=['device_token'])]

    def __str__(self):
        return self.device_name or self.printer_name or str(self.id)


class PrintJob(models.Model):
    STATUS_CHOICES = (
        ('pending', 'pending'),
        ('printing', 'printing'),
        ('completed', 'completed'),
        ('failed', 'failed'),
    )

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    clinic = models.ForeignKey('clinics.Clinic', on_delete=models.CASCADE, related_name='print_jobs')
    reception_room = models.ForeignKey('clinics.ClinicDepartment', on_delete=models.SET_NULL, null=True, blank=True, related_name='print_jobs')
    printer_device = models.ForeignKey(PrinterDevice, on_delete=models.SET_NULL, null=True, blank=True, related_name='jobs')
    appointment = models.ForeignKey('medical.Appointment', on_delete=models.SET_NULL, null=True, blank=True, related_name='print_jobs')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='print_jobs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    printed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['clinic', 'status']), models.Index(fields=['printer_device', 'status'])]

    def __str__(self):
        return f'{self.id} - {self.status}'

    def mark_printed(self):
        self.status = 'completed'
        self.printed_at = timezone.now()
        self.save(update_fields=['status', 'printed_at', 'updated_at'])
