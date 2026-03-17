from django.urls import reverse
from django.utils import timezone
from datetime import timedelta, datetime, date
from rest_framework.test import APITestCase
from typing import Any, cast

from apps.users.models import CustomUser
from apps.clinics.models import Clinic
from apps.doctors.models import Doctor, Specialization, DoctorAvailability, DoctorEmployment, DoctorWorkRecord
from apps.patients.models import Patient
from apps.medical.models import Appointment, MedicalRecord


class DoctorEmploymentLifecycleTests(APITestCase):
    def auth_as(self, user: CustomUser) -> None:
        cast(Any, self.client).force_authenticate(user=user)

    def setUp(self):
        self.owner_a = CustomUser.objects.create_user(
            username='clinic_owner_a',
            email='owner.a@example.com',
            password='Pass12345!',
            role='clinic',
            first_name='Clinic',
            last_name='OwnerA',
        )
        self.clinic_a = Clinic.objects.create(
            owner=self.owner_a,
            name='Clinic A',
            slug='clinic-a',
            address='Address A',
            phone_number='+998901110000',
            email='clinic.a@example.com',
            registration_number='REG-CLINIC-A',
            status='active',
        )

        self.owner_b = CustomUser.objects.create_user(
            username='clinic_owner_b',
            email='owner.b@example.com',
            password='Pass12345!',
            role='clinic',
            first_name='Clinic',
            last_name='OwnerB',
        )
        self.clinic_b = Clinic.objects.create(
            owner=self.owner_b,
            name='Clinic B',
            slug='clinic-b',
            address='Address B',
            phone_number='+998902220000',
            email='clinic.b@example.com',
            registration_number='REG-CLINIC-B',
            status='active',
        )

        self.doctor_user = CustomUser.objects.create_user(
            username='doctor.user',
            email='doctor.user@example.com',
            password='Pass12345!',
            role='doctor',
            first_name='Doctor',
            last_name='User',
        )
        self.doctor = Doctor.objects.create(
            user=self.doctor_user,
            clinic=self.clinic_a,
            license_number='LIC-EMP-001',
            pinfl='12345678901234',
            passport_id='AB1234567',
            date_of_birth=date(1990, 1, 1),
            is_active=True,
        )

    def _list_results(self, response):
        payload = response.json()
        if isinstance(payload, dict) and 'results' in payload:
            return payload['results']
        return payload

    def _rehire_doctor_to_clinic_b(self, **extra_payload):
        self.auth_as(self.owner_b)
        create_url = reverse('doctor-list')
        payload = {
            'pinfl': '12345678901234',
            'passport_id': 'AB1234567',
            'date_of_birth': '1990-01-01',
            'first_name': 'Doctor',
            'last_name': 'User',
            'email': 'doctor.user@example.com',
        }
        payload.update(extra_payload)
        return self.client.post(create_url, payload, format='json')

    def test_identity_check_blocks_active_doctor_in_other_clinic(self):
        self.auth_as(self.owner_b)
        url = reverse('doctor-identity-check')

        response = self.client.post(url, {
            'pinfl': '12345678901234',
            'passport_id': 'AB1234567',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get('status'), 'blocked_other_clinic')
        self.assertFalse(payload.get('can_submit'))

    def test_identity_check_allows_new_doctor_when_identity_not_found(self):
        self.auth_as(self.owner_a)
        url = reverse('doctor-identity-check')

        response = self.client.post(url, {
            'pinfl': '77778888999900',
            'passport_id': 'AA7654321',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get('status'), 'new_doctor_allowed')
        self.assertTrue(payload.get('can_submit'))

    def test_identity_check_marks_existing_doctor_as_eligible_rehire_on_full_match(self):
        self.auth_as(self.owner_a)
        terminate_url = reverse('doctor-terminate', args=[self.doctor.id])
        self.client.post(terminate_url, {})

        self.auth_as(self.owner_b)
        url = reverse('doctor-identity-check')
        response = self.client.post(url, {
            'pinfl': '12345678901234',
            'passport_id': 'AB1234567',
            'date_of_birth': '1990-01-01',
            'first_name': 'Doctor',
            'last_name': 'User',
            'email': 'doctor.user@example.com',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get('status'), 'eligible_rehire')
        self.assertTrue(payload.get('can_submit'))

    def test_active_doctor_cannot_be_hired_to_other_clinic_by_pinfl(self):
        self.auth_as(self.owner_b)
        create_url = reverse('doctor-list')

        response = self.client.post(create_url, {'pinfl': '12345678901234'}, format='json')

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIn('detail', payload)
        self.assertIn('boshqa klinikada ham faoliyat yuritadi', str(payload['detail']).lower())

    def test_active_doctor_cannot_be_hired_to_other_clinic_by_passport(self):
        self.auth_as(self.owner_b)
        create_url = reverse('doctor-list')

        response = self.client.post(create_url, {'passport_id': 'AB1234567'}, format='json')

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIn('detail', payload)
        self.assertIn('boshqa klinikada ham faoliyat yuritadi', str(payload['detail']).lower())

    def test_active_doctor_duplicate_pinfl_in_same_clinic_returns_field_error(self):
        self.auth_as(self.owner_a)
        create_url = reverse('doctor-list')

        response = self.client.post(create_url, {'pinfl': '12345678901234'}, format='json')

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIn('pinfl', payload)
        self.assertIn('allaqachon mavjud', str(payload['pinfl']).lower())

    def test_active_doctor_duplicate_passport_in_same_clinic_returns_field_error(self):
        self.auth_as(self.owner_a)
        create_url = reverse('doctor-list')

        response = self.client.post(create_url, {'passport_id': 'AB1234567'}, format='json')

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIn('passport_id', payload)
        self.assertIn('allaqachon mavjud', str(payload['passport_id']).lower())

    def test_terminate_keeps_profile_but_unassigns_clinic(self):
        self.auth_as(self.owner_a)
        url = reverse('doctor-terminate', args=[self.doctor.id])

        response = self.client.post(url, {})

        self.assertEqual(response.status_code, 200)
        self.doctor.refresh_from_db()
        self.assertFalse(self.doctor.is_active)
        self.assertIsNone(self.doctor.clinic)

    def test_terminate_and_rehire_preserve_employment_history(self):
        self.doctor.compensation_type = 'salary'
        self.doctor.compensation_value = 2500000
        self.doctor.save(update_fields=['compensation_type', 'compensation_value', 'updated_at'])

        self.auth_as(self.owner_a)
        terminate_url = reverse('doctor-terminate', args=[self.doctor.id])

        terminate_response = self.client.post(terminate_url, {})
        self.assertEqual(terminate_response.status_code, 200)

        old_employment = DoctorEmployment.objects.filter(
            doctor=self.doctor,
            clinic=self.clinic_a,
        ).order_by('-started_at').first()
        self.assertIsNotNone(old_employment)
        self.assertIsNotNone(old_employment.ended_at)
        self.assertEqual(old_employment.terminated_by_id, self.owner_a.id)
        self.assertEqual(old_employment.compensation_type, 'salary')
        self.assertEqual(float(cast(Any, old_employment.compensation_value)), 2500000.0)

        rehire_response = self._rehire_doctor_to_clinic_b(
            compensation_type='percent',
            compensation_value='30',
        )
        self.assertEqual(rehire_response.status_code, 201)

        active_employment = DoctorEmployment.objects.filter(
            doctor=self.doctor,
            clinic=self.clinic_b,
            ended_at__isnull=True,
        ).first()
        self.assertIsNotNone(active_employment)
        self.assertEqual(active_employment.compensation_type, 'percent')
        self.assertEqual(float(cast(Any, active_employment.compensation_value)), 30.0)

    def test_include_former_list_keeps_old_clinic_stats_and_isolates_new_clinic_stats(self):
        today = timezone.localdate()
        old_work_date = today.replace(day=1)
        new_work_date = today if today.day != 1 else today.replace(day=2)

        old_start_dt = timezone.make_aware(datetime.combine(old_work_date, datetime.min.time()))
        Doctor.objects.filter(id=self.doctor.id).update(
            created_at=old_start_dt,
            updated_at=old_start_dt,
            compensation_type='salary',
            compensation_value=2000000,
            consultation_fee=100000,
        )
        self.doctor.refresh_from_db()

        DoctorWorkRecord.objects.create(
            doctor=self.doctor,
            date=old_work_date,
            checked_in_at=datetime.strptime('09:00', '%H:%M').time(),
            checked_out_at=datetime.strptime('13:00', '%H:%M').time(),
        )

        patient_user = CustomUser.objects.create_user(
            username='patient-for-scope',
            email='patient.scope@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Scope',
            last_name='Patient',
        )
        patient = Patient.objects.create(user=patient_user, national_id='99887766554433')

        old_appointment = Appointment.objects.create(
            patient=patient,
            doctor=self.doctor,
            clinic=self.clinic_a,
            status=Appointment.Status.COMPLETED,
            scheduled_date=timezone.make_aware(datetime.combine(old_work_date, datetime.strptime('10:00', '%H:%M').time())),
            consultation_fee=100000,
        )
        MedicalRecord.objects.create(
            patient=patient,
            doctor=self.doctor,
            clinic=self.clinic_a,
            appointment=old_appointment,
        )

        self.auth_as(self.owner_a)
        terminate_url = reverse('doctor-terminate', args=[self.doctor.id])
        terminate_response = self.client.post(terminate_url, {})
        self.assertEqual(terminate_response.status_code, 200)

        rehire_response = self._rehire_doctor_to_clinic_b(
            compensation_type='percent',
            compensation_value='40',
            consultation_fee='200000',
        )
        self.assertEqual(rehire_response.status_code, 201)
        self.doctor.refresh_from_db()

        DoctorWorkRecord.objects.create(
            doctor=self.doctor,
            date=new_work_date,
            checked_in_at=datetime.strptime('10:00', '%H:%M').time(),
            checked_out_at=datetime.strptime('16:00', '%H:%M').time(),
        )

        new_appointment = Appointment.objects.create(
            patient=patient,
            doctor=self.doctor,
            clinic=self.clinic_b,
            status=Appointment.Status.COMPLETED,
            scheduled_date=timezone.make_aware(datetime.combine(new_work_date, datetime.strptime('11:00', '%H:%M').time())),
            consultation_fee=200000,
        )
        MedicalRecord.objects.create(
            patient=patient,
            doctor=self.doctor,
            clinic=self.clinic_b,
            appointment=new_appointment,
        )

        self.auth_as(self.owner_a)
        old_list_response = self.client.get(reverse('doctor-list'), {
            'clinic': str(self.clinic_a.id),
            'include_former': '1',
        })
        self.assertEqual(old_list_response.status_code, 200)
        old_results = self._list_results(old_list_response)
        old_doctor = next((item for item in old_results if str(item['id']) == str(self.doctor.id)), None)
        self.assertIsNotNone(old_doctor)
        self.assertEqual(old_doctor['clinic_association_status'], 'former')
        self.assertTrue(old_doctor['is_former_for_scope_clinic'])
        self.assertAlmostEqual(float(old_doctor['monthly_hours']), 4.0, places=2)
        self.assertEqual(old_doctor['monthly_patients'], 1)
        self.assertAlmostEqual(float(old_doctor['monthly_effective_revenue']), 100000.0, places=2)
        self.assertAlmostEqual(float(old_doctor['monthly_estimated_salary']), 2000000.0, places=2)

        self.auth_as(self.owner_b)
        new_list_response = self.client.get(reverse('doctor-list'), {
            'clinic': str(self.clinic_b.id),
            'include_former': '1',
        })
        self.assertEqual(new_list_response.status_code, 200)
        new_results = self._list_results(new_list_response)
        new_doctor = next((item for item in new_results if str(item['id']) == str(self.doctor.id)), None)
        self.assertIsNotNone(new_doctor)
        self.assertEqual(new_doctor['clinic_association_status'], 'current')
        self.assertFalse(new_doctor['is_former_for_scope_clinic'])
        self.assertAlmostEqual(float(new_doctor['monthly_hours']), 6.0, places=2)
        self.assertEqual(new_doctor['monthly_patients'], 1)
        self.assertAlmostEqual(float(new_doctor['monthly_effective_revenue']), 200000.0, places=2)
        self.assertAlmostEqual(float(new_doctor['monthly_estimated_salary']), 80000.0, places=2)

    def test_rehire_by_pinfl_reuses_same_doctor_profile(self):
        self.auth_as(self.owner_a)
        terminate_url = reverse('doctor-terminate', args=[self.doctor.id])
        terminate_response = self.client.post(terminate_url, {})
        self.assertEqual(terminate_response.status_code, 200)

        self.auth_as(self.owner_b)
        create_url = reverse('doctor-list')
        doctor_count_before = Doctor.objects.count()

        response = self.client.post(create_url, {
            'pinfl': '12345678901234',
            'passport_id': 'AB1234567',
            'date_of_birth': '1990-01-01',
            'first_name': 'Doctor',
            'last_name': 'User',
            'email': 'doctor.user@example.com',
        }, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Doctor.objects.count(), doctor_count_before)
        self.doctor.refresh_from_db()
        self.assertTrue(self.doctor.is_active)
        self.assertEqual(self.doctor.clinic, self.clinic_b)

    def test_rehire_by_passport_reuses_same_doctor_profile(self):
        self.auth_as(self.owner_a)
        terminate_url = reverse('doctor-terminate', args=[self.doctor.id])
        terminate_response = self.client.post(terminate_url, {})
        self.assertEqual(terminate_response.status_code, 200)

        self.auth_as(self.owner_b)
        create_url = reverse('doctor-list')
        doctor_count_before = Doctor.objects.count()

        response = self.client.post(create_url, {
            'pinfl': '12345678901234',
            'passport_id': 'AB1234567',
            'date_of_birth': '1990-01-01',
            'first_name': 'Doctor',
            'last_name': 'User',
            'email': 'doctor.user@example.com',
        }, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Doctor.objects.count(), doctor_count_before)
        self.doctor.refresh_from_db()
        self.assertTrue(self.doctor.is_active)
        self.assertEqual(self.doctor.clinic, self.clinic_b)

    def test_rehire_with_same_email_for_same_doctor_is_allowed(self):
        self.auth_as(self.owner_a)
        terminate_url = reverse('doctor-terminate', args=[self.doctor.id])
        self.client.post(terminate_url, {})

        self.auth_as(self.owner_b)
        create_url = reverse('doctor-list')
        response = self.client.post(create_url, {
            'pinfl': '12345678901234',
            'passport_id': 'AB1234567',
            'date_of_birth': '1990-01-01',
            'first_name': 'Doctor',
            'last_name': 'User',
            'email': 'doctor.user@example.com',
        }, format='json')

        self.assertEqual(response.status_code, 201)
        self.doctor.refresh_from_db()
        self.assertEqual(self.doctor.clinic, self.clinic_b)

    def test_rehire_with_email_of_another_doctor_returns_error(self):
        other_user = CustomUser.objects.create_user(
            username='doctor.other',
            email='other.doctor@example.com',
            password='Pass12345!',
            role='doctor',
            first_name='Other',
            last_name='Doctor',
        )
        Doctor.objects.create(
            user=other_user,
            clinic=self.clinic_b,
            license_number='LIC-OTHER-001',
            pinfl='55556666777788',
            is_active=True,
        )

        self.auth_as(self.owner_a)
        terminate_url = reverse('doctor-terminate', args=[self.doctor.id])
        self.client.post(terminate_url, {})

        self.auth_as(self.owner_b)
        create_url = reverse('doctor-list')
        response = self.client.post(create_url, {
            'pinfl': '12345678901234',
            'passport_id': 'AB1234567',
            'date_of_birth': '1990-01-01',
            'first_name': 'Doctor',
            'last_name': 'User',
            'email': 'other.doctor@example.com',
        }, format='json')

        self.assertEqual(response.status_code, 400)
        response_json = response.json()
        self.assertIn('email', response_json)
        self.assertIn('boshqa doktorga tegishli', str(response_json['email']).lower())

    def test_rehire_rejects_when_full_identity_does_not_match_existing_doctor(self):
        self.auth_as(self.owner_a)
        terminate_url = reverse('doctor-terminate', args=[self.doctor.id])
        self.client.post(terminate_url, {})

        self.auth_as(self.owner_b)
        create_url = reverse('doctor-list')
        response = self.client.post(create_url, {
            'pinfl': '12345678901234',
            'passport_id': 'AB1234567',
            'date_of_birth': '1990-01-01',
            'first_name': 'WrongName',
            'last_name': 'User',
            'email': 'doctor.user@example.com',
        }, format='json')

        self.assertEqual(response.status_code, 400)
        response_json = response.json()
        self.assertIn('first_name', response_json)
        self.assertIn('mos emas', str(response_json['first_name']).lower())

    def test_delete_doctor_is_not_allowed(self):
        self.auth_as(self.owner_a)
        url = reverse('doctor-detail', args=[self.doctor.id])

        response = self.client.delete(url)

        self.assertEqual(response.status_code, 405)

    def test_fired_doctor_can_update_own_profile(self):
        self.auth_as(self.owner_a)
        terminate_url = reverse('doctor-terminate', args=[self.doctor.id])
        self.client.post(terminate_url, {})

        self.auth_as(self.doctor_user)
        update_url = reverse('doctor-my-update')
        current_year = timezone.localdate().year
        response = self.client.patch(update_url, {
            'first_name': 'Updated',
            'last_name': 'Doctor',
            'phone_number': '+998900001122',
            'bio': 'Updated bio',
            'first_work_year': current_year - 7,
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.doctor.refresh_from_db()
        self.assertEqual(self.doctor.user.first_name, 'Updated')
        self.assertEqual(self.doctor.user.phone_number, '+998900001122')
        self.assertEqual(self.doctor.bio, 'Updated bio')
        self.assertEqual(self.doctor.years_of_experience, 7)

    def test_doctor_self_update_cannot_change_work_time(self):
        self.auth_as(self.doctor_user)
        update_url = reverse('doctor-my-update')
        response = self.client.patch(update_url, {
            'available_from': '12:00',
            'available_until': '18:00',
        }, format='json')

        self.assertEqual(response.status_code, 400)
        self.doctor.refresh_from_db()
        self.assertNotEqual(str(self.doctor.available_from)[:5], '12:00')

    def test_doctor_self_update_can_change_slot_minutes(self):
        self.auth_as(self.doctor_user)
        update_url = reverse('doctor-my-update')

        response = self.client.patch(update_url, {
            'slot_minutes': 20,
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.doctor.refresh_from_db()
        self.assertEqual(self.doctor.slot_minutes, 20)

    def test_doctor_pinfl_immutable_once_set(self):
        self.auth_as(self.doctor_user)
        update_url = reverse('doctor-my-update')
        response = self.client.patch(update_url, {'pinfl': '99999999999999'}, format='json')

        self.assertEqual(response.status_code, 400)
        self.doctor.refresh_from_db()
        self.assertEqual(self.doctor.pinfl, '12345678901234')

    def test_doctor_can_add_pinfl_if_missing(self):
        self.doctor.pinfl = None
        self.doctor.save(update_fields=['pinfl'])
        self.auth_as(self.doctor_user)
        update_url = reverse('doctor-my-update')
        response = self.client.patch(update_url, {'pinfl': '77777777777777'}, format='json')

        self.assertEqual(response.status_code, 200)
        self.doctor.refresh_from_db()
        self.assertEqual(self.doctor.pinfl, '77777777777777')

    def test_experience_uses_first_work_month(self):
        self.auth_as(self.doctor_user)
        update_url = reverse('doctor-my-update')

        today = timezone.localdate()
        year = today.year - 5
        month = 12

        response = self.client.patch(update_url, {
            'first_work_year': year,
            'first_work_month': month,
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.doctor.refresh_from_db()
        expected_experience = max(0, (today.year - year) - (1 if today.month < month else 0))
        self.assertEqual(self.doctor.years_of_experience, expected_experience)

    def test_create_doctor_without_license_with_identity_and_compensation_fields(self):
        self.auth_as(self.owner_a)
        create_url = reverse('doctor-list')
        specialization = Specialization.objects.create(name='Kardiolog', code='CARD')

        payload = {
            'pinfl': '88887777666655',
            'first_name': 'Yangi',
            'last_name': 'Doktor',
            'email': 'new.doctor@example.com',
            'phone_number': '+998901234567',
            'password': 'Pass12345!',
            'passport_id': 'AA1234567',
            'date_of_birth': '1990-01-20',
            'compensation_type': 'percent',
            'compensation_value': '25',
            'specialization_ids': [str(specialization.id)],
            'available_from': '08:00',
            'available_until': '16:00',
            'lunch_break_start': '12:00',
            'lunch_break_end': '13:00',
            'working_days': 'Mon,Tue,Wed,Thu,Fri',
        }

        response = self.client.post(create_url, payload, format='json')

        self.assertEqual(response.status_code, 201)
        created = Doctor.objects.get(pinfl='88887777666655')
        self.assertTrue(created.license_number.startswith('AUTO-'))
        self.assertEqual(created.passport_id, 'AA1234567')
        self.assertEqual(created.compensation_type, 'percent')
        self.assertIsNotNone(created.compensation_value)
        self.assertEqual(float(cast(Any, created.compensation_value)), 25.0)
        self.assertEqual(str(created.lunch_break_start)[:5], '12:00')
        self.assertEqual(str(created.lunch_break_end)[:5], '13:00')

    def test_create_doctor_rejects_non_numeric_pinfl(self):
        self.auth_as(self.owner_a)
        create_url = reverse('doctor-list')
        specialization = Specialization.objects.create(name='Nevrolog', code='NEUR')

        payload = {
            'pinfl': '1234ABCD5678',
            'first_name': 'Yangi',
            'last_name': 'Doktor',
            'email': 'pinfl.invalid@example.com',
            'phone_number': '+998901231111',
            'password': 'Pass12345!',
            'consultation_fee': '60000',
            'specialization_ids': [str(specialization.id)],
            'available_from': '09:00',
            'available_until': '18:00',
            'working_days': 'Mon,Tue,Wed,Thu,Fri',
        }

        response = self.client.post(create_url, payload, format='json')

        self.assertEqual(response.status_code, 400)
        response_json = response.json()
        self.assertIn('pinfl', response_json)
        self.assertIn('faqat raqamlardan iborat', str(response_json['pinfl']).lower())

    def test_create_doctor_rejects_non_14_digit_jshshir(self):
        self.auth_as(self.owner_a)
        create_url = reverse('doctor-list')
        specialization, _ = Specialization.objects.get_or_create(
            code='ENDO',
            defaults={'name': 'Endokrinolog'},
        )

        payload = {
            'pinfl': '1234567890123',
            'first_name': 'Yangi',
            'last_name': 'Doktor',
            'email': 'pinfl.short@example.com',
            'phone_number': '+998901231112',
            'password': 'Pass12345!',
            'consultation_fee': '60000',
            'specialization_ids': [str(specialization.id)],
            'available_from': '09:00',
            'available_until': '18:00',
            'working_days': 'Mon,Tue,Wed,Thu,Fri',
        }

        response = self.client.post(create_url, payload, format='json')

        self.assertEqual(response.status_code, 400)
        response_json = response.json()
        self.assertIn('pinfl', response_json)
        self.assertIn('14', str(response_json['pinfl']))

    def test_create_doctor_rejects_passport_id_used_by_patient(self):
        patient_user = CustomUser.objects.create_user(
            username='patient-passport-owner',
            email='patient.passport.owner@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Patient',
            last_name='Owner',
        )
        Patient.objects.create(
            user=patient_user,
            national_id='AA1234567',
        )

        self.auth_as(self.owner_a)
        create_url = reverse('doctor-list')
        specialization = Specialization.objects.create(name='Pulmonolog', code='PULM')

        payload = {
            'pinfl': '11112222333344',
            'first_name': 'Yangi',
            'last_name': 'Doktor',
            'email': 'passport.conflict@example.com',
            'phone_number': '+998901231113',
            'password': 'Pass12345!',
            'passport_id': 'AA1234567',
            'consultation_fee': '60000',
            'specialization_ids': [str(specialization.id)],
            'available_from': '09:00',
            'available_until': '18:00',
            'working_days': 'Mon,Tue,Wed,Thu,Fri',
        }

        response = self.client.post(create_url, payload, format='json')

        self.assertEqual(response.status_code, 400)
        response_json = response.json()
        self.assertIn('passport_id', response_json)
        self.assertIn('boshqa odamga tegishli', str(response_json['passport_id']).lower())

    def test_clinic_owner_can_update_doctor_lunch_schedule(self):
        self.auth_as(self.owner_a)
        url = reverse('doctor-detail', args=[self.doctor.id])

        response = self.client.patch(url, {
            'available_from': '09:00',
            'available_until': '18:00',
            'lunch_break_start': '13:00',
            'lunch_break_end': '14:00',
            'working_days': 'Mon,Tue,Wed,Thu,Fri',
            'version': self.doctor.updated_at.isoformat(),
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.doctor.refresh_from_db()
        self.assertEqual(str(self.doctor.lunch_break_start)[:5], '13:00')
        self.assertEqual(str(self.doctor.lunch_break_end)[:5], '14:00')

    def _next_weekday(self):
        target = timezone.localdate() + timedelta(days=1)
        while target.weekday() >= 5:
            target += timedelta(days=1)
        return target

    def test_available_endpoint_rebuilds_legacy_available_slots_for_current_interval(self):
        target_date = self._next_weekday()

        self.doctor.available_from = datetime.strptime('09:00', '%H:%M').time()
        self.doctor.available_until = datetime.strptime('11:00', '%H:%M').time()
        self.doctor.working_days = 'Mon,Tue,Wed,Thu,Fri'
        self.doctor.slot_minutes = 20
        self.doctor.save(update_fields=['available_from', 'available_until', 'working_days', 'slot_minutes', 'updated_at'])

        DoctorAvailability.objects.create(
            doctor=self.doctor,
            date=target_date,
            start_time=datetime.strptime('09:15', '%H:%M').time(),
            end_time=datetime.strptime('09:30', '%H:%M').time(),
            status='available',
        )
        DoctorAvailability.objects.create(
            doctor=self.doctor,
            date=target_date,
            start_time=datetime.strptime('09:30', '%H:%M').time(),
            end_time=datetime.strptime('10:00', '%H:%M').time(),
            status='available',
        )

        url = reverse('doctor-availability-available')
        response = self.client.get(url, {'doctor': str(self.doctor.id), 'date': target_date.isoformat()})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(len(data) > 0)

        for slot in data:
            start = datetime.strptime(slot['start_time'][:5], '%H:%M')
            end = datetime.strptime(slot['end_time'][:5], '%H:%M')
            self.assertEqual(int((end - start).total_seconds() // 60), 20)

        ordered = sorted(data, key=lambda item: item['start_time'])
        for idx in range(1, len(ordered)):
            prev_end = datetime.strptime(ordered[idx - 1]['end_time'][:5], '%H:%M')
            curr_start = datetime.strptime(ordered[idx]['start_time'][:5], '%H:%M')
            self.assertGreaterEqual(curr_start, prev_end)

    def test_available_endpoint_does_not_create_slots_overlapping_booked_slot(self):
        target_date = self._next_weekday()

        self.doctor.available_from = datetime.strptime('09:00', '%H:%M').time()
        self.doctor.available_until = datetime.strptime('11:00', '%H:%M').time()
        self.doctor.working_days = 'Mon,Tue,Wed,Thu,Fri'
        self.doctor.slot_minutes = 20
        self.doctor.save(update_fields=['available_from', 'available_until', 'working_days', 'slot_minutes', 'updated_at'])

        DoctorAvailability.objects.create(
            doctor=self.doctor,
            date=target_date,
            start_time=datetime.strptime('09:30', '%H:%M').time(),
            end_time=datetime.strptime('10:00', '%H:%M').time(),
            status='booked',
        )

        url = reverse('doctor-availability-available')
        response = self.client.get(url, {'doctor': str(self.doctor.id), 'date': target_date.isoformat()})

        self.assertEqual(response.status_code, 200)
        data = response.json()

        blocked_start = datetime.strptime('09:30', '%H:%M')
        blocked_end = datetime.strptime('10:00', '%H:%M')

        for slot in data:
            start = datetime.strptime(slot['start_time'][:5], '%H:%M')
            end = datetime.strptime(slot['end_time'][:5], '%H:%M')
            self.assertFalse(start < blocked_end and end > blocked_start)
