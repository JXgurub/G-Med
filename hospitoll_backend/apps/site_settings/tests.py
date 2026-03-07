from typing import Any, cast

from rest_framework.test import APITestCase
from django.urls import reverse

from apps.users.models import CustomUser
from apps.site_settings.models import SystemAlert
from core.error_logging import ErrorLogger


class SiteSettingsSystemAlertTests(APITestCase):
    def auth_as(self, user: CustomUser) -> None:
        cast(Any, self.client).force_authenticate(user=user)

    def setUp(self):
        self.admin_user = CustomUser.objects.create_user(
            username='admin_system_alerts',
            email='admin.alerts@example.com',
            password='Pass12345!',
            role='admin',
            first_name='Admin',
            last_name='Alerts',
        )
        self.doctor_user = CustomUser.objects.create_user(
            username='doctor_system_alerts',
            email='doctor.alerts@example.com',
            password='Pass12345!',
            role='doctor',
            first_name='Doctor',
            last_name='Alerts',
        )

    def test_error_logger_persists_system_alert(self):
        ErrorLogger.log_error(
            error_type='unit_test_alert',
            message='System alert persistence test',
            context={'source': 'test'},
            severity='error',
        )
        self.assertTrue(SystemAlert.objects.filter(alert_type='unit_test_alert').exists())

    def test_admin_can_list_and_resolve_system_alert(self):
        alert = SystemAlert.objects.create(
            alert_type='manual_test_alert',
            message='Manual alert',
            severity='warning',
            context={'a': 1},
        )

        self.auth_as(self.admin_user)
        list_url = reverse('system-alerts-admin-list')
        list_response = self.client.get(list_url, {'unresolved_only': 'true'})

        self.assertEqual(list_response.status_code, 200)
        payload = list_response.json()
        self.assertTrue(any(item['id'] == str(alert.id) for item in payload))

        resolve_url = reverse('system-alerts-resolve', args=[alert.id])
        resolve_response = self.client.patch(resolve_url, {}, format='json')
        self.assertEqual(resolve_response.status_code, 200)

        alert.refresh_from_db()
        self.assertTrue(alert.is_resolved)
        self.assertIsNotNone(alert.resolved_by)
        if alert.resolved_by is not None:
            self.assertEqual(alert.resolved_by.id, self.admin_user.id)

    def test_non_admin_cannot_access_system_alert_endpoints(self):
        alert = SystemAlert.objects.create(
            alert_type='manual_test_alert_2',
            message='Manual alert 2',
            severity='error',
            context={},
        )

        self.auth_as(self.doctor_user)
        list_url = reverse('system-alerts-admin-list')
        list_response = self.client.get(list_url)
        self.assertEqual(list_response.status_code, 403)

        resolve_url = reverse('system-alerts-resolve', args=[alert.id])
        resolve_response = self.client.patch(resolve_url, {}, format='json')
        self.assertEqual(resolve_response.status_code, 403)

    def test_client_alert_suppresses_expected_permission_noise(self):
        url = reverse('system-alerts-client-create')
        before_count = SystemAlert.objects.count()

        payload = {
            'alert_type': 'frontend_api_error',
            'message': 'You do not have permission to perform this action.',
            'severity': 'warning',
            'context': {
                'endpoint': '/site-settings/contact-leads/admin/?limit=100',
                'status': 403,
                'method': 'GET',
            },
        }

        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.json().get('suppressed'))
        self.assertEqual(SystemAlert.objects.count(), before_count)

    def test_client_alert_persists_unexpected_frontend_error(self):
        url = reverse('system-alerts-client-create')

        payload = {
            'alert_type': 'frontend_api_error',
            'message': 'Unexpected server failure.',
            'severity': 'error',
            'context': {
                'endpoint': '/payments/payments/admin_create_subscription_payment/',
                'status': 500,
                'method': 'POST',
            },
        }

        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(SystemAlert.objects.filter(message='Unexpected server failure.').exists())
