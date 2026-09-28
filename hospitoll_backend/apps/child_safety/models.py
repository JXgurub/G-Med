from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from uuid import uuid4


class SafetyRegion(models.Model):
    class Level(models.TextChoices):
        REGION = 'region', 'Viloyat / shahar'
        DISTRICT = 'district', 'Tuman / shahar'
        MAHALLA = 'mahalla', 'Mahalla'

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=160)
    level = models.CharField(max_length=16, choices=Level.choices)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='children',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'child_safety_regions'
        ordering = ('level', 'name')
        constraints = [
            models.UniqueConstraint(
                fields=('parent', 'level', 'name'),
                name='child_safety_unique_sibling_region',
            ),
            models.CheckConstraint(
                check=(
                    Q(level='region', parent__isnull=True)
                    | Q(level__in=('district', 'mahalla'), parent__isnull=False)
                ),
                name='child_safety_region_parent_required',
            ),
        ]
        indexes = [models.Index(fields=('parent', 'is_active'))]

    def __str__(self):
        return f'{self.name} ({self.get_level_display()})'


class SafetyVote(models.Model):
    class Choice(models.TextChoices):
        SAFE = 'safe', 'Xavfsiz'
        CAUTION = 'caution', 'Ehtiyot bo‘lish kerak'
        DANGER = 'danger', 'Xavfsizlik muammolari bor'

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    region = models.ForeignKey(SafetyRegion, on_delete=models.PROTECT, related_name='votes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='child_safety_votes')
    choice = models.CharField(max_length=12, choices=Choice.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='revoked_child_safety_votes',
    )
    revoke_reason = models.TextField(blank=True)

    class Meta:
        db_table = 'child_safety_votes'
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(fields=('user', 'region'), name='child_safety_one_vote_per_user_region'),
            models.CheckConstraint(
                check=(
                    Q(is_active=True, revoked_at__isnull=True, revoked_by__isnull=True)
                    | Q(is_active=False, revoked_at__isnull=False, revoked_by__isnull=False)
                ),
                name='child_safety_vote_revocation_consistent',
            ),
        ]
        indexes = [models.Index(fields=('region', 'is_active', 'choice'))]


class SafetyVoteAudit(models.Model):
    class Action(models.TextChoices):
        CAST = 'cast', 'Ovoz berildi'
        REVOKE = 'revoke', 'Ovoz moderator tomonidan bekor qilindi'

    class ReasonCategory(models.TextChoices):
        ABUSE = 'abuse', 'Abuse'
        FRAUD = 'fraud', 'Fraud'

    region = models.ForeignKey(SafetyRegion, on_delete=models.PROTECT, related_name='vote_audit')
    vote = models.ForeignKey(
        SafetyVote,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_events',
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='child_safety_audit_events',
    )
    action = models.CharField(max_length=12, choices=Action.choices)
    choice = models.CharField(max_length=12, choices=SafetyVote.Choice.choices, blank=True)
    reason_category = models.CharField(max_length=12, choices=ReasonCategory.choices, blank=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'child_safety_vote_audit'
        ordering = ('-created_at',)
        indexes = [models.Index(fields=('region', '-created_at'))]