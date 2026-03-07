from django.conf import settings
import logging
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .telegram_bot_service import TelegramBotService

logger = logging.getLogger(__name__)


class TelegramWebhookView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []

    def post(self, request, secret: str, *args, **kwargs):
        expected = getattr(settings, 'TELEGRAM_WEBHOOK_SECRET', '') or ''
        if not expected:
            return Response({'detail': 'Webhook secret not configured'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if secret != expected:
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        service = TelegramBotService()
        try:
            service.handle_update(request.data)
        except Exception as e:
            # Telegram expects 200 OK quickly; avoid retry storms.
            logger.exception("Telegram webhook handler error: %s", e)
            return Response({'ok': True}, status=status.HTTP_200_OK)

        return Response({'ok': True}, status=status.HTTP_200_OK)
