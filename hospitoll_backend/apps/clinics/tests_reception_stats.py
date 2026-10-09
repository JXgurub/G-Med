from datetime import datetime, date
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core import signing
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.clinics.models import Clinic, ReceptionStaff
from apps.clinics.views import ClinicViewSet
from apps.doctors.models import Doctor, DoctorSpecialization, Specialization
from apps.medical.models import Appointment
from apps.patients.models import Patient
from apps.pharmacies.views import PharmacyViewSet
from apps.users.models import CustomUser


LOGIN_THROTTLE_TEST_SETTINGS = dict(settings.REST_FRAMEWORK)
LOGIN_THROTTLE_TEST_SETTINGS['DEFAULT_THROTTLE_RATES'] = dict(
    settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {}),
    anon='1/day',
    auth='100/minute',
)

PUBLIC_LIST_THROTTLE_TEST_SETTINGS = dict(settings.REST_FRAMEWORK)
PUBLIC_LIST_THROTTLE_TEST_SETTINGS['DEFAULT_THROTTLE_RATES'] = dict(
    settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {}),
    anon='1/hour',
    user='100/minute',
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

    def test_reception_staff_can_add_custom_doctor_specialty_price_in_own_clinic(self):
        self.clinic.reception_room_enabled = True
        self.clinic.save(update_fields=['reception_room_enabled'])

        response = self.client.post(
            '/api/v1/clinics/reception-staff/specialty-prices/',
            {
                'doctor_id': str(self.doctor.id),
                'name': 'Qabulxona qo‘shimcha xizmati',
                'consultation_fee': '75000',
            },
            format='json',
            **self._reception_headers(),
        )

        self.assertEqual(response.status_code, 201)
        specialty_price = DoctorSpecialization.objects.get(id=response.json()['id'])
        self.assertEqual(specialty_price.doctor_id, self.doctor.id)
        self.assertEqual(specialty_price.doctor.clinic_id, self.reception_staff.clinic_id)
        self.assertTrue(specialty_price.doctor_custom)
        self.assertEqual(specialty_price.custom_name, 'Qabulxona qo‘shimcha xizmati')
        self.assertEqual(float(specialty_price.consultation_fee), 75000.0)

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

    def test_stats_keeps_in_progress_patient_visible_until_visit_is_completed(self):
        self.patient.date_of_birth = date(2000, 5, 17)
        self.patient.save(update_fields=['date_of_birth'])
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
        accepted.payment_method = 'card'
        accepted.ticket_number = 7
        accepted.save(update_fields=['payment_method', 'ticket_number'])
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
        self.assertIn(str(accepted.id), queue_ids)
        self.assertNotIn(str(completed.id), queue_ids)
        self.assertIn(str(accepted.id), accepted_ids)
        self.assertIn(str(completed.id), accepted_ids)
        accepted_item = next(item for item in payload['doctor_accepted_patients'] if item['id'] == str(accepted.id))
        self.assertEqual(accepted_item['payment_method'], 'Plastik')
        self.assertEqual(accepted_item['doctor_id'], str(self.doctor.id))
        self.assertEqual(accepted_item['date_of_birth'], '2000-05-17')
        self.assertEqual(accepted_item['ticket_number'], 7)

    def test_stats_keeps_auto_queue_behavior_when_reception_feature_is_disabled(self):
        self.clinic.reception_room_enabled = False
        self.clinic.save(update_fields=['reception_room_enabled'])
        in_progress = self._create_appointment(
            timezone.make_aware(datetime(2026, 8, 24, 10, 0)),
            40000,
            Appointment.Status.IN_PROGRESS,
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
        self.assertNotIn(str(in_progress.id), queue_ids)
        self.assertIn(str(in_progress.id), accepted_ids)

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

    def test_public_api_list_views_disable_global_throttling(self):
        clinic_view = ClinicViewSet()
        clinic_view.action = 'list'
        self.assertEqual(clinic_view.get_throttles(), [])

        clinic_detail = ClinicViewSet()
        clinic_detail.action = 'retrieve'
        self.assertEqual(clinic_detail.get_throttles(), [])

        pharmacy_view = PharmacyViewSet()
        pharmacy_view.action = 'list'
        self.assertEqual(pharmacy_view.get_throttles(), [])

        pharmacy_detail = PharmacyViewSet()
        pharmacy_detail.action = 'retrieve'
        self.assertEqual(pharmacy_detail.get_throttles(), [])

    @patch('apps.medical.views.AppointmentViewSet._enqueue_reception_print_job')
    def test_reception_patient_search_and_online_appointment_actions(self, enqueue_print):
        patient_response = self.client.get(
            '/api/v1/clinics/reception-staff/patients/',
            {'q': 'Patient Stats'},
            **self._reception_headers(),
        )
        self.assertEqual(patient_response.status_code, 200)
        self.assertEqual(len(patient_response.json()), 1)

        first = self._create_appointment(
            timezone.make_aware(datetime(2026, 9, 28, 10, 0)),
            25000,
            Appointment.Status.PENDING_TELEGRAM_CONFIRMATION,
        )
        original_specialty = Specialization.objects.create(name='Onlayn xizmat', code='ONLINE-ORIGINAL')
        added_specialty = Specialization.objects.create(name='Qabulxona xizmati', code='RECEPTION-ADDED')
        original_price = DoctorSpecialization.objects.create(
            doctor=self.doctor,
            specialization=original_specialty,
            consultation_fee=25000,
            is_active=True,
        )
        added_price = DoctorSpecialization.objects.create(
            doctor=self.doctor,
            specialization=added_specialty,
            consultation_fee=35000,
            is_active=True,
        )
        first.selected_specialties = [{
            'id': str(original_price.id),
            'name': original_specialty.name,
            'price': 25000.0,
        }]
        first.save(update_fields=['selected_specialties'])
        pending_response = self.client.get(
            '/api/v1/clinics/reception-staff/online-appointments/',
            **self._reception_headers(),
        )
        self.assertEqual(pending_response.status_code, 200)
        self.assertEqual([item['id'] for item in pending_response.json()], [str(first.id)])

        confirm_response = self.client.post(
            f'/api/v1/clinics/reception-staff/online-appointments/{first.id}/confirm/',
            {'specialty_price_ids': [str(original_price.id), str(added_price.id)]},
            format='json',
            **self._reception_headers(),
        )
        self.assertEqual(confirm_response.status_code, 200, confirm_response.data)
        first.refresh_from_db()
        self.assertEqual(first.status, Appointment.Status.SCHEDULED)
        self.assertEqual(first.payment_method, 'cash')
        self.assertEqual(float(first.consultation_fee), 60000.0)
        self.assertEqual({item['id'] for item in first.selected_specialties}, {str(original_price.id), str(added_price.id)})
        enqueue_print.assert_called_once()
        printed_appointment = enqueue_print.call_args.args[0]
        self.assertEqual(float(printed_appointment.consultation_fee), 60000.0)
        self.assertEqual({item['id'] for item in printed_appointment.selected_specialties}, {str(original_price.id), str(added_price.id)})

        second = self._create_appointment(
            timezone.make_aware(datetime(2026, 9, 28, 11, 0)),
            25000,
            Appointment.Status.PENDING_TELEGRAM_CONFIRMATION,
        )
        cancel_response = self.client.post(
            f'/api/v1/clinics/reception-staff/online-appointments/{second.id}/cancel/',
            {},
            format='json',
            **self._reception_headers(),
        )
        self.assertEqual(cancel_response.status_code, 200)
        second.refresh_from_db()
        self.assertEqual(second.status, Appointment.Status.CANCELLED)

    @override_settings(REST_FRAMEWORK=PUBLIC_LIST_THROTTLE_TEST_SETTINGS)
    def test_public_clinic_and_pharmacy_lists_are_not_rate_limited(self):
        first_clinic = self.client.get(reverse('clinic-list'))
        second_clinic = self.client.get(reverse('clinic-list'))
        first_pharmacy = self.client.get(reverse('pharmacy-list'))
        second_pharmacy = self.client.get(reverse('pharmacy-list'))

        self.assertEqual(first_clinic.status_code, 200)
        self.assertEqual(second_clinic.status_code, 200)
        self.assertEqual(first_pharmacy.status_code, 200)
        self.assertEqual(second_pharmacy.status_code, 200)
