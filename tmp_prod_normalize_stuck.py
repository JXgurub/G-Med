from django.utils import timezone
from apps.medical.models import Appointment

appt_id = 'd7c66bf2-e507-4b46-9c29-19e62dc47922'
try:
    appt = Appointment.objects.get(id=appt_id)
except Appointment.DoesNotExist:
    print('NOT_FOUND', appt_id)
else:
    appt.status = Appointment.Status.CANCELLED
    appt.auto_turn_started_at = None
    appt.auto_turn_prompt_sent_at = None
    appt.auto_turn_last_reminder_at = None
    appt.auto_turn_response = None
    appt.auto_turn_responded_at = None
    appt.save(update_fields=[
        'status',
        'auto_turn_started_at',
        'auto_turn_prompt_sent_at',
        'auto_turn_last_reminder_at',
        'auto_turn_response',
        'auto_turn_responded_at',
        'updated_at',
    ])
    print('NORMALIZED', appt_id, appt.status, timezone.localtime(appt.scheduled_date).strftime('%Y-%m-%d %H:%M'))