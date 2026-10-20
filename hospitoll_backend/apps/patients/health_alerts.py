import logging

from django.db import transaction
from django.db.models import Q

from apps.clinics.models import Clinic
from apps.doctors.models import Doctor
from apps.site_settings.models import BroadcastNotification

from .health_thresholds import URGENT

logger = logging.getLogger(__name__)

METRIC_LABELS = {
    'blood_pressure': 'Qon bosimi',
    'blood_glucose': 'Qon qandi',
    'liver_alt': 'ALT',
    'liver_ast': 'AST',
    'liver_bilirubin': 'Bilirubin',
    'liver_albumin': 'Albumin',
    'liver_ggt': 'GGT',
    'liver_viral_load': 'Virus yuklamasi',
}


def linked_doctor_users(patient):
    doctors = Doctor.objects.filter(appointments__patient=patient).select_related('user').distinct()
    return [doctor.user for doctor in doctors]


def linked_clinic_owners(patient):
    clinics = Clinic.objects.filter(
        Q(patients=patient) | Q(appointments__patient=patient)
    ).select_related('owner').distinct()
    return [clinic.owner for clinic in clinics]


def format_reading(reading):
    if reading.metric == 'blood_pressure':
        return f'{reading.systolic}/{reading.diastolic} mm sim. ust.'
    if reading.metric == 'blood_glucose':
        return f'{reading.glucose_mmol} mmol/L'
    return f'{reading.value} {reading.unit}'


def notify_care_team(reading):
    """Chegaradan tashqari ko'rsatkichni bemorning shifokor va klinikalariga yuboradi."""
    if not reading.share_with_care_team or reading.severity == 'normal':
        return

    recipients = {
        user.pk: user
        for user in linked_doctor_users(reading.patient) + linked_clinic_owners(reading.patient)
        if user and user.is_active
    }
    if not recipients:
        return

    patient_name = reading.patient.user.get_full_name() or reading.patient.user.get_username()
    prefix = '🚨 Shoshilinch' if reading.severity == URGENT else '⚠️ E’tibor talab'
    title = f'{prefix}: {METRIC_LABELS[reading.metric]}'
    message = f'{patient_name}: {format_reading(reading)}. {reading.alert_reason}'

    notifications = BroadcastNotification.objects.bulk_create([
        BroadcastNotification(
            user=user,
            title=title[:120],
            message=message,
            data={
                'notification_type': 'health_alert',
                'reading_id': str(reading.id),
                'patient_id': str(reading.patient_id),
                'severity': reading.severity,
            },
        )
        for user in recipients.values()
    ])
    notification_ids = [str(notification.id) for notification in notifications]

    def send_push():
        try:
            from apps.site_settings.tasks import send_saved_broadcast_push

            send_saved_broadcast_push.delay(notification_ids)
        except Exception:
            logger.exception('Health alert push could not be queued')

    transaction.on_commit(send_push)


def notify_missed_dose_to_care_team(reminder):
    """Yangi tasdiqlanmagan dozani bemorning bog‘langan tibbiy jamoasiga bildiradi."""
    recipients = {
        user.pk: user
        for user in linked_doctor_users(reminder.patient)
        + linked_clinic_owners(reminder.patient)
        if user and user.is_active
    }
    if not recipients:
        return False

    patient_name = (
        reminder.patient.user.get_full_name()
        or reminder.patient.user.get_username()
    )
    missed_at = reminder.pending_dose_at
    notifications = BroadcastNotification.objects.bulk_create([
        BroadcastNotification(
            user=user,
            title='⚠️ Dori dozasi o‘tkazib yuborildi',
            message=(
                f'{patient_name}: {reminder.medication_name} dorisining '
                f'{missed_at:%d.%m.%Y %H:%M} dagi dozasi eslatmadan keyin tasdiqlanmadi.'
            ),
            data={
                'notification_type': 'missed_medication_dose',
                'reminder_id': reminder.pk,
                'patient_id': str(reminder.patient_id),
                'medication_name': reminder.medication_name,
                'missed_dose_at': missed_at.isoformat(),
            },
        )
        for user in recipients.values()
    ])
    notification_ids = [str(notification.id) for notification in notifications]

    def send_push():
        try:
            from apps.site_settings.tasks import send_saved_broadcast_push

            send_saved_broadcast_push.delay(notification_ids)
        except Exception:
            logger.exception('Missed medication dose push could not be queued')

    transaction.on_commit(send_push)
    return True
