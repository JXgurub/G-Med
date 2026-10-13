import json
import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import BroadcastNotification, WebPushSubscription

logger = logging.getLogger(__name__)


@shared_task
def purge_read_broadcast_notifications() -> dict[str, int]:
    cutoff = timezone.now() - timedelta(days=2)
    deleted, _ = BroadcastNotification.objects.filter(read_at__lt=cutoff).delete()
    return {'deleted': deleted}


@shared_task
def send_saved_broadcast_push(notification_ids: list[str]) -> dict[str, int]:
    if not settings.WEB_PUSH_VAPID_PRIVATE_KEY_B64 or not settings.WEB_PUSH_VAPID_PUBLIC_KEY:
        return {'sent': 0, 'failed': 0, 'expired': 0}

    from pywebpush import WebPushException, webpush

    result = {'sent': 0, 'failed': 0, 'expired': 0}
    notifications = BroadcastNotification.objects.filter(id__in=notification_ids).prefetch_related('user__web_push_subscriptions')
    for notification in notifications:
        payload = json.dumps({
            'id': str(notification.id),
            'title': notification.title,
            'body': notification.message,
            'url': notification.data.get('url', '/'),
            'category': notification.data.get('category', 'general'),
            'priority': notification.data.get('priority', 'normal'),
        })
        for subscription in notification.user.web_push_subscriptions.all():
            if not subscription.is_active:
                continue
            subscription_info = {
                'endpoint': subscription.endpoint,
                'keys': {'p256dh': subscription.p256dh, 'auth': subscription.auth},
            }
            try:
                webpush(
                    subscription_info=subscription_info,
                    data=payload,
                    vapid_private_key=settings.WEB_PUSH_VAPID_PRIVATE_KEY_B64,
                    vapid_claims={'sub': settings.WEB_PUSH_VAPID_SUBJECT},
                    ttl=3600,
                    timeout=10,
                )
                result['sent'] += 1
            except WebPushException as error:
                status_code = getattr(error, 'status_code', None) or getattr(getattr(error, 'response', None), 'status_code', None)
                if status_code in {404, 410}:
                    subscription.delete()
                    result['expired'] += 1
                else:
                    result['failed'] += 1
                    logger.warning('Web Push delivery failed (status=%s)', status_code)

    return result