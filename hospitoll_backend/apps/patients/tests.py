from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.patients.models import (
    Patient,
    PatientMedicationReminder,
    PatientTreatmentPlan,
    PatientTreatmentStep,
)
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

    def test_patient_can_add_daily_reminder_times(self):
        response = self.client.post(
            self.url,
            {
                'medication_name': 'Alsetro',
                'interval_hours': None,
                'daily_times': ['20:00', '08:00'],
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        reminder = PatientMedicationReminder.objects.get(patient=self.patient)
        self.assertIsNone(reminder.interval_hours)
        self.assertIsNone(reminder.next_reminder_at)
        self.assertEqual(reminder.daily_times, ['08:00', '20:00'])
        self.assertEqual(response.data['daily_times'], ['08:00', '20:00'])
        self.assertGreater(reminder.next_scheduled_reminder_at, timezone.now())

    def test_daily_reminder_times_must_be_valid_and_unique(self):
        for times in (['24:00'], ['08:00', '08:00']):
            with self.subTest(times=times):
                response = self.client.post(
                    self.url,
                    {
                        'medication_name': 'Alsetro',
                        'interval_hours': None,
                        'daily_times': times,
                    },
                    format='json',
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn('daily_times', response.data)

    def test_patient_can_switch_from_interval_to_fixed_daily_times(self):
        reminder = PatientMedicationReminder.objects.create(
            patient=self.patient,
            medication_name='Alsetro',
            interval_hours=8,
            next_reminder_at=timezone.now() + timedelta(hours=6),
        )

        response = self.client.patch(
            reverse('patient-medication-reminder-detail', args=[reminder.id]),
            {
                'interval_hours': None,
                'daily_times': ['20:00', '08:00'],
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        reminder.refresh_from_db()
        self.assertIsNone(reminder.interval_hours)
        self.assertIsNone(reminder.next_reminder_at)
        self.assertEqual(reminder.daily_times, ['08:00', '20:00'])
        self.assertGreater(reminder.next_scheduled_reminder_at, timezone.now())

    def test_patient_can_switch_from_fixed_daily_times_to_interval(self):
        reminder = PatientMedicationReminder.objects.create(
            patient=self.patient,
            medication_name='Alsetro',
            interval_hours=None,
            daily_times=['08:00', '20:00'],
            next_reminder_at=None,
        )

        response = self.client.patch(
            reverse('patient-medication-reminder-detail', args=[reminder.id]),
            {
                'interval_hours': 8,
                'daily_times': [],
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        reminder.refresh_from_db()
        self.assertEqual(reminder.interval_hours, 8)
        self.assertGreater(reminder.next_reminder_at, timezone.now())
        self.assertEqual(reminder.daily_times, [])

    def test_reminder_requires_exactly_one_schedule_type(self):
        invalid_payloads = (
            {'interval_hours': None, 'daily_times': []},
            {'interval_hours': 8, 'daily_times': ['08:00']},
        )
        for schedule in invalid_payloads:
            with self.subTest(schedule=schedule):
                response = self.client.post(
                    self.url,
                    {'medication_name': 'Alsetro', **schedule},
                    format='json',
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn('non_field_errors', response.data)

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

    def test_daily_reminder_time_sends_notification_and_advances_to_next_day(self):
        user = CustomUser.objects.create_user(
            username='scheduled-reminder-patient',
            email='scheduled-reminder-patient@example.com',
            password='Pass12345!',
            role='patient',
        )
        patient = Patient.objects.create(user=user)
        now = timezone.now()
        scheduled_time = now - timedelta(minutes=1)
        reminder = PatientMedicationReminder.objects.create(
            patient=patient,
            medication_name='Alsetro',
            interval_hours=None,
            daily_times=['08:00', '20:00'],
            next_reminder_at=None,
            next_scheduled_reminder_at=scheduled_time,
        )

        with patch('apps.site_settings.tasks.send_saved_broadcast_push.delay') as push_task:
            result = send_due_medication_reminders.run()

        reminder.refresh_from_db()
        notification = BroadcastNotification.objects.get(user=user)
        self.assertEqual(result, {'sent': 1})
        self.assertEqual(reminder.pending_dose_at, scheduled_time)
        self.assertIsNone(reminder.next_reminder_at)
        self.assertGreater(reminder.next_scheduled_reminder_at, timezone.now())
        self.assertEqual(notification.data['notification_type'], 'medication_reminder')
        self.assertEqual(push_task.call_count, 1)

    def test_unacknowledged_dose_is_reported_to_linked_doctor_once(self):
        from apps.doctors.models import Doctor
        from apps.medical.models import Appointment

        user = CustomUser.objects.create_user(
            username='missed-dose-patient',
            email='missed-dose-patient@example.com',
            password='Pass12345!',
            role='patient',
        )
        patient = Patient.objects.create(user=user)
        doctor_user = CustomUser.objects.create_user(
            username='missed-dose-doctor',
            email='missed-dose-doctor@example.com',
            password='Pass12345!',
            role='doctor',
        )
        doctor = Doctor.objects.create(user=doctor_user, license_number='LIC-MISSED-1')
        Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            scheduled_date=timezone.localdate(),
        )
        reminder = PatientMedicationReminder.objects.create(
            patient=patient,
            medication_name='Gepatit dorisi',
            interval_hours=8,
            next_reminder_at=timezone.now() + timedelta(hours=8),
            pending_dose_at=timezone.now() - timedelta(minutes=11),
            next_nudge_at=timezone.now() - timedelta(minutes=1),
            acknowledgement_token=uuid4(),
        )

        with patch('apps.site_settings.tasks.send_saved_broadcast_push.delay'):
            result = send_due_medication_reminders.run()
            second_result = send_due_medication_reminders.run()

        reminder.refresh_from_db()
        alerts = BroadcastNotification.objects.filter(
            user=doctor_user,
            data__notification_type='missed_medication_dose',
        )
        self.assertEqual(result, {'sent': 1})
        self.assertEqual(second_result, {'sent': 0})
        self.assertIsNotNone(reminder.missed_dose_reported_at)
        self.assertEqual(alerts.count(), 1)


class PatientTreatmentPlanApiTests(APITestCase):
    def setUp(self):
        self.patient_user = CustomUser.objects.create_user(
            username='roadmap-patient',
            email='roadmap-patient@example.com',
            password='Pass12345!',
            role='patient',
        )
        self.patient = Patient.objects.create(user=self.patient_user)
        self.other_user = CustomUser.objects.create_user(
            username='other-roadmap-patient',
            email='other-roadmap-patient@example.com',
            password='Pass12345!',
            role='patient',
        )
        self.other_patient = Patient.objects.create(user=self.other_user)
        self.plans_url = reverse('patient-treatment-plan-list')
        self.steps_url = reverse('patient-treatment-step-list')
        self.client.force_authenticate(user=self.patient_user)

    def test_patient_can_create_plan_and_step(self):
        plan_response = self.client.post(
            self.plans_url,
            {
                'title': 'Reabilitatsiya',
                'summary': 'Shifokor bilan kelishilgan reja',
                'start_date': '2026-10-17',
                'target_date': '2026-11-17',
            },
            format='json',
        )

        self.assertEqual(plan_response.status_code, 201)
        plan = PatientTreatmentPlan.objects.get(patient=self.patient)
        step_response = self.client.post(
            self.steps_url,
            {
                'plan': str(plan.id),
                'title': 'Nazorat ko‘rigiga borish',
                'due_date': '2026-10-24',
            },
            format='json',
        )

        self.assertEqual(step_response.status_code, 201)
        step = PatientTreatmentStep.objects.get(plan=plan)
        self.assertEqual(step.title, 'Nazorat ko‘rigiga borish')
        completion_response = self.client.patch(
            reverse('patient-treatment-step-detail', args=[step.id]),
            {'is_completed': True},
            format='json',
        )
        self.assertEqual(completion_response.status_code, 200)
        step.refresh_from_db()
        self.assertTrue(step.is_completed)
        self.assertIsNotNone(step.completed_at)
        plan_list = self.client.get(self.plans_url).data
        self.assertEqual(plan_list['count'], 1)
        self.assertEqual(len(plan_list['results']), 1)
        self.assertTrue(plan_list['results'][0]['steps'][0]['is_completed'])

    def test_patient_cannot_access_another_patients_plan_or_steps(self):
        other_plan = PatientTreatmentPlan.objects.create(
            patient=self.other_patient,
            title='Shaxsiy reja',
        )
        other_step = PatientTreatmentStep.objects.create(
            plan=other_plan,
            title='Shaxsiy qadam',
        )

        plan_list = self.client.get(self.plans_url).data
        self.assertEqual(plan_list['count'], 0)
        self.assertEqual(plan_list['results'], [])
        self.assertEqual(self.client.patch(
            reverse('patient-treatment-plan-detail', args=[other_plan.id]),
            {'status': PatientTreatmentPlan.Status.COMPLETED},
            format='json',
        ).status_code, 404)
        self.assertEqual(self.client.patch(
            reverse('patient-treatment-step-detail', args=[other_step.id]),
            {'is_completed': True},
            format='json',
        ).status_code, 404)

    def test_patient_cannot_add_step_to_another_patients_plan(self):
        other_plan = PatientTreatmentPlan.objects.create(
            patient=self.other_patient,
            title='Boshqa reja',
        )

        response = self.client.post(
            self.steps_url,
            {'plan': str(other_plan.id), 'title': 'Ruxsatsiz qadam'},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('plan', response.data)

    def test_target_date_cannot_be_before_start_date(self):
        response = self.client.post(
            self.plans_url,
            {
                'title': 'Noto‘g‘ri sanali reja',
                'start_date': '2026-10-20',
                'target_date': '2026-10-19',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('target_date', response.data)


class PatientHealthMonitoringApiTests(APITestCase):
    def setUp(self):
        from apps.clinics.models import Clinic
        from apps.doctors.models import Doctor
        from apps.medical.models import Appointment

        self.patient_user = CustomUser.objects.create_user(
            username='chronic-patient', email='chronic-patient@example.com',
            password='Pass12345!', role='patient',
        )
        self.patient = Patient.objects.create(user=self.patient_user)
        self.other_user = CustomUser.objects.create_user(
            username='chronic-other', email='chronic-other@example.com',
            password='Pass12345!', role='patient',
        )
        self.other_patient = Patient.objects.create(user=self.other_user)
        self.doctor_user = CustomUser.objects.create_user(
            username='chronic-doctor', email='chronic-doctor@example.com',
            password='Pass12345!', role='doctor',
        )
        self.doctor = Doctor.objects.create(user=self.doctor_user, license_number='LIC-CH-1')
        self.unlinked_doctor_user = CustomUser.objects.create_user(
            username='chronic-doctor2', email='chronic-doctor2@example.com',
            password='Pass12345!', role='doctor',
        )
        Doctor.objects.create(user=self.unlinked_doctor_user, license_number='LIC-CH-2')
        self.clinic_user = CustomUser.objects.create_user(
            username='chronic-clinic', email='chronic-clinic@example.com',
            password='Pass12345!', role='clinic',
        )
        self.clinic = Clinic.objects.create(
            owner=self.clinic_user, name='Chronic Clinic', slug='chronic-clinic',
            address='Toshkent', phone_number='+998900000000',
            email='clinic-chronic@example.com', registration_number='REG-CH-1',
        )
        self.patient.clinics.add(self.clinic)
        Appointment.objects.create(
            patient=self.patient, doctor=self.doctor, clinic=self.clinic,
            scheduled_date=timezone.localdate(),
        )
        self.url = reverse('patient-health-reading-list')
        self.alerts_url = reverse('patient-health-alert-list')

    def _post_bp(self, systolic, diastolic, **extra):
        self.client.force_authenticate(user=self.patient_user)
        payload = {
            'metric': 'blood_pressure', 'systolic': systolic, 'diastolic': diastolic,
        }
        payload.update(extra)
        with patch('apps.site_settings.tasks.send_saved_broadcast_push.delay'):
            with self.captureOnCommitCallbacks(execute=True):
                return self.client.post(self.url, payload, format='json')

    def test_normal_reading_creates_no_alert(self):
        response = self._post_bp(118, 76)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['severity'], 'normal')
        self.assertEqual(BroadcastNotification.objects.count(), 0)

    def test_high_reading_notifies_doctor_and_clinic(self):
        response = self._post_bp(150, 95)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['severity'], 'attention')
        users = set(BroadcastNotification.objects.values_list('user_id', flat=True))
        self.assertEqual(users, {self.doctor_user.id, self.clinic_user.id})

        self.client.force_authenticate(user=self.doctor_user)
        alerts = self.client.get(self.alerts_url).data
        self.assertEqual(alerts['count'], 1)
        self.client.force_authenticate(user=self.clinic_user)
        self.assertEqual(self.client.get(self.alerts_url).data['count'], 1)
        self.client.force_authenticate(user=self.unlinked_doctor_user)
        self.assertEqual(self.client.get(self.alerts_url).data['count'], 0)

    def test_urgent_glucose(self):
        self.client.force_authenticate(user=self.patient_user)
        with patch('apps.site_settings.tasks.send_saved_broadcast_push.delay'):
            response = self.client.post(
                self.url,
                {'metric': 'blood_glucose', 'glucose_mmol': '2.5', 'glucose_context': 'fasting'},
                format='json',
            )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['severity'], 'urgent')

    def test_not_shared_reading_is_hidden(self):
        response = self._post_bp(190, 125, share_with_care_team=False)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(BroadcastNotification.objects.count(), 0)
        self.client.force_authenticate(user=self.doctor_user)
        self.assertEqual(self.client.get(self.alerts_url).data['count'], 0)

    def test_review_marks_alert(self):
        self._post_bp(150, 95)
        self.client.force_authenticate(user=self.doctor_user)
        alert_id = self.client.get(self.alerts_url).data['results'][0]['id']
        response = self.client.post(
            reverse('patient-health-alert-review', args=[alert_id]), {}, format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_reviewed'])
        self.assertEqual(self.client.get(self.alerts_url).data['count'], 0)
        self.assertEqual(self.client.get(self.alerts_url, {'status': 'all'}).data['count'], 1)

    def test_validation_and_isolation(self):
        self.client.force_authenticate(user=self.patient_user)
        bad = self.client.post(
            self.url, {'metric': 'blood_pressure', 'systolic': 80, 'diastolic': 120}, format='json',
        )
        self.assertEqual(bad.status_code, 400)
        self._post_bp(120, 80)
        self.client.force_authenticate(user=self.other_user)
        self.assertEqual(self.client.get(self.url).data['count'], 0)
        self.client.force_authenticate(user=self.patient_user)
        self.assertEqual(self.client.get(self.url).data['count'], 1)
        self.client.force_authenticate(user=self.doctor_user)
        self.assertEqual(self.client.get(self.url).data['count'], 0)
        self.assertEqual(self.client.post(self.url, {}, format='json').status_code, 403)

    def test_liver_results_use_lab_reference_range_and_alert_linked_care_team(self):
        self.client.force_authenticate(user=self.patient_user)
        payload = {
            'metric': 'liver_alt',
            'value': '75',
            'unit': 'U/L',
            'reference_min': '0',
            'reference_max': '40',
        }
        with patch('apps.site_settings.tasks.send_saved_broadcast_push.delay'):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(self.url, payload, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['severity'], 'attention')
        self.assertEqual(response.data['value'], '75.000')
        self.assertEqual(response.data['alert_reason'], 'Natija laboratoriya ko‘rsatgan me’yordan yuqori.')
        self.assertEqual(
            set(BroadcastNotification.objects.values_list('user_id', flat=True)),
            {self.doctor_user.id, self.clinic_user.id},
        )

    def test_liver_result_must_include_lab_unit_and_reference_range(self):
        self.client.force_authenticate(user=self.patient_user)
        response = self.client.post(
            self.url,
            {'metric': 'liver_albumin', 'value': '40', 'unit': 'g/L'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('reference_max', response.data)


class PatientLiverJournalApiTests(APITestCase):
    def setUp(self):
        self.patient_user = CustomUser.objects.create_user(
            username='liver-journal-patient',
            email='liver-journal-patient@example.com',
            password='Pass12345!',
            role='patient',
        )
        self.patient = Patient.objects.create(user=self.patient_user)
        self.other_user = CustomUser.objects.create_user(
            username='other-liver-journal-patient',
            email='other-liver-journal-patient@example.com',
            password='Pass12345!',
            role='patient',
        )
        self.other_patient = Patient.objects.create(user=self.other_user)
        self.url = reverse('patient-liver-journal-list')
        self.client.force_authenticate(user=self.patient_user)

    def test_patient_can_store_symptoms_and_daily_measurements(self):
        response = self.client.post(
            self.url,
            {
                'symptoms': ['fatigue', 'dark_urine'],
                'weight_kg': '72.5',
                'abdominal_circumference_cm': '90',
                'salt_grams': '4',
                'fluid_ml': 1500,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['symptoms'], ['fatigue', 'dark_urine'])
        self.assertEqual(response.data['weight_kg'], '72.50')
        self.assertEqual(self.client.get(self.url).data['count'], 1)

    def test_patient_cannot_view_another_patients_journal(self):
        from apps.patients.models import PatientLiverJournalEntry

        PatientLiverJournalEntry.objects.create(
            patient=self.other_patient,
            symptoms=['jaundice'],
        )
        self.assertEqual(self.client.get(self.url).data['count'], 0)
        self.assertEqual(
            self.client.post(self.url, {'symptoms': ['unknown']}, format='json').status_code,
            400,
        )
