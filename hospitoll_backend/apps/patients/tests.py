from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.patients.models import Patient, PatientMedicationReminder
from apps.site_settings.models import BroadcastNotification
from apps.users.models import CustomUser
from apps.patients.tasks import send_due_medication_reminders


class PatientMedicationReminderApiTests(APITestCase):
    def setUp(self):
        self.patient_user = CustomUser.objects.create_user(
            username='reminder-patient',
            email='reminder-patient@example.com',
            password='Pass12345!',
            role='patient',
        )
        self.patient = Patient.objects.create(user=self.patient_user)
        self.other_user = CustomUser.objects.create_user(
            username='other-reminder-patient',
            email='other-reminder-patient@example.com',
            password='Pass12345!',
            role='patient',
        )
        self.other_patient = Patient.objects.create(user=self.other_user)
        self.url = reverse('patient-medication-reminder-list')
        self.client.force_authenticate(user=self.patient_user)

    def test_patient_can_create_an_interval_reminder(self):
        response = self.client.post(
            self.url,
            {'medication_name': 'Alsetro', 'interval_hours': 8},
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        reminder = PatientMedicationReminder.objects.get(patient=self.patient)
        self.assertEqual(reminder.medication_name, 'Alsetro')
        self.assertEqual(reminder.interval_hours, 8)
        self.assertGreater(reminder.next_reminder_at, timezone.now())

    def test_patient_only_sees_own_reminders(self):
        owned = PatientMedicationReminder.objects.create(
            patient=self.patient,
            medication_name='Alsetro',
            interval_hours=8,
            next_reminder_at=timezone.now() + timedelta(hours=8),
        )
        PatientMedicationReminder.objects.create(
            patient=self.other_patient,
            medication_name='Boshqa dori',
            interval_hours=6,
            next_reminder_at=timezone.now() + timedelta(hours=6),
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        results = response.data.get('results', response.data)
        self.assertEqual([item['id'] for item in results], [owned.id])

    def test_interval_must_be_between_one_hour_and_one_week(self):
        response = self.client.post(
            self.url,
            {'medication_name': 'Alsetro', 'interval_hours': 200},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('interval_hours', response.data)

    def test_non_patient_cannot_create_a_reminder(self):
        doctor = CustomUser.objects.create_user(
            username='reminder-doctor',
            email='reminder-doctor@example.com',
            password='Pass12345!',
            role='doctor',
        )
        self.client.force_authenticate(user=doctor)

        response = self.client.post(
            self.url,
            {'medication_name': 'Alsetro', 'interval_hours': 8},
            format='json',
        )

        self.assertEqual(response.status_code, 403)

    def test_acknowledging_a_dose_stops_nudges_and_clears_its_inbox_notice(self):
        token = uuid4()
        reminder = PatientMedicationReminder.objects.create(
            patient=self.patient,
            medication_name='Alsetro',
            interval_hours=8,
            next_reminder_at=timezone.now() + timedelta(hours=8),
            pending_dose_at=timezone.now() - timedelta(minutes=2),
            next_nudge_at=timezone.now() + timedelta(minutes=8),
            acknowledgement_token=token,
        )
        notification = BroadcastNotification.objects.create(
            user=self.patient_user,
            title='Dori ichish vaqti',
            message='Alsetro',
            data={
                'notification_type': 'medication_reminder',
                'reminder_id': reminder.pk,
                'acknowledgement_token': str(token),
            },
        )
        self.client.force_authenticate(user=None)

        response = self.client.post(
            reverse('patient-medication-reminder-acknowledge'),
            {'acknowledgement_token': str(token)},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'acknowledged': True})
        reminder.refresh_from_db()
        notification.refresh_from_db()
        self.assertIsNone(reminder.pending_dose_at)
        self.assertIsNone(reminder.next_nudge_at)
        self.assertIsNone(reminder.acknowledgement_token)
        self.assertIsNotNone(notification.read_at)

    def test_acknowledgement_rejects_malformed_tokens(self):
        self.client.force_authenticate(user=None)

        response = self.client.post(
            reverse('patient-medication-reminder-acknowledge'),
            {'acknowledgement_token': 'not-a-uuid'},
            format='json',
        )

        self.assertEqual(response.status_code, 400)


class PatientMedicationReminderTaskTests(APITestCase):
    def test_beat_schedule_targets_the_discoverable_celery_task(self):
        self.assertEqual(
            settings.CELERY_BEAT_SCHEDULE['send-due-medication-reminders']['task'],
            send_due_medication_reminders.name,
        )

    def test_due_reminders_send_varied_messages_and_advance_schedule(self):
        user = CustomUser.objects.create_user(
            username='due-reminder-patient',
            email='due-reminder-patient@example.com',
            password='Pass12345!',
            role='patient',
        )
        patient = Patient.objects.create(user=user)
        due_time = timezone.now() - timedelta(minutes=5)
        reminder = PatientMedicationReminder.objects.create(
            patient=patient,
            medication_name='Alsetro',
            interval_hours=8,
            next_reminder_at=due_time,
        )

        with patch('apps.site_settings.tasks.send_saved_broadcast_push.delay') as push_task:
            first_result = send_due_medication_reminders.run()
            first_message = BroadcastNotification.objects.get(user=user).message
            reminder.refresh_from_db()
            first_next_reminder = reminder.next_reminder_at
            first_acknowledgement_token = reminder.acknowledgement_token

            no_nudge_result = send_due_medication_reminders.run()
            reminder.next_nudge_at = timezone.now() - timedelta(minutes=1)
            reminder.save(update_fields=['next_nudge_at'])
            second_result = send_due_medication_reminders.run()

        notifications = list(
            BroadcastNotification.objects.filter(user=user).order_by('created_at')
        )
        self.assertEqual(first_result, {'sent': 1})
        self.assertEqual(no_nudge_result, {'sent': 0})
        self.assertEqual(second_result, {'sent': 1})
        self.assertEqual(len(notifications), 2)
        self.assertNotEqual(notifications[0].message, notifications[1].message)
        self.assertEqual(
            notifications[0].data['acknowledgement_token'],
            str(first_acknowledgement_token),
        )
        self.assertEqual(
            notifications[1].data['acknowledgement_token'],
            str(first_acknowledgement_token),
        )
        self.assertIsNotNone(notifications[0].read_at)
        self.assertIsNone(notifications[1].read_at)
        self.assertIn('Alsetro', first_message)
        self.assertGreater(first_next_reminder, timezone.now())
        reminder.refresh_from_db()
        self.assertEqual(reminder.acknowledgement_token, first_acknowledgement_token)
        self.assertGreater(reminder.next_nudge_at, timezone.now())
        self.assertEqual(push_task.call_count, 2)
