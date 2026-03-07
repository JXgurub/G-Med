from __future__ import annotations

from datetime import datetime, timedelta

from django.utils import timezone


def validate_doctor_booking_window(
    doctor,
    target_date,
    target_time,
    duration_minutes: int,
) -> str | None:
    day_key = target_date.strftime('%a')
    working_days = [d.strip() for d in (doctor.working_days or '').split(',') if d.strip()]
    if working_days and day_key not in working_days:
        return 'Doktor bu kunda ishlamaydi.'

    start_dt = datetime.combine(target_date, doctor.available_from)
    end_dt = datetime.combine(target_date, doctor.available_until)
    req_start = datetime.combine(target_date, target_time)
    req_end = req_start + timedelta(minutes=duration_minutes)

    if req_start < start_dt or req_end > end_dt:
        return 'Tanlangan vaqt doktor ish vaqti tashqarisida.'

    lunch_start = getattr(doctor, 'lunch_break_start', None)
    lunch_end = getattr(doctor, 'lunch_break_end', None)
    if lunch_start and lunch_end:
        lunch_start_dt = datetime.combine(target_date, lunch_start)
        lunch_end_dt = datetime.combine(target_date, lunch_end)
        if lunch_start_dt < lunch_end_dt and req_start < lunch_end_dt and req_end > lunch_start_dt:
            return 'Tanlangan vaqt doktorning abet vaqtiga to‘g‘ri keladi.'

    cutoff_start = end_dt - timedelta(minutes=10)
    if req_start >= cutoff_start:
        return 'Doktor ish vaqti tugashiga 10 daqiqa qolganda navbat berilmaydi.'

    if target_date == timezone.localdate():
        now_local = timezone.localtime()
        cutoff_local = timezone.make_aware(cutoff_start, timezone.get_current_timezone())
        if now_local >= cutoff_local:
            return 'Onlayn navbat yopilgan (ish tugashiga 10 daqiqadan kam qoldi).'

    return None
