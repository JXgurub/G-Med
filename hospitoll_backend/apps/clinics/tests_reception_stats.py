from datetime import datetime, date

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core import signing
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.clinics.models import Clinic, ReceptionStaff
from apps.doctors.models import Doctor
from apps.medical.models import Appointment
from apps.patients.models import Patient
from apps.users.models import CustomUser


LOGIN_THROTTLE_TEST_SETTINGS = dict(settings.REST_FRAMEWORK)
LOGIN_THROTTLE_TEST_SETTINGS['DEFAULT_THROTTLE_RATES'] = dict(
    settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {}),
    anon='1/day',
    auth='100/minute',
)


class ReceptionStatsAndThrottleTests(TestCase):
    def setUp(self):
        self.owner = CustomUser.objects.create_user(
            username='clinic_owner_stats',
            email='owner.stats@example.com',
            password='Pass12345!',
            role='clinic',
            first_name='Owner',
            last_name='Stats',
        )
        self.clinic = Clinic.objects.create(
            owner=self.owner,
            name='Stats Clinic',
            slug='stats-clinic',
            address='Street 10',
            phone_number='+998901112233',
            email='clinic.stats@example.com',
            registration_number='REG-STATS-001',
            status='active',
            reception_room_enabled=True,
        )

        self.reception_staff = ReceptionStaff.objects.create(
            clinic=self.clinic,
            pinfl='12345678901234',
            passport_id='AA1234567',
            date_of_birth=date(1995, 1, 1),
            first_name='Reception',
            last_name='User',
            phone_number='+998901112244',
            email='reception.stats@example.com',
            password_hash=make_password('Secret123!'),
            compensation_type='salary',
            compensation_value=1200000,
            is_active=True,
        )

        doctor_user = CustomUser.objects.create_user(
            username='doctor_stats',
            email='doctor.stats@example.com',
            password='Pass12345!',
            role='doctor',
            first_name='Doc',
            last_name='Stats',
        )
        self.doctor = Doctor.objects.create(
            user=doctor_user,
            clinic=self.clinic,
            license_number='DOC-LIC-STATS-001',
            consultation_fee=100000,
        )

        patient_user = CustomUser.objects.create_user(
            username='patient_stats',
            email='patient.stats@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Patient',
            last_name='Stats',
        )
        self.patient = Patient.objects.create(
            user=patient_user,
            phone_number='+998901112255',
            birth_year=2000,
        )
        self.patient.clinics.add(self.clinic)

    def _reception_headers(self):
        token = signing.dumps(
            {
                'staff_id': str(self.reception_staff.id),
                'clinic_id': str(self.clinic.id),
            },
            salt='reception-staff-session',
        )
        return {'HTTP_X_RECEPTION_SESSION': token}

    def _create_appointment(self, when_dt, fee, status):
        return Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            clinic=self.clinic,
            reception_staff=self.reception_staff,
            scheduled_date=when_dt,
            consultation_fee=fee,
            status=status,
        )

    def test_stats_monthly_revenue_stays_within_selected_month(self):
        report_date = date(2026, 8, 15)

        self._create_appointment(
            timezone.make_aware(datetime(2026, 8, 15, 9, 0)),
            30000,
            Appointment.Status.WAITING,
        )
        self._create_appointment(
            timezone.make_aware(datetime(2026, 8, 10, 10, 0)),
            100000,
            Appointment.Status.SCHEDULED,
        )
        self._create_appointment(
            timezone.make_aware(datetime(2026, 8, 11, 11, 0)),
            50000,
            Appointment.Status.COMPLETED,
        )
        self._create_appointment(
            timezone.make_aware(datetime(2026, 8, 12, 12, 0)),
            900000,
            Appointment.Status.CANCELLED,
        )
        self._create_appointment(
            timezone.make_aware(datetime(2026, 9, 2, 13, 0)),
            700000,
            Appointment.Status.COMPLETED,
        )

        url = reverse('reception-staff-stats')
        response = self.client.get(
            url,
            {'date': str(report_date)},
            **self._reception_headers(),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['accepted_count'], 1)
        self.assertEqual(float(payload['daily_revenue']), 30000.0)
        self.assertEqual(float(payload['monthly_revenue']), 180000.0)

    def test_stats_moves_patient_from_today_queue_to_accepted_after_doctor_accepts(self):
        self._create_appointment(
            timezone.make_aware(datetime(2026, 8, 24, 9, 0)),
            30000,
            Appointment.Status.WAITING,
        )
        accepted = self._create_appointment(
            timezone.make_aware(datetime(2026, 8, 24, 10, 0)),
            40000,
            Appointment.Status.IN_PROGRESS,
        )
        completed = self._create_appointment(
            timezone.make_aware(datetime(2026, 8, 24, 11, 0)),
            50000,
            Appointment.Status.COMPLETED,
        )

        response = self.client.get(
            reverse('reception-staff-stats'),
            {'date': '2026-08-24'},
            **self._reception_headers(),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        queue_ids = {item['id'] for item in payload['queue_patients']}
        accepted_ids = {item['id'] for item in payload['doctor_accepted_patients']}
        self.assertNotIn(str(accepted.id), queue_ids)
        self.assertNotIn(str(completed.id), queue_ids)
        self.assertIn(str(accepted.id), accepted_ids)
        self.assertIn(str(completed.id), accepted_ids)

    @override_settings(REST_FRAMEWORK=LOGIN_THROTTLE_TEST_SETTINGS)
    def test_reception_login_not_blocked_by_global_anon_throttle(self):
        url = reverse('reception-staff-login')
        bad_payload = {
            'email': self.reception_staff.email,
            'password': 'wrong-pass',
        }

        first = self.client.post(url, bad_payload, content_type='application/json')
        second = self.client.post(url, bad_payload, content_type='application/json')

        self.assertEqual(first.status_code, 401)
        self.assertEqual(second.status_code, 401)
