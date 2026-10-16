from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.printers.models import PrinterDevice, PrintJob
from apps.users.models import CustomUser
from .serializers import PharmacySerializer
from .models import (
    Medicine,
    Pharmacy,
    PharmacyMarchandise,
    PharmacyPosDevice,
    PharmacySale,
    PharmacySaleLine,
)


class PharmacyPublicInventorySerializationTests(TestCase):
    def setUp(self):
        owner = CustomUser.objects.create_user(
            username='public-pharmacy',
            email='public-pharmacy@example.com',
            password='Pass12345!',
            role='pharmacy',
        )
        self.pharmacy = Pharmacy.objects.create(
            owner=owner,
            name='Public Pharmacy',
            slug='public-pharmacy',
            registration_number='PUBLIC-REG-001',
            address='Street 1',
            phone_number='+998901234567',
            email='public@example.com',
            status='active',
        )

    def test_public_medicine_list_exposes_generic_name_and_only_current_stock(self):
        today = timezone.localdate()
        available = Medicine.objects.create(name='Glyukofaj', generic_name='Metformin', strength='500 mg')
        zero_stock = Medicine.objects.create(name='Metformin zero')
        expired = Medicine.objects.create(name='Metformin expired')
        PharmacyMarchandise.objects.create(
            pharmacy=self.pharmacy,
            medicine=available,
            batch_number='available',
            expiry_date=today + timedelta(days=30),
            quantity_in_stock=4,
            unit_price=Decimal('12000.00'),
        )
        PharmacyMarchandise.objects.create(
            pharmacy=self.pharmacy,
            medicine=zero_stock,
            batch_number='zero-stock',
            expiry_date=today + timedelta(days=30),
            quantity_in_stock=0,
            unit_price=Decimal('10000.00'),
        )
        PharmacyMarchandise.objects.create(
            pharmacy=self.pharmacy,
            medicine=expired,
            batch_number='expired',
            expiry_date=today - timedelta(days=1),
            quantity_in_stock=5,
            unit_price=Decimal('10000.00'),
        )

        medicines = PharmacySerializer(self.pharmacy).data['medicines']

        self.assertEqual(len(medicines), 1)
        self.assertEqual(medicines[0]['name'], 'Glyukofaj')
        self.assertEqual(medicines[0]['generic_name'], 'Metformin')
        self.assertEqual(medicines[0]['stock'], 4)


class PharmacyOfflinePosTests(TestCase):
    def setUp(self):
        self.owner = CustomUser.objects.create_user(
            username='pos-owner',
            email='pos-owner@example.com',
            password='Pass12345!',
            role='pharmacy',
        )
        self.pharmacy = Pharmacy.objects.create(
            owner=self.owner,
            name='Offline Pharmacy',
            slug='offline-pharmacy',
            registration_number='POS-REG-001',
            address='Street 1',
            phone_number='+998901234567',
            email='offline@example.com',
            status='active',
        )
        self.medicine = Medicine.objects.create(name='Test medicine')
        self.inventory = PharmacyMarchandise.objects.create(
            pharmacy=self.pharmacy,
            medicine=self.medicine,
            batch_number='POS-BATCH-001',
            expiry_date='2027-12-31',
            quantity_in_stock=5,
            unit_price=Decimal('10.00'),
        )
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.device_url = reverse('pharmacy-pos-devices')

    def register_device(self, name='Kassa 1'):
        create_response = self.client.post(self.device_url, {'name': name}, format='json')
        self.assertEqual(create_response.status_code, 201)
        activation_response = self.client.post(
            reverse('pharmacy-pos-activate-device'),
            {
                'activation_code': create_response.data['activation_code'],
                'client_id': str(uuid4()),
                'name': name,
            },
            format='json',
        )
        self.assertEqual(activation_response.status_code, 200)
        return activation_response.data['client_id']

    def sale_payload(self, client_id, quantity, sale_id=None):
        return {
            'id': str(sale_id or uuid4()),
            'client_id': client_id,
            'sold_at': timezone.now().isoformat(),
            'total': str(quantity * 10),
            'lines': [{
                'inventory_id': str(self.inventory.id),
                'medicine_id': str(self.medicine.id),
                'medicine_name': self.medicine.name,
                'quantity': quantity,
                'cached_stock_before_sale': self.inventory.quantity_in_stock,
                'unit_price': '10',
                'line_total': str(quantity * 10),
            }],
        }

    def test_owner_can_generate_and_activate_cashier_device(self):
        create_response = self.client.post(self.device_url, {'name': 'Kassa 2'}, format='json')
        self.assertEqual(create_response.status_code, 201)
        self.assertTrue(create_response.data['activation_code'])
        self.assertEqual(len(create_response.data['activation_code']), 12)

        client_id = str(uuid4())
        activation_response = self.client.post(
            reverse('pharmacy-pos-activate-device'),
            {
                'activation_code': create_response.data['activation_code'],
                'client_id': client_id,
                'name': 'Kassa 2',
            },
            format='json',
        )
        self.assertEqual(activation_response.status_code, 200)
        self.assertTrue(activation_response.data['is_active'])
        self.assertEqual(PharmacyPosDevice.objects.filter(pharmacy=self.pharmacy, is_active=True).count(), 1)

    def test_sale_sync_is_idempotent_and_decrements_stock_once(self):
        client_id = self.register_device()
        sale_id = uuid4()
        payload = self.sale_payload(client_id, 2, sale_id)
        url = reverse('pharmacy-pos-sync-sale')

        first_response = self.client.post(url, payload, format='json')
        retry_response = self.client.post(url, payload, format='json')

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(retry_response.status_code, 200)
        self.assertTrue(retry_response.data['already_synced'])
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity_in_stock, 3)
        self.assertEqual(PharmacySale.objects.count(), 1)
        self.assertEqual(PharmacySaleLine.objects.get().quantity, 2)

    def test_pharmacy_printer_registration_is_scoped_to_active_pos_device(self):
        client_id = self.register_device()
        url = reverse('pharmacy-pos-printer')

        first_response = self.client.post(url, {'client_id': client_id}, format='json')
        retry_response = self.client.post(url, {'client_id': client_id}, format='json')

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(retry_response.status_code, 200)
        self.assertEqual(first_response.data['device_token'], retry_response.data['device_token'])
        printer = PrinterDevice.objects.get(pos_device__client_id=client_id)
        self.assertIsNone(printer.clinic)
        self.assertEqual(printer.pharmacy, self.pharmacy)

        status_response = self.client.get(url, {'client_id': client_id})
        self.assertEqual(status_response.status_code, 200)
        self.assertFalse(status_response.data['device']['printer_ready'])

    def test_windows_printer_registration_uses_pharmacy_owner_login_and_is_idempotent(self):
        url = reverse('pharmacy-printer-service-register')

        first_response = self.client.post(
            url,
            {'device_name': 'Windows Dorixona Printeri'},
            format='json',
        )
        retry_response = self.client.post(
            url,
            {'device_name': 'Windows Dorixona Printeri'},
            format='json',
        )

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(retry_response.status_code, 200)
        self.assertEqual(first_response.data['device_token'], retry_response.data['device_token'])
        printer = PrinterDevice.objects.get(device_token=first_response.data['device_token'])
        self.assertEqual(printer.pharmacy, self.pharmacy)
        self.assertIsNone(printer.clinic)
        self.assertIsNone(printer.pos_device)

    def test_windows_printer_registration_rejects_non_pharmacy_accounts(self):
        doctor = CustomUser.objects.create_user(
            username='printer-installer-doctor',
            email='installer-doctor@example.com',
            password='Pass12345!',
            role='doctor',
        )
        self.client.force_authenticate(doctor)

        response = self.client.post(
            reverse('pharmacy-printer-service-register'),
            {'device_name': 'Unauthorized Printer'},
            format='json',
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(PrinterDevice.objects.exists())

    def test_windows_printer_can_print_sales_from_registered_cashiers(self):
        client_id = self.register_device()
        sale_response = self.client.post(
            reverse('pharmacy-pos-sync-sale'),
            self.sale_payload(client_id, 2),
            format='json',
        )
        printer_response = self.client.post(
            reverse('pharmacy-printer-service-register'),
            {'device_name': 'Windows Dorixona Printeri'},
            format='json',
        )
        printer = PrinterDevice.objects.get(pk=printer_response.data['device_id'])
        printer.status = 'ready'
        printer.last_seen = timezone.now()
        printer.save(update_fields=['status', 'last_seen'])
        printer_status = self.client.get(
            reverse('pharmacy-pos-printer'),
            {'client_id': str(uuid4())},
        )
        self.assertEqual(printer_status.status_code, 200)
        self.assertEqual(printer_status.data['device']['id'], str(printer.id))

        print_response = self.client.post(
            reverse('pharmacy-pos-print-sale'),
            {'sale_id': sale_response.data['id'], 'client_id': client_id},
            format='json',
        )

        self.assertEqual(print_response.status_code, 201)
        print_job = PrintJob.objects.get(sale_id=sale_response.data['id'])
        self.assertEqual(print_job.printer_device, printer)
        printer_jobs = self.client.get(
            reverse('print-job-pending'),
            {
                'device_token': printer.device_token,
                'pharmacy_id': str(self.pharmacy.id),
            },
        )
        self.assertEqual([job['id'] for job in printer_jobs.data['jobs']], [str(print_job.id)])

    def test_pharmacy_owner_receipt_settings_are_saved_and_used_in_print_job(self):
        client_id = self.register_device()
        sale_response = self.client.post(
            reverse('pharmacy-pos-sync-sale'),
            self.sale_payload(client_id, 2),
            format='json',
        )
        update_response = self.client.patch(
            reverse('pharmacy-detail', args=[self.pharmacy.id]),
            {
                'receipt_show_address': False,
                'receipt_show_phone': False,
                'receipt_show_website': True,
                'website': 'https://example.uz',
                'receipt_instagram_url': '@offline_pharmacy',
                'receipt_show_instagram': True,
            },
            format='json',
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertTrue(update_response.data['receipt_show_website'])
        self.assertTrue(update_response.data['receipt_show_instagram'])

        printer_response = self.client.post(
            reverse('pharmacy-printer-service-register'),
            {'device_name': 'Receipt Settings Printer'},
            format='json',
        )
        printer = PrinterDevice.objects.get(pk=printer_response.data['device_id'])
        printer.status = 'ready'
        printer.last_seen = timezone.now()
        printer.save(update_fields=['status', 'last_seen'])
        print_response = self.client.post(
            reverse('pharmacy-pos-print-sale'),
            {'sale_id': sale_response.data['id'], 'client_id': client_id},
            format='json',
        )

        self.assertEqual(print_response.status_code, 201)
        job = PrintJob.objects.get(sale_id=sale_response.data['id'])
        receipt_text = '\n'.join(job.payload['lines'])
        self.assertNotIn('Manzil:', receipt_text)
        self.assertNotIn('Telefon:', receipt_text)
        self.assertIn('Sayt: https://example.uz', receipt_text)
        self.assertIn('Instagram: @offline_pharmacy', receipt_text)

    def test_synced_sale_is_queued_once_for_ready_pharmacy_printer(self):
        client_id = self.register_device()
        sale_payload = self.sale_payload(client_id, 2)
        sale_response = self.client.post(
            reverse('pharmacy-pos-sync-sale'),
            sale_payload,
            format='json',
        )
        printer_response = self.client.post(
            reverse('pharmacy-pos-printer'),
            {'client_id': client_id},
            format='json',
        )
        printer = PrinterDevice.objects.get(pk=printer_response.data['device_id'])
        print_url = reverse('pharmacy-pos-print-sale')
        print_payload = {'sale_id': sale_response.data['id'], 'client_id': client_id}

        unavailable_response = self.client.post(print_url, print_payload, format='json')
        self.assertEqual(unavailable_response.status_code, 409)
        self.assertFalse(PrintJob.objects.filter(sale_id=sale_response.data['id']).exists())

        wrong_pharmacy_heartbeat = self.client.post(
            reverse('printer-heartbeat'),
            {
                'device_id': printer.device_token,
                'pharmacy_id': str(uuid4()),
                'printer_connected': True,
                'printer_status': 'ready',
            },
            format='json',
        )
        self.assertEqual(wrong_pharmacy_heartbeat.status_code, 403)
        heartbeat_response = self.client.post(
            reverse('printer-heartbeat'),
            {
                'device_id': printer.device_token,
                'pharmacy_id': str(self.pharmacy.id),
                'printer_connected': True,
                'printer_status': 'ready',
            },
            format='json',
        )
        self.assertEqual(heartbeat_response.status_code, 200)
        self.assertEqual(heartbeat_response.data['status'], 'ready')

        first_response = self.client.post(print_url, print_payload, format='json')
        retry_response = self.client.post(print_url, print_payload, format='json')

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(retry_response.status_code, 200)
        self.assertEqual(first_response.data['job_id'], retry_response.data['job_id'])
        job = PrintJob.objects.get(sale_id=sale_response.data['id'])
        self.assertEqual(job.pharmacy, self.pharmacy)
        self.assertIsNone(job.clinic)
        self.assertEqual(job.payload['receipt_type'], 'pharmacy')
        self.assertEqual(job.payload['receipt_width'], 32)
        self.assertTrue(all(len(line) <= 32 for line in job.payload['lines']))
        self.assertTrue(any('SOTUV CHEKI' in line for line in job.payload['lines']))
        self.assertEqual(PrintJob.objects.filter(sale_id=sale_response.data['id']).count(), 1)

        pending_response = self.client.get(reverse('print-job-pending'), {
            'device_token': printer.device_token,
            'pharmacy_id': str(self.pharmacy.id),
        })
        self.assertEqual(pending_response.status_code, 200)
        self.assertEqual([row['id'] for row in pending_response.data['jobs']], [str(job.id)])

        status_response = self.client.patch(
            reverse('print-job-status-update', args=[job.id]),
            {
                'status': 'completed',
                'device_id': printer.device_token,
                'pharmacy_id': str(self.pharmacy.id),
            },
            format='json',
            HTTP_X_DEVICE_TOKEN=printer.device_token,
        )
        self.assertEqual(status_response.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.status, 'completed')

    def test_offline_oversell_is_recorded_and_marked_as_discrepancy(self):
        client_id = self.register_device()
        response = self.client.post(
            reverse('pharmacy-pos-sync-sale'),
            self.sale_payload(client_id, 7),
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['has_stock_discrepancy'])
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity_in_stock, 0)
        self.assertEqual(PharmacySaleLine.objects.get().stock_shortfall, 2)
        self.assertTrue(PharmacySaleLine.objects.get().stock_mismatch)

    def test_other_computer_stock_change_is_reported_without_overselling(self):
        first_client_id = self.register_device('Kassa 1')
        second_client_id = self.register_device('Kassa 2')
        sync_url = reverse('pharmacy-pos-sync-sale')

        first_sale = self.client.post(
            sync_url,
            self.sale_payload(first_client_id, 2),
            format='json',
        )
        second_sale = self.client.post(
            sync_url,
            self.sale_payload(second_client_id, 1),
            format='json',
        )

        self.assertEqual(first_sale.status_code, 201)
        self.assertFalse(first_sale.data['has_stock_discrepancy'])
        self.assertEqual(second_sale.status_code, 201)
        self.assertTrue(second_sale.data['has_stock_discrepancy'])
        second_line = PharmacySaleLine.objects.order_by('-id').first()
        self.assertEqual(second_line.stock_shortfall, 0)
        self.assertTrue(second_line.stock_mismatch)
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity_in_stock, 2)

    def test_invalid_sale_does_not_change_inventory(self):
        client_id = self.register_device()
        payload = self.sale_payload(client_id, 2)
        payload['total'] = '19'
        payload['lines'][0]['line_total'] = '20'

        response = self.client.post(reverse('pharmacy-pos-sync-sale'), payload, format='json')

        self.assertEqual(response.status_code, 400)
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity_in_stock, 5)
        self.assertEqual(PharmacySale.objects.count(), 0)

    def test_deactivated_terminal_cannot_sync_sales(self):
        client_id = self.register_device()
        device = PharmacyPosDevice.objects.get(client_id=client_id)
        self.client.delete(
            reverse('pharmacy-pos-device-detail', args=[device.id]),
            format='json',
        )

        response = self.client.post(
            reverse('pharmacy-pos-sync-sale'),
            self.sale_payload(client_id, 1),
            format='json',
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(PharmacySale.objects.count(), 0)

    def test_activation_code_expires(self):
        create_response = self.client.post(self.device_url, {'name': 'Expired terminal'}, format='json')
        device = PharmacyPosDevice.objects.get(pk=create_response.data['id'])
        device.activation_code_created_at = timezone.now() - timedelta(minutes=31)
        device.save(update_fields=['activation_code_created_at'])

        response = self.client.post(
            reverse('pharmacy-pos-activate-device'),
            {
                'activation_code': create_response.data['activation_code'],
                'client_id': str(uuid4()),
                'name': device.name,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        device.refresh_from_db()
        self.assertFalse(device.is_active)

    def test_snapshot_returns_local_pos_catalog_and_inventory(self):
        response = self.client.get(reverse('pharmacy-pos-snapshot'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['pharmacy']['id'], str(self.pharmacy.id))
        self.assertEqual(response.data['medicines'][0]['id'], str(self.medicine.id))
        self.assertEqual(response.data['inventory'][0]['quantity_in_stock'], 5)

    def test_inventory_list_for_pharmacy_owner_only_contains_their_pharmacy(self):
        other_owner = CustomUser.objects.create_user(
            username='other-pharmacy-owner',
            email='other-pharmacy-owner@example.com',
            password='Pass12345!',
            role='pharmacy',
        )
        other_pharmacy = Pharmacy.objects.create(
            owner=other_owner,
            name='Other Pharmacy',
            slug='other-pharmacy',
            registration_number='POS-REG-002',
            address='Street 2',
            phone_number='+998901234568',
            email='other@example.com',
            status='active',
        )
        other_inventory = PharmacyMarchandise.objects.create(
            pharmacy=other_pharmacy,
            medicine=Medicine.objects.create(name='Other pharmacy medicine'),
            batch_number='OTHER-BATCH-001',
            expiry_date='2028-12-31',
            quantity_in_stock=900,
            unit_price=Decimal('99.00'),
        )

        response = self.client.get(reverse('pharmacy-inventory-list'))

        self.assertEqual(response.status_code, 200)
        rows = response.data.get('results', response.data)
        self.assertEqual([row['id'] for row in rows], [self.inventory.id])
        self.assertNotIn(other_inventory.id, [row['id'] for row in rows])

        explicitly_filtered_response = self.client.get(
            reverse('pharmacy-inventory-list'),
            {'pharmacy': other_pharmacy.id},
        )
        explicitly_filtered_rows = explicitly_filtered_response.data.get(
            'results',
            explicitly_filtered_response.data,
        )
        self.assertEqual(explicitly_filtered_response.status_code, 200)
        self.assertEqual(explicitly_filtered_rows, [])
