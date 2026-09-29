from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import get_user_model
import hashlib
import logging



from .models import BroadcastNotification, ContactLead, HomeContactSettings, SystemAlert, WebPushSubscription
from .serializers import (
    ContactLeadAdminSerializer,
    ContactLeadCreateSerializer,
    HomeContactSettingsSerializer,
    SystemAlertAdminSerializer,
)
from apps.doctors.models import Doctor
from apps.medical.models import Appointment
from apps.patients.models import Patient


logger = logging.getLogger(__name__)


class IsAdministrator(BasePermission):
    # pyright: ignore[reportIncompatibleMethodOverride]
    def has_permission(self, request, view):  # type: ignore[override]
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        return bool(getattr(user, 'is_superuser', False) or getattr(user, 'is_administrator', False))


class HomeContactSettingsView(APIView):
    """Public GET for homepage; admin PATCH for updating the contact section."""

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated(), IsAdministrator()]

    def get_throttles(self):
        if self.request.method == 'GET':
            return []
        return super().get_throttles()

    def get(self, request):
        settings_obj = HomeContactSettings.get_solo()
        serializer = HomeContactSettingsSerializer(settings_obj, context={'request': request})
        return Response(serializer.data)

    def patch(self, request):
        settings_obj = HomeContactSettings.get_solo()
        serializer = HomeContactSettingsSerializer(
            settings_obj,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class ContactLeadCreateView(APIView):
    """Public lead capture (no auth)."""

    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

    def post(self, request):
        serializer = ContactLeadCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lead = serializer.save()  # pyright: ignore[reportGeneralTypeIssues]
        return Response(ContactLeadCreateSerializer(lead).data, status=status.HTTP_201_CREATED)


class ContactLeadAdminListView(APIView):
    """Admin can view contact leads."""

    permission_classes = [IsAuthenticated, IsAdministrator]

    def get(self, request):
        qs = ContactLead.objects.all().order_by('-created_at')
        unread_only = request.query_params.get('unread_only')
        if unread_only in ['1', 'true', 'True', 'yes']:
            qs = qs.filter(is_read=False)

        limit_param = request.query_params.get('limit')
        try:
            limit = int(limit_param) if limit_param else 50
        except ValueError:
            limit = 50
        limit = max(1, min(limit, 200))
        leads = list(qs[:limit])
        return Response(ContactLeadAdminSerializer(leads, many=True).data, status=status.HTTP_200_OK)


class ContactLeadMarkReadView(APIView):
    """Admin marks a lead as read."""

    permission_classes = [IsAuthenticated, IsAdministrator]

    def patch(self, request, pk):
        lead = ContactLead.objects.filter(pk=pk).first()
        if not lead:
            return Response({'detail': 'Xabar topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        if not lead.is_read:
            lead.is_read = True
            lead.read_at = timezone.now()
            lead.save(update_fields=['is_read', 'read_at'])

        return Response(ContactLeadAdminSerializer(lead).data, status=status.HTTP_200_OK)


class SystemAlertClientCreateView(APIView):
    """Frontend clients send runtime/API errors here for admin visibility."""

    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

    @staticmethod
    def _get_client_ip(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    @staticmethod
    def _normalize_endpoint_path(value):
        endpoint = str(value or '').strip()
        if not endpoint:
            return ''
        return endpoint.split('?', 1)[0]

    @classmethod
    def _is_expected_noise(cls, alert_type, message, context):
        if alert_type != 'frontend_api_error':
            return False

        endpoint_path = cls._normalize_endpoint_path(context.get('endpoint') or context.get('path') or context.get('url'))
        status_raw = context.get('status') or context.get('status_code')
        try:
            status_code = int(status_raw)
        except (TypeError, ValueError):
            status_code = None

        lowered_message = str(message or '').lower()

        if status_code in {400, 401} and endpoint_path.startswith('/users/token/'):
            return True

        if status_code in {401, 403} and (
            endpoint_path.startswith('/site-settings/contact-leads/admin/')
            or endpoint_path.startswith('/site-settings/system-alerts/admin/')
            or endpoint_path.startswith('/medical/appointments/clinic_dashboard_stats/')
        ):
            return True

        if status_code == 400 and endpoint_path.startswith('/doctors/check_out/'):
            return True

        if status_code in {401, 403} and ('permission' in lowered_message or 'faqat ' in lowered_message):
            return True

        return False

    def post(self, request):
        payload = request.data or {}
        alert_type = str(payload.get('alert_type') or 'frontend_error').strip()[:120]
        message = str(payload.get('message') or '').strip()[:3000]
        severity = str(payload.get('severity') or 'error').strip().lower()
        context = payload.get('context') if isinstance(payload.get('context'), dict) else {}
        traceback_text = str(payload.get('traceback') or '').strip()[:12000]

        if severity not in {'warning', 'error', 'critical'}:
            severity = 'error'

        if not message:
            return Response({'detail': 'message required'}, status=status.HTTP_400_BAD_REQUEST)

        enriched_context = {
            **context,
            'client_url': str(payload.get('url') or context.get('url') or ''),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'client_ip': self._get_client_ip(request),
            'is_authenticated': bool(getattr(request.user, 'is_authenticated', False)),
            'user_id': str(request.user.id) if getattr(request.user, 'is_authenticated', False) else None,
        }

        if self._is_expected_noise(alert_type, message, enriched_context):
            return Response({'accepted': True, 'suppressed': True}, status=status.HTTP_202_ACCEPTED)

        endpoint_path = self._normalize_endpoint_path(
            enriched_context.get('endpoint') or enriched_context.get('path') or enriched_context.get('url')
        )
        status_value = enriched_context.get('status') or enriched_context.get('status_code') or ''
        method_value = str(enriched_context.get('method') or '').upper()

        dedupe_source = (
            f"{alert_type}|{message}|{endpoint_path}|{status_value}|{method_value}|"
            f"{enriched_context.get('client_url','')}|{severity}"
        )
        dedupe_hash = hashlib.sha256(dedupe_source.encode('utf-8')).hexdigest()
        dedupe_key = f"system_alert_client_dedupe:{dedupe_hash}"

        dedupe_hit = False
        try:
            dedupe_hit = bool(cache.get(dedupe_key))
        except Exception as cache_error:
            logger.warning('SystemAlert dedupe cache GET failed: %s', cache_error)

        if dedupe_hit:
            return Response({'accepted': True, 'deduplicated': True}, status=status.HTTP_202_ACCEPTED)

        alert = SystemAlert.objects.create(
            alert_type=alert_type,
            message=message,
            severity=severity,
            context=enriched_context,
            traceback=traceback_text,
        )
        try:
            cache.set(dedupe_key, True, timeout=120)
        except Exception as cache_error:
            logger.warning('SystemAlert dedupe cache SET failed: %s', cache_error)

        return Response({'accepted': True, 'id': str(alert.id)}, status=status.HTTP_201_CREATED)


class SystemAlertAdminListView(APIView):
    """Admin can view system alerts."""

    permission_classes = [IsAuthenticated, IsAdministrator]

    def get(self, request):
        qs = SystemAlert.objects.all().order_by('-created_at')

        unresolved_only = request.query_params.get('unresolved_only')
        if unresolved_only in ['1', 'true', 'True', 'yes']:
            qs = qs.filter(is_resolved=False)

        severity = (request.query_params.get('severity') or '').strip().lower()
        if severity in {'warning', 'error', 'critical'}:
            qs = qs.filter(severity=severity)

        limit_param = request.query_params.get('limit')
        try:
            limit = int(limit_param) if limit_param else 100
        except ValueError:
            limit = 100
        limit = max(1, min(limit, 500))

        alerts = list(qs[:limit])
        return Response(SystemAlertAdminSerializer(alerts, many=True).data, status=status.HTTP_200_OK)


class AdminBroadcastView(APIView):
    """Admin-only recipient statistics and broadcast delivery."""

    permission_classes = [IsAuthenticated, IsAdministrator]

    @staticmethod
    def _site_users():
        user_model = get_user_model()
        return user_model.objects.filter(is_active=True).exclude(role='admin')

    @staticmethod
    def _telegram_chat_ids():
        chat_ids = set()
        chat_sources = (
            Patient.objects.values_list('telegram_chat_id', flat=True),
            Doctor.objects.values_list('telegram_chat_id', flat=True),
            Appointment.objects.values_list('telegram_chat_id', flat=True),
        )
        for source in chat_sources:
            chat_ids.update(int(chat_id) for chat_id in source if chat_id)
        return chat_ids

    def get(self, request):
        return Response({
            'site_users': self._site_users().count(),
            'telegram_users': len(self._telegram_chat_ids()),
            'push_devices': WebPushSubscription.objects.filter(
                is_active=True,
                user__is_active=True,
            ).exclude(user__role='admin').count(),
        }, status=status.HTTP_200_OK)

    def post(self, request):
        title = str(request.data.get('title') or '').strip()
        message = str(request.data.get('message') or '').strip()
        channels = request.data.get('channels')
        if not title or not message:
            return Response({'detail': 'Sarlavha va xabar matnini kiriting.'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(channels, list) or not channels or any(channel not in {'site', 'telegram'} for channel in channels):
            return Response({'detail': 'Kamida bitta yuborish kanalini tanlang.'}, status=status.HTTP_400_BAD_REQUEST)

        telegram_client = None
        if 'telegram' in channels:
            from apps.medical.telegram_bot_service import TelegramBotService

            try:
                telegram_client = TelegramBotService()._require_client()
            except RuntimeError:
                return Response({'detail': 'Telegram Bot tokeni sozlanmagan.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        result = {'site_sent': 0, 'site_total': 0, 'telegram_sent': 0, 'telegram_total': 0}
        if 'site' in channels:
            from core.websocket_service import WebSocketService

            users = list(self._site_users().values_list('id', flat=True))
            result['site_total'] = len(users)
            notifications = BroadcastNotification.objects.bulk_create([
                BroadcastNotification(user_id=user_id, title=title, message=message)
                for user_id in users
            ])
            result['site_sent'] = len(notifications)
            for notification in notifications:
                WebSocketService.send_notification(
                    notification.user_id,
                    'admin_broadcast',
                    {
                        'notification_id': str(notification.id),
                        'title': notification.title,
                        'message': notification.message,
                    },
                )
            push_subscriptions = WebPushSubscription.objects.filter(
                user_id__in=users,
                user__is_active=True,
                is_active=True,
            )
            result['push_queued'] = push_subscriptions.count()
            if result['push_queued'] and settings.WEB_PUSH_VAPID_PUBLIC_KEY and settings.WEB_PUSH_VAPID_PRIVATE_KEY_B64:
                from .tasks import send_saved_broadcast_push

                send_saved_broadcast_push.delay([str(notification.id) for notification in notifications])

        if 'telegram' in channels:
            from html import escape

            chat_ids = self._telegram_chat_ids()
            result['telegram_total'] = len(chat_ids)
            telegram_text = f'<b>{escape(title)}</b>\n\n{escape(message)}'
            for chat_id in chat_ids:
                if telegram_client and telegram_client.send_message(chat_id, telegram_text):
                    result['telegram_sent'] += 1

        return Response(result, status=status.HTTP_200_OK)


class WebPushConfigView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        public_key = settings.WEB_PUSH_VAPID_PUBLIC_KEY
        return Response({
            'enabled': bool(public_key and settings.WEB_PUSH_VAPID_PRIVATE_KEY_B64),
            'public_key': public_key,
        }, status=status.HTTP_200_OK)


class WebPushSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        subscription = request.data.get('subscription')
        if not isinstance(subscription, dict):
            return Response({'detail': 'Push subscription ma’lumotlari noto‘g‘ri.'}, status=status.HTTP_400_BAD_REQUEST)
        keys = subscription.get('keys')
        if not isinstance(keys, dict):
            return Response({'detail': 'Push subscription kalitlari noto‘g‘ri.'}, status=status.HTTP_400_BAD_REQUEST)
        endpoint = str(subscription.get('endpoint') or '').strip()
        p256dh = str(keys.get('p256dh') or '').strip()
        auth = str(keys.get('auth') or '').strip()
        if (
            not endpoint.startswith('https://')
            or len(endpoint) > 2048
            or not p256dh
            or len(p256dh) > 255
            or not auth
            or len(auth) > 255
        ):
            return Response({'detail': 'Push subscription ma’lumotlari noto‘g‘ri.'}, status=status.HTTP_400_BAD_REQUEST)

        row, created = WebPushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                'user': request.user,
                'p256dh': p256dh,
                'auth': auth,
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:512],
                'is_active': True,
            },
        )
        return Response({'id': str(row.id), 'created': created}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request):
        endpoint = str(request.data.get('endpoint') or '').strip()
        if not endpoint:
            return Response({'detail': 'Push endpoint required.'}, status=status.HTTP_400_BAD_REQUEST)
        WebPushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BroadcastNotificationInboxView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = BroadcastNotification.objects.filter(
            user=request.user,
            read_at__isnull=True,
        )[:50]
        return Response([
            {
                'id': str(notification.id),
                'title': notification.title,
                'message': notification.message,
                'created_at': notification.created_at,
            }
            for notification in notifications
        ], status=status.HTTP_200_OK)

    def patch(self, request, pk):
        notification = BroadcastNotification.objects.filter(user=request.user, pk=pk).first()
        if not notification:
            return Response({'detail': 'Bildirishnoma topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=['read_at'])
        return Response({'read': True}, status=status.HTTP_200_OK)


class SystemAlertResolveView(APIView):
    """Admin resolves a system alert."""

    permission_classes = [IsAuthenticated, IsAdministrator]

    def patch(self, request, pk):
        alert = SystemAlert.objects.filter(pk=pk).first()
        if not alert:
            return Response({'detail': 'Alert topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        if not alert.is_resolved:
            alert.is_resolved = True
            alert.resolved_at = timezone.now()
            alert.resolved_by = request.user
            alert.save(update_fields=['is_resolved', 'resolved_at', 'resolved_by'])

        return Response(SystemAlertAdminSerializer(alert).data, status=status.HTTP_200_OK)
