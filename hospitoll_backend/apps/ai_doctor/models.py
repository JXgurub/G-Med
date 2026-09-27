import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class AnalysisResult(models.Model):
    FILE_TYPE_CHOICES = [
        ("image", _("Rasm")),
        ("pdf", _("PDF")),
        ("excel", _("Excel")),
        ("word", _("Word")),
        ("html", _("HTML")),
    ]
    STATUS_CHOICES = [
        ("pending", _("Kutilmoqda")),
        ("completed", _("Bajarildi")),
        ("failed", _("Xatolik")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_analyses",
        null=True,
        blank=True
    )
    session_key = models.CharField(max_length=64, blank=True, db_index=True)
    file = models.FileField(upload_to="ai_analyses/")
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES, default="image")
    result_text = models.TextField(blank=True)
    language = models.CharField(max_length=10, default="uz")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"AnalysisResult {self.id} ({self.status})"
