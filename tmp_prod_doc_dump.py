from django.utils import timezone
from apps.medical.models import Appointment

def patient_name(p):
    for attr in ('full_name', 'fullname', 'name'):
        if hasattr(p, attr):
            val = getattr(p, attr)
            if callable(val):
                try:
                    val = val()
                except Exception:
                    val = None
            if val:
                return str(val)
    fn = getattr(p, 'first_name', '') or ''
    ln = getattr(p, 'last_name', '') or ''
    return (fn + ' ' + ln).strip() or str(getattr(p, 'id', '-'))

def dump_for_doc(doc_id, label):
    now = timezone.localtime()
    today = now.date()
    qs = Appointment.objects.filter(doctor_id=doc_id, scheduled_date__date=today).select_related('patient').order_by('scheduled_date','created_at')
    print(f'--- {label} doc={doc_id} now={now:%Y-%m-%d %H:%M} today_count={qs.count()} ---')
    for a in qs:
        p = patient_name(a.patient) if a.patient_id else '-'
        print(f"appt={a.id} status={a.status} q={a.queue_position} at={timezone.localtime(a.scheduled_date):%H:%M} chat={a.telegram_chat_id} auto_started={a.auto_turn_started_at} prompt={a.auto_turn_prompt_sent_at} last_rem={a.auto_turn_last_reminder_at} response={a.auto_turn_response} patient={p}")

dump_for_doc('1b69810a-5070-4f1f-adb3-da4854ad096f', 'PROBLEM_DOC')
dump_for_doc('18781df7-89cd-4813-a2b6-c9dbcaccb7a0', 'SUXROB_DOC')