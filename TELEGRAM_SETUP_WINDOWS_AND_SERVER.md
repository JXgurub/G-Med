# Telegram integration: Windows + Server

## Local Windows (no Docker)

### 1) Run backend
- `C:/Hospitoll/hospitoll_backend/venv/Scripts/python.exe manage.py runserver 0.0.0.0:8000`

### 2) Run ngrok
- `ngrok http 8000`

### 3) Configure `.env`
In `hospitoll_backend/.env`:
- `TELEGRAM_BOT_USERNAME=GMed1_bot`
- `TELEGRAM_WEBHOOK_SECRET=<random>`
- `TELEGRAM_BOT_TOKEN=<your token>`
- `ALLOWED_HOSTS` must include your current `*.ngrok-free.app` host

### 4) Set Telegram webhook (safe prompt)
- Run: `powershell -ExecutionPolicy Bypass -File C:/Hospitoll/hospitoll_backend/setup_telegram_webhook_ngrok.ps1`

### 5) Enable reminders + auto-cancel without Celery
This project supports a fallback scheduler (no Redis/Celery) using a management command:
- `python manage.py process_telegram_jobs`

To run it every minute via Windows Task Scheduler:
- `powershell -ExecutionPolicy Bypass -File C:/Hospitoll/hospitoll_backend/setup_windows_telegram_jobs_task.ps1`

To remove the task:
- `powershell -ExecutionPolicy Bypass -File C:/Hospitoll/hospitoll_backend/remove_windows_telegram_jobs_task.ps1`

## Server / Production (recommended)

### Recommended architecture
- Public HTTPS endpoint (Nginx + domain)
- Redis + Celery worker running (for ETA jobs + reminders)
- Webhook enabled

### Option A: docker-compose (if Docker available)
Use the existing `docker-compose.yml` (includes Redis + Celery worker + Celery beat).

You still must set env vars:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_BOT_USERNAME`
- `TELEGRAM_WEBHOOK_SECRET`
- `ALLOWED_HOSTS` includes your domain

Then set webhook using the management command inside the backend container.

### Option B: systemd (no Docker)
Run:
- Gunicorn/Daphne (ASGI)
- Redis
- `celery -A config worker -l info`
- `celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler`

Webhook URL should be:
- `https://YOUR_DOMAIN/api/v1/medical/telegram/webhook/<TELEGRAM_WEBHOOK_SECRET>/`

### Notes
- If both Celery and fallback scheduler run, duplicate reminders are prevented by `Appointment.telegram_reminder_sent_at`.
- If you use ngrok in dev: its host changes every restart, so you must re-set webhook.
