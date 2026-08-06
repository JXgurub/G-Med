from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.doctors.models import DoctorAvailability
from apps.medical.models import Appointment
from apps.medical.telegram_bot_service import TelegramBotService


class Command(BaseCommand):
    help = "Process Telegram-related jobs without Celery (cancel expired confirmations, send reminders)"

    def add_arguments(self, parser):
        parser.add_argument("--cancel-expired", action="store_true", help="Cancel expired pending Telegram confirmations")
        parser.add_argument("--send-reminders", action="store_true", help="Send Telegram reminders 1 hour before appointment")
        parser.add_argument("--send-15min-prompts", action="store_true", help="Send Telegram 15-minute prompts with attend/cancel buttons")
        parser.add_argument(
            "--reminder-window-minutes",
            type=int,
            default=2,
            help="Reminder window size around 60 minutes before start (default: 2 => 59-61 minutes)",
        )

    def handle(self, *args, **options):
        cancel_expired = bool(options.get("cancel_expired"))
        send_reminders = bool(options.get("send_reminders"))
        send_15min = bool(options.get("send_15min_prompts"))

        # Default: do both
        if not cancel_expired and not send_reminders and not send_15min:
            cancel_expired = True
            send_reminders = True
            send_15min = True

        cancelled = 0
        reminded = 0
        prompted = 0

        if cancel_expired:
            cancelled = self._cancel_expired_pending()

        if send_reminders:
            reminded = self._send_reminders(window_minutes=int(options.get("reminder_window_minutes") or 2))

        if send_15min:
            prompted = self._send_15min_prompts(window_minutes=2)

        self.stdout.write(self.style.SUCCESS(f"Done. cancelled={cancelled}, reminded={reminded}, prompted_15min={prompted}"))

    def _cancel_expired_pending(self) -> int:
        now = timezone.now()
        qs = Appointment.objects.filter(
            status=Appointment.Status.PENDING_TELEGRAM_CONFIRMATION,
            telegram_token_expires_at__isnull=False,
            telegram_token_expires_at__lte=now,
        ).select_related("slot")

        count = 0
        for appt in qs:
            with transaction.atomic():
                appt = Appointment.objects.select_for_update().filter(id=appt.id).first()
                if not appt:
                    continue
                if appt.status != Appointment.Status.PENDING_TELEGRAM_CONFIRMATION:
                    continue
                if not appt.telegram_token_expires_at or timezone.now() < appt.telegram_token_expires_at:
                    continue

                slot_id = getattr(appt, 'slot_id', None)
                if slot_id:
                    try:
                        slot = DoctorAvailability.objects.select_for_update().get(id=slot_id)
                        if slot.status == "booked":
                            slot.status = "available"
                            slot.save(update_fields=["status"])
                    except DoctorAvailability.DoesNotExist:
                        pass

                appt.status = Appointment.Status.CANCELLED
                appt.telegram_token = None
                appt.telegram_token_expires_at = None
                appt.save(update_fields=["status", "telegram_token", "telegram_token_expires_at", "updated_at"])
                count += 1

        return count

    def _send_reminders(self, window_minutes: int) -> int:
        # Find appointments starting in ~1 hour (59-61 minutes by default)
        now = timezone.now()
        start = now + timedelta(minutes=60 - window_minutes)
        end = now + timedelta(minutes=60 + window_minutes)

        qs = (
            Appointment.objects.filter(
                telegram_chat_id__isnull=False,
                telegram_user_id__isnull=False,
                scheduled_date__gte=start,
                scheduled_date__lte=end,
                telegram_reminder_sent_at__isnull=True,
                patient_arrival_confirmed_at__isnull=True,
            )
            .exclude(status__in=[
                Appointment.Status.CANCELLED,
                Appointment.Status.NO_SHOW,
                Appointment.Status.COMPLETED,
                Appointment.Status.IN_PROGRESS,
            ])
            .select_related("doctor", "clinic")
            .order_by("scheduled_date")
        )

        service = TelegramBotService()
        try:
            client = service._require_client()
        except Exception:
            return 0

        count = 0
        for appt in qs:
            if not appt.telegram_chat_id:
                continue

            claimed_at = timezone.now()
            claimed = Appointment.objects.filter(
                id=appt.id,
                telegram_reminder_sent_at__isnull=True,
            ).update(telegram_reminder_sent_at=claimed_at)
            if not claimed:
                continue

            when = timezone.localtime(appt.scheduled_date).strftime("%d.%m.%Y %H:%M")
            doctor_name = appt.doctor_name or (appt.doctor.user.get_full_name() if appt.doctor else "Doktor")
            clinic_name = appt.clinic_name or (appt.clinic.name if appt.clinic else "Klinika")

            try:
                client.send_message(
                    appt.telegram_chat_id,
                    f"⏰ Eslatma: 1 soatdan keyin randevu bor!\n\n📍 {clinic_name}\n👨‍⚕️ {doctor_name}\n🕒 {when}",
                )
            except Exception:
                Appointment.objects.filter(id=appt.id, telegram_reminder_sent_at=claimed_at).update(telegram_reminder_sent_at=None)
                continue

            count += 1

        return count

    def _send_15min_prompts(self, window_minutes: int) -> int:
        now = timezone.now()
        start = now + timedelta(minutes=15 - window_minutes)
        end = now + timedelta(minutes=15 + window_minutes)

        qs = (
            Appointment.objects.filter(
                telegram_chat_id__isnull=False,
                telegram_user_id__isnull=False,
                scheduled_date__gte=start,
                scheduled_date__lte=end,
                telegram_15min_prompt_sent_at__isnull=True,
                patient_arrival_confirmed_at__isnull=True,
            )
            .exclude(status__in=[
                Appointment.Status.CANCELLED,
                Appointment.Status.NO_SHOW,
                Appointment.Status.COMPLETED,
                Appointment.Status.IN_PROGRESS,
            ])
            .select_related('doctor', 'clinic')
            .order_by('scheduled_date')
        )

        service = TelegramBotService()
        try:
            client = service._require_client()
        except Exception:
            return 0

        count = 0
        for appt in qs:
            if not appt.telegram_chat_id:
                continue

            claimed_at = timezone.now()
            claimed = Appointment.objects.filter(
                id=appt.id,
                telegram_15min_prompt_sent_at__isnull=True,
            ).update(telegram_15min_prompt_sent_at=claimed_at)
            if not claimed:
                continue

            if (
                appt.doctor_id
                and timezone.localtime(appt.scheduled_date).date() == timezone.localtime().date()
                and appt.status in (
                    Appointment.Status.SCHEDULED,
                    Appointment.Status.CONFIRMED,
                    Appointment.Status.WAITING,
                    Appointment.Status.IN_PROGRESS,
                )
            ):
                Appointment.objects.filter(id=appt.id, telegram_15min_prompt_sent_at=claimed_at).update(telegram_15min_prompt_sent_at=None)
                continue

            when = timezone.localtime(appt.scheduled_date).strftime('%d.%m.%Y %H:%M')
            doctor_name = appt.doctor_name or (appt.doctor.user.get_full_name() if appt.doctor else 'Doktor')
            clinic_name = appt.clinic_name or (appt.clinic.name if appt.clinic else 'Klinika')
            reply_markup = {
                'inline_keyboard': [[
                    {'text': '✅ Qabulga kiraman', 'callback_data': f'arrive:{appt.id}'},
                    {'text': '❌ Bekor qilinsin', 'callback_data': f'cancel15:{appt.id}'},
                ]]
            }
            try:
                client.send_message(
                    appt.telegram_chat_id,
                    f"⏳ 15 daqiqadan keyin navbatingiz keladi.\n\n📍 {clinic_name}\n👨‍⚕️ {doctor_name}\n🕒 {when}\n\nQabulga kira olasizmi?",
                    reply_markup=reply_markup,
                )
            except Exception:
                Appointment.objects.filter(id=appt.id, telegram_15min_prompt_sent_at=claimed_at).update(telegram_15min_prompt_sent_at=None)
                continue

            count += 1

        return count
