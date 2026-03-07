import json

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Set Telegram webhook for the configured bot"

    def add_arguments(self, parser):
        parser.add_argument(
            "--webhook-url",
            type=str,
            help="Full webhook URL to set (recommended). Example: https://api.example.com/api/v1/medical/telegram/webhook/<secret>/",
        )
        parser.add_argument(
            "--base-url",
            type=str,
            help="Base public URL (alternative). Example: https://api.example.com",
        )
        parser.add_argument(
            "--drop-pending-updates",
            action="store_true",
            help="Drop pending updates on Telegram side when setting the webhook.",
        )

    def handle(self, *args, **options):
        token = getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""
        username = getattr(settings, "TELEGRAM_BOT_USERNAME", "") or ""
        secret = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "") or ""

        if not token:
            raise CommandError("TELEGRAM_BOT_TOKEN is not configured")
        if not secret:
            raise CommandError("TELEGRAM_WEBHOOK_SECRET is not configured")

        webhook_url = options.get("webhook_url")
        base_url = options.get("base_url")

        if not webhook_url:
            if not base_url:
                raise CommandError("Provide --webhook-url or --base-url")
            webhook_url = base_url.rstrip("/") + f"/api/v1/medical/telegram/webhook/{secret}/"

        payload = {
            "url": webhook_url,
            "drop_pending_updates": bool(options.get("drop_pending_updates")),
        }

        api_url = f"https://api.telegram.org/bot{token}/setWebhook"
        try:
            resp = requests.post(api_url, json=payload, timeout=15)
            data = resp.json()
        except Exception as e:
            raise CommandError(f"Failed to call Telegram setWebhook: {e}")

        ok = bool(data.get("ok"))
        if not ok:
            raise CommandError(f"Telegram setWebhook failed: {json.dumps(data, ensure_ascii=False)}")

        # Don't print token. URL is safe-ish but still includes secret; keep it short.
        self.stdout.write(self.style.SUCCESS("Webhook set successfully"))
        if username:
            self.stdout.write(f"Bot: @{username}")
        self.stdout.write(f"Webhook URL: {webhook_url}")
