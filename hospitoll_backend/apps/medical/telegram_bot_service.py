import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import requests
from django.conf import settings
from django.db import transaction
from django.db import IntegrityError
from django.db import models
from django.utils import timezone

from apps.doctors.models import DoctorAvailability
from apps.medical.models import Appointment, TelegramConversationState
from apps.medical.schedule_utils import validate_doctor_booking_window
from apps.medical.schedule_utils import validate_doctor_booking_window

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TelegramMessageContext:
    user_id: int
    chat_id: int
    text: str


class TelegramBotClient:
    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"

    def send_message(self, chat_id: int, text: str, reply_markup: dict | None = None) -> None:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            resp = requests.post(f"{self.base_url}/sendMessage", json=payload, timeout=10)
            data = resp.json() if resp.content else {}
            if not data.get('ok', False):
                logger.warning("Telegram sendMessage failed: %s", data)
        except Exception as e:
            logger.exception("Telegram sendMessage exception: %s", e)

    def answer_callback_query(self, callback_query_id: str, text: str | None = None) -> None:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        try:
            resp = requests.post(f"{self.base_url}/answerCallbackQuery", json=payload, timeout=10)
            data = resp.json() if resp.content else {}
            if not data.get('ok', False):
                logger.warning("Telegram answerCallbackQuery failed: %s", data)
        except Exception as e:
            logger.exception("Telegram answerCallbackQuery exception: %s", e)


class TelegramBotService:
    """Production-safe Telegram update handler.

    Notes:
    - Uses webhook updates (recommended).
    - Minimal state is stored in DB via TelegramConversationState.
    """

    def __init__(self):
        token = getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""
        self.bot_username = getattr(settings, "TELEGRAM_BOT_USERNAME", "") or "hosptol_bot"
        self.client: TelegramBotClient | None = TelegramBotClient(token) if token else None

    def _require_client(self) -> TelegramBotClient:
        if not self.client:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
        return self.client

    def handle_update(self, update: dict[str, Any]) -> None:
        if not update:
            return

        if "callback_query" in update:
            self._handle_callback_query(update["callback_query"])
            return

        message = update.get("message") or update.get("edited_message")
        if message and message.get("text"):
            ctx = TelegramMessageContext(
                user_id=int(message["from"]["id"]),
                chat_id=int(message["chat"]["id"]),
                text=str(message["text"]),
            )
            self._handle_message(ctx)

    def _handle_message(self, ctx: TelegramMessageContext) -> None:
        text = ctx.text.strip()
        if text.startswith("/start"):
            token = ""
            parts = text.split(maxsplit=1)
            if len(parts) == 2:
                token = parts[1].strip()
            logger.info("Telegram /start received user_id=%s chat_id=%s token=%s", ctx.user_id, ctx.chat_id, 'present' if bool(token) else 'missing')
            self._handle_start(ctx, token)
            return

        if text.startswith("/myappointments"):
            logger.info("Telegram /myappointments received user_id=%s chat_id=%s", ctx.user_id, ctx.chat_id)
            self._handle_myappointments(ctx)
            return

        # Reschedule conversation state (awaiting date/time)
        state = (
            TelegramConversationState.objects.filter(
                telegram_user_id=ctx.user_id,
                expires_at__gt=timezone.now(),
            )
            .select_related("appointment", "appointment__doctor", "appointment__clinic")
            .order_by("-created_at")
            .first()
        )
        if state and state.action == TelegramConversationState.Action.RESCHEDULE_AWAITING_DATETIME:
            self._handle_reschedule_datetime(ctx, state)
            return

        self._require_client().send_message(
            ctx.chat_id,
            "Buyruqlar:\n"
            "• /myappointments — yaqin randevular\n"
            "Token bilan tasdiqlash uchun: /start &lt;telegram_token&gt;",
        )

    def _handle_start(self, ctx: TelegramMessageContext, token: str) -> None:
        if not token:
            self._require_client().send_message(ctx.chat_id, "Token topilmadi. Linkdagi /start &lt;token&gt; ni qayta bosing.")
            return

        try:
            # token is UUID
            appointment = Appointment.objects.select_related("doctor", "clinic", "patient").get(telegram_token=token)
        except Appointment.DoesNotExist:
            self._require_client().send_message(ctx.chat_id, "Token noto‘g‘ri yoki ishlatilgan.")
            return

        if appointment.telegram_token_is_expired or appointment.status != Appointment.Status.PENDING_TELEGRAM_CONFIRMATION:
            self._require_client().send_message(ctx.chat_id, "Token muddati tugagan yoki randevu allaqachon tasdiqlangan.")
            return

        with transaction.atomic():
            appointment = Appointment.objects.select_for_update().get(id=appointment.id)
            if appointment.telegram_user_id and appointment.telegram_user_id != ctx.user_id:
                self._require_client().send_message(ctx.chat_id, "Bu randevu boshqa Telegram akkauntga bog‘langan.")
                return

            appointment.telegram_user_id = ctx.user_id
            appointment.telegram_chat_id = ctx.chat_id
            appointment.telegram_confirmed_at = timezone.now()
            # Keep legacy doctor dashboards working (they filter by 'scheduled')
            appointment.status = Appointment.Status.SCHEDULED

            # Make token one-time
            appointment.telegram_token = None
            appointment.telegram_token_expires_at = None
            appointment.save(
                update_fields=[
                    "telegram_user_id",
                    "telegram_chat_id",
                    "telegram_confirmed_at",
                    "status",
                    "telegram_token",
                    "telegram_token_expires_at",
                    "updated_at",
                ]
            )

        self._schedule_reminder_best_effort(appointment)

        when = timezone.localtime(appointment.scheduled_date).strftime("%d.%m.%Y %H:%M")
        doctor_name = appointment.doctor_name or (appointment.doctor.user.get_full_name() if appointment.doctor else "Doktor")
        clinic_name = appointment.clinic_name or (appointment.clinic.name if appointment.clinic else "Klinika")
        patient_name = (
            appointment.patient.user.get_full_name()
            if getattr(appointment, 'patient', None) and getattr(appointment.patient, 'user', None)
            else 'Bemor'
        )

        self._require_client().send_message(
            ctx.chat_id,
            f"✅ Tasdiqlandi!\n\n👤 {patient_name}\n📍 {clinic_name}\n👨‍⚕️ {doctor_name}\n🕒 {when}\n\n/myappointments orqali boshqaring.",
        )

    def _handle_myappointments(self, ctx: TelegramMessageContext) -> None:
        upcoming = (
            Appointment.objects.filter(
                telegram_user_id=ctx.user_id,
                scheduled_date__gte=timezone.now(),
            )
            .exclude(status__in=[Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW])
            .select_related("doctor", "clinic")
            .order_by("scheduled_date")
        )[:10]

        if not upcoming:
            self._require_client().send_message(ctx.chat_id, "Yaqin randevu topilmadi.")
            return

        lines: list[str] = ["📅 Yaqin randevular:"]
        keyboard: list[list[dict[str, str]]] = []

        for appt in upcoming:
            when = timezone.localtime(appt.scheduled_date).strftime("%d.%m.%Y %H:%M")
            doctor_name = appt.doctor_name or (appt.doctor.user.get_full_name() if appt.doctor else "Doktor")
            clinic_name = appt.clinic_name or (appt.clinic.name if appt.clinic else "Klinika")
            short_id = str(appt.id)[:8]
            if appt.status == Appointment.Status.IN_PROGRESS:
                lines.append(f"• ✅ <b>Doktor qabul qilgan</b> — {clinic_name} — {doctor_name} (#{short_id})")
            elif appt.status == Appointment.Status.COMPLETED:
                lines.append(f"• ✅ <b>Qabul yakunlangan</b> — {clinic_name} — {doctor_name} (#{short_id})")
            else:
                lines.append(f"• <b>{when}</b> — {clinic_name} — {doctor_name} (#{short_id})")

            # After doctor starts/finishes the visit, patient cannot manage queue/time from bot.
            if appt.status not in [Appointment.Status.IN_PROGRESS, Appointment.Status.COMPLETED]:
                keyboard.append(
                    [
                        {"text": "❌ Cancel", "callback_data": f"cancel:{appt.id}"},
                        {"text": "🗓 Reschedule", "callback_data": f"reschedule:{appt.id}"},
                    ]
                )

        self._require_client().send_message(
            ctx.chat_id,
            "\n".join(lines),
            reply_markup={"inline_keyboard": keyboard},
        )

    def _handle_callback_query(self, cq: dict[str, Any]) -> None:
        callback_id = str(cq.get("id"))
        data = str(cq.get("data") or "")
        from_user = cq.get("from") or {}
        message = cq.get("message") or {}
        chat = message.get("chat") or {}

        raw_user_id = from_user.get("id")
        raw_chat_id = chat.get("id")
        if raw_user_id is None or raw_chat_id is None:
            # Malformed update
            return
        user_id = int(raw_user_id)
        chat_id = int(raw_chat_id)

        client = self._require_client()
        try:
            if data.startswith('resday:'):
                parts = data.split(':', 2)
                if len(parts) != 3:
                    client.answer_callback_query(callback_id, "Noto‘g‘ri format")
                    return

                appt_id = parts[1]
                day_mode = parts[2]
                appt = Appointment.objects.filter(id=appt_id).select_related('doctor').only('id', 'telegram_user_id', 'status', 'doctor_id').first()
                if not appt or appt.telegram_user_id != user_id:
                    client.answer_callback_query(callback_id, "Ruxsat yo‘q")
                    return
                if appt.status in [Appointment.Status.IN_PROGRESS, Appointment.Status.COMPLETED]:
                    self._require_client().send_message(chat_id, "⚠️ Doktor qabulni boshlab yuborgan. Endi navbat vaqtini o‘zgartirib bo‘lmaydi.")
                    client.answer_callback_query(callback_id, "Locked")
                    return

                self._send_reschedule_day_slots(chat_id=chat_id, appointment=appt, day_mode=day_mode)
                client.answer_callback_query(callback_id, "Bo‘sh vaqtlar")
                return

            if data.startswith('reslot:'):
                parts = data.split(':', 2)
                if len(parts) != 3:
                    client.answer_callback_query(callback_id, "Noto‘g‘ri format")
                    return
                appt_id = parts[1]
                dt_token = parts[2]
                try:
                    target_dt = datetime.strptime(dt_token, "%Y%m%d%H%M")
                    target_date = target_dt.date()
                    target_time = target_dt.time().replace(second=0, microsecond=0)
                except Exception:
                    client.answer_callback_query(callback_id, "Vaqt formati xato")
                    return

                ok = self._attempt_reschedule(
                    telegram_user_id=user_id,
                    chat_id=chat_id,
                    appointment_id=appt_id,
                    target_date=target_date,
                    target_time=target_time,
                    state_id=None,
                )
                client.answer_callback_query(callback_id, "O‘zgartirildi" if ok else "Band yoki mos emas")
                return

            if data.startswith("cancel:"):
                appt_id = data.split(":", 1)[1]
                appt = Appointment.objects.filter(id=appt_id).only('id', 'telegram_user_id', 'status').first()
                if not appt or appt.telegram_user_id != user_id:
                    client.answer_callback_query(callback_id, "Ruxsat yo‘q")
                    return
                if appt.status in [Appointment.Status.IN_PROGRESS, Appointment.Status.COMPLETED]:
                    self._require_client().send_message(chat_id, "⚠️ Doktor qabulni boshlab yuborgan. Endi navbatni boshqarib bo‘lmaydi.")
                    client.answer_callback_query(callback_id, "Locked")
                    return
                self._cancel_appointment_from_bot(user_id, chat_id, appt_id)
                client.answer_callback_query(callback_id, "Cancelled")
                return

            if data.startswith("reschedule:"):
                appt_id = data.split(":", 1)[1]
                appt = Appointment.objects.filter(id=appt_id).only('id', 'telegram_user_id', 'status').first()
                if not appt or appt.telegram_user_id != user_id:
                    client.answer_callback_query(callback_id, "Ruxsat yo‘q")
                    return
                if appt.status in [Appointment.Status.IN_PROGRESS, Appointment.Status.COMPLETED]:
                    self._require_client().send_message(chat_id, "⚠️ Doktor qabulni boshlab yuborgan. Endi navbat vaqtini o‘zgartirib bo‘lmaydi.")
                    client.answer_callback_query(callback_id, "Locked")
                    return
                self._start_reschedule_flow(user_id, chat_id, appt_id)
                client.answer_callback_query(callback_id, "Reschedule")
                return

            if data.startswith('arrive:'):
                appt_id = data.split(':', 1)[1]
                appt = Appointment.objects.filter(id=appt_id).only('id', 'telegram_user_id', 'status').first()
                if not appt or appt.telegram_user_id != user_id:
                    client.answer_callback_query(callback_id, "Ruxsat yo‘q")
                    return
                if appt.status in [Appointment.Status.COMPLETED, Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW]:
                    self._require_client().send_message(chat_id, "⚠️ Doktor qabulni boshlab yuborgan. Endi navbatni boshqarib bo‘lmaydi.")
                    client.answer_callback_query(callback_id, "Locked")
                    return
                self._confirm_arrival_from_bot(user_id, chat_id, appt_id)
                client.answer_callback_query(callback_id, 'OK')
                return

            if data.startswith('cancel15:'):
                appt_id = data.split(':', 1)[1]
                appt = Appointment.objects.filter(id=appt_id).only('id', 'telegram_user_id', 'status').first()
                if not appt or appt.telegram_user_id != user_id:
                    client.answer_callback_query(callback_id, "Ruxsat yo‘q")
                    return
                if appt.status in [Appointment.Status.IN_PROGRESS, Appointment.Status.COMPLETED]:
                    self._require_client().send_message(chat_id, "⚠️ Doktor qabulni boshlab yuborgan. Endi navbatni boshqarib bo‘lmaydi.")
                    client.answer_callback_query(callback_id, "Locked")
                    return
                self._cancel_appointment_from_bot(user_id, chat_id, appt_id, compress_queue=True)
                client.answer_callback_query(callback_id, 'Cancelled')
                return

            client.answer_callback_query(callback_id)
        except Exception as e:
            logger.exception("Telegram callback handling error: %s", e)
            try:
                client.answer_callback_query(callback_id, "Error")
            except Exception:
                pass

    def _cancel_appointment_from_bot(self, telegram_user_id: int, chat_id: int, appointment_id: str, compress_queue: bool = False) -> None:
        with transaction.atomic():
            appt = Appointment.objects.select_for_update().select_related("slot").filter(id=appointment_id).first()
            if not appt or appt.telegram_user_id != telegram_user_id:
                self._require_client().send_message(chat_id, "Randevu topilmadi yoki ruxsat yo‘q.")
                return

            if appt.status in [Appointment.Status.IN_PROGRESS, Appointment.Status.COMPLETED]:
                self._require_client().send_message(
                    chat_id,
                    "⚠️ Doktor qabulni boshlab yuborgan. Endi navbatni boshqarib bo‘lmaydi.",
                )
                return

            if appt.status == Appointment.Status.CANCELLED:
                self._require_client().send_message(chat_id, "Randevu allaqachon bekor qilingan.")
                return

            # Free slot
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
            appt.save(update_fields=["status", "updated_at"])

            if compress_queue and getattr(appt, 'doctor_id', None) and getattr(appt, 'queue_position', 0):
                Appointment.objects.filter(
                    doctor_id=getattr(appt, 'doctor_id', None),
                    scheduled_date__date=timezone.localdate(appt.scheduled_date),
                    queue_position__gt=appt.queue_position,
                ).update(queue_position=models.F('queue_position') - 1)

        self._require_client().send_message(chat_id, "✅ Randevu bekor qilindi.")

    def _confirm_arrival_from_bot(self, telegram_user_id: int, chat_id: int, appointment_id: str) -> None:
        queue_updates: list[dict[str, Any]] = []
        confirmed_id: str | None = None
        with transaction.atomic():
            appt = Appointment.objects.select_for_update().filter(id=appointment_id).first()
            if not appt or appt.telegram_user_id != telegram_user_id:
                self._require_client().send_message(chat_id, "Randevu topilmadi yoki ruxsat yo‘q.")
                return
            if appt.status in [Appointment.Status.COMPLETED, Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW]:
                self._require_client().send_message(
                    chat_id,
                    "⚠️ Doktor qabulni boshlab yuborgan. Endi navbatni boshqarib bo‘lmaydi.",
                )
                return
            if getattr(appt, 'patient_arrival_confirmed_at', None) is None:
                appt.patient_arrival_confirmed_at = timezone.now()
                appt.save(update_fields=['patient_arrival_confirmed_at', 'updated_at'])
            confirmed_id = str(appt.id)

            doctor_id = getattr(appt, 'doctor_id', None)
            if doctor_id:
                appointment_date = timezone.localtime(appt.scheduled_date).date()
                queue_step_minutes = 30
                active_statuses = (
                    Appointment.Status.SCHEDULED,
                    Appointment.Status.CONFIRMED,
                    Appointment.Status.WAITING,
                    Appointment.Status.IN_PROGRESS,
                )
                queue_items = list(
                    Appointment.objects.select_for_update()
                    .filter(
                        doctor_id=doctor_id,
                        scheduled_date__date=appointment_date,
                        status__in=active_statuses,
                    )
                    .order_by('queue_position', 'scheduled_date', 'created_at')
                )

                target_position = int(getattr(appt, 'queue_position', 1) or 1)
                queue_cursor = timezone.localtime().replace(second=0, microsecond=0)
                next_position = target_position
                for item in queue_items:
                    item_position = int(getattr(item, 'queue_position', 0) or 0)
                    if item_position < target_position:
                        continue

                    current_local = timezone.localtime(item.scheduled_date).replace(second=0, microsecond=0)
                    new_local = queue_cursor

                    update_fields = ['updated_at']
                    if item.queue_position != next_position:
                        item.queue_position = next_position
                        update_fields.append('queue_position')
                    if new_local != current_local:
                        item.scheduled_date = new_local
                        update_fields.append('scheduled_date')
                    item.save(update_fields=update_fields)

                    queue_updates.append(
                        {
                            'id': str(item.id),
                            'chat_id': int(item.telegram_chat_id) if item.telegram_chat_id else None,
                            'old_dt': current_local,
                            'new_dt': new_local,
                        }
                    )

                    next_position += 1
                    queue_cursor = new_local + timedelta(minutes=queue_step_minutes)

        self._require_client().send_message(chat_id, "✅ Qabulga borishingiz tasdiqlandi.")

        skip_threshold = timezone.now() - timedelta(minutes=10)
        for rec in queue_updates:
            if not rec.get('chat_id'):
                continue

            if confirmed_id and rec['id'] == confirmed_id:
                recent_confirm = Appointment.objects.filter(
                    id=confirmed_id,
                    patient_arrival_confirmed_at__gte=skip_threshold,
                ).exists()
                if recent_confirm:
                    continue

            self._require_client().send_message(
                rec['chat_id'],
                "⏱️ Navbat vaqtingiz yangilandi.\n"
                f"Eski vaqt: {rec['old_dt'].strftime('%d.%m.%Y %H:%M')}\n"
                f"Yangi vaqt: {rec['new_dt'].strftime('%d.%m.%Y %H:%M')}\n"
                "Sabab: navbat oldinga surildi.",
            )

    def _start_reschedule_flow(self, telegram_user_id: int, chat_id: int, appointment_id: str) -> None:
        appt = Appointment.objects.filter(id=appointment_id, telegram_user_id=telegram_user_id).first()
        if not appt:
            self._require_client().send_message(chat_id, "Randevu topilmadi yoki ruxsat yo‘q.")
            return

        if appt.status in [Appointment.Status.IN_PROGRESS, Appointment.Status.COMPLETED]:
            self._require_client().send_message(
                chat_id,
                "⚠️ Doktor qabulni boshlab yuborgan. Endi navbat vaqtini o‘zgartirib bo‘lmaydi.",
            )
            return

        TelegramConversationState.objects.filter(telegram_user_id=telegram_user_id).delete()
        TelegramConversationState.objects.create(
            telegram_user_id=telegram_user_id,
            appointment=appt,
            action=TelegramConversationState.Action.RESCHEDULE_AWAITING_DATETIME,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        self._require_client().send_message(
            chat_id,
            "Yangi vaqtni yuboring: <b>YYYY-MM-DD HH:MM</b> (masalan: 2026-03-01 14:30)\n\n"
            "Yoki bo‘sh vaqtlarni kun bo‘yicha tanlang:",
            reply_markup={
                "inline_keyboard": [
                    [{"text": "📅 Bugun", "callback_data": f"resday:{appt.id}:today"}],
                    [{"text": "📅 Ertaga", "callback_data": f"resday:{appt.id}:tomorrow"}],
                    [{"text": "📅 Keyingi 3 kun", "callback_data": f"resday:{appt.id}:next3"}],
                ]
            },
        )

    def _send_reschedule_day_slots(self, chat_id: int, appointment: Appointment, day_mode: str) -> None:
        if day_mode == 'today':
            day_offsets = [0]
            title = 'Bugungi bo‘sh vaqtlar:'
        elif day_mode == 'tomorrow':
            day_offsets = [1]
            title = 'Ertangi bo‘sh vaqtlar:'
        else:
            day_offsets = [1, 2, 3]
            title = 'Keyingi 3 kun ichidagi bo‘sh vaqtlar:'

        suggestions = self._format_slot_suggestions(
            doctor=appointment.doctor,
            from_dt=timezone.localtime(),
            exclude_appointment_id=appointment.id,
            limit=12,
            day_offsets=day_offsets,
        )

        if not suggestions:
            self._require_client().send_message(chat_id, f"{title}\nBo‘sh vaqt topilmadi.")
            return

        keyboard = [
            [{
                "text": dt_obj.strftime("%d.%m %H:%M"),
                "callback_data": f"reslot:{appointment.id}:{dt_obj.strftime('%Y%m%d%H%M')}"
            }]
            for dt_obj in suggestions
        ]
        self._require_client().send_message(
            chat_id,
            title,
            reply_markup={"inline_keyboard": keyboard},
        )

    def _format_slot_suggestions(self, doctor, from_dt: datetime, exclude_appointment_id=None, limit: int = 5, day_offsets: list[int] | None = None) -> list[datetime]:
        duration_minutes = int(getattr(doctor, "slot_minutes", 30) or 30)
        if duration_minutes not in (15, 20, 30):
            duration_minutes = 30

        tz = timezone.get_current_timezone()
        now_local = timezone.localtime(from_dt)
        max_date = now_local.date() + timedelta(days=3)

        busy_intervals: dict = {}
        appointments_qs = (
            Appointment.objects.filter(
                doctor=doctor,
                scheduled_date__date__gte=now_local.date(),
                scheduled_date__date__lte=max_date,
            )
            .exclude(status__in=[Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW])
            .exclude(id=exclude_appointment_id)
            .only('scheduled_date', 'duration_minutes')
        )
        for appt in appointments_qs:
            start_local = timezone.localtime(appt.scheduled_date)
            day = start_local.date()
            end_local = start_local + timedelta(minutes=int(appt.duration_minutes or duration_minutes))
            busy_intervals.setdefault(day, []).append((start_local, end_local))

        blocked_starts = set(
            DoctorAvailability.objects.filter(
                doctor=doctor,
                date__gte=now_local.date(),
                date__lte=max_date,
            )
            .exclude(status='available')
            .values_list('date', 'start_time')
        )

        suggestions: list[datetime] = []
        offsets = day_offsets if day_offsets is not None else [0, 1, 2, 3]
        for day_offset in offsets:
            target_date = now_local.date() + timedelta(days=day_offset)

            day_key = target_date.strftime('%a')
            working_days = [d.strip() for d in (doctor.working_days or '').split(',') if d.strip()]
            if working_days and day_key not in working_days:
                continue

            day_start = datetime.combine(target_date, doctor.available_from)
            day_end = datetime.combine(target_date, doctor.available_until)
            if day_start >= day_end:
                continue

            lunch_start = getattr(doctor, 'lunch_break_start', None)
            lunch_end = getattr(doctor, 'lunch_break_end', None)
            lunch_start_dt = datetime.combine(target_date, lunch_start) if lunch_start else None
            lunch_end_dt = datetime.combine(target_date, lunch_end) if lunch_end else None

            step = timedelta(minutes=duration_minutes)
            cutoff_start = day_end - timedelta(minutes=10)
            cursor = day_start

            while cursor + step <= day_end:
                slot_end = cursor + step

                if cursor >= cutoff_start:
                    cursor += step
                    continue

                if lunch_start_dt and lunch_end_dt and lunch_start_dt < lunch_end_dt and cursor < lunch_end_dt and slot_end > lunch_start_dt:
                    cursor += step
                    continue

                slot_start_aware = timezone.make_aware(cursor, tz)
                slot_end_aware = timezone.make_aware(slot_end, tz)
                if slot_start_aware <= now_local:
                    cursor += step
                    continue

                if (target_date, cursor.time()) in blocked_starts:
                    cursor += step
                    continue

                is_busy = False
                for busy_start, busy_end in busy_intervals.get(target_date, []):
                    if slot_start_aware < busy_end and slot_end_aware > busy_start:
                        is_busy = True
                        break
                if is_busy:
                    cursor += step
                    continue

                suggestions.append(slot_start_aware)
                if len(suggestions) >= limit:
                    return suggestions

                cursor += step

        return suggestions

    def _send_reschedule_reject_with_suggestions(self, chat_id: int, doctor, base_message: str, from_dt: datetime, exclude_appointment_id=None, appointment_id=None) -> None:
        suggestions = self._format_slot_suggestions(
            doctor=doctor,
            from_dt=from_dt,
            exclude_appointment_id=exclude_appointment_id,
            limit=5,
        )
        if suggestions:
            suggestion_text = "\n".join([f"• {item.strftime('%d.%m.%Y %H:%M')}" for item in suggestions])
            reply_markup = None
            if appointment_id:
                keyboard = [
                    [{
                        "text": dt_obj.strftime("%d.%m %H:%M"),
                        "callback_data": f"reslot:{appointment_id}:{dt_obj.strftime('%Y%m%d%H%M')}"
                    }]
                    for dt_obj in suggestions
                ]
                reply_markup = {"inline_keyboard": keyboard}
            self._require_client().send_message(
                chat_id,
                f"{base_message}\n\nYaqin bo‘sh vaqtlar:\n{suggestion_text}",
                reply_markup=reply_markup,
            )
            return

        self._require_client().send_message(
            chat_id,
            f"{base_message}\n\nYaqin bo‘sh vaqt topilmadi.",
        )

    def _attempt_reschedule(self, telegram_user_id: int, chat_id: int, appointment_id: str, target_date, target_time, state_id=None) -> bool:
        appt = Appointment.objects.filter(id=appointment_id).select_related('doctor', 'slot').first()
        if not appt or appt.telegram_user_id != telegram_user_id:
            self._require_client().send_message(chat_id, "Ruxsat yo‘q.")
            return False

        if appt.status in [Appointment.Status.IN_PROGRESS, Appointment.Status.COMPLETED]:
            self._require_client().send_message(
                chat_id,
                "⚠️ Doktor qabulni boshlab yuborgan. Endi navbat vaqtini o‘zgartirib bo‘lmaydi.",
            )
            if state_id:
                TelegramConversationState.objects.filter(id=state_id).delete()
            return False

        doctor = appt.doctor
        if not doctor:
            self._require_client().send_message(chat_id, "Doktor topilmadi.")
            return False

        duration_minutes = int(getattr(doctor, "slot_minutes", 30) or 30)
        if duration_minutes not in (15, 20, 30):
            duration_minutes = 30

        tz = timezone.get_current_timezone()
        new_dt = timezone.make_aware(datetime.combine(target_date, target_time), tz)
        if new_dt < timezone.now():
            self._require_client().send_message(chat_id, "O‘tgan vaqtni tanlab bo‘lmaydi.")
            return False

        booking_window_error = validate_doctor_booking_window(
            doctor=doctor,
            target_date=target_date,
            target_time=target_time,
            duration_minutes=duration_minutes,
        )
        if booking_window_error:
            self._send_reschedule_reject_with_suggestions(
                chat_id=chat_id,
                doctor=doctor,
                base_message=booking_window_error,
                from_dt=max(new_dt, timezone.now()),
                exclude_appointment_id=appt.id,
                appointment_id=appointment_id,
            )
            return False

        req_start = datetime.combine(target_date, target_time)
        req_end_dt = req_start + timedelta(minutes=duration_minutes)
        req_end = req_end_dt.time()

        with transaction.atomic():
            appt = Appointment.objects.select_for_update().select_related("slot").get(id=appt.id)
            try:
                slot_obj, _ = DoctorAvailability.objects.get_or_create(
                    doctor=doctor,
                    date=target_date,
                    start_time=target_time,
                    defaults={"end_time": req_end, "status": "available"},
                )
            except IntegrityError:
                slot_obj = DoctorAvailability.objects.get(
                    doctor=doctor,
                    date=target_date,
                    start_time=target_time,
                )
            slot_obj = DoctorAvailability.objects.select_for_update().get(id=slot_obj.id)

            if slot_obj.end_time != req_end:
                self._send_reschedule_reject_with_suggestions(
                    chat_id=chat_id,
                    doctor=doctor,
                    base_message="Tanlangan vaqt slot tizimiga mos emas.",
                    from_dt=max(new_dt, timezone.now()),
                    exclude_appointment_id=appt.id,
                    appointment_id=appointment_id,
                )
                return False
            if slot_obj.status != "available":
                self._send_reschedule_reject_with_suggestions(
                    chat_id=chat_id,
                    doctor=doctor,
                    base_message="Tanlangan vaqt band qilingan.",
                    from_dt=max(new_dt, timezone.now()),
                    exclude_appointment_id=appt.id,
                    appointment_id=appointment_id,
                )
                return False

            old_slot_id = getattr(appt, 'slot_id', None)
            if old_slot_id:
                try:
                    old_slot = DoctorAvailability.objects.select_for_update().get(id=old_slot_id)
                    if old_slot.status == "booked":
                        old_slot.status = "available"
                        old_slot.save(update_fields=["status"])
                except DoctorAvailability.DoesNotExist:
                    pass

            slot_obj.status = "booked"
            slot_obj.save(update_fields=["status"])

            appt.slot = slot_obj  # type: ignore[assignment]
            appt.scheduled_date = new_dt
            appt.duration_minutes = duration_minutes
            appt.status = Appointment.Status.SCHEDULED
            appt.telegram_reminder_sent_at = None
            appt.save(update_fields=["slot", "scheduled_date", "duration_minutes", "status", "telegram_reminder_sent_at", "updated_at"])

            if state_id:
                TelegramConversationState.objects.filter(id=state_id).delete()

        self._schedule_reminder_best_effort(appt)
        when = timezone.localtime(appt.scheduled_date).strftime("%d.%m.%Y %H:%M")
        self._require_client().send_message(chat_id, f"✅ O‘zgartirildi: {when}")
        return True

    def _handle_reschedule_datetime(self, ctx: TelegramMessageContext, state: TelegramConversationState) -> None:
        text = ctx.text.strip()
        m = re.match(r"^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})$", text)
        if not m:
            self._require_client().send_message(ctx.chat_id, "Format noto‘g‘ri. Masalan: 2026-03-01 14:30")
            return

        try:
            target_date = datetime.strptime(m.group(1), "%Y-%m-%d").date()
            target_time = datetime.strptime(m.group(2), "%H:%M").time()
        except Exception:
            self._require_client().send_message(ctx.chat_id, "Sana/vaqt noto‘g‘ri.")
            return

        self._attempt_reschedule(
            telegram_user_id=ctx.user_id,
            chat_id=ctx.chat_id,
            appointment_id=str(state.appointment_id),
            target_date=target_date,
            target_time=target_time,
            state_id=state.id,
        )

    def _schedule_reminder_best_effort(self, appt: Appointment) -> None:
        try:
            from .tasks import send_telegram_appointment_reminder

            eta = appt.scheduled_date - timedelta(hours=1)
            if eta <= timezone.now():
                return
            if not appt.telegram_chat_id:
                return
            send_telegram_appointment_reminder.apply_async(args=[str(appt.id)], eta=eta)  # type: ignore[attr-defined]
        except Exception:
            # Don't break webhook
            return
