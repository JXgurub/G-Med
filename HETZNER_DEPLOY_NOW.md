# Hetzner Deploy Now (Ubuntu 24.04)

This is the fastest path to deploy G-Med on your new Hetzner server.

## 0. DNS first (required)
Point domain records to your server IP:
- `A` -> `g-med.uz` -> `<SERVER_IPV4>`
- `A` -> `www.g-med.uz` -> `<SERVER_IPV4>`
- `AAAA` (optional) -> IPv6 address

Wait until DNS is propagated (`nslookup g-med.uz`).

## 1. Server bootstrap
SSH into server and run:
```bash
sudo apt-get update && sudo apt-get install -y git
```

Clone project:
```bash
git clone <YOUR_REPO_URL> Hospitoll
cd Hospitoll
```

Run bootstrap script:
```bash
bash scripts/hetzner-bootstrap.sh
```

Then re-login to SSH (important for docker group).

## 2. Prepare production env
```bash
cd ~/Hospitoll
cp .env.production.example .env.production
nano .env.production
```

Set real values at minimum:
- `DJANGO_SECRET_KEY`
- `DB_PASSWORD`
- `HOSPITOLL_ADMIN_PASSWORD`
- `HOSPITOLL_APP_PASSWORD`
- `DOMAIN=g-med.uz`
- `ALLOWED_HOSTS=g-med.uz,www.g-med.uz`
- `CORS_ALLOWED_ORIGINS=https://g-med.uz,https://www.g-med.uz`
- `CSRF_TRUSTED_ORIGINS=https://g-med.uz,https://www.g-med.uz`
- `EMAIL_*`
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_WEBHOOK_SECRET` (if Telegram bot is enabled)

## 3. Get SSL certificates (Let's Encrypt)
Stop anything on port 80 if running, then:
```bash
sudo apt-get install -y certbot
sudo certbot certonly --standalone -d g-med.uz -d www.g-med.uz -m <YOUR_EMAIL> --agree-tos --no-eff-email -n

mkdir -p ssl
sudo cp /etc/letsencrypt/live/g-med.uz/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/g-med.uz/privkey.pem ssl/key.pem
sudo chown $USER:$USER ssl/cert.pem ssl/key.pem
chmod 600 ssl/key.pem
```

## 4. Deploy
```bash
cd ~/Hospitoll
bash scripts/prod-preflight.sh
bash deploy.sh
```

Create Django admin:
```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec backend python manage.py createsuperuser
```

## 5. Verify
```bash
curl -I http://localhost/health
curl -I https://g-med.uz

docker compose --env-file .env.production -f docker-compose.prod.yml ps
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f backend
```

## 6. SSL auto-renew hook
Create deploy-hook for nginx restart after renew:
```bash
sudo bash -c 'cat > /etc/letsencrypt/renewal-hooks/deploy/hospitoll-nginx-reload.sh << "EOF"
#!/usr/bin/env bash
set -e
cd /home/$SUDO_USER/Hospitoll || cd /root/Hospitoll
docker compose --env-file .env.production -f docker-compose.prod.yml restart nginx
EOF'

sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/hospitoll-nginx-reload.sh
```

Test renew:
```bash
sudo certbot renew --dry-run
```

## Notes
- Current production stack is tuned for 4GB RAM (CPX22): Gunicorn+Uvicorn ASGI, Celery concurrency limits, Redis and Postgres memory tuning.
- For growth, first upgrade DB resources, then move app to CPX31/CPX41.
