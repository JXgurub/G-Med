from django.core import signing
from django.test import TestCase
from django.urls import reverse

from apps.clinics.models import Clinic, ClinicDepartment, ReceptionStaff
from apps.printers.models import PrinterDevice, PrintJob
from apps.users.models import CustomUser


class PrinterRegistrationAndRetryTests(TestCase):
    def setUp(self):
        self.owner = CustomUser.objects.create_user(
            username='printer_owner',
            email='owner@example.com',
            password='Pass12345!',
            role='clinic',
            first_name='Owner',
            last_name='Clinic',
        )
        self.clinic = Clinic.objects.create(
            owner=self.owner,
            name='Printer Clinic',
            slug='printer-clinic',
            address='Street 1',
            phone_number='+998901234567',
            email='clinic@example.com',
            registration_number='REG-PRINTER-001',
            status='active',
        )
        self.department = ClinicDepartment.objects.create(
            clinic=self.clinic,
            name='Qabulxona',
        )

    def test_register_device_creates_unique_token_for_clinic_room(self):
        self.client.force_login(self.owner)
        url = reverse('printer-device-register')
        response = self.client.post(url, {
            'clinic_id': str(self.clinic.id),
            'reception_room_id': str(self.department.id),
            'device_name': 'Windows clinic PC 01',
        }, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        self.assertIn('device_token', response.json())
        self.assertTrue(response.json()['device_token'])
        self.assertEqual(PrinterDevice.objects.filter(clinic=self.clinic, reception_room=self.department).count(), 1)

    def test_failed_print_job_can_be_retried(self):
        self.client.force_login(self.owner)
        device = PrinterDevice.objects.create(
            clinic=self.clinic,
            reception_room=self.department,
            device_name='Windows clinic PC 02',
            device_token='retry-token-123',
            status='offline',
        )
        job = PrintJob.objects.create(
            clinic=self.clinic,
            reception_room=self.department,
            printer_device=device,
            status='failed',
            error_message='Printer disconnected',
            payload={'lines': ['FAIL']},
        )

        url = reverse('print-job-retry', args=[job.id])
        response = self.client.post(url, {}, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.status, 'pending')
        self.assertEqual(job.error_message, '')

    def test_test_print_accepts_reception_session_token(self):
        staff = ReceptionStaff.objects.create(
            clinic=self.clinic,
            pinfl='12345678901234',
            passport_id='AA1234567',
            date_of_birth='1990-01-01',
            first_name='Salim',
            last_name='Bek',
            phone_number='+998901234567',
            email='reception@example.com',
            password_hash='pbkdf2_sha256$dummy$dummy',
            is_active=True,
        )
        device = PrinterDevice.objects.create(
            clinic=self.clinic,
            reception_room=self.department,
            device_name='Windows clinic PC 03',
            device_token='session-test-token',
            status='ready',
        )
        token = signing.dumps({'staff_id': str(staff.id), 'clinic_id': str(self.clinic.id)}, salt='reception-staff-session')

        url = reverse('print-job-test-print')
        response = self.client.post(url, {}, HTTP_X_RECEPTION_SESSION=token)

        self.assertEqual(response.status_code, 200)
        self.assertIn('job_id', response.json())
        self.assertEqual(PrintJob.objects.filter(clinic=self.clinic, printer_device=device).count(), 1)

    def test_legacy_printer_root_routes_still_work(self):
        self.client.force_login(self.owner)

        register_response = self.client.post('/api/v1/printers/register/', {
            'clinic_id': str(self.clinic.id),
            'reception_room_id': str(self.department.id),
            'device_name': 'Legacy clinic PC',
        }, content_type='application/json')
        self.assertEqual(register_response.status_code, 200)
        self.assertIn('device_token', register_response.json())

        status_response = self.client.get('/api/v1/printers/my-status/', {
            'clinic_id': str(self.clinic.id),
        })
        self.assertEqual(status_response.status_code, 200)
        self.assertIn('devices', status_response.json())

    def test_status_update_allows_device_token_without_user_auth(self):
        device = PrinterDevice.objects.create(
            clinic=self.clinic,
            reception_room=self.department,
            device_name='Windows clinic PC 04',
            device_token='status-token-123',
            status='ready',
        )
        job = PrintJob.objects.create(
            clinic=self.clinic,
            reception_room=self.department,
            printer_device=device,
            status='pending',
            payload={'lines': ['TEST']},
        )

        url = reverse('print-job-status-update', args=[job.id])
        response = self.client.patch(
            url,
            {'status': 'completed', 'device_id': device.device_token},
            content_type='application/json',
            HTTP_X_DEVICE_TOKEN=device.device_token,
        )

        self.assertEqual(response.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.status, 'completed')
        self.assertEqual(job.printer_device_id, device.id)
        self.assertIsNotNone(job.printed_at)

    def test_status_update_rejects_wrong_device_clinic(self):
        other_owner = CustomUser.objects.create_user(
            username='other_printer_owner',
            email='other-owner@example.com',
            password='Pass12345!',
            role='clinic',
            first_name='Other',
            last_name='Clinic',
        )
        other_clinic = Clinic.objects.create(
            owner=other_owner,
            name='Other Printer Clinic',
            slug='other-printer-clinic',
            address='Street 2',
            phone_number='+998909876543',
            email='other-clinic@example.com',
            registration_number='REG-PRINTER-002',
            status='active',
        )
        foreign_device = PrinterDevice.objects.create(
            clinic=other_clinic,
            device_name='Foreign device',
            device_token='foreign-status-token',
            status='ready',
        )
        job = PrintJob.objects.create(
            clinic=self.clinic,
            reception_room=self.department,
            status='pending',
            payload={'lines': ['TEST']},
        )

        url = reverse('print-job-status-update', args=[job.id])
        response = self.client.patch(
            url,
            {'status': 'completed', 'device_id': foreign_device.device_token},
            content_type='application/json',
            HTTP_X_DEVICE_TOKEN=foreign_device.device_token,
        )

        self.assertEqual(response.status_code, 403)
        job.refresh_from_db()
        self.assertEqual(job.status, 'pending')

    def test_status_update_accepts_null_error_message_for_printing(self):
        device = PrinterDevice.objects.create(
            clinic=self.clinic,
            reception_room=self.department,
            device_name='Windows clinic PC 05',
            device_token='status-token-null-error',
            status='ready',
        )
        job = PrintJob.objects.create(
            clinic=self.clinic,
            reception_room=self.department,
            printer_device=device,
            status='pending',
            payload={'lines': ['TEST']},
        )

        url = reverse('print-job-status-update', args=[job.id])
        response = self.client.patch(
            url,
            {'status': 'printing', 'error_message': None, 'device_id': device.device_token},
            content_type='application/json',
            HTTP_X_DEVICE_TOKEN=device.device_token,
        )

        self.assertEqual(response.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.status, 'printing')
