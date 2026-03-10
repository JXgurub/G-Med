from datetime import datetime, timedelta
import calendar
import re
from uuid import uuid4
from typing import Any, cast
from decimal import Decimal

from django.db import transaction
from django.db import IntegrityError
from django.db.models import Count, Sum, Q, Value, DecimalField
from django.db.models.functions import TruncMonth, Coalesce
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
import django_filters
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

from apps.doctors.models import Doctor, DoctorAvailability, DoctorWorkRecord, DoctorSpecialization
from apps.clinics.models import Clinic
from apps.patients.models import Patient
from apps.users.models import CustomUser
from core.permissions.custom_permissions import IsDoctor
from core.error_logging import ErrorLogger
from .models import Appointment, MedicalRecord, Diagnosis, Prescription, LabTest
from .serializers import (
    AppointmentSerializer,
    OnlineAppointmentSerializer,
    PublicTelegramBookingSerializer,
    MedicalRecordSerializer,
    DiagnosisSerializer,
    PrescriptionSerializer,
    LabTestSerializer,
)
from .schedule_utils import validate_doctor_booking_window


def _resolve_default_consultation_fee_for_doctor(doctor: Doctor | None) -> Decimal:
    if not doctor:
        return Decimal('0')

    doctor_default_fee = Decimal(getattr(doctor, 'consultation_fee', 0) or 0)
    if doctor_default_fee > 0:
        return doctor_default_fee

    specialty_fees = [
        Decimal(fee or 0)
        for fee in DoctorSpecialization.objects.filter(
            doctor=doctor,
            is_active=True,
        ).values_list('consultation_fee', flat=True).distinct()
    ]
    positive_fees = [fee for fee in specialty_fees if fee > 0]
    if len(set(positive_fees)) == 1:
        return positive_fees[0]

    return doctor_default_fee


class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.select_related('patient', 'doctor', 'clinic').all()
    serializer_class = AppointmentSerializer

    class Filter(django_filters.FilterSet):
        status = django_filters.CharFilter(method='filter_status')

        class Meta:
            model = Appointment
            fields = ['patient', 'doctor', 'clinic', 'status']

        def filter_status(self, queryset, name, value):
            if not value:
                return queryset
            raw = str(value)
            if ',' in raw:
                statuses = [s.strip() for s in raw.split(',') if s.strip()]
                return queryset.filter(status__in=statuses) if statuses else queryset
            return queryset.filter(status=raw.strip())

    filterset_class = Filter
    permission_classes = [permissions.IsAuthenticated]

    def _require_active_assigned_doctor(self, request):
        doctor = getattr(request.user, 'doctor', None)
        if not doctor:
            return None
        if not doctor.is_active or not doctor.clinic_id:
            raise PermissionDenied("Siz klinikada faol emassiz. Faqat profilingizni tahrirlashingiz mumkin.")
        return doctor

    def perform_update(self, serializer):
        before: Appointment = self.get_object()
        before_status = before.status
        instance: Appointment = serializer.save()

        # Note: patient notification is sent via explicit endpoint (notify_ready)
        # to avoid duplicates and to allow including patient portal login details.

    @action(detail=True, methods=['post'], permission_classes=[IsDoctor])
    def notify_ready(self, request, pk=None):
        """Send a Telegram message to the patient when doctor accepts the visit.

        Notes:
        - Django passwords are hashed; we cannot read a patient's existing password back from DB.
        - If doctor just set a new password in the UI, it can be passed in request body to include
          in this one-time message.
        """
        appointment: Appointment = self.get_object()

        doctor = self._require_active_assigned_doctor(request)
        if not doctor or not appointment.doctor_id or appointment.doctor_id != doctor.id:
            return Response({'detail': 'Ruxsat berilmagan'}, status=status.HTTP_403_FORBIDDEN)

        if not appointment.telegram_chat_id:
            return Response(
                {'detail': 'Bemor Telegram orqali tasdiqlamagan (chat_id topilmadi)'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mode = (request.data or {}).get('mode')
        mode = str(mode).strip().lower() if mode is not None else ''

        passport_id = (request.data or {}).get('passport_id')
        password = (request.data or {}).get('password')
        if not passport_id:
            passport_id = getattr(appointment.patient, 'national_id', None) or ''
        passport_id = str(passport_id).strip() if passport_id is not None else ''
        password = str(password).strip() if password is not None else ''

        frontend_url = (getattr(settings, 'FRONTEND_URL', '') or '').rstrip('/')
        login_url = f"{frontend_url}/patient-login" if frontend_url else "/patient-login"

        from .telegram_bot_service import TelegramBotService

        try:
            service = TelegramBotService()
            client = service._require_client()
        except Exception:
            return Response(
                {'detail': 'Telegram bot sozlanmagan (TELEGRAM_BOT_TOKEN)'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if mode == 'ready':
            client.send_message(
                int(appointment.telegram_chat_id),
                "Doktor sizni qabul qilishga tayyor",
            )
            return Response({'sent': True})

        text = (
            "✅ Doktor sizni qabul qildi.\n\n"
            "Doktorni baholash va o'zinggizning kasallik tarixinggiz va yozilgan dorilarni "
            f"ko'rmoqchi bo'lsanggiz shu {login_url} link orqali pasport idsi va parolni "
            "tergan xolatda ko'rishinggiz mumkin.\n\n"
        )
        text += f"Pasport ID: {passport_id}\n"
        if password:
            text += f"Parol: {password}\n"
        else:
            has_existing_password = bool(
                getattr(getattr(appointment, 'patient', None), 'user', None)
                and appointment.patient.user.has_usable_password()
            )
            if has_existing_password:
                text += (
                    "Parol: (sizda oldindan parol mavjud, shu parol orqali bemalol kirishingiz mumkin. "
                    "Yoki sayt orqali yangi parol o'rnatishingiz mumkin)\n"
                )
            else:
                text += "Parol: (hali o‘rnatilmagan. Doktor sizga parol o‘rnatib yuboradi)\n"

        client.send_message(int(appointment.telegram_chat_id), text)
        return Response({'sent': True})

    def _normalize_phone(self, phone: str) -> str:
        phone = (phone or '').strip()
        digits = re.sub(r"\D+", "", phone)
        return digits

    def _split_full_name(self, full_name: str) -> tuple[str, str]:
        full_name = (full_name or '').strip()
        parts = [p for p in re.split(r"\s+", full_name) if p]
        if not parts:
            return "Guest", ""
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], " ".join(parts[1:])

    def _validate_doctor_booking_window(
        self,
        doctor,
        target_date,
        target_time,
        duration_minutes: int,
    ) -> str | None:
        return validate_doctor_booking_window(
            doctor=doctor,
            target_date=target_date,
            target_time=target_time,
            duration_minutes=duration_minutes,
        )

    def _free_slot_if_possible(self, appointment: Appointment) -> None:
        slot = getattr(appointment, 'slot', None)
        if not slot:
            return
        try:
            locked = DoctorAvailability.objects.select_for_update().get(id=slot.id)
        except DoctorAvailability.DoesNotExist:
            return
        if locked.status == 'booked':
            locked.status = 'available'
            locked.save(update_fields=['status'])

    def _queue_active_statuses(self) -> tuple[str, ...]:
        return (
            Appointment.Status.SCHEDULED,
            Appointment.Status.CONFIRMED,
            Appointment.Status.WAITING,
            Appointment.Status.IN_PROGRESS,
        )

    def _format_local_dt(self, dt) -> str:
        return timezone.localtime(dt).strftime('%d.%m.%Y %H:%M')

    def _to_bool(self, value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}

    def _resolve_booking_fee(self, doctor: Doctor, specialty_price_id: str | None = None) -> tuple[Decimal | None, str | None]:
        doctor_default_fee = _resolve_default_consultation_fee_for_doctor(doctor)

        if specialty_price_id:
            specialty_price = DoctorSpecialization.objects.filter(
                id=specialty_price_id,
                doctor=doctor,
                is_active=True,
            ).only('consultation_fee').first()
            if specialty_price:
                specialty_fee = Decimal(specialty_price.consultation_fee or 0)
                if specialty_fee > 0:
                    return specialty_fee, None
                if doctor_default_fee > 0:
                    return doctor_default_fee, None
                return specialty_price.consultation_fee, None
            return None, 'Tanlangan ixtisoslik narxi topilmadi yoki faol emas.'

        active_specialty_fees = list(
            DoctorSpecialization.objects.filter(
                doctor=doctor,
                is_active=True,
            )
            .values_list('consultation_fee', flat=True)
            .distinct()
        )
        if len(active_specialty_fees) == 1:
            specialty_fee = Decimal(active_specialty_fees[0] or 0)
            if specialty_fee > 0:
                return specialty_fee, None
            if doctor_default_fee > 0:
                return doctor_default_fee, None
            return specialty_fee, None
        if len(active_specialty_fees) > 1:
            return None, 'Bir nechta ixtisoslik narxlari mavjud. Iltimos ixtisoslikni tanlang.'

        return doctor_default_fee, None

    @action(detail=True, methods=['post'], permission_classes=[IsDoctor])
    def queue_decision(self, request, pk=None):
        """Doctor queue controls from dashboard buttons.

        decision=enter  -> patient can enter now (no extra delay)
        decision=wait   -> add 15-minute delay and recalculate queue times
        decision=cancel -> cancel appointment and compress queue

        For appointments shifted by >=15 minutes, a Telegram update is sent (best-effort).
        """
        appointment: Appointment = self.get_object()
        doctor = self._require_active_assigned_doctor(request)
        if not doctor or not appointment.doctor_id or appointment.doctor_id != doctor.id:
            return Response({'detail': 'Ruxsat berilmagan'}, status=status.HTTP_403_FORBIDDEN)

        decision = str((request.data or {}).get('decision') or '').strip().lower()
        notify_current = self._to_bool((request.data or {}).get('notify_current'), default=True)
        notify_all_shifted = self._to_bool((request.data or {}).get('notify_all_shifted'), default=False)
        if decision not in {'enter', 'wait', 'cancel'}:
            return Response({'detail': 'decision faqat enter, wait yoki cancel bo‘lishi mumkin.'}, status=status.HTTP_400_BAD_REQUEST)

        if appointment.status in [Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW, Appointment.Status.COMPLETED]:
            return Response({'detail': 'Bu qabul uchun navbat boshqaruvi mumkin emas.'}, status=status.HTTP_400_BAD_REQUEST)

        status_filter = self._queue_active_statuses()
        shifted_records: list[dict[str, Any]] = []
        queue_updated_count = 0
        selected_new_local = None
        now_local = timezone.localtime().replace(second=0, microsecond=0)
        queue_step_minutes = int(getattr(doctor, 'slot_minutes', 30) or 30)
        if queue_step_minutes not in (15, 20, 30):
            queue_step_minutes = 30

        if decision == 'cancel':
            with transaction.atomic():
                target = (
                    Appointment.objects.select_for_update()
                    .filter(id=appointment.id, doctor=doctor)
                    .first()
                )
                if not target:
                    return Response({'detail': 'Qabul topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
                if target.status in [Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW, Appointment.Status.COMPLETED]:
                    return Response({'detail': 'Bu qabulni bekor qilib bo‘lmaydi.'}, status=status.HTTP_400_BAD_REQUEST)

                appointment_date = timezone.localtime(target.scheduled_date).date()
                target_queue_position = int(target.queue_position or 1)
                self._free_slot_if_possible(target)
                target.status = Appointment.Status.CANCELLED
                target.save(update_fields=['status', 'updated_at'])

                later_items = list(
                    Appointment.objects.select_for_update()
                    .filter(
                        doctor=doctor,
                        scheduled_date__date=appointment_date,
                        status__in=status_filter,
                        queue_position__gt=target_queue_position,
                    )
                    .order_by('queue_position', 'scheduled_date', 'created_at')
                )

                next_pos = target_queue_position
                queue_cursor = now_local
                for item in later_items:
                    current_local = timezone.localtime(item.scheduled_date).replace(second=0, microsecond=0)
                    new_local = queue_cursor

                    update_fields = ['updated_at']
                    row_changed = False
                    if item.queue_position != next_pos:
                        item.queue_position = next_pos
                        update_fields.append('queue_position')
                        row_changed = True
                    next_pos += 1

                    if new_local != current_local:
                        delta_minutes = int((new_local - current_local).total_seconds() // 60)
                        item.scheduled_date = new_local
                        update_fields.append('scheduled_date')
                        row_changed = True
                        shifted_records.append(
                            {
                                'id': str(item.id),
                                'chat_id': int(item.telegram_chat_id) if item.telegram_chat_id else None,
                                'old_dt': current_local,
                                'new_dt': new_local,
                                'delta_minutes': delta_minutes,
                            }
                        )

                    item.save(update_fields=update_fields)
                    if row_changed:
                        queue_updated_count += 1
                    queue_cursor = new_local + timedelta(minutes=queue_step_minutes)

                appointment = target
        else:
            appointment_date = timezone.localtime(appointment.scheduled_date).date()
            extra_delay_minutes = 15 if decision == 'wait' else 0
            queue_cursor = now_local + timedelta(minutes=extra_delay_minutes)

            with transaction.atomic():
                queue_items = list(
                    Appointment.objects.select_for_update()
                    .filter(
                        doctor=doctor,
                        scheduled_date__date=appointment_date,
                        status__in=status_filter,
                    )
                    .order_by('queue_position', 'scheduled_date', 'created_at')
                )

                if not any(item.id == appointment.id for item in queue_items):
                    return Response({'detail': 'Qabul bugungi faol navbatda topilmadi.'}, status=status.HTTP_400_BAD_REQUEST)

                # Backend safety: only queue leader can be entered or deferred.
                queue_leader = queue_items[0] if queue_items else None
                if queue_leader and queue_leader.id != appointment.id:
                    return Response(
                        {'detail': 'Faqat navbatdagi 1-bemor uchun ushbu amalni bajarish mumkin.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                target_item = next(item for item in queue_items if item.id == appointment.id)
                remaining_items = [item for item in queue_items if item.id != appointment.id]

                if decision == 'enter':
                    ordered_items = [target_item, *remaining_items]
                else:
                    # wait: move selected patient one step back, then recalculate ETA.
                    old_index = next((idx for idx, item in enumerate(queue_items) if item.id == target_item.id), 0)
                    new_index = min(old_index + 1, len(remaining_items))
                    ordered_items = [
                        *remaining_items[:new_index],
                        target_item,
                        *remaining_items[new_index:],
                    ]

                min_wait_local = now_local + timedelta(minutes=15)
                for next_pos, item in enumerate(ordered_items, start=1):
                    current_local = timezone.localtime(item.scheduled_date).replace(second=0, microsecond=0)
                    base_local = current_local if current_local > queue_cursor else queue_cursor

                    if decision == 'enter' and item.id == appointment.id:
                        new_local = queue_cursor
                    elif decision == 'wait' and item.id == appointment.id:
                        new_local = base_local if base_local > min_wait_local else min_wait_local
                    else:
                        new_local = base_local

                    update_fields = ['updated_at']
                    row_changed = False

                    if item.queue_position != next_pos:
                        item.queue_position = next_pos
                        update_fields.append('queue_position')
                        row_changed = True

                    if item.id == appointment.id:
                        selected_new_local = new_local

                    if new_local != current_local:
                        delta_minutes = int((new_local - current_local).total_seconds() // 60)
                        item.scheduled_date = new_local
                        update_fields.append('scheduled_date')
                        row_changed = True
                        shifted_records.append(
                            {
                                'id': str(item.id),
                                'chat_id': int(item.telegram_chat_id) if item.telegram_chat_id else None,
                                'old_dt': current_local,
                                'new_dt': new_local,
                                'delta_minutes': delta_minutes,
                            }
                        )

                    item.save(update_fields=update_fields)
                    if row_changed:
                        queue_updated_count += 1

                    queue_cursor = new_local + timedelta(minutes=queue_step_minutes)

        notified_count = 0
        try:
            from .telegram_bot_service import TelegramBotService

            service = TelegramBotService()
            client = service._require_client()

            if appointment.telegram_chat_id and notify_current:
                if decision == 'enter':
                    display_dt = selected_new_local or timezone.localtime(appointment.scheduled_date)
                    client.send_message(
                        int(appointment.telegram_chat_id),
                        f"🚪 Navbat sizga keldi, kirishingiz mumkin.\n🕒 Taxminiy vaqt: {self._format_local_dt(display_dt)}",
                    )
                    notified_count += 1
                elif decision == 'wait':
                    display_dt = selected_new_local or timezone.localtime(appointment.scheduled_date)
                    client.send_message(
                        int(appointment.telegram_chat_id),
                        f"⏳ Iltimos biroz kuting. Navbat qayta hisoblandi.\n🕒 Yangi taxminiy vaqt: {self._format_local_dt(display_dt)}",
                    )
                    notified_count += 1
                elif decision == 'cancel':
                    client.send_message(
                        int(appointment.telegram_chat_id),
                        "❌ Qabulingiz bekor qilindi.\nAgar kerak bo‘lsa qayta navbat olishingiz mumkin.",
                    )
                    notified_count += 1

            recently_arrived_ids: set[str] = set()
            if shifted_records:
                threshold = timezone.now() - timedelta(minutes=10)
                shifted_ids = [rec['id'] for rec in shifted_records if rec.get('id')]
                if shifted_ids:
                    recently_arrived_ids = {
                        str(item_id)
                        for item_id in Appointment.objects.filter(
                            id__in=shifted_ids,
                            patient_arrival_confirmed_at__gte=threshold,
                        ).values_list('id', flat=True)
                    }

            for rec in shifted_records:
                if not rec['chat_id']:
                    continue

                if rec.get('id') in recently_arrived_ids:
                    continue

                if not notify_all_shifted and decision != 'cancel' and abs(rec['delta_minutes']) < 15:
                    continue

                trend_text = 'kechikdi' if rec['delta_minutes'] > 0 else 'oldinga surildi'
                client.send_message(
                    rec['chat_id'],
                    "⏱️ Navbat vaqtingiz yangilandi.\n"
                    f"Eski vaqt: {rec['old_dt'].strftime('%d.%m.%Y %H:%M')}\n"
                    f"Yangi vaqt: {rec['new_dt'].strftime('%d.%m.%Y %H:%M')}\n"
                    f"Sabab: navbat {trend_text}.",
                )
                notified_count += 1
        except Exception:
            # Telegram best-effort: queue update should not fail if bot is unavailable.
            pass

        return Response(
            {
                'decision': decision,
                'queue_updated': queue_updated_count,
                'notified_count': notified_count,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=['get'])
    def monthly_stats(self, request):
        """Return current/previous month clinic report stats from DB records.

        For clinic owners, clinic is inferred from authenticated user.
        Admins may pass `clinic` query param.
        """
        user = request.user
        clinic_param = request.query_params.get('clinic')

        clinic = None
        if user and user.is_authenticated and getattr(user, 'is_clinic', False):
            clinic = getattr(user, 'clinic', None)
            if not clinic:
                return Response({'detail': 'Klinika topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
            if clinic_param and str(clinic.id) != str(clinic_param):
                return Response({'detail': 'Faqat o‘zingizning klinika statistikasi mavjud.'}, status=status.HTTP_403_FORBIDDEN)
        elif user and user.is_authenticated and (
            getattr(user, 'is_superuser', False) or getattr(user, 'is_administrator', False)
        ):
            if not clinic_param:
                return Response({'detail': 'clinic param required'}, status=status.HTTP_400_BAD_REQUEST)
            clinic = Clinic.objects.filter(id=clinic_param).first()
            if not clinic:
                return Response({'detail': 'Klinika topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({'detail': 'Ruxsat berilmagan.'}, status=status.HTTP_403_FORBIDDEN)

        tz = timezone.get_current_timezone()
        today = timezone.localdate()

        def month_range(year: int, month: int):
            start_date = datetime(year, month, 1, 0, 0, 0)
            start = timezone.make_aware(start_date, tz)
            if month == 12:
                end = timezone.make_aware(datetime(year + 1, 1, 1, 0, 0, 0), tz)
            else:
                end = timezone.make_aware(datetime(year, month + 1, 1, 0, 0, 0), tz)
            return start, end

        cur_start, cur_end = month_range(today.year, today.month)
        prev_year = today.year if today.month > 1 else today.year - 1
        prev_month = today.month - 1 if today.month > 1 else 12
        prev_start, prev_end = month_range(prev_year, prev_month)

        def _effective_fee_from_record(record: MedicalRecord) -> Decimal:
            appointment = record.appointment
            appointment_fee = Decimal(appointment.consultation_fee or 0) if appointment else Decimal('0')
            if appointment_fee > 0:
                return appointment_fee
            return _resolve_default_consultation_fee_for_doctor(record.doctor)

        def compute(start_dt, end_dt):
            records = list(
                MedicalRecord.objects.filter(
                    clinic=clinic,
                    created_at__gte=start_dt,
                    created_at__lt=end_dt,
                    doctor__isnull=False,
                )
                .select_related('doctor', 'appointment')
                .prefetch_related('doctor__specializations')
            )

            month_appointments = len(records)
            revenue_total = Decimal('0.00')
            paid_revenue = Decimal('0.00')
            spec_counts: dict[str, int] = {}

            for record in records:
                effective_fee = _effective_fee_from_record(record)
                revenue_total += effective_fee

                appointment = record.appointment
                if appointment and appointment.is_paid:
                    paid_revenue += effective_fee

                doctor_obj = cast(Any, record.doctor)
                if doctor_obj:
                    specializations = getattr(doctor_obj, 'specializations', None)
                    if specializations:
                        for spec in specializations.all():
                            name = getattr(spec, 'name', None)
                            if not name:
                                continue
                            spec_counts[name] = spec_counts.get(name, 0) + 1

            top_spec = '—'
            if spec_counts:
                top_spec = max(spec_counts.items(), key=lambda kv: kv[1])[0]

            return {
                'appointments': month_appointments,
                'revenue_total': revenue_total,
                'revenue_paid': paid_revenue,
                'top_specialization': top_spec,
            }

        cur_stats = compute(cur_start, cur_end)
        prev_stats = compute(prev_start, prev_end)

        cur_count = int(cur_stats['appointments'])
        cur_revenue_total = cast(Decimal, cur_stats['revenue_total'])
        cur_revenue_paid = cast(Decimal, cur_stats['revenue_paid'])
        cur_top = str(cur_stats['top_specialization'])

        prev_count = int(prev_stats['appointments'])
        prev_revenue_total = cast(Decimal, prev_stats['revenue_total'])
        prev_revenue_paid = cast(Decimal, prev_stats['revenue_paid'])
        prev_top = str(prev_stats['top_specialization'])

        days_in_month = calendar.monthrange(today.year, today.month)[1]
        days_elapsed = max(1, today.day)
        ratio = days_elapsed / max(1, days_in_month)
        forecast_count = int(round(cur_count / ratio)) if ratio > 0 else cur_count
        forecast_revenue_total = float(cur_revenue_total / Decimal(str(ratio))) if ratio > 0 else float(cur_revenue_total)
        forecast_revenue_paid = float(cur_revenue_paid / Decimal(str(ratio))) if ratio > 0 else float(cur_revenue_paid)

        def pct_change(current, previous):
            if previous in (0, 0.0):
                return None
            return float((current - previous) / previous * 100)

        history_records = list(
            MedicalRecord.objects.filter(clinic=clinic, doctor__isnull=False)
            .select_related('doctor', 'appointment')
            .order_by('created_at')
        )

        month_data: dict[str, dict[str, float | int]] = {}
        for record in history_records:
            local_created = timezone.localtime(record.created_at)
            month_key = local_created.strftime('%Y-%m')
            month_values = month_data.setdefault(
                month_key,
                {
                    'year': local_created.year,
                    'month': local_created.month,
                    'appointments': 0,
                    'revenue_total': 0.0,
                    'revenue_paid': 0.0,
                },
            )

            effective_fee = _effective_fee_from_record(record)
            month_values['appointments'] = int(month_values['appointments']) + 1
            month_values['revenue_total'] = float(month_values['revenue_total']) + float(effective_fee)

            appointment = record.appointment
            if appointment and appointment.is_paid:
                month_values['revenue_paid'] = float(month_values['revenue_paid']) + float(effective_fee)

        history = []
        cumulative_appointments = 0
        cumulative_revenue_paid = 0.0
        cumulative_revenue_total = 0.0

        if month_data:
            first_month_key = min(month_data.keys())
            cursor_year = int(first_month_key[:4])
            cursor_month = int(first_month_key[5:7])

            while (cursor_year < today.year) or (cursor_year == today.year and cursor_month <= today.month):
                cursor_key = f"{cursor_year}-{cursor_month:02d}"
                month_values = month_data.get(cursor_key, {})
                appointments_value = int(month_values.get('appointments', 0))
                revenue_total_value = float(month_values.get('revenue_total', 0.0))
                revenue_value = float(month_values.get('revenue_paid', 0.0))

                cumulative_appointments += appointments_value
                cumulative_revenue_total += revenue_total_value
                cumulative_revenue_paid += revenue_value

                history.append({
                    'year': cursor_year,
                    'month': cursor_month,
                    'month_key': f"{cursor_year}-{cursor_month:02d}",
                    'appointments': appointments_value,
                    'revenue_total': revenue_total_value,
                    'revenue_paid': revenue_value,
                    'cumulative_appointments': cumulative_appointments,
                    'cumulative_revenue_total': cumulative_revenue_total,
                    'cumulative_revenue_paid': cumulative_revenue_paid,
                })

                if cursor_month == 12:
                    cursor_month = 1
                    cursor_year += 1
                else:
                    cursor_month += 1

        return Response({
            'clinic_id': str(clinic.id),
            'current': {
                'year': today.year,
                'month': today.month,
                'appointments': cur_count,
                'revenue_total': float(cur_revenue_total),
                'revenue_paid': float(cur_revenue_paid),
                'top_specialization': cur_top,
                'days_elapsed': days_elapsed,
                'days_in_month': days_in_month,
                'forecast_appointments': forecast_count,
                'forecast_revenue_total': forecast_revenue_total,
                'forecast_revenue_paid': forecast_revenue_paid,
            },
            'previous': {
                'year': prev_year,
                'month': prev_month,
                'appointments': prev_count,
                'revenue_total': float(prev_revenue_total),
                'revenue_paid': float(prev_revenue_paid),
                'top_specialization': prev_top,
            },
            'comparison': {
                'appointments_diff': cur_count - prev_count,
                'appointments_pct': pct_change(cur_count, prev_count),
                'revenue_total_diff': float(cur_revenue_total - prev_revenue_total),
                'revenue_total_pct': pct_change(float(cur_revenue_total), float(prev_revenue_total)),
                'revenue_paid_diff': float(cur_revenue_paid - prev_revenue_paid),
                'revenue_paid_pct': pct_change(float(cur_revenue_paid), float(prev_revenue_paid)),
            },
            'history': history,
        })

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def online_booking(self, request):
        serializer = OnlineAppointmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = cast(dict, serializer.validated_data)

        clinic = validated['clinic']
        doctor = validated['doctor']
        slot = validated['slot_id']
        specialty_price_id = validated.get('specialty_price_id')
        first_name = str(validated['first_name']).strip()
        last_name = str(validated['last_name']).strip()
        passport_id = str(validated['passport_id']).strip()
        phone_number = str(validated.get('phone_number', '') or '').strip()
        reason = str(validated.get('reason', '') or '').strip()

        if doctor.clinic_id != clinic.id:
            return Response({'detail': 'Doktor klinikaga tegishli emas.'}, status=status.HTTP_400_BAD_REQUEST)
        if not doctor.is_active or not clinic.is_active_status:
            return Response({'detail': 'Doktor yoki klinika faol emas.'}, status=status.HTTP_400_BAD_REQUEST)
        if slot.doctor_id != doctor.id:
            return Response({'detail': 'Slot ushbu doktorga tegishli emas.'}, status=status.HTTP_400_BAD_REQUEST)

        scheduled_dt = timezone.make_aware(datetime.combine(slot.date, slot.start_time))
        if scheduled_dt < timezone.now():
            return Response({'detail': 'Tanlangan vaqt allaqachon o‘tib ketgan.'}, status=status.HTTP_400_BAD_REQUEST)

        # Limit booking to at most 3 days ahead (today + next 3 days)
        max_date = timezone.localdate() + timedelta(days=3)
        if slot.date > max_date:
            return Response({'detail': 'Onlayn navbatni faqat 3 kun ichida olish mumkin.'}, status=status.HTTP_400_BAD_REQUEST)

        slot_duration = int((
            datetime.combine(slot.date, slot.end_time) - datetime.combine(slot.date, slot.start_time)
        ).total_seconds() / 60)
        if slot_duration <= 0:
            return Response({'detail': 'Tanlangan slot muddati noto‘g‘ri.'}, status=status.HTTP_400_BAD_REQUEST)

        booking_window_error = self._validate_doctor_booking_window(
            doctor=doctor,
            target_date=slot.date,
            target_time=slot.start_time,
            duration_minutes=slot_duration,
        )
        if booking_window_error:
            return Response({'detail': booking_window_error}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            slot = DoctorAvailability.objects.select_for_update().get(id=slot.id)
            if slot.status != 'available':
                return Response({'detail': 'Tanlangan vaqt band qilingan.'}, status=status.HTTP_409_CONFLICT)

            passport_norm = re.sub(r"\s+", "", (passport_id or '').strip().upper())
            patient = Patient.objects.select_related('user').filter(national_id__iexact=passport_norm).first()
            if patient:
                if getattr(patient, 'requires_deposit', False):
                    return Response({'detail': 'Keyingi navbat uchun depozit talab qilinadi.'}, status=status.HTTP_409_CONFLICT)
                exists = Appointment.objects.filter(
                    patient=patient,
                    doctor=doctor,
                    status='scheduled',
                    scheduled_date__date=slot.date
                ).exists()
                if exists:
                    return Response(
                        {'detail': 'Bu bemor bugun ushbu doktorga allaqachon navbat olgan.'},
                        status=status.HTTP_409_CONFLICT
                    )
            if not patient:
                base_email = f"{passport_norm}@guest.hospitoll.local"
                if CustomUser.objects.filter(email=base_email).exists():
                    base_email = f"{passport_id}-{timezone.now().strftime('%H%M%S')}@guest.hospitoll.local"
                user = CustomUser.objects.create_user(
                    username=base_email,
                    email=base_email,
                    password=None,
                    first_name=first_name,
                    last_name=last_name,
                    phone_number=phone_number,
                    role='patient'
                )
                user.set_unusable_password()
                user.save(update_fields=['password'])
                patient = Patient.objects.create(
                    user=user,
                    national_id=passport_norm,
                    phone_number=phone_number
                )
            else:
                if patient.user and (patient.user.first_name != first_name or patient.user.last_name != last_name):
                    patient.user.first_name = first_name
                    patient.user.last_name = last_name
                    patient.user.save(update_fields=['first_name', 'last_name'])
                if phone_number and patient.phone_number != phone_number:
                    patient.phone_number = phone_number
                    patient.save(update_fields=['phone_number'])

            expires_at = timezone.now() + timedelta(minutes=20)
            booking_fee, fee_error = self._resolve_booking_fee(doctor, str(specialty_price_id) if specialty_price_id else None)
            if fee_error:
                return Response({'detail': fee_error}, status=status.HTTP_400_BAD_REQUEST)
            appointment = Appointment.objects.create(
                patient=patient,
                doctor=doctor,
                clinic=clinic,
                slot=slot,
                status=Appointment.Status.PENDING_TELEGRAM_CONFIRMATION,
                scheduled_date=scheduled_dt,
                duration_minutes=slot_duration,
                reason=reason,
                consultation_fee=booking_fee,
                telegram_token=uuid4(),
                telegram_token_expires_at=expires_at,
                queue_position=(
                    Appointment.objects.filter(
                        doctor=doctor,
                        scheduled_date__date=slot.date
                    ).exclude(status=Appointment.Status.CANCELLED).count() + 1
                ),
            )

            patient.clinics.add(clinic)
            slot.status = 'booked'
            slot.save(update_fields=['status'])

        queue_number = Appointment.objects.filter(
            doctor=doctor,
            scheduled_date__date=slot.date
        ).count()

        # Schedule auto-cancel (best-effort)
        try:
            from .tasks import auto_cancel_unconfirmed_appointment

            task: Any = auto_cancel_unconfirmed_appointment
            apply_async = getattr(task, 'apply_async', None)
            if callable(apply_async):
                apply_async(args=[str(appointment.id)], eta=appointment.telegram_token_expires_at)
        except Exception:
            pass

        bot_username = getattr(settings, 'TELEGRAM_BOT_USERNAME', '') or 'hosptol_bot'
        bot_link = f"https://t.me/{bot_username}?start={appointment.telegram_token}"

        return Response({
            'appointment': AppointmentSerializer(appointment).data,
            'queue_number': queue_number,
            'telegram_bot_link': bot_link,
        }, status=status.HTTP_201_CREATED)


    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def public_booking(self, request):
        """Public booking endpoint (no login) that requires Telegram confirmation."""
        serializer = PublicTelegramBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = cast(dict, serializer.validated_data)

        clinic = validated['clinic']
        doctor = validated['doctor']
        specialty_price_id = validated.get('specialty_price_id')
        full_name = str(validated['full_name'])
        phone_number = str(validated['phone_number'])
        target_date = validated['date']
        target_time = validated['time']
        reason = str(validated.get('reason') or '').strip()

        if doctor.clinic_id != clinic.id:
            return Response({'detail': 'Doktor klinikaga tegishli emas.'}, status=status.HTTP_400_BAD_REQUEST)
        if not doctor.is_active or not clinic.is_active_status:
            return Response({'detail': 'Doktor yoki klinika faol emas.'}, status=status.HTTP_400_BAD_REQUEST)

        tz = timezone.get_current_timezone()
        scheduled_dt = timezone.make_aware(datetime.combine(target_date, target_time), tz)
        if scheduled_dt < timezone.now():
            return Response({'detail': 'Tanlangan vaqt allaqachon o‘tib ketgan.'}, status=status.HTTP_400_BAD_REQUEST)

        # Limit booking to at most 3 days ahead (today + next 3 days)
        max_date = timezone.localdate() + timedelta(days=3)
        if target_date > max_date:
            return Response({'detail': 'Onlayn navbatni faqat 3 kun ichida olish mumkin.'}, status=status.HTTP_400_BAD_REQUEST)

        duration_minutes = int(getattr(doctor, 'slot_minutes', 30) or 30)
        if duration_minutes not in (15, 20, 30):
            duration_minutes = 30

        booking_window_error = self._validate_doctor_booking_window(
            doctor=doctor,
            target_date=target_date,
            target_time=target_time,
            duration_minutes=duration_minutes,
        )
        if booking_window_error:
            return Response({'detail': booking_window_error}, status=status.HTTP_400_BAD_REQUEST)

        req_start = datetime.combine(target_date, target_time)
        req_end = req_start + timedelta(minutes=duration_minutes)

        phone_norm = self._normalize_phone(phone_number)
        first_name, last_name = self._split_full_name(full_name)

        with transaction.atomic():
            # Find or create patient by phone
            patient = Patient.objects.select_related('user').filter(phone_number=phone_norm).first()
            if patient and getattr(patient, 'requires_deposit', False):
                return Response({'detail': 'Keyingi navbat uchun depozit talab qilinadi.'}, status=status.HTTP_409_CONFLICT)

            if not patient:
                base_email = f"{phone_norm or uuid4()}@guest.hospitoll.local"
                if CustomUser.objects.filter(email=base_email).exists():
                    base_email = f"{phone_norm or 'guest'}-{timezone.now().strftime('%H%M%S')}@guest.hospitoll.local"
                user = CustomUser.objects.create_user(
                    username=base_email,
                    email=base_email,
                    password=None,
                    first_name=first_name,
                    last_name=last_name,
                    phone_number=phone_norm,
                    role='patient'
                )
                user.set_unusable_password()
                user.save(update_fields=['password'])
                patient = Patient.objects.create(user=user, phone_number=phone_norm)
            else:
                if patient.user and (patient.user.first_name != first_name or patient.user.last_name != last_name):
                    patient.user.first_name = first_name
                    patient.user.last_name = last_name
                    patient.user.save(update_fields=['first_name', 'last_name'])
                if phone_norm and patient.phone_number != phone_norm:
                    patient.phone_number = phone_norm
                    patient.save(update_fields=['phone_number'])

            # Ensure slot exists (idempotent) then lock it
            slot_defaults = {
                'end_time': (req_end.time()),
                'status': 'available'
            }
            try:
                slot_obj, _ = DoctorAvailability.objects.get_or_create(
                    doctor=doctor,
                    date=target_date,
                    start_time=target_time,
                    defaults=slot_defaults
                )
            except IntegrityError:
                slot_obj = DoctorAvailability.objects.get(
                    doctor=doctor,
                    date=target_date,
                    start_time=target_time,
                )
            slot_obj = DoctorAvailability.objects.select_for_update().get(id=slot_obj.id)

            # If existing slot has different end_time, treat as invalid request
            if slot_obj.end_time != req_end.time():
                return Response({'detail': 'Tanlangan vaqt slot tizimiga mos emas.'}, status=status.HTTP_400_BAD_REQUEST)
            if slot_obj.status != 'available':
                return Response({'detail': 'Tanlangan vaqt band qilingan.'}, status=status.HTTP_409_CONFLICT)

            expires_at = timezone.now() + timedelta(minutes=20)
            booking_fee, fee_error = self._resolve_booking_fee(doctor, str(specialty_price_id) if specialty_price_id else None)
            if fee_error:
                return Response({'detail': fee_error}, status=status.HTTP_400_BAD_REQUEST)
            appointment = Appointment.objects.create(
                patient=patient,
                doctor=doctor,
                clinic=clinic,
                slot=slot_obj,
                status=Appointment.Status.PENDING_TELEGRAM_CONFIRMATION,
                scheduled_date=scheduled_dt,
                duration_minutes=duration_minutes,
                reason=reason,
                consultation_fee=booking_fee,
                queue_position=(
                    Appointment.objects.filter(
                        doctor=doctor,
                        scheduled_date__date=target_date,
                    ).exclude(status=Appointment.Status.CANCELLED).count() + 1
                ),
                telegram_token=uuid4(),
                telegram_token_expires_at=expires_at,
            )

            patient.clinics.add(clinic)
            slot_obj.status = 'booked'
            slot_obj.save(update_fields=['status'])

        # Schedule auto-cancel (best-effort)
        try:
            from .tasks import auto_cancel_unconfirmed_appointment

            task: Any = auto_cancel_unconfirmed_appointment
            apply_async = getattr(task, 'apply_async', None)
            if callable(apply_async):
                apply_async(
                    args=[str(appointment.id)],
                    eta=appointment.telegram_token_expires_at,
                )
        except Exception:
            pass

        bot_username = getattr(settings, 'TELEGRAM_BOT_USERNAME', '') or 'hosptol_bot'
        bot_link = f"https://t.me/{bot_username}?start={appointment.telegram_token}"

        return Response({
            'appointment': AppointmentSerializer(appointment).data,
            'telegram_bot_link': bot_link,
        }, status=status.HTTP_201_CREATED)


    @action(detail=False, methods=['get'], permission_classes=[IsDoctor])
    def today(self, request):
        """Doctor panel: list today's appointments ordered by queue_position then time."""
        doctor = self._require_active_assigned_doctor(request)
        if not doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        today = timezone.localdate()
        qs = Appointment.objects.filter(
            doctor=doctor,
            scheduled_date__date=today,
        ).select_related('patient', 'clinic', 'slot').order_by('queue_position', 'scheduled_date')
        return Response(AppointmentSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], permission_classes=[IsDoctor])
    def doctor_dashboard_stats(self, request):
        """Doctor dashboard stats from DB.

        - today_24h_patients: patients seen today within doctor's work session
        - monthly_cancelled_appointments: cancelled or no_show in current month
        - monthly_arrived_patients: patients who came in current month
        - monthly_estimated_balance: doctor's own monthly balance by compensation settings
        """
        doctor = self._require_active_assigned_doctor(request)
        if not doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.localtime()
        tz = timezone.get_current_timezone()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        today_local = now.date()
        visits_qs = MedicalRecord.objects.filter(doctor=doctor)

        today_24h_patients = 0
        today_work_record = DoctorWorkRecord.objects.filter(doctor=doctor, date=today_local).first()
        if today_work_record and today_work_record.checked_in_at:
            session_start = timezone.make_aware(
                datetime.combine(today_local, today_work_record.checked_in_at),
                tz,
            )
            session_end_time = today_work_record.checked_out_at or now.time()
            session_end = timezone.make_aware(
                datetime.combine(today_local, session_end_time),
                tz,
            )
            if session_end < session_start:
                session_end = now

            today_24h_patients = visits_qs.filter(
                created_at__gte=session_start,
                created_at__lte=session_end,
            ).count()

        base = Appointment.objects.filter(doctor=doctor)

        monthly_cancelled_appointments = base.filter(
            updated_at__gte=month_start,
            updated_at__lte=now,
            status__in=[Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW],
        ).count()

        monthly_records = visits_qs.filter(
            created_at__gte=month_start,
            created_at__lte=now,
        ).select_related('appointment')
        monthly_arrived_patients = monthly_records.count()

        monthly_effective_revenue = Decimal('0.00')
        for record in monthly_records:
            appointment_fee = Decimal('0')
            appointment = record.appointment
            if appointment:
                appointment_fee = Decimal(appointment.consultation_fee or 0)

            effective_fee = appointment_fee if appointment_fee > 0 else _resolve_default_consultation_fee_for_doctor(doctor)
            monthly_effective_revenue += effective_fee

        compensation_type = str(getattr(doctor, 'compensation_type', 'salary') or 'salary')
        compensation_value = Decimal(getattr(doctor, 'compensation_value', 0) or 0)

        if compensation_type == 'percent':
            monthly_estimated_balance = (monthly_effective_revenue * compensation_value) / Decimal('100')
        else:
            monthly_estimated_balance = compensation_value

        legacy_monthly_patients = visits_qs.filter(
            created_at__date__gte=month_start.date(),
            created_at__date__lte=today_local,
        ).count()

        mismatch_delta = int(monthly_arrived_patients) - int(legacy_monthly_patients)
        if mismatch_delta != 0:
            cache_key = f"doctor_stats_mismatch_alert:{doctor.id}:{month_start.date().isoformat()}:{mismatch_delta}"
            cache_suppressed = False
            try:
                cache_suppressed = bool(cache.get(cache_key))
            except Exception:
                cache_suppressed = False

            if not cache_suppressed:
                ErrorLogger.log_error(
                    error_type='doctor_stats_mismatch',
                    message='Doctor dashboard monthly patient stats mismatch detected',
                    context={
                        'doctor_id': str(doctor.id),
                        'doctor_user_id': str(doctor.user_id) if doctor.user_id else None,
                        'clinic_id': str(doctor.clinic_id) if doctor.clinic_id else None,
                        'api_monthly_arrived_patients': int(monthly_arrived_patients),
                        'legacy_monthly_patients': int(legacy_monthly_patients),
                        'delta': mismatch_delta,
                        'month_start': month_start.isoformat(),
                        'now': now.isoformat(),
                    },
                    severity='critical',
                )
                try:
                    cache.set(cache_key, True, timeout=3600)
                except Exception:
                    pass

        return Response(
            {
                'today_24h_patients': today_24h_patients,
                'monthly_cancelled_appointments': monthly_cancelled_appointments,
                'monthly_arrived_patients': monthly_arrived_patients,
                'compensation_type': compensation_type,
                'compensation_value': float(compensation_value),
                'monthly_effective_revenue': float(monthly_effective_revenue),
                'monthly_estimated_balance': float(monthly_estimated_balance),
            },
            headers={
                'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
                'Pragma': 'no-cache',
            },
        )

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def clinic_doctor_stats_audit(self, request):
        """Clinic owner audit: compare doctor dashboard metrics with DB calculations."""
        user = request.user
        if not user or not user.is_authenticated or not user.is_clinic:
            return Response({'detail': 'Faqat klinika egasi uchun.'}, status=status.HTTP_403_FORBIDDEN)

        clinic = getattr(user, 'clinic', None)
        if not clinic:
            return Response({'detail': 'Klinika topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.localtime()
        tz = timezone.get_current_timezone()
        today_local = now.date()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        doctors = clinic.doctors.select_related('user').all().order_by('created_at')
        doctor_rows = []
        mismatch_count = 0

        for doctor in doctors:
            visits_qs = MedicalRecord.objects.filter(doctor=doctor)
            appointments_qs = Appointment.objects.filter(doctor=doctor)

            api_monthly_arrived = visits_qs.filter(
                created_at__gte=month_start,
                created_at__lte=now,
            ).count()

            legacy_monthly_patients = visits_qs.filter(
                created_at__date__gte=month_start.date(),
                created_at__date__lte=today_local,
            ).count()

            monthly_cancelled = appointments_qs.filter(
                updated_at__gte=month_start,
                updated_at__lte=now,
                status__in=[Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW],
            ).count()

            today_24h_patients = 0
            today_work_record = DoctorWorkRecord.objects.filter(doctor=doctor, date=today_local).first()
            if today_work_record and today_work_record.checked_in_at:
                session_start = timezone.make_aware(
                    datetime.combine(today_local, today_work_record.checked_in_at),
                    tz,
                )
                session_end_time = today_work_record.checked_out_at or now.time()
                session_end = timezone.make_aware(
                    datetime.combine(today_local, session_end_time),
                    tz,
                )
                if session_end < session_start:
                    session_end = now

                today_24h_patients = visits_qs.filter(
                    created_at__gte=session_start,
                    created_at__lte=session_end,
                ).count()

            is_monthly_match = api_monthly_arrived == legacy_monthly_patients
            if not is_monthly_match:
                mismatch_count += 1

            doctor_rows.append(
                {
                    'doctor_id': str(doctor.id),
                    'doctor_username': doctor.user.username if doctor.user_id else '',
                    'doctor_full_name': (
                        f"{doctor.user.first_name or ''} {doctor.user.last_name or ''}".strip()
                        if doctor.user_id
                        else ''
                    ),
                    'today_24h_patients': today_24h_patients,
                    'monthly_cancelled_appointments': monthly_cancelled,
                    'api_monthly_arrived_patients': api_monthly_arrived,
                    'legacy_monthly_patients': legacy_monthly_patients,
                    'monthly_delta': api_monthly_arrived - legacy_monthly_patients,
                    'is_monthly_match': is_monthly_match,
                }
            )

        return Response(
            {
                'clinic_id': str(clinic.id),
                'clinic_name': clinic.name,
                'month_start': month_start.isoformat(),
                'now': now.isoformat(),
                'doctor_count': len(doctor_rows),
                'mismatch_count': mismatch_count,
                'doctors': doctor_rows,
            },
            headers={
                'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
                'Pragma': 'no-cache',
            },
        )

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def clinic_dashboard_stats(self, request):
        """Clinic owner dashboard stats from DB only."""
        user = request.user
        if not user or not user.is_authenticated or not user.is_clinic:
            return Response({'detail': 'Faqat klinika egasi uchun.'}, status=status.HTTP_403_FORBIDDEN)

        clinic = getattr(user, 'clinic', None)
        if not clinic:
            return Response({'detail': 'Klinika topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.localtime()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        doctors_qs = Doctor.objects.filter(clinic=clinic)
        active_doctors = doctors_qs.filter(is_active=True).count()
        total_doctors = doctors_qs.count()

        monthly_records = (
            MedicalRecord.objects.filter(
                clinic=clinic,
                created_at__gte=month_start,
                created_at__lte=now,
                doctor__isnull=False,
            )
            .select_related('doctor__user', 'appointment')
            .order_by('created_at')
        )

        monthly_arrived_patients = monthly_records.count()

        monthly_work_records = DoctorWorkRecord.objects.filter(
            doctor__clinic=clinic,
            date__gte=month_start.date(),
            date__lte=now.date(),
        )
        monthly_total_hours = round(sum(float(record.work_duration) for record in monthly_work_records), 2)

        per_doctor_totals: dict[str, dict[str, Any]] = {}
        for record in monthly_records:
            doctor = record.doctor
            if not doctor:
                continue

            doctor_id = str(doctor.id)
            if doctor_id not in per_doctor_totals:
                first_name = (getattr(doctor.user, 'first_name', '') or '').strip() if doctor.user_id else ''
                last_name = (getattr(doctor.user, 'last_name', '') or '').strip() if doctor.user_id else ''
                username = (getattr(doctor.user, 'username', '') or '').strip() if doctor.user_id else ''
                full_name = f"{first_name} {last_name}".strip() or username or 'Doktor'
                per_doctor_totals[doctor_id] = {
                    'doctor_id': doctor_id,
                    'doctor_name': full_name,
                    'seen_patients': 0,
                    'estimated_revenue': Decimal('0.00'),
                }

            appointment_fee = Decimal('0')
            appointment = record.appointment
            if appointment:
                appointment_fee = Decimal(appointment.consultation_fee or 0)

            effective_fee = appointment_fee if appointment_fee > 0 else _resolve_default_consultation_fee_for_doctor(doctor)
            per_doctor_totals[doctor_id]['seen_patients'] += 1
            per_doctor_totals[doctor_id]['estimated_revenue'] += effective_fee

        monthly_estimated_revenue = sum(
            cast(Decimal, row['estimated_revenue']) for row in per_doctor_totals.values()
        )

        doctor_revenue_rows = []
        for row in sorted(
            per_doctor_totals.values(),
            key=lambda item: (cast(Decimal, item['estimated_revenue']), item['seen_patients']),
            reverse=True,
        ):
            seen_patients = int(row['seen_patients'])
            estimated_revenue = cast(Decimal, row['estimated_revenue'])
            per_patient_fee = (estimated_revenue / seen_patients) if seen_patients > 0 else Decimal('0.00')
            doctor_revenue_rows.append(
                {
                    'doctor_id': row['doctor_id'],
                    'doctor_name': row['doctor_name'],
                    'seen_patients': seen_patients,
                    'consultation_fee': float(per_patient_fee),
                    'estimated_revenue': float(estimated_revenue),
                }
            )

        return Response(
            {
                'clinic_id': str(clinic.id),
                'month_start': month_start.isoformat(),
                'now': now.isoformat(),
                'active_doctors': active_doctors,
                'total_doctors': total_doctors,
                'monthly_arrived_patients': monthly_arrived_patients,
                'monthly_total_hours': monthly_total_hours,
                'monthly_estimated_revenue': float(monthly_estimated_revenue),
                'monthly_estimated_revenue_by_doctor': doctor_revenue_rows,
            },
            headers={
                'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
                'Pragma': 'no-cache',
            },
        )


    @action(detail=True, methods=['post'], permission_classes=[IsDoctor])
    def set_status(self, request, pk=None):
        """Doctor panel: update appointment status with side-effects (slot freeing, no-show counters)."""
        allowed = {
            Appointment.Status.WAITING,
            Appointment.Status.IN_PROGRESS,
            Appointment.Status.COMPLETED,
            Appointment.Status.NO_SHOW,
            Appointment.Status.CANCELLED,
            Appointment.Status.CONFIRMED,
        }
        new_status = (request.data.get('status') or '').strip()
        if new_status not in allowed:
            return Response({'detail': 'Status noto‘g‘ri.'}, status=status.HTTP_400_BAD_REQUEST)

        doctor = self._require_active_assigned_doctor(request)
        if not doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            appointment = Appointment.objects.select_for_update().select_related('patient').get(id=pk)
            if getattr(appointment, 'doctor_id', None) != doctor.id:
                return Response({'detail': 'Ruxsat yo‘q.'}, status=status.HTTP_403_FORBIDDEN)

            # Apply side-effects
            if new_status == Appointment.Status.CANCELLED:
                self._free_slot_if_possible(appointment)
            if new_status == Appointment.Status.NO_SHOW and appointment.status != Appointment.Status.NO_SHOW:
                patient = appointment.patient
                if patient:
                    patient.no_show_count = int(getattr(patient, 'no_show_count', 0) or 0) + 1
                    if patient.no_show_count >= 3:
                        patient.requires_deposit = True
                    patient.save(update_fields=['no_show_count', 'requires_deposit'])

            appointment.status = new_status
            appointment.save(update_fields=['status', 'updated_at'])

        return Response(AppointmentSerializer(appointment).data)


    @action(detail=False, methods=['post'], permission_classes=[IsDoctor])
    def reorder_queue(self, request):
        """Doctor panel: reorder today's queue. Body: {"ordered_ids": [uuid, ...]}"""
        ordered_ids = request.data.get('ordered_ids')
        if not isinstance(ordered_ids, list) or not ordered_ids:
            return Response({'detail': 'ordered_ids kerak.'}, status=status.HTTP_400_BAD_REQUEST)

        doctor = self._require_active_assigned_doctor(request)
        if not doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        today = timezone.localdate()
        with transaction.atomic():
            qs = Appointment.objects.select_for_update().filter(
                doctor=doctor,
                scheduled_date__date=today,
                id__in=ordered_ids,
            )
            found_ids = set(str(a.id) for a in qs)
            missing = [str(i) for i in ordered_ids if str(i) not in found_ids]
            if missing:
                return Response({'detail': 'Ba’zi appointment topilmadi.', 'missing_ids': missing}, status=status.HTTP_400_BAD_REQUEST)

            pos = 1
            for appt_id in ordered_ids:
                Appointment.objects.filter(id=appt_id, doctor=doctor).update(queue_position=pos)
                pos += 1

        return Response({'detail': 'Queue yangilandi.'}, status=status.HTTP_200_OK)


class MedicalRecordViewSet(viewsets.ModelViewSet):
    queryset = MedicalRecord.objects.select_related('patient', 'doctor', 'clinic').all()
    serializer_class = MedicalRecordSerializer
    filterset_fields = ['patient', 'doctor', 'clinic', 'is_locked']
    permission_classes = [permissions.IsAuthenticated]

    def _resolve_completed_appointment_for_record(self, serializer):
        validated_data = serializer.validated_data
        appointment = validated_data.get('appointment')
        doctor = validated_data.get('doctor')
        clinic = validated_data.get('clinic')
        patient = validated_data.get('patient')

        doctor_fee = _resolve_default_consultation_fee_for_doctor(doctor)

        if appointment:
            should_save = False
            if appointment.status != Appointment.Status.COMPLETED:
                appointment.status = Appointment.Status.COMPLETED
                should_save = True
            if doctor_fee > 0 and Decimal(appointment.consultation_fee or 0) <= 0:
                appointment.consultation_fee = doctor_fee
                should_save = True
            if should_save:
                appointment.save()
            return appointment

        if doctor and clinic and patient:
            return Appointment.objects.create(
                patient=patient,
                doctor=doctor,
                clinic=clinic,
                status=Appointment.Status.COMPLETED,
                scheduled_date=timezone.now(),
                consultation_fee=doctor_fee,
            )

        return None

    def _ensure_doctor_can_practice(self):
        user = getattr(self.request, 'user', None)
        if not user or not user.is_authenticated or not user.is_doctor:
            return
        doctor = getattr(user, 'doctor', None)
        if not doctor or not doctor.is_active or not doctor.clinic_id:
            raise PermissionDenied("Siz klinikada faol emassiz. Faqat profilingizni tahrirlashingiz mumkin.")

    def create(self, request, *args, **kwargs):
        self._ensure_doctor_can_practice()
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        appointment = self._resolve_completed_appointment_for_record(serializer)
        if appointment:
            serializer.save(appointment=appointment)
            return
        serializer.save()

    def update(self, request, *args, **kwargs):
        self._ensure_doctor_can_practice()
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        self._ensure_doctor_can_practice()
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self._ensure_doctor_can_practice()
        return super().destroy(request, *args, **kwargs)


class DiagnosisViewSet(viewsets.ModelViewSet):
    queryset = Diagnosis.objects.select_related('medical_record').all()
    serializer_class = DiagnosisSerializer
    filterset_fields = ['medical_record', 'is_primary']
    permission_classes = [permissions.IsAuthenticated]

    def _ensure_doctor_can_practice(self):
        user = getattr(self.request, 'user', None)
        if not user or not user.is_authenticated or not user.is_doctor:
            return
        doctor = getattr(user, 'doctor', None)
        if not doctor or not doctor.is_active or not doctor.clinic_id:
            raise PermissionDenied("Siz klinikada faol emassiz. Faqat profilingizni tahrirlashingiz mumkin.")

    def create(self, request, *args, **kwargs):
        self._ensure_doctor_can_practice()
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        self._ensure_doctor_can_practice()
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        self._ensure_doctor_can_practice()
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self._ensure_doctor_can_practice()
        return super().destroy(request, *args, **kwargs)


class PrescriptionViewSet(viewsets.ModelViewSet):
    queryset = Prescription.objects.select_related('patient', 'doctor').all()
    serializer_class = PrescriptionSerializer
    filterset_fields = ['patient', 'doctor', 'status']
    permission_classes = [permissions.IsAuthenticated]

    def _ensure_doctor_can_practice(self):
        user = getattr(self.request, 'user', None)
        if not user or not user.is_authenticated or not user.is_doctor:
            return
        doctor = getattr(user, 'doctor', None)
        if not doctor or not doctor.is_active or not doctor.clinic_id:
            raise PermissionDenied("Siz klinikada faol emassiz. Faqat profilingizni tahrirlashingiz mumkin.")

    def create(self, request, *args, **kwargs):
        self._ensure_doctor_can_practice()
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        self._ensure_doctor_can_practice()
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        self._ensure_doctor_can_practice()
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self._ensure_doctor_can_practice()
        return super().destroy(request, *args, **kwargs)


class LabTestViewSet(viewsets.ModelViewSet):
    queryset = LabTest.objects.select_related('patient', 'doctor', 'medical_record').all()
    serializer_class = LabTestSerializer
    filterset_fields = ['patient', 'doctor', 'status']
    permission_classes = [permissions.IsAuthenticated]

    def _ensure_doctor_can_practice(self):
        user = getattr(self.request, 'user', None)
        if not user or not user.is_authenticated or not user.is_doctor:
            return
        doctor = getattr(user, 'doctor', None)
        if not doctor or not doctor.is_active or not doctor.clinic_id:
            raise PermissionDenied("Siz klinikada faol emassiz. Faqat profilingizni tahrirlashingiz mumkin.")

    def create(self, request, *args, **kwargs):
        self._ensure_doctor_can_practice()
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        self._ensure_doctor_can_practice()
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        self._ensure_doctor_can_practice()
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self._ensure_doctor_can_practice()
        return super().destroy(request, *args, **kwargs)
