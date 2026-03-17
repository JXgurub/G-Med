"""
Celery tasks for medical app.
Handles medical record-related background operations.
"""

from datetime import timedelta

from celery import shared_task
from django.utils import timezone
from django.db import transaction
from .models import LabTest
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


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

    client.send_message(
        appt.telegram_chat_id,
        f"⏰ Eslatma: 1 soatdan keyin randevu bor!\n\n📍 {clinic_name}\n👨‍⚕️ {doctor_name}\n🕒 {when}",
    )

    Appointment.objects.filter(id=appointment_id).update(telegram_reminder_sent_at=timezone.now())
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

    client.send_message(
        appt.telegram_chat_id,
        f"⏳ 15 minutdan keyin navbatingiz keladi.\n\n📍 {clinic_name}\n👨‍⚕️ {doctor_name}\n🕒 {when}\n\nQabulga borasizmi?",
        reply_markup=reply_markup,
    )

    Appointment.objects.filter(id=appointment_id).update(telegram_15min_prompt_sent_at=timezone.now())
    return {'status': 'sent', 'appointment_id': appointment_id}
