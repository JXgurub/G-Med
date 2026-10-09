import random
from datetime import timedelta
from uuid import uuid4

from celery import shared_task
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.site_settings.models import BroadcastNotification
from .models import PatientMedicationReminder
from .reminder_utils import next_scheduled_reminder_at


REMINDER_MESSAGES = (
    ('take_now', '⏰ Vaqti bo‘ldi! {name} dorisini qabul qilishni unutmang.'),
    ('health_first', '💊 Sog‘lig‘ingiz uchun tanaffus qiling va {name} dorisini iching.'),
    ('stay_on_track', '🌿 Rejangizdan chekinmang — {name} dorisini qabul qilish vaqti keldi!'),
    ('gentle_nudge', '😊 Kichik eslatma: {name} dorisini ichish vaqti bo‘ldi.'),
    ('care_for_yourself', '✨ O‘zingizga g‘amxo‘rlik qiling! {name} dorisini qabul qilishni eslang.'),
    ('medicine_time', '🕒 Dori vaqti: {name}. Qabul qilganingizdan so‘ng o‘zingizni kuzatib boring.'),
)


def _build_reminder_message(reminder):
    available_messages = [
        message for message in REMINDER_MESSAGES
        if message[0] != reminder.last_message_key
    ]
    message_key, message_template = random.choice(available_messages)
    return message_key, message_template.format(name=reminder.medication_name)


@shared_task
def send_due_medication_reminders():
    now = timezone.now()
    due_reminder_ids = list(
        PatientMedicationReminder.objects.filter(
            is_active=True,
        ).filter(
            Q(pending_dose_at__isnull=True, next_reminder_at__lte=now)
            | Q(pending_dose_at__isnull=True, next_scheduled_reminder_at__lte=now)
            | Q(pending_dose_at__isnull=False, next_nudge_at__lte=now)
            | Q(pending_dose_at__isnull=False, next_scheduled_reminder_at__lte=now),
        ).order_by('next_reminder_at').values_list('pk', flat=True)[:100]
    )
    notification_ids = []

    for reminder_id in due_reminder_ids:
        with transaction.atomic():
            reminder = (
                PatientMedicationReminder.objects.select_for_update()
                .select_related('patient__user')
                .filter(
                    pk=reminder_id,
                    is_active=True,
                )
                .filter(
                    Q(pending_dose_at__isnull=True, next_reminder_at__lte=now)
                    | Q(pending_dose_at__isnull=True, next_scheduled_reminder_at__lte=now)
                    | Q(pending_dose_at__isnull=False, next_nudge_at__lte=now)
                    | Q(pending_dose_at__isnull=False, next_scheduled_reminder_at__lte=now),
                )
                .first()
            )
            if reminder is None:
                continue

            interval_due = (
                reminder.next_reminder_at is not None
                and reminder.next_reminder_at <= now
            )
            scheduled_due = (
                reminder.next_scheduled_reminder_at is not None
                and reminder.next_scheduled_reminder_at <= now
            )
            scheduled_dose_at = reminder.next_scheduled_reminder_at if scheduled_due else None
            dose_is_pending = reminder.pending_dose_at is not None

            if scheduled_due:
                reminder.next_scheduled_reminder_at = next_scheduled_reminder_at(
                    reminder.daily_times,
                    after=now,
                )
                if (
                    dose_is_pending
                    and (reminder.next_nudge_at is None or reminder.next_nudge_at > now)
                ):
                    reminder.save(update_fields=[
                        'next_scheduled_reminder_at',
                        'updated_at',
                    ])
                    continue

            message_key, message = _build_reminder_message(reminder)
            if reminder.pending_dose_at is None:
                due_times = []
                if interval_due:
                    interval = timedelta(hours=reminder.interval_hours)
                    missed_intervals = (now - reminder.next_reminder_at) // interval + 1
                    due_times.append(reminder.next_reminder_at)
                    reminder.next_reminder_at += interval * missed_intervals
                if scheduled_due:
                    due_times.append(scheduled_dose_at)
                reminder.pending_dose_at = min(due_times)
                reminder.acknowledgement_token = uuid4()
            reminder.next_nudge_at = now + timedelta(minutes=10)
            reminder.last_message_key = message_key
            reminder.save(update_fields=[
                'next_reminder_at',
                'next_scheduled_reminder_at',
                'pending_dose_at',
                'next_nudge_at',
                'acknowledgement_token',
                'last_message_key',
                'updated_at',
            ])

            acknowledgement_token = str(reminder.acknowledgement_token)
            BroadcastNotification.objects.filter(
                user=reminder.patient.user,
                data__acknowledgement_token=acknowledgement_token,
                read_at__isnull=True,
            ).update(read_at=now)

            notification = BroadcastNotification.objects.create(
                user=reminder.patient.user,
                title='💊 Dori ichish vaqti',
                message=message,
                data={
                    'notification_type': 'medication_reminder',
                    'reminder_id': reminder.pk,
                    'acknowledgement_token': acknowledgement_token,
                },
            )
            notification_ids.append(str(notification.id))

    if notification_ids:
        from apps.site_settings.tasks import send_saved_broadcast_push

        send_saved_broadcast_push.delay(notification_ids)

    return {'sent': len(notification_ids)}
