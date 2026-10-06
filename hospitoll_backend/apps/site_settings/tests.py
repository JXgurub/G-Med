from typing import Any, cast
import json
from unittest.mock import patch

from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.users.models import CustomUser
from apps.site_settings.models import HomeContactSettings, SystemAlert
from apps.site_settings.models import BroadcastNotification, WebPushSubscription
from apps.site_settings.tasks import send_saved_broadcast_push
from core.error_logging import ErrorLogger
from apps.patients.models import Patient

PUBLIC_HOME_CONTACT_THROTTLE_SETTINGS = dict(settings.REST_FRAMEWORK)
PUBLIC_HOME_CONTACT_THROTTLE_SETTINGS['DEFAULT_THROTTLE_RATES'] = dict(
    settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {}),
    anon='1/hour',
    user='100/minute',
)


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

    def test_admin_can_view_broadcast_recipient_statistics(self):
        patient_user = CustomUser.objects.create_user(
            username='patient_broadcast_stats',
            email='patient.broadcast@example.com',
            password='Pass12345!',
            role='patient',
        )
        Patient.objects.create(user=patient_user, telegram_chat_id=445566)

        self.auth_as(self.admin_user)
        response = self.client.get(reverse('admin-broadcast'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'site_users': 2, 'telegram_users': 1, 'push_devices': 0})

    @patch('apps.medical.telegram_bot_service.TelegramBotService._require_client')
    @patch('core.websocket_service.WebSocketService.send_notification', return_value=True)
    def test_admin_can_send_broadcast_to_site_and_telegram(self, send_site, get_telegram_client):
        patient_user = CustomUser.objects.create_user(
            username='patient_broadcast_send',
            email='patient.broadcast.send@example.com',
            password='Pass12345!',
            role='patient',
        )
        Patient.objects.create(user=patient_user, telegram_chat_id=778899)
        telegram_client = get_telegram_client.return_value
        telegram_client.send_message.return_value = True

        self.auth_as(self.admin_user)
        response = self.client.post(reverse('admin-broadcast'), {
            'title': 'Muhim xabar',
            'message': 'Sayt yangilandi',
            'channels': ['site', 'telegram'],
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'site_sent': 2,
            'site_total': 2,
            'telegram_sent': 1,
            'telegram_total': 1,
            'push_queued': 0,
        })
        self.assertEqual(send_site.call_count, 2)
        telegram_client.send_message.assert_called_once()
        self.assertEqual(BroadcastNotification.objects.filter(user=patient_user).count(), 1)

    @patch('core.websocket_service.WebSocketService.send_notification', return_value=True)
    def test_saved_site_broadcast_is_available_until_recipient_reads_it(self, send_site):
        patient_user = CustomUser.objects.create_user(
            username='patient_broadcast_inbox',
            email='patient.broadcast.inbox@example.com',
            password='Pass12345!',
            role='patient',
        )
        self.auth_as(self.admin_user)
        send_response = self.client.post(reverse('admin-broadcast'), {
            'title': 'Sayt xabari',
            'message': 'Keyinroq ham ko‘rinadi',
            'channels': ['site'],
        }, format='json')
        self.assertEqual(send_response.status_code, 200)

        self.auth_as(patient_user)
        inbox_url = reverse('broadcast-inbox')
        inbox_response = self.client.get(inbox_url)
        self.assertEqual(inbox_response.status_code, 200)
        self.assertEqual(len(inbox_response.data), 1)
        notification_id = inbox_response.data[0]['id']

        read_response = self.client.patch(reverse('broadcast-inbox-read', args=[notification_id]), {}, format='json')
        self.assertEqual(read_response.status_code, 200)
        self.assertEqual(self.client.get(inbox_url).data, [])
        self.assertEqual(send_site.call_count, 2)

    @patch('pywebpush.webpush')
    @override_settings(WEB_PUSH_VAPID_PUBLIC_KEY='BElocal-test-key', WEB_PUSH_VAPID_PRIVATE_KEY_B64='dGVzdA==')
    def test_medication_push_contains_a_taken_action(self, webpush):
        notification = BroadcastNotification.objects.create(
            user=self.doctor_user,
            title='💊 Dori ichish vaqti',
            message='Alsetro',
            data={
                'notification_type': 'medication_reminder',
                'reminder_id': 42,
                'acknowledgement_token': 'b7b883a7-e1a5-4a85-a6e0-8837c4e133a1',
            },
        )
        WebPushSubscription.objects.create(
            user=self.doctor_user,
            endpoint='https://push.example.test/subscription/medication-action',
            p256dh='public-key',
            auth='auth-key',
        )

        result = send_saved_broadcast_push.run([str(notification.id)])
        payload = json.loads(webpush.call_args.kwargs['data'])

        self.assertEqual(result, {'sent': 1, 'failed': 0, 'expired': 0})
        self.assertEqual(payload['actions'], [{'action': 'taken', 'title': 'Ichdingizmi?'}])
        self.assertTrue(payload['renotify'])
        self.assertEqual(payload['tag'], 'medication-reminder-42')
        self.assertEqual(
            payload['data']['acknowledgement_token'],
            'b7b883a7-e1a5-4a85-a6e0-8837c4e133a1',
        )

    @override_settings(WEB_PUSH_VAPID_PUBLIC_KEY='BElocal-test-key', WEB_PUSH_VAPID_PRIVATE_KEY_B64='dGVzdA==')
    def test_user_can_register_a_web_push_subscription(self):
        self.auth_as(self.doctor_user)
        response = self.client.post(reverse('web-push-subscriptions'), {
            'subscription': {
                'endpoint': 'https://push.example.test/subscription/device-1',
                'keys': {'p256dh': 'public-key', 'auth': 'auth-key'},
            },
        }, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertTrue(WebPushSubscription.objects.filter(
            user=self.doctor_user,
            endpoint='https://push.example.test/subscription/device-1',
            is_active=True,
        ).exists())

    @override_settings(WEB_PUSH_VAPID_PUBLIC_KEY='BElocal-test-key', WEB_PUSH_VAPID_PRIVATE_KEY_B64='dGVzdA==')
    def test_push_config_exposes_only_public_key(self):
        response = self.client.get(reverse('web-push-config'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'enabled': True, 'public_key': 'BElocal-test-key'})

    @patch('apps.site_settings.tasks.send_saved_broadcast_push.delay')
    @patch('core.websocket_service.WebSocketService.send_notification', return_value=True)
    @override_settings(WEB_PUSH_VAPID_PUBLIC_KEY='BElocal-test-key', WEB_PUSH_VAPID_PRIVATE_KEY_B64='dGVzdA==')
    def test_site_broadcast_queues_push_for_subscribed_devices(self, send_site, queue_push):
        patient_user = CustomUser.objects.create_user(
            username='patient_broadcast_push',
            email='patient.broadcast.push@example.com',
            password='Pass12345!',
            role='patient',
        )
        WebPushSubscription.objects.create(
            user=patient_user,
            endpoint='https://push.example.test/subscription/device-2',
            p256dh='public-key',
            auth='auth-key',
        )
        self.auth_as(self.admin_user)

        response = self.client.post(reverse('admin-broadcast'), {
            'title': 'Push sinovi',
            'message': 'Telefon bildirishnomasi',
            'channels': ['site'],
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['push_queued'], 1)
        queue_push.assert_called_once()
        self.assertEqual(send_site.call_count, 2)

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

    @override_settings(REST_FRAMEWORK=PUBLIC_HOME_CONTACT_THROTTLE_SETTINGS)
    def test_home_contact_public_get_is_not_rate_limited(self):
        settings_obj = HomeContactSettings.get_solo()
        settings_obj.text = 'Home contact text'
        settings_obj.phone_number = '+998901234567'
        settings_obj.telegram_link = 'https://t.me/gmed'
        settings_obj.save(update_fields=['text', 'phone_number', 'telegram_link'])

        first_response = self.client.get(reverse('home-contact-settings'))
        second_response = self.client.get(reverse('home-contact-settings'))

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertIn('phone_number', second_response.json())
