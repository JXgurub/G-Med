"""
Celery tasks for medical app.
Handles medical record-related background operations.
"""

from datetime import datetime, timedelta

from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from .models import LabTest
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def _resolve_queue_step_minutes(doctor, queue_items) -> int:
    """Resolve queue step safely for both configured and legacy interval values.

    Priority:
    1) Doctor.slot_minutes when positive.
    2) First queue item's duration_minutes when positive.
    3) Default 30.
    """

    raw_doctor_minutes = getattr(doctor, 'slot_minutes', None)
    try:
        doctor_minutes = int(raw_doctor_minutes)
    except (TypeError, ValueError):
        doctor_minutes = None

    if doctor_minutes and doctor_minutes > 0:
        return doctor_minutes

    first_item = queue_items[0] if queue_items else None
    if first_item is not None:
        try:
            first_duration = int(getattr(first_item, 'duration_minutes', 0) or 0)
        except (TypeError, ValueError):
            first_duration = 0
        if first_duration > 0:
            return first_duration

    return 30


def _queue_active_statuses() -> tuple[str, ...]:
    from .models import Appointment

    return (
        Appointment.Status.SCHEDULED,
        Appointment.Status.CONFIRMED,
        Appointment.Status.WAITING,
        Appointment.Status.IN_PROGRESS,
    )


def _queue_ordering() -> tuple[str, ...]:
    """Canonical queue ordering shared across queue flows.

    `queue_position` can become stale during partial updates, so scheduled time
    is the primary source of truth for who is next.
    """

    return ('scheduled_date', 'created_at', 'queue_position')


def _format_patient_name(appt) -> str:
    patient = getattr(appt, 'patient', None)
    user = getattr(patient, 'user', None) if patient else None
    if user:
        full_name = user.get_full_name().strip()
        if full_name:
            return full_name
    return 'Bemor'


def _reset_auto_turn_fields(appt):
    appt.auto_turn_started_at = None
    appt.auto_turn_prompt_sent_at = None
    appt.auto_turn_last_reminder_at = None
    appt.auto_turn_response = None
    appt.auto_turn_responded_at = None


def _make_aware_at_local_time(day, local_time):
    return timezone.make_aware(
        datetime.combine(day, local_time),
        timezone.get_current_timezone(),
    )


def _autoq_reply_markup(appointment_id):
    return {
        'inline_keyboard': [
            [
                {'text': '✅ Kirdim', 'callback_data': f'autoq:yes:{appointment_id}'},
                {'text': '🕒 Kutyapman', 'callback_data': f'autoq:wait:{appointment_id}'},
            ],
            [
                {'text': '❌ Navbatni bekor qilish', 'callback_data': f'autoq:cancel:{appointment_id}'},
            ],
        ]
    }


def _can_start_auto_queue_for_doctor(doctor, first_appt, now) -> bool:
    """Start rules for auto queue.

    - If doctor is checked in: start immediately.
    - Otherwise: start only when first queued patient's scheduled time has arrived.
    """

    if bool(getattr(doctor, 'is_checked_in', False)):
        return True

    first_local = timezone.localtime(first_appt.scheduled_date).replace(second=0, microsecond=0)
    return first_local <= now


def _run_auto_queue_tick_once() -> dict:
    from django.db.models import Prefetch
    from apps.doctors.models import Doctor
    from .models import Appointment
    from .telegram_bot_service import TelegramBotService

    now = timezone.localtime().replace(second=0, microsecond=0)
    today = now.date()

    doctors = list(
        Doctor.objects.filter(
            is_active=True,
            appointments__scheduled_date__date=today,
            appointments__status__in=_queue_active_statuses(),
        )
        .select_related('user')
        .order_by('created_at')
        .distinct()
    )
    if not doctors:
        return {'processed_doctors': 0, 'prompts_sent': 0, 'queues_shifted': 0, 'reminders_sent': 0}

    service = TelegramBotService()
    try:
        client = service._require_client()
    except Exception:
        return {'processed_doctors': len(doctors), 'prompts_sent': 0, 'queues_shifted': 0, 'reminders_sent': 0, 'bot': 'not_configured'}

    prompts_sent = 0
    queues_shifted = 0
    reminders_sent = 0

    for doctor in doctors:
        if not doctor.available_from or not doctor.available_until:
            continue

        work_start = now.replace(
            hour=doctor.available_from.hour,
            minute=doctor.available_from.minute,
            second=0,
            microsecond=0,
        )
        work_end = now.replace(
            hour=doctor.available_until.hour,
            minute=doctor.available_until.minute,
            second=0,
            microsecond=0,
        )
        if work_end <= work_start:
            work_end = work_end + timedelta(days=1)

        if now < work_start or now > work_end:
            continue

        with transaction.atomic():
            queue_items = list(
                Appointment.objects.select_for_update()
                .filter(
                    doctor=doctor,
                    scheduled_date__date=today,
                    status__in=_queue_active_statuses(),
                )
                .order_by(*_queue_ordering())
            )
            if not queue_items:
                continue

            # Self-heal stale queue states: keep canonical ordering/positions and
            # allow only the leader to stay IN_PROGRESS.
            for idx, item in enumerate(queue_items, start=1):
                update_fields = ['updated_at']
                changed = False

                if item.queue_position != idx:
                    item.queue_position = idx
                    update_fields.append('queue_position')
                    changed = True

                if idx > 1 and item.status == Appointment.Status.IN_PROGRESS:
                    item.status = Appointment.Status.SCHEDULED
                    _reset_auto_turn_fields(item)
                    update_fields.extend([
                        'status',
                        'auto_turn_started_at',
                        'auto_turn_prompt_sent_at',
                        'auto_turn_last_reminder_at',
                        'auto_turn_response',
                        'auto_turn_responded_at',
                    ])
                    changed = True

                if changed:
                    item.save(update_fields=update_fields)

            step_minutes = _resolve_queue_step_minutes(doctor, queue_items)
            slot_delta = timedelta(minutes=step_minutes)

            first = queue_items[0]
            if not _can_start_auto_queue_for_doctor(doctor, first, now):
                continue

            if first.auto_turn_started_at is None:
                first.auto_turn_started_at = now
                first.status = Appointment.Status.IN_PROGRESS
                first.save(update_fields=['auto_turn_started_at', 'status', 'updated_at'])

                if first.telegram_chat_id:
                    clinic_name = first.clinic_name or (first.clinic.name if first.clinic else 'Klinika')
                    doctor_name = first.doctor_name or (doctor.user.get_full_name() if doctor.user_id else 'Doktor')
                    client.send_message(
                        int(first.telegram_chat_id),
                        (
                            "👨‍⚕️ Doktor qabulni boshladi.\n"
                            f"📍 Klinika: {clinic_name}\n"
                            f"🩺 Doktor: {doctor_name}\n\n"
                            "Iltimos, kirishga tayyor bo‘ling."
                        ),
                    )
                    reminders_sent += 1

            wait_followup_qs = list(
                Appointment.objects.select_for_update().filter(
                    doctor=doctor,
                    scheduled_date__date=today,
                    status__in=_queue_active_statuses(),
                    auto_turn_response='wait',
                    auto_turn_responded_at__isnull=False,
                )
            )
            for wait_appt in wait_followup_qs:
                if wait_appt.id != first.id:
                    continue

                if wait_appt.auto_turn_responded_at is None:
                    continue

                responded_at = timezone.localtime(wait_appt.auto_turn_responded_at)
                if now - responded_at < timedelta(minutes=15):
                    continue

                last_reminder = wait_appt.auto_turn_last_reminder_at
                # Send only one follow-up for each explicit "wait" response.
                if last_reminder and timezone.localtime(last_reminder) > responded_at:
                    continue

                if not wait_appt.telegram_chat_id:
                    continue

                clinic_name = wait_appt.clinic_name or (wait_appt.clinic.name if wait_appt.clinic else 'Klinika')
                doctor_name = wait_appt.doctor_name or (doctor.user.get_full_name() if doctor.user_id else 'Doktor')
                when = timezone.localtime(wait_appt.scheduled_date).strftime('%H:%M')
                client.send_message(
                    int(wait_appt.telegram_chat_id),
                    (
                        "⏰ 10 daqiqa o‘tdi. Holatingizni qayta tasdiqlang.\n\n"
                        f"📍 Klinika: {clinic_name}\n"
                        f"👨‍⚕️ Doktor: {doctor_name}\n"
                        f"🕒 Taxminiy vaqt: {when}\n\n"
                        "Doktor qabuliga kirdingizmi, iltimos tasdiqlang."
                    ),
                    reply_markup=_autoq_reply_markup(wait_appt.id),
                )
                wait_appt.auto_turn_last_reminder_at = now
                wait_appt.save(update_fields=['auto_turn_last_reminder_at', 'updated_at'])
                reminders_sent += 1

            # Compatibility: if turn is already active but legacy data missed prompt timestamp,
            # send the questionnaire now so queue can continue instead of getting stuck.
            if first.auto_turn_prompt_sent_at is None and first.telegram_chat_id:
                clinic_name = first.clinic_name or (first.clinic.name if first.clinic else 'Klinika')
                doctor_name = first.doctor_name or (doctor.user.get_full_name() if doctor.user_id else 'Doktor')
                patient_name = _format_patient_name(first)
                client.send_message(
                    int(first.telegram_chat_id),
                    (
                        "⏱ Sizning navbat vaqtingiz keldi.\n\n"
                        f"👤 Bemor: {patient_name}\n"
                        f"📍 Klinika: {clinic_name}\n"
                        f"👨‍⚕️ Doktor: {doctor_name}\n\n"
                        "Doktor qabuliga kirdingizmi, iltimos tasdiqlang."
                    ),
                    reply_markup=_autoq_reply_markup(first.id),
                )
                first.auto_turn_prompt_sent_at = now
                first.auto_turn_last_reminder_at = now
                first.save(update_fields=['auto_turn_prompt_sent_at', 'auto_turn_last_reminder_at', 'updated_at'])
                prompts_sent += 1
                continue

            if first.auto_turn_prompt_sent_at and not first.auto_turn_response:
                timeout_auto_cancel = False
                prompt_elapsed = now - timezone.localtime(first.auto_turn_prompt_sent_at)
                if prompt_elapsed >= timedelta(minutes=30):
                    first.auto_turn_response = 'cancel'
                    first.auto_turn_responded_at = timezone.now()
                    first.save(update_fields=['auto_turn_response', 'auto_turn_responded_at', 'updated_at'])
                    timeout_auto_cancel = True
            else:
                timeout_auto_cancel = False

            if first.auto_turn_response == 'yes':
                if len(queue_items) > 1:
                    _reset_auto_turn_fields(first)
                    first.status = Appointment.Status.COMPLETED
                    first.save(update_fields=[
                        'auto_turn_started_at',
                        'auto_turn_prompt_sent_at',
                        'auto_turn_last_reminder_at',
                        'auto_turn_response',
                        'auto_turn_responded_at',
                        'status',
                        'updated_at',
                    ])

                    new_cursor = now
                    for idx, item in enumerate(queue_items[1:], start=1):
                        item.queue_position = idx
                        item.scheduled_date = _make_aware_at_local_time(new_cursor.date(), new_cursor.time())
                        if idx == 1:
                            item.status = Appointment.Status.IN_PROGRESS
                            _reset_auto_turn_fields(item)
                            item.auto_turn_started_at = now
                        item.save(update_fields=['queue_position', 'scheduled_date', 'status', 'auto_turn_started_at', 'auto_turn_prompt_sent_at', 'auto_turn_last_reminder_at', 'auto_turn_response', 'auto_turn_responded_at', 'updated_at'])
                        new_cursor = new_cursor + slot_delta

                    for idx, item in enumerate(queue_items[1:], start=1):
                        if not item.telegram_chat_id:
                            continue
                        when = timezone.localtime(item.scheduled_date).strftime('%H:%M')
                        if idx == 1:
                            text = (
                                "📢 Oldingizdagi bemor qabulga kirdi. "
                                f"Iltimos, tayyor turing. Keyingi navbat sizniki bo‘ladi. Taxminiy vaqt: {when}"
                            )
                        else:
                            text = (
                                "🔄 Navbat yangilandi. "
                                f"Yangi tartibda sizning taxminiy vaqtingiz: {when}"
                            )
                        client.send_message(int(item.telegram_chat_id), text)
                        reminders_sent += 1

                    queues_shifted += 1
                else:
                    _reset_auto_turn_fields(first)
                    first.status = Appointment.Status.COMPLETED
                    first.save(update_fields=['auto_turn_started_at', 'auto_turn_prompt_sent_at', 'auto_turn_last_reminder_at', 'auto_turn_response', 'auto_turn_responded_at', 'status', 'updated_at'])
                continue

            if first.auto_turn_response == 'cancel':
                first.status = Appointment.Status.CANCELLED
                _reset_auto_turn_fields(first)
                first.save(update_fields=['status', 'auto_turn_started_at', 'auto_turn_prompt_sent_at', 'auto_turn_last_reminder_at', 'auto_turn_response', 'auto_turn_responded_at', 'updated_at'])

                if timeout_auto_cancel and first.telegram_chat_id:
                    client.send_message(
                        int(first.telegram_chat_id),
                        (
                            "❌ Navbatingiz avtomatik bekor qilindi.\n\n"
                            "Sabab: 30 daqiqa ichida javob kelmadi.\n"
                            "Qayta navbat olish uchun iltimos klinika bilan bog‘laning yoki yangi slot tanlang."
                        ),
                    )
                    reminders_sent += 1

                new_cursor = now
                for idx, item in enumerate(queue_items[1:], start=1):
                    item.queue_position = idx
                    item.scheduled_date = _make_aware_at_local_time(new_cursor.date(), new_cursor.time())
                    if idx == 1:
                        item.status = Appointment.Status.IN_PROGRESS
                        _reset_auto_turn_fields(item)
                        item.auto_turn_started_at = now
                    item.save(update_fields=['queue_position', 'scheduled_date', 'status', 'auto_turn_started_at', 'auto_turn_prompt_sent_at', 'auto_turn_last_reminder_at', 'auto_turn_response', 'auto_turn_responded_at', 'updated_at'])
                    new_cursor = new_cursor + slot_delta

                for idx, item in enumerate(queue_items[1:], start=1):
                    if not item.telegram_chat_id:
                        continue
                    when = timezone.localtime(item.scheduled_date).strftime('%H:%M')
                    if idx == 1:
                        text = (
                            "📢 Oldingi bemor navbatdan chiqdi. "
                            f"Endi sizning navbatingiz. Taxminiy vaqt: {when}"
                        )
                    else:
                        text = (
                            "🔄 Navbat yangilandi. "
                            f"Yangi tartibda sizning taxminiy vaqtingiz: {when}"
                        )
                    client.send_message(int(item.telegram_chat_id), text)
                    reminders_sent += 1

                queues_shifted += 1
                continue

            if first.auto_turn_response == 'wait':
                responded_at = first.auto_turn_responded_at
                last_reminder = first.auto_turn_last_reminder_at
                should_process_wait = bool(
                    responded_at and (
                        last_reminder is None or timezone.localtime(last_reminder) < timezone.localtime(responded_at)
                    )
                )

                if should_process_wait:
                    wait_delay = timedelta(minutes=15)
                    # Recalculate from current time so ETA is always real-time and collision-free.
                    new_cursor = now + wait_delay
                    for idx, item in enumerate(queue_items, start=1):
                        current_local = timezone.localtime(item.scheduled_date).replace(second=0, microsecond=0)
                        target_local = current_local + wait_delay
                        final_local = target_local if target_local > new_cursor else new_cursor
                        item.scheduled_date = _make_aware_at_local_time(final_local.date(), final_local.time())
                        update_fields = ['scheduled_date', 'updated_at']
                        if idx == 1:
                            item.status = Appointment.Status.WAITING
                            item.auto_turn_last_reminder_at = responded_at
                            update_fields.extend(['status', 'auto_turn_last_reminder_at'])
                        item.save(update_fields=update_fields)
                        new_cursor = final_local + slot_delta

                    first = queue_items[0]
                    when = timezone.localtime(first.scheduled_date).strftime('%H:%M')

                    if first.telegram_chat_id:
                        client.send_message(
                            int(first.telegram_chat_id),
                            (
                                "⏳ So'rovingiz qabul qilindi.\n"
                                f"🕒 Yangi taxminiy vaqtingiz: {when}\n"
                                "15 daqiqadan keyin holatingizni yana so'raymiz."
                            ),
                        )
                        reminders_sent += 1

                    for item in queue_items[1:]:
                        if not item.telegram_chat_id:
                            continue
                        item_when = timezone.localtime(item.scheduled_date).strftime('%H:%M')
                        client.send_message(
                            int(item.telegram_chat_id),
                            (
                                "⏳ Navbatingiz 15 daqiqaga kechiktirildi.\n"
                                f"🕒 Yangi taxminiy vaqtingiz: {item_when}"
                            ),
                        )
                        reminders_sent += 1
                    queues_shifted += 1

                else:
                    # If a previous WAIT decision has already been consumed, but the turn is
                    # due again, reset response fields so we can re-prompt instead of stalling.
                    stale_wait_due_again = bool(
                        first.scheduled_date <= now and (
                            responded_at is None or
                            timezone.localtime(responded_at) <= now
                        )
                    )
                    if stale_wait_due_again:
                        first.auto_turn_response = None
                        first.auto_turn_responded_at = None
                        first.auto_turn_prompt_sent_at = None
                        first.auto_turn_last_reminder_at = None
                        first.save(update_fields=[
                            'auto_turn_response',
                            'auto_turn_responded_at',
                            'auto_turn_prompt_sent_at',
                            'auto_turn_last_reminder_at',
                            'updated_at',
                        ])

                continue

            if first.auto_turn_prompt_sent_at and not first.auto_turn_response:
                last_reminder = first.auto_turn_last_reminder_at or first.auto_turn_prompt_sent_at
                if last_reminder and (now - timezone.localtime(last_reminder)) >= timedelta(minutes=5):
                    if first.telegram_chat_id:
                        client.send_message(
                            int(first.telegram_chat_id),
                            "⏳ Iltimos holatingizni belgilang.",
                            reply_markup=_autoq_reply_markup(first.id),
                        )
                        first.auto_turn_last_reminder_at = now
                        first.save(update_fields=['auto_turn_last_reminder_at', 'updated_at'])
                        reminders_sent += 1

    return {
        'processed_doctors': len(doctors),
        'prompts_sent': prompts_sent,
        'queues_shifted': queues_shifted,
        'reminders_sent': reminders_sent,
    }


@shared_task
def process_lab_test_results(lab_test_id):
    """
    Process lab test results when they become available.
    Could integrate with external lab systems.
    """
    try:
        from .models import LabTest
        lab_test = LabTest.objects.get(id=lab_test_id)
        
        logger.info(f"Processing lab test results for {lab_test.test_name}")
        # Integration with external lab system would go here
        
        return {'status': 'processed', 'test_id': str(lab_test_id)}
    except LabTest.DoesNotExist:
        logger.error(f"Lab test {lab_test_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error processing lab test: {str(e)}")
        raise


@shared_task
def send_appointment_reminders():
    """
    Send reminders for upcoming appointments.
    This should run periodically via Celery Beat.
    """
    try:
        from datetime import timedelta
        from .models import Appointment
        from django.utils import timezone
        
        tomorrow = timezone.now() + timedelta(days=1)
        upcoming_appointments = Appointment.objects.filter(
            status='scheduled',
            scheduled_date__date=tomorrow.date()
        )
        
        reminder_count = 0
        for appointment in upcoming_appointments:
            # Send reminder via SMS/Email
            logger.info(
                f"Reminder sent for appointment: "
                f"{appointment.patient.user.email} - {appointment.doctor.user.email}"
            )
            reminder_count += 1
        
        logger.info(f"Total appointment reminders sent: {reminder_count}")
        return {'reminders_sent': reminder_count}
    except Exception as e:
        logger.error(f"Error sending appointment reminders: {str(e)}")
        raise


@shared_task
def auto_cancel_unconfirmed_appointment(appointment_id: str) -> dict:
    """Cancel appointment if Telegram confirmation didn't happen within token window."""
    from .models import Appointment
    from apps.doctors.models import DoctorAvailability

    try:
        with transaction.atomic():
            appt = Appointment.objects.select_for_update().filter(id=appointment_id).first()
            if not appt:
                return {'status': 'missing', 'appointment_id': appointment_id}

            if appt.status != Appointment.Status.PENDING_TELEGRAM_CONFIRMATION:
                return {'status': 'skipped', 'reason': 'not_pending', 'appointment_id': appointment_id}

            if not appt.telegram_token_expires_at or timezone.now() < appt.telegram_token_expires_at:
                return {'status': 'skipped', 'reason': 'not_expired', 'appointment_id': appointment_id}

            # Free slot
            if appt.slot_id:
                try:
                    slot = DoctorAvailability.objects.select_for_update().get(id=appt.slot_id)
                    if slot.status == 'booked':
                        slot.status = 'available'
                        slot.save(update_fields=['status'])
                except DoctorAvailability.DoesNotExist:
                    pass

            appt.status = Appointment.Status.CANCELLED
            appt.telegram_token = None
            appt.telegram_token_expires_at = None
            appt.save(update_fields=['status', 'telegram_token', 'telegram_token_expires_at', 'updated_at'])

        return {'status': 'cancelled', 'appointment_id': appointment_id}
    except Exception as e:
        logger.error(f"Error auto-cancelling appointment {appointment_id}: {str(e)}")
        raise


@shared_task
def send_telegram_appointment_reminder(appointment_id: str) -> dict:
    """Send Telegram reminder 1 hour before appointment (best-effort)."""
    from .models import Appointment
    from .telegram_bot_service import TelegramBotService

    appt = Appointment.objects.select_related('doctor', 'clinic', 'patient').filter(id=appointment_id).first()
    if not appt:
        return {'status': 'missing', 'appointment_id': appointment_id}

    if getattr(appt, 'telegram_reminder_sent_at', None) is not None:
        return {'status': 'skipped', 'reason': 'already_sent', 'appointment_id': appointment_id}

    if appt.status in (
        Appointment.Status.CANCELLED,
        Appointment.Status.NO_SHOW,
        Appointment.Status.COMPLETED,
        Appointment.Status.IN_PROGRESS,
    ):
        return {'status': 'skipped', 'reason': 'inactive_status', 'appointment_id': appointment_id}
    if getattr(appt, 'patient_arrival_confirmed_at', None) is not None:
        return {'status': 'skipped', 'reason': 'already_arrived', 'appointment_id': appointment_id}
    if not appt.telegram_chat_id:
        return {'status': 'skipped', 'reason': 'no_chat', 'appointment_id': appointment_id}

    reminder_window_minutes = int(getattr(settings, 'TELEGRAM_REMINDER_WINDOW_MINUTES', 2) or 2)
    if reminder_window_minutes < 0:
        reminder_window_minutes = 0

    now = timezone.now()
    remaining = appt.scheduled_date - now
    min_remaining = timedelta(minutes=max(0, 60 - reminder_window_minutes))
    max_remaining = timedelta(minutes=60 + reminder_window_minutes)
    if remaining < min_remaining or remaining > max_remaining:
        return {
            'status': 'skipped',
            'reason': 'outside_one_hour_window',
            'appointment_id': appointment_id,
        }

    when = timezone.localtime(appt.scheduled_date).strftime('%d.%m.%Y %H:%M')
    doctor_name = appt.doctor_name or (appt.doctor.user.get_full_name() if appt.doctor else 'Doktor')
    clinic_name = appt.clinic_name or (appt.clinic.name if appt.clinic else 'Klinika')

    try:
        service = TelegramBotService()
        client = service._require_client()
    except Exception:
        return {'status': 'skipped', 'reason': 'bot_not_configured', 'appointment_id': appointment_id}

    claimed_at = timezone.now()
    claimed = Appointment.objects.filter(
        id=appointment_id,
        telegram_reminder_sent_at__isnull=True,
    ).update(telegram_reminder_sent_at=claimed_at)
    if not claimed:
        return {'status': 'skipped', 'reason': 'already_sent', 'appointment_id': appointment_id}

    try:
        client.send_message(
            appt.telegram_chat_id,
            f"⏰ Eslatma: 1 soatdan keyin randevu bor!\n\n📍 {clinic_name}\n👨‍⚕️ {doctor_name}\n🕒 {when}",
        )
    except Exception:
        Appointment.objects.filter(id=appointment_id, telegram_reminder_sent_at=claimed_at).update(telegram_reminder_sent_at=None)
        raise

    return {'status': 'sent', 'appointment_id': appointment_id}


@shared_task
def send_telegram_appointment_15min_prompt(appointment_id: str) -> dict:
    """Send Telegram prompt 15 minutes before appointment with buttons (attend/cancel)."""
    from .models import Appointment
    from .telegram_bot_service import TelegramBotService

    appt = Appointment.objects.select_related('doctor', 'clinic', 'patient').filter(id=appointment_id).first()
    if not appt:
        return {'status': 'missing', 'appointment_id': appointment_id}

    if getattr(appt, 'telegram_15min_prompt_sent_at', None) is not None:
        return {'status': 'skipped', 'reason': 'already_sent', 'appointment_id': appointment_id}
    if not appt.telegram_chat_id:
        return {'status': 'skipped', 'reason': 'no_chat', 'appointment_id': appointment_id}

    if appt.status in (
        Appointment.Status.CANCELLED,
        Appointment.Status.NO_SHOW,
        Appointment.Status.COMPLETED,
        Appointment.Status.IN_PROGRESS,
    ):
        return {'status': 'skipped', 'reason': 'inactive_status', 'appointment_id': appointment_id}

    # Unified queue flow: today's active queue is handled by auto-queue callbacks.
    if (
        appt.doctor_id
        and timezone.localtime(appt.scheduled_date).date() == timezone.localtime().date()
        and appt.status in _queue_active_statuses()
    ):
        return {'status': 'skipped', 'reason': 'managed_by_auto_queue', 'appointment_id': appointment_id}

    if getattr(appt, 'patient_arrival_confirmed_at', None) is not None:
        return {'status': 'skipped', 'reason': 'already_arrived', 'appointment_id': appointment_id}

    prompt_window_minutes = int(getattr(settings, 'TELEGRAM_15MIN_WINDOW_MINUTES', 2) or 2)
    if prompt_window_minutes < 0:
        prompt_window_minutes = 0

    now = timezone.now()
    remaining = appt.scheduled_date - now
    min_remaining = timedelta(minutes=max(0, 15 - prompt_window_minutes))
    max_remaining = timedelta(minutes=15 + prompt_window_minutes)
    if remaining < min_remaining or remaining > max_remaining:
        return {
            'status': 'skipped',
            'reason': 'outside_15min_window',
            'appointment_id': appointment_id,
        }

    try:
        service = TelegramBotService()
        client = service._require_client()
    except Exception:
        return {'status': 'skipped', 'reason': 'bot_not_configured', 'appointment_id': appointment_id}

    when = timezone.localtime(appt.scheduled_date).strftime('%d.%m.%Y %H:%M')
    doctor_name = appt.doctor_name or (appt.doctor.user.get_full_name() if appt.doctor else 'Doktor')
    clinic_name = appt.clinic_name or (appt.clinic.name if appt.clinic else 'Klinika')

    reply_markup = {
        'inline_keyboard': [[
            {'text': '✅ Qabulga boraman', 'callback_data': f'arrive:{appt.id}'},
            {'text': '❌ Bekor qilinsin', 'callback_data': f'cancel15:{appt.id}'},
        ]]
    }

    claimed_at = timezone.now()
    claimed = Appointment.objects.filter(
        id=appointment_id,
        telegram_15min_prompt_sent_at__isnull=True,
    ).update(telegram_15min_prompt_sent_at=claimed_at)
    if not claimed:
        return {'status': 'skipped', 'reason': 'already_sent', 'appointment_id': appointment_id}

    try:
        client.send_message(
            appt.telegram_chat_id,
            f"⏳ 15 minutdan keyin navbatingiz keladi.\n\n📍 {clinic_name}\n👨‍⚕️ {doctor_name}\n🕒 {when}\n\nQabulga borasizmi?",
            reply_markup=reply_markup,
        )
    except Exception:
        Appointment.objects.filter(id=appointment_id, telegram_15min_prompt_sent_at=claimed_at).update(telegram_15min_prompt_sent_at=None)
        raise

    return {'status': 'sent', 'appointment_id': appointment_id}


@shared_task
def run_auto_queue_cycle() -> dict:
    """Periodic automatic queue engine.

    - Starts first patient turn when doctor is checked-in and work hours started.
    - After slot interval, asks current patient yes/no via Telegram.
    - If no, shifts queue forward and notifies affected patients.
    - If yes, advances queue and notifies next patient.
    """

    try:
        return _run_auto_queue_tick_once()
    except Exception as e:
        logger.error(f"Error in run_auto_queue_cycle: {str(e)}")
        raise


@shared_task
def send_today_first_queue_reminders() -> dict:
    """Send reminder to first patient 30 minutes before doctor's work start.

    This task is read-only for queue ordering and statuses; it sends a single
    reminder per appointment per day (idempotent via cache key).
    """

    from apps.doctors.models import Doctor
    from .models import Appointment
    from .telegram_bot_service import TelegramBotService

    now = timezone.localtime()
    today = now.date()
    doctors = list(
        Doctor.objects.filter(is_active=True)
        .select_related('user')
        .order_by('created_at')
    )

    try:
        service = TelegramBotService()
        client = service._require_client()
    except Exception:
        return {
            'processed_doctors': len(doctors),
            'sent': 0,
            'skipped_no_queue': 0,
            'skipped_no_chat': 0,
            'skipped_already_sent': 0,
            'bot': 'not_configured',
        }

    sent = 0
    skipped_no_queue = 0
    skipped_no_chat = 0
    skipped_already_sent = 0

    reminder_window_minutes = int(getattr(settings, 'AUTO_QUEUE_START_REMINDER_WINDOW_MINUTES', 3) or 3)
    if reminder_window_minutes < 0:
        reminder_window_minutes = 0

    skipped_not_in_window = 0

    for doctor in doctors:
        if not doctor.available_from:
            skipped_not_in_window += 1
            continue

        doctor_start = now.replace(
            hour=doctor.available_from.hour,
            minute=doctor.available_from.minute,
            second=0,
            microsecond=0,
        )
        reminder_target = doctor_start - timedelta(minutes=30)
        if abs((now - reminder_target).total_seconds()) > reminder_window_minutes * 60:
            skipped_not_in_window += 1
            continue

        first = (
            Appointment.objects.filter(
                doctor=doctor,
                scheduled_date__date=today,
                status__in=_queue_active_statuses(),
            )
            .order_by(*_queue_ordering())
            .first()
        )

        if not first:
            skipped_no_queue += 1
            continue

        if not first.telegram_chat_id:
            skipped_no_chat += 1
            continue

        dedupe_key = f"autoq:first-morning:{first.id}:{today.isoformat()}"
        if cache.get(dedupe_key):
            skipped_already_sent += 1
            continue

        queue_step = _resolve_queue_step_minutes(doctor, [first])
        when = timezone.localtime(first.scheduled_date).strftime('%H:%M')
        clinic_name = first.clinic_name or (first.clinic.name if first.clinic else 'Klinika')
        doctor_name = first.doctor_name or (doctor.user.get_full_name() if doctor.user_id else 'Doktor')

        client.send_message(
            int(first.telegram_chat_id),
            (
                "🌅 Xayrli tong! Bugungi navbat bo‘yicha eslatma.\n\n"
                "✅ Siz bugungi ro‘yxatda 1-navbatdasiz.\n"
                f"🕒 Taxminiy vaqt: {when}\n"
                f"⏱ Qabul oralig‘i: {queue_step} daqiqa\n"
                f"📍 Klinika: {clinic_name}\n"
                f"👨‍⚕️ Doktor: {doctor_name}\n\n"
                "Doktor qabulni boshlagach sizga yangi auto-navbat tugmalari bilan xabar yuboriladi."
            ),
        )

        cache.set(dedupe_key, 1, timeout=60 * 60 * 24)
        sent += 1

    return {
        'processed_doctors': len(doctors),
        'sent': sent,
        'skipped_no_queue': skipped_no_queue,
        'skipped_no_chat': skipped_no_chat,
        'skipped_already_sent': skipped_already_sent,
        'skipped_not_in_window': skipped_not_in_window,
    }
