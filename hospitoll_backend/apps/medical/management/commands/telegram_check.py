import json

import requests
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Check Telegram bot configuration and webhook status (does not print token)"

    def handle(self, *args, **options):
        token = getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""
        username = getattr(settings, "TELEGRAM_BOT_USERNAME", "") or ""
        secret = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "") or ""

        self.stdout.write("Telegram config:")
        self.stdout.write(f"- TELEGRAM_BOT_USERNAME: {username or '(missing)'}")
        self.stdout.write(f"- TELEGRAM_WEBHOOK_SECRET: {'set' if bool(secret) else '(missing)'}")
        self.stdout.write(f"- TELEGRAM_BOT_TOKEN: {'set' if bool(token) else '(missing)'}")

        if not secret:
            self.stdout.write(self.style.WARNING("Webhook URL cannot be validated: TELEGRAM_WEBHOOK_SECRET is missing"))
        else:
            self.stdout.write("Expected webhook path:")
            self.stdout.write(f"- /api/v1/medical/telegram/webhook/{secret}/")

        if not token:
            self.stdout.write(self.style.WARNING("Cannot call Telegram API: TELEGRAM_BOT_TOKEN is missing"))
            return

        # getWebhookInfo
        try:
            resp = requests.get(f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=10)
            data = resp.json()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to call getWebhookInfo: {e}"))
            return

        if not data.get("ok"):
            self.stdout.write(self.style.ERROR(f"getWebhookInfo returned error: {json.dumps(data, ensure_ascii=False)}"))
            return

        info = data.get("result") or {}
        # Print only safe fields
        safe = {
            "url": info.get("url"),
            "has_custom_certificate": info.get("has_custom_certificate"),
            "pending_update_count": info.get("pending_update_count"),
            "last_error_date": info.get("last_error_date"),
            "last_error_message": info.get("last_error_message"),
            "max_connections": info.get("max_connections"),
            "ip_address": info.get("ip_address"),
        }
        self.stdout.write("Telegram getWebhookInfo:")
        self.stdout.write(json.dumps(safe, ensure_ascii=False, indent=2))
