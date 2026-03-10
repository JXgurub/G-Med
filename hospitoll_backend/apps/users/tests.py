from unittest.mock import patch
from datetime import date

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.clinics.models import Clinic
from apps.doctors.models import Doctor


User = get_user_model()


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
        self.assertIn('debug_code', body)
        self.assertTrue(sent_messages)
        self.assertEqual(sent_messages[-1]['chat_id'], 700001)

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
