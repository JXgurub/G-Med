from unittest.mock import patch
from datetime import date, timedelta
from uuid import UUID
import re

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.clinics.models import Clinic
from apps.doctors.models import Doctor
from apps.patients.models import Patient
from apps.pharmacies.models import Pharmacy
from apps.users.models import ClinicResetTelegramSession, DoctorResetTelegramSession, PatientRegistrationSession, PatientResetTelegramSession, PharmacyResetTelegramSession
from apps.medical.telegram_bot_service import TelegramBotService


User = get_user_model()


class PatientRegistrationTests(APITestCase):
    def setUp(self):
        self.url = reverse('patient_registration')
        self.payload = {
            'first_name': 'New',
            'last_name': 'Patient',
            'phone_number': '+998901234567',
            'password': 'Patient123!',
            'password_confirm': 'Patient123!',
        }

    def request_code(self):
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn('bot_link', body)
        self.assertEqual(Patient.objects.count(), 0)

        sent_messages = []

        class _Client:
            def send_message(self, chat_id, text, reply_markup=None):
                sent_messages.append({'chat_id': chat_id, 'text': text})

        session_token = UUID(body['token'])
        with patch.object(TelegramBotService, '_require_client', return_value=_Client()):
            TelegramBotService().handle_update({
                'message': {
                    'from': {'id': 812345},
                    'chat': {'id': 912345},
                    'text': f'/start reg_{session_token.hex}',
                },
            })

        self.assertTrue(sent_messages)
        code_match = re.search(r'Kod: <b>(\d{6})</b>', sent_messages[-1]['text'])
        self.assertIsNotNone(code_match)
        return body['token'], code_match.group(1)

    def test_registration_creates_patient_user(self):
        token, code = self.request_code()
        with patch.object(TelegramBotService, '_require_client', return_value=type('Client', (), {'send_message': lambda *args, **kwargs: None})()):
            response = self.client.post(
                reverse('patient_registration_verify'),
                {
                    'token': token,
                    'code': code,
                    'password': 'Patient123!',
                    'password_confirm': 'Patient123!',
                },
                format='json',
            )

        self.assertEqual(response.status_code, 201)
        patient = Patient.objects.select_related('user').get(phone_number='+998901234567')
        self.assertEqual(patient.user.role, 'patient')
        self.assertEqual(patient.user.first_name, 'New')
        self.assertTrue(patient.user.check_password('Patient123!'))
        self.assertEqual(patient.telegram_user_id, 812345)
        self.assertEqual(patient.telegram_chat_id, 912345)
        self.assertIsNotNone(patient.telegram_linked_at)

        login_response = self.client.post(
            reverse('patient_token_obtain'),
            {
                'phone_number': '+998901234567',
                'password': 'Patient123!',
            },
            format='json',
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(login_response.json()['user']['role'], 'patient')

        reuse_response = self.client.post(
            reverse('patient_registration_verify'),
            {'token': token, 'code': code},
            format='json',
        )
        self.assertEqual(reuse_response.status_code, 400)

    def test_registration_rejects_existing_patient_phone(self):
        user = User.objects.create_user(
            username='existing_patient',
            email='existing.patient@example.com',
            password='Patient123!',
            role='patient',
            phone_number='+998901234567',
        )
        Patient.objects.create(user=user, phone_number='+998901234567')

        response = self.client.post(self.url, self.payload, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Patient.objects.count(), 1)

    def test_registration_rejects_incorrect_code_without_creating_patient(self):
        token, code = self.request_code()
        wrong_code = f'{(int(code) + 1) % 1000000:06d}'

        response = self.client.post(
            reverse('patient_registration_verify'),
            {
                'token': token,
                'code': wrong_code,
                'password': 'Patient123!',
                'password_confirm': 'Patient123!',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Patient.objects.count(), 0)
        self.assertEqual(PatientRegistrationSession.objects.get(token=token).failed_attempts, 1)

    def test_linked_patient_can_use_bot_menu_without_booking_token(self):
        user = User.objects.create_user(
            username='patient_linked_bot',
            email='patient.linked.bot@example.com',
            password='Patient123!',
            role='patient',
        )
        Patient.objects.create(user=user, telegram_user_id=812345, telegram_chat_id=912345)
        sent_messages = []

        class _Client:
            def send_message(self, chat_id, text, reply_markup=None):
                sent_messages.append(text)

        with patch.object(TelegramBotService, '_require_client', return_value=_Client()):
            TelegramBotService().handle_update({
                'message': {
                    'from': {'id': 812345},
                    'chat': {'id': 912345},
                    'text': '/start',
                },
            })

        self.assertTrue(sent_messages)
        self.assertIn('Yaqin randevu topilmadi', sent_messages[-1])

    def test_registration_rejects_mismatched_passwords(self):
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.status_code, 200)

        verify_response = self.client.post(
            reverse('patient_registration_verify'),
            {
                'token': response.json()['token'],
                'code': '123456',
                'password': 'Patient123!',
                'password_confirm': 'Different123!',
            },
            format='json',
        )

        self.assertEqual(verify_response.status_code, 400)
        self.assertEqual(Patient.objects.count(), 0)


class DoctorPasswordResetFlowTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='clinic_owner_reset',
            email='clinic.reset@example.com',
            password='Pass12345!',
            role='clinic',
            first_name='Clinic',
            last_name='Owner',
            phone_number='+998909999999',
        )
        self.clinic = Clinic.objects.create(
            owner=self.owner,
            name='Reset Clinic',
            slug='reset-clinic',
            address='Reset street 1',
            phone_number='+998901111111',
            email='reset.clinic@example.com',
            registration_number='REG-RESET-001',
            status='active',
        )

        self.doctor_user = User.objects.create_user(
            username='doctor_reset_user',
            email='doctor.reset@example.com',
            password='OldPass123!',
            role='doctor',
            first_name='Reset',
            last_name='Doctor',
            phone_number='+998901234567',
        )
        self.doctor = Doctor.objects.create(
            user=self.doctor_user,
            clinic=self.clinic,
            pinfl='12345678901234',
            passport_id='AA1234567',
            date_of_birth=date(2003, 3, 20),
            license_number='LIC-RESET-001',
            working_days='Mon,Tue,Wed,Thu,Fri,Sat,Sun',
            telegram_user_id=600001,
            telegram_chat_id=700001,
        )

    @override_settings(DEBUG=True)
    def test_request_with_numeric_pinfl_sends_code(self):
        sent_messages = []

        DoctorResetTelegramSession.objects.create(
            user=self.doctor_user,
            doctor=self.doctor,
            telegram_user_id=600001,
            telegram_chat_id=700001,
            linked_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=1),
        )

        class _Client:
            def send_message(self, chat_id, text, reply_markup=None):
                sent_messages.append({'chat_id': chat_id, 'text': text})

        with patch('apps.medical.telegram_bot_service.TelegramBotService') as mocked_service:
            mocked_service.return_value._require_client.return_value = _Client()
            url = reverse('doctor_password_reset_request')
            response = self.client.post(
                url,
                {
                    'passport_id': 'AA-123 4567',
                    'birth_date': '2003-03-20',
                    'pinfl': '12345678901234',
                },
                format='json',
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body.get('expires_in'), 120)
        self.assertEqual(body.get('session_expires_in'), 3600)
        self.assertTrue(str(body.get('bot_link') or '').startswith('https://t.me/'))
        self.assertIn('debug_code', body)
        self.assertTrue(sent_messages)
        self.assertEqual(sent_messages[-1]['chat_id'], 700001)

    @override_settings(DEBUG=True)
    def test_request_without_linked_chat_returns_bot_link_and_creates_session(self):
        self.doctor.telegram_user_id = None
        self.doctor.telegram_chat_id = None
        self.doctor.save(update_fields=['telegram_user_id', 'telegram_chat_id', 'updated_at'])

        url = reverse('doctor_password_reset_request')
        response = self.client.post(
            url,
            {
                'passport_id': 'AA1234567',
                'birth_date': '2003-03-20',
                'pinfl': '12345678901234',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body.get('expires_in'), 120)
        self.assertEqual(body.get('session_expires_in'), 3600)
        self.assertIn('bot_note', body)
        self.assertTrue(str(body.get('bot_link') or '').startswith('https://t.me/'))

        session = DoctorResetTelegramSession.objects.filter(user=self.doctor_user).order_by('-created_at').first()
        self.assertIsNotNone(session)
        if session is None:
            self.fail('Doctor reset Telegram session was not created')
        self.assertIsNone(session.telegram_chat_id)

    @override_settings(DEBUG=True)
    def test_verify_and_confirm_updates_password_and_email(self):
        class _Client:
            def send_message(self, chat_id, text, reply_markup=None):
                return None

        with patch('apps.medical.telegram_bot_service.TelegramBotService') as mocked_service:
            mocked_service.return_value._require_client.return_value = _Client()
            request_url = reverse('doctor_password_reset_request')
            request_res = self.client.post(
                request_url,
                {
                    'passport_id': 'AA 1234567',
                    'birth_date': '20.03.2003',
                    'pinfl': '12345678901234',
                },
                format='json',
            )

        self.assertEqual(request_res.status_code, 200)
        code = request_res.json().get('debug_code')
        self.assertTrue(code)

        verify_url = reverse('doctor_password_reset_verify')
        verify_res = self.client.post(
            verify_url,
            {
                'passport_id': 'AA-123-4567',
                'birth_date': '2003-03-20',
                'pinfl': '12345678901234',
                'code': code,
            },
            format='json',
        )
        self.assertEqual(verify_res.status_code, 200)
        self.assertEqual(verify_res.json().get('expires_in'), 3600)
        token = verify_res.json().get('token')
        self.assertTrue(token)

        confirm_url = reverse('doctor_password_reset_confirm')
        confirm_res = self.client.post(
            confirm_url,
            {
                'token': token,
                'new_password': 'NewPass123!',
                'new_email': 'doctor_reset_new@gmail.com',
            },
            format='json',
        )
        self.assertEqual(confirm_res.status_code, 200)

        self.doctor_user.refresh_from_db()
        self.assertEqual(self.doctor_user.email, 'doctor_reset_new@gmail.com')
        self.assertTrue(self.doctor_user.check_password('NewPass123!'))


class ClinicOwnerPasswordResetFlowTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='clinic_owner_reset_2',
            email='clinic.owner.reset@example.com',
            password='OwnerPass123!',
            role='clinic',
            first_name='Clinic',
            last_name='Owner2',
            phone_number='+998901112233',
        )
        self.clinic = Clinic.objects.create(
            owner=self.owner,
            owner_passport_id='AA5566778',
            name='Clinic Owner Reset',
            slug='clinic-owner-reset',
            address='Reset avenue 10',
            phone_number='+998901010101',
            email='clinic.owner.reset@clinic.example.com',
            registration_number='CLN-RESET-001',
            status='active',
        )

    @override_settings(DEBUG=True)
    def test_request_without_linked_chat_returns_bot_link_and_creates_session(self):
        url = reverse('clinic_password_reset_request')
        response = self.client.post(
            url,
            {
                'clinic_number': 'CLN-RESET-001',
                'passport_id': 'AA5566778',
                'phone_number': '+998901112233',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body.get('expires_in'), 120)
        self.assertEqual(body.get('session_expires_in'), 3600)
        self.assertIn('bot_note', body)
        self.assertTrue(str(body.get('bot_link') or '').startswith('https://t.me/'))

        session = ClinicResetTelegramSession.objects.filter(user=self.owner).order_by('-created_at').first()
        self.assertIsNotNone(session)
        if session is None:
            self.fail('Clinic reset Telegram session was not created')
        self.assertIsNone(session.telegram_chat_id)

    @override_settings(DEBUG=True)
    def test_request_with_linked_chat_sends_code(self):
        sent_messages = []

        ClinicResetTelegramSession.objects.create(
            user=self.owner,
            clinic=self.clinic,
            telegram_user_id=610001,
            telegram_chat_id=710001,
            linked_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=1),
        )

        class _Client:
            def send_message(self, chat_id, text, reply_markup=None):
                sent_messages.append({'chat_id': chat_id, 'text': text})

        with patch('apps.medical.telegram_bot_service.TelegramBotService') as mocked_service:
            mocked_service.return_value._require_client.return_value = _Client()
            url = reverse('clinic_password_reset_request')
            response = self.client.post(
                url,
                {
                    'clinic_number': 'CLN-RESET-001',
                    'passport_id': 'AA5566778',
                    'phone_number': '+998901112233',
                },
                format='json',
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn('debug_code', body)
        self.assertTrue(sent_messages)
        self.assertEqual(sent_messages[-1]['chat_id'], 710001)

    @override_settings(DEBUG=True)
    def test_verify_and_confirm_updates_password_and_email(self):
        class _Client:
            def send_message(self, chat_id, text, reply_markup=None):
                return None

        with patch('apps.medical.telegram_bot_service.TelegramBotService') as mocked_service:
            mocked_service.return_value._require_client.return_value = _Client()
            request_url = reverse('clinic_password_reset_request')
            request_res = self.client.post(
                request_url,
                {
                    'clinic_number': 'CLN-RESET-001',
                    'passport_id': 'AA5566778',
                    'phone_number': '+998901112233',
                },
                format='json',
            )

        self.assertEqual(request_res.status_code, 200)
        code = request_res.json().get('debug_code')
        self.assertTrue(code)

        verify_url = reverse('clinic_password_reset_verify')
        verify_res = self.client.post(
            verify_url,
            {
                'clinic_number': 'CLN-RESET-001',
                'passport_id': 'AA5566778',
                'phone_number': '+998901112233',
                'code': code,
            },
            format='json',
        )
        self.assertEqual(verify_res.status_code, 200)
        self.assertEqual(verify_res.json().get('expires_in'), 3600)
        token = verify_res.json().get('token')
        self.assertTrue(token)

        confirm_url = reverse('clinic_password_reset_confirm')
        confirm_res = self.client.post(
            confirm_url,
            {
                'token': token,
                'new_password': 'OwnerNewPass123!',
                'new_email': 'clinic.owner.updated@gmail.com',
            },
            format='json',
        )
        self.assertEqual(confirm_res.status_code, 200)

        self.owner.refresh_from_db()
        self.assertEqual(self.owner.email, 'clinic.owner.updated@gmail.com')
        self.assertTrue(self.owner.check_password('OwnerNewPass123!'))


class PatientPasswordResetFlowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='patient_reset_user',
            email='patient.reset@example.com',
            password='PatientOld123!',
            role='patient',
            first_name='Reset',
            last_name='Patient',
            phone_number='+998901234560',
        )
        self.patient = Patient.objects.create(
            user=self.user,
            phone_number='+998901234560',
            is_active=True,
        )

    @override_settings(DEBUG=True)
    def test_request_without_linked_chat_returns_bot_link_and_creates_session(self):
        url = reverse('password_reset_request')
        response = self.client.post(
            url,
            {
                'phone_number': '+998901234560',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body.get('expires_in'), 120)
        self.assertEqual(body.get('session_expires_in'), 3600)
        self.assertIn('bot_note', body)
        self.assertTrue(str(body.get('bot_link') or '').startswith('https://t.me/'))

        session = PatientResetTelegramSession.objects.filter(user=self.user).order_by('-created_at').first()
        self.assertIsNotNone(session)
        if session is None:
            self.fail('Patient reset Telegram session was not created')
        self.assertIsNone(session.telegram_chat_id)

    @override_settings(DEBUG=True)
    def test_request_with_linked_chat_sends_code(self):
        sent_messages = []

        PatientResetTelegramSession.objects.create(
            user=self.user,
            patient=self.patient,
            telegram_user_id=620001,
            telegram_chat_id=720001,
            linked_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=1),
        )

        class _Client:
            def send_message(self, chat_id, text, reply_markup=None):
                sent_messages.append({'chat_id': chat_id, 'text': text})

        with patch('apps.medical.telegram_bot_service.TelegramBotService') as mocked_service:
            mocked_service.return_value._require_client.return_value = _Client()
            url = reverse('password_reset_request')
            response = self.client.post(
                url,
                {
                    'phone_number': '+998901234560',
                },
                format='json',
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn('debug_code', body)
        self.assertTrue(sent_messages)
        self.assertEqual(sent_messages[-1]['chat_id'], 720001)

    @override_settings(DEBUG=True)
    def test_verify_and_confirm_updates_password(self):
        class _Client:
            def send_message(self, chat_id, text, reply_markup=None):
                return None

        with patch('apps.medical.telegram_bot_service.TelegramBotService') as mocked_service:
            mocked_service.return_value._require_client.return_value = _Client()
            request_url = reverse('password_reset_request')
            request_res = self.client.post(
                request_url,
                {
                    'phone_number': '+998901234560',
                },
                format='json',
            )

        self.assertEqual(request_res.status_code, 200)
        code = request_res.json().get('debug_code')
        self.assertTrue(code)

        verify_url = reverse('password_reset_verify')
        verify_res = self.client.post(
            verify_url,
            {
                'phone_number': '+998901234560',
                'code': code,
            },
            format='json',
        )
        self.assertEqual(verify_res.status_code, 200)
        self.assertEqual(verify_res.json().get('expires_in'), 3600)
        token = verify_res.json().get('token')
        self.assertTrue(token)

        confirm_url = reverse('password_reset_confirm')
        confirm_res = self.client.post(
            confirm_url,
            {
                'token': token,
                'new_password': 'PatientNew123!',
            },
            format='json',
        )
        self.assertEqual(confirm_res.status_code, 200)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('PatientNew123!'))


class PharmacyOwnerPasswordResetFlowTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='pharmacy_owner_reset_1',
            email='pharmacy.owner.reset@example.com',
            password='PharmacyOldPass123!',
            role='pharmacy',
            first_name='Pharmacy',
            last_name='Owner',
            phone_number='+998909001122',
        )
        self.pharmacy = Pharmacy.objects.create(
            owner=self.owner,
            owner_passport_id='AA6677889',
            name='Pharmacy Owner Reset',
            slug='pharmacy-owner-reset',
            address='Reset avenue 77',
            phone_number='+998909001122',
            email='pharmacy.owner.reset@pharmacy.example.com',
            registration_number='PHR-RESET-001',
            status='active',
        )

    @override_settings(DEBUG=True)
    def test_request_without_linked_chat_returns_bot_link_and_creates_session(self):
        url = reverse('pharmacy_password_reset_request')
        response = self.client.post(
            url,
            {
                'pharmacy_number': 'PHR-RESET-001',
                'passport_id': 'AA6677889',
                'phone_number': '+998909001122',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body.get('expires_in'), 120)
        self.assertEqual(body.get('session_expires_in'), 3600)
        self.assertIn('bot_note', body)
        self.assertTrue(str(body.get('bot_link') or '').startswith('https://t.me/'))

        session = PharmacyResetTelegramSession.objects.filter(user=self.owner).order_by('-created_at').first()
        self.assertIsNotNone(session)
        if session is None:
            self.fail('Pharmacy reset Telegram session was not created')
        self.assertIsNone(session.telegram_chat_id)

    @override_settings(DEBUG=True)
    def test_request_with_linked_chat_sends_code(self):
        sent_messages = []

        PharmacyResetTelegramSession.objects.create(
            user=self.owner,
            pharmacy=self.pharmacy,
            telegram_user_id=630001,
            telegram_chat_id=730001,
            linked_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=1),
        )

        class _Client:
            def send_message(self, chat_id, text, reply_markup=None):
                sent_messages.append({'chat_id': chat_id, 'text': text})

        with patch('apps.medical.telegram_bot_service.TelegramBotService') as mocked_service:
            mocked_service.return_value._require_client.return_value = _Client()
            url = reverse('pharmacy_password_reset_request')
            response = self.client.post(
                url,
                {
                    'pharmacy_number': 'PHR-RESET-001',
                    'passport_id': 'AA6677889',
                    'phone_number': '+998909001122',
                },
                format='json',
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn('debug_code', body)
        self.assertTrue(sent_messages)
        self.assertEqual(sent_messages[-1]['chat_id'], 730001)

    @override_settings(DEBUG=True)
    def test_verify_and_confirm_updates_password_and_email(self):
        class _Client:
            def send_message(self, chat_id, text, reply_markup=None):
                return None

        with patch('apps.medical.telegram_bot_service.TelegramBotService') as mocked_service:
            mocked_service.return_value._require_client.return_value = _Client()
            request_url = reverse('pharmacy_password_reset_request')
            request_res = self.client.post(
                request_url,
                {
                    'pharmacy_number': 'PHR-RESET-001',
                    'passport_id': 'AA6677889',
                    'phone_number': '+998909001122',
                },
                format='json',
            )

        self.assertEqual(request_res.status_code, 200)
        code = request_res.json().get('debug_code')
        self.assertTrue(code)

        verify_url = reverse('pharmacy_password_reset_verify')
        verify_res = self.client.post(
            verify_url,
            {
                'pharmacy_number': 'PHR-RESET-001',
                'passport_id': 'AA6677889',
                'phone_number': '+998909001122',
                'code': code,
            },
            format='json',
        )
        self.assertEqual(verify_res.status_code, 200)
        self.assertEqual(verify_res.json().get('expires_in'), 3600)
        token = verify_res.json().get('token')
        self.assertTrue(token)

        confirm_url = reverse('pharmacy_password_reset_confirm')
        confirm_res = self.client.post(
            confirm_url,
            {
                'token': token,
                'new_password': 'PharmacyNewPass123!',
                'new_email': 'pharmacy.owner.updated@gmail.com',
            },
            format='json',
        )
        self.assertEqual(confirm_res.status_code, 200)

        self.owner.refresh_from_db()
        self.assertEqual(self.owner.email, 'pharmacy.owner.updated@gmail.com')
        self.assertTrue(self.owner.check_password('PharmacyNewPass123!'))
