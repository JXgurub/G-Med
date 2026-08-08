from collections import defaultdict
from django.utils import timezone
from apps.medical.models import Appointment
from apps.doctors.models import Doctor

now = timezone.localtime()
today = now.date()
ACTIVE = (
    Appointment.Status.SCHEDULED,
    Appointment.Status.CONFIRMED,
    Appointment.Status.WAITING,
    Appointment.Status.IN_PROGRESS,
)

qs = (
    Appointment.objects.filter(scheduled_date__date=today)
    .select_related('doctor__user', 'patient')
    .order_by('doctor_id', 'queue_position', 'scheduled_date', 'created_at')
)
by_doc = defaultdict(list)
for appt in qs:
    if appt.doctor_id:
        by_doc[appt.doctor_id].append(appt)

print(f'NOW={now:%Y-%m-%d %H:%M}')
print(f'TODAY_DOCTORS_WITH_ANY_APPTS={len(by_doc)}')

problem_docs = 0
active_docs = 0
for did in sorted(by_doc.keys()):
    items = by_doc[did]
    active = [a for a in items if a.status in ACTIVE]
    if not active:
        continue

    active_docs += 1
    d = items[0].doctor
    name = d.user.get_full_name() if (d and d.user_id) else f'Doctor#{did}'

    active = sorted(active, key=lambda x: ((x.queue_position or 9999), x.scheduled_date, x.created_at))
    leader = active[0]
    inprog = [a for a in active if a.status == Appointment.Status.IN_PROGRESS]
    positions = [a.queue_position for a in active]
    expected = list(range(1, len(active) + 1))

    flags = []
    if positions != expected:
        flags.append(f'position_mismatch:{positions}->{expected}')
    if len(inprog) > 1:
        flags.append(f'multiple_in_progress:{len(inprog)}')
    if len(inprog) == 1 and inprog[0].id != leader.id:
        flags.append('leader_not_in_progress')
    if len(inprog) == 0 and leader.scheduled_date <= now:
        flags.append('leader_past_due_not_started')
    if leader.auto_turn_started_at and not leader.auto_turn_prompt_sent_at:
        flags.append('leader_started_without_prompt')

    leader_time = timezone.localtime(leader.scheduled_date).strftime('%H:%M')
    print(
        f"DOC#{did} {name} | active={len(active)} | leader={leader.status} | at={leader_time} | inprog={len(inprog)} | flags={';'.join(flags) if flags else 'OK'}"
    )

    if flags:
        problem_docs += 1

print(f'ACTIVE_DOCTORS={active_docs}')
print(f'PROBLEM_DOCTORS={problem_docs}')

print('--- POSSIBLE MATCH: KURBANIYAZOV / SUXROB ---')
for d in Doctor.objects.select_related('user').all().order_by('id'):
    full_name = d.user.get_full_name() if d.user_id else ''
    txt = f"{full_name} {d.user.first_name if d.user_id else ''} {d.user.last_name if d.user_id else ''}".lower()
    if ('kurbani' in txt) or ('sux' in txt) or ('suh' in txt) or ('сух' in txt) or ('курбан' in txt):
        active = [a for a in by_doc.get(d.id, []) if a.status in ACTIVE]
        print(f"MATCH_DOC#{d.id} name={full_name} active_today={len(active)}")
        for a in sorted(active, key=lambda x: ((x.queue_position or 9999), x.scheduled_date)):
            p = (a.patient.full_name if a.patient_id else '-')
            print(f"  - appt={a.id} q={a.queue_position} status={a.status} at={timezone.localtime(a.scheduled_date):%H:%M} patient={p} auto_started={a.auto_turn_started_at} prompt_sent={a.auto_turn_prompt_sent_at} response={a.auto_turn_response}")
