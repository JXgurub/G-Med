import json
import logging

from celery import shared_task
from django.conf import settings

from .models import BroadcastNotification, WebPushSubscription

logger = logging.getLogger(__name__)


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
            'url': '/',
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