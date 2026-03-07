import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Set Telegram webhook to the production medical endpoint"

    def add_arguments(self, parser):
        parser.add_argument(
            "--base-url",
            default=(getattr(settings, "FRONTEND_URL", "") or "").strip(),
            help="Public base URL (e.g. https://g-med.uz)",
        )
        parser.add_argument(
            "--drop-pending-updates",
            action="store_true",
            help="Drop pending Telegram updates when setting webhook",
        )

    def handle(self, *args, **options):
        token = (getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
        secret = (getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "") or "").strip()
        base_url = (options.get("base_url") or "").strip().rstrip("/")

        if not token:
            raise CommandError("TELEGRAM_BOT_TOKEN is not configured")
        if not secret:
            raise CommandError("TELEGRAM_WEBHOOK_SECRET is not configured")
        if not base_url:
            raise CommandError("--base-url is required or FRONTEND_URL must be configured")
        if not base_url.startswith("https://"):
            raise CommandError("Webhook base URL must use https://")

        webhook_url = f"{base_url}/api/v1/medical/telegram/webhook/{secret}/"
        api_base = f"https://api.telegram.org/bot{token}"

        payload = {
            "url": webhook_url,
            "drop_pending_updates": bool(options.get("drop_pending_updates")),
            "allowed_updates": ["message", "edited_message", "callback_query"],
        }

        response = requests.post(f"{api_base}/setWebhook", json=payload, timeout=15)
        data = response.json() if response.content else {}
        if not data.get("ok"):
            raise CommandError(f"setWebhook failed: {data}")

        self.stdout.write(self.style.SUCCESS(f"Webhook set: {webhook_url}"))
