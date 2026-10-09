from datetime import datetime, time, timedelta

from django.utils import timezone


def next_scheduled_reminder_at(daily_times, after=None):
    if not daily_times:
        return None

    after = after or timezone.now()
    local_after = timezone.localtime(after)
    current_timezone = timezone.get_current_timezone()

    for day_offset in range(2):
        reminder_date = local_after.date() + timedelta(days=day_offset)
        for reminder_time in sorted(daily_times):
            local_reminder = datetime.combine(
                reminder_date,
                time.fromisoformat(reminder_time),
            )
            scheduled_at = timezone.make_aware(local_reminder, current_timezone)
            if scheduled_at > after:
                return scheduled_at

    return None
