# Production Go-Live (Hospitoll)

This file is the shortest path to launch in real production.

## 1. Server prerequisites
- Ubuntu 20.04+ (or similar Linux)
- Docker + Docker Compose plugin
- Domain DNS pointing to server IP
- Ports `80` and `443` open in firewall

## 2. Upload project to server
```bash
git clone <your-repo-url> Hospitoll
cd Hospitoll
```

## 3. Prepare production env
```bash
cp .env.production.example .env.production
```

Edit `.env.production` and replace all placeholders:
- `DJANGO_SECRET_KEY`
- `DB_PASSWORD`
- `HOSPITOLL_ADMIN_PASSWORD`
- `HOSPITOLL_APP_PASSWORD`
- `DOMAIN`, `ALLOWED_HOSTS`
- `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`
- SMTP credentials
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` (if Telegram bot is used)
- CPX22 tuning defaults:
  - `GUNICORN_WORKERS=2`
  - `GUNICORN_THREADS=2`
  - `CELERY_WORKER_CONCURRENCY=2`
  - `CELERY_WORKER_PREFETCH_MULTIPLIER=1`

Generate strong Django secret key example:
```bash
python3 - << 'PY'
from secrets import token_urlsafe
print(token_urlsafe(64))
PY
```

## 4. SSL certificates
Place files in:
- `ssl/cert.pem`
- `ssl/key.pem`

## 5. Validate before launch
```bash
bash scripts/prod-preflight.sh
```

## 6. Launch production stack
```bash
bash deploy.sh
```

## 7. Create admin user
```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec backend python manage.py createsuperuser
```

## 8. Post-launch checks
```bash
curl -I http://localhost/health
curl -I https://<your-domain>

docker compose --env-file .env.production -f docker-compose.prod.yml ps
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f backend

# WebSocket and Telegram checks
docker compose --env-file .env.production -f docker-compose.prod.yml exec backend python manage.py check --deploy --tag security
docker compose --env-file .env.production -f docker-compose.prod.yml exec backend python manage.py telegram_check
```

## 9. Backup command (run daily with cron)
```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T db \
  pg_dump -U "$DB_USER" "$DB_NAME" > backup_$(date +%Y%m%d_%H%M%S).sql
```

## Notes
- Production stack uses `docker-compose.prod.yml`.
- DB init runs through `scripts/init-db.sh` and safely passes role passwords to `init.sql`.
- Security deploy check is included in `deploy.sh`.
- HTTP + WebSocket are served by ASGI (`Gunicorn + UvicornWorker`) on backend.
