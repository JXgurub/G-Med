# Hospitoll Deployment & Setup Guide

## Table of Contents
1. [System Requirements](#system-requirements)
2. [Local Development Setup](#local-development-setup)
3. [Docker Deployment](#docker-deployment)
4. [Production Deployment](#production-deployment)
5. [Troubleshooting](#troubleshooting)

## System Requirements

### Local Development
- Python 3.11+
- Node.js 18+
- PostgreSQL 13+
- Redis 7+
- Git

### Production
- Docker & Docker Compose
- Linux server (Ubuntu 20.04+ recommended)
- 4GB+ RAM
- 20GB+ disk space
- Domain name & SSL certificate

## Local Development Setup

### Backend Setup
```bash
# Navigate to backend directory
cd hospitoll_backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Configure database (PostgreSQL)
# Update .env with database credentials

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# Run development server
python manage.py runserver

# In another terminal, start Celery worker
celery -A config worker -l info

# In another terminal, start Celery beat
celery -A config beat -l info
```

### Frontend Setup
```bash
# Navigate to frontend directory
cd hospitoll_frontend

# Install dependencies
npm install

# Create environment file
cp .env.example .env

# Update .env with API URL
# VITE_API_BASE_URL=http://localhost:8000/api

# Run development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Docker Deployment

### Quick Start (Local)
```bash
# From root directory
docker-compose up -d

# Check services
docker-compose ps

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Docker Compose Services
- **db**: PostgreSQL database
- **redis**: Redis cache & broker
- **backend**: Django ASGI API server (Gunicorn + Uvicorn worker)
- **celery_worker**: Background task worker
- **celery_beat**: Scheduled tasks
- **frontend**: React/Vite frontend
- **nginx**: Reverse proxy

### Database Access
```bash
# Enter database container
docker-compose exec db psql -U hospitoll_user -d hospitoll_db

# Create dumps
docker-compose exec db pg_dump -U hospitoll_user hospitoll_db > backup.sql

# Restore dumps
docker-compose exec -T db psql -U hospitoll_user hospitoll_db < backup.sql
```

## Production Deployment

### Prerequisites
1. Linux server with Docker installed
2. Domain name configured
3. SSL certificates ready
4. Environment variables configured

### Deployment Steps

1. **Clone Repository**
```bash
git clone https://github.com/yourusername/Hospitoll.git
cd Hospitoll
```

2. **Configure Environment**
```bash
# Copy and update production environment
cp .env.production.example .env.production

# Update important variables:
# - DJANGO_SECRET_KEY (generate new)
# - DB_PASSWORD
# - HOSPITOLL_ADMIN_PASSWORD / HOSPITOLL_APP_PASSWORD
# - EMAIL credentials
# - Domain name
```

3. **Run preflight validation**
```bash
bash scripts/prod-preflight.sh
```

This verifies:
- Docker/Compose availability
- `.env.production` required values
- SSL files (`ssl/cert.pem`, `ssl/key.pem`)
- `docker-compose.prod.yml` validity

4. **Setup SSL Certificates**
```bash
mkdir -p ssl

# Option 1: Use Let's Encrypt with Certbot
certbot certonly --standalone -d hospitoll.uz -d www.hospitoll.uz
cp /etc/letsencrypt/live/hospitoll.uz/fullchain.pem ssl/cert.pem
cp /etc/letsencrypt/live/hospitoll.uz/privkey.pem ssl/key.pem

# Option 2: Use self-signed certificate (testing only)
openssl req -x509 -newkey rsa:4096 -nodes -out ssl/cert.pem -keyout ssl/key.pem -days 365
```

5. **Deploy with production compose**
```bash
# One-command deploy (recommended)
bash deploy.sh

# Manual alternative
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T backend python manage.py migrate
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T backend python manage.py collectstatic --noinput
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T backend python manage.py check --deploy --tag security
```

6. **Create admin user**
```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec backend python manage.py createsuperuser
```

7. **Configure Telegram webhook (optional)**
```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec backend \
  python manage.py telegram_set_webhook --base-url https://hospitoll.uz
docker compose --env-file .env.production -f docker-compose.prod.yml exec backend \
  python manage.py telegram_check
```

8. **Nginx Configuration**
- Review and update nginx.conf for your domain
- Ensure SSL paths match your certificates
- Configure firewall rules

9. **Monitoring**
```bash
# View logs
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f backend

# Check health
curl -i http://localhost/health

# Database backup
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T db pg_dump -U $DB_USER $DB_NAME > backup_$(date +%Y%m%d).sql
```

### SSL Certificate Renewal
```bash
# Schedule with cron (runs monthly)
0 3 1 * * certbot renew --quiet && \
  cp /etc/letsencrypt/live/hospitoll.uz/fullchain.pem /path/to/ssl/cert.pem && \
  cp /etc/letsencrypt/live/hospitoll.uz/privkey.pem /path/to/ssl/key.pem && \
  docker-compose restart nginx
```

### Automatic Backups
```bash
# Create backup script
cat > backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
docker-compose exec -T db pg_dump -U hospitoll_user hospitoll_db > $BACKUP_DIR/db_$TIMESTAMP.sql
docker-compose exec -T backend tar -czf $BACKUP_DIR/media_$TIMESTAMP.tar.gz /app/media
EOF

# Schedule with cron (daily at 2 AM)
0 2 * * * bash /path/to/backup.sh
```

## Troubleshooting

### Database Connection Issues
```bash
# Check database is running
docker-compose ps db

# View database logs
docker-compose logs db

# Test connection
docker-compose exec db psql -U hospitoll_user -d hospitoll_db -c "SELECT 1;"
```

### Backend Not Starting
```bash
# Check logs
docker-compose logs backend

# Re-run migrations
docker-compose exec backend python manage.py migrate

# Check static files
docker-compose exec backend python manage.py collectstatic --noinput
```

### Frontend Not Loading
```bash
# Check logs
docker-compose logs frontend

# Verify API connection
curl http://localhost:8000/api/

# Check nginx configuration
docker-compose exec nginx nginx -t
```

### Redis Connection Issues
```bash
# Check Redis
docker-compose exec redis redis-cli ping

# Clear cache
docker-compose exec redis redis-cli FLUSHALL
```

### Celery Tasks Not Running
```bash
# Check worker logs
docker-compose logs celery_worker

# Check Redis broker
docker-compose exec redis redis-cli KEYS "*"

# Restart worker
docker-compose restart celery_worker
```

### SSL Certificate Issues
```bash
# Check certificate expiry
openssl x509 -in ssl/cert.pem -text -noout | grep -A 2 "Validity"

# Test SSL
curl -I https://hospitoll.uz

# Nginx SSL test
docker-compose exec nginx nginx -t
```

## Performance Optimization

### Database
- Enable query caching
- Create appropriate indexes
- Monitor slow queries
- Regular vacuuming

### Redis
- Monitor memory usage
- Configure eviction policy
- Enable persistence

### Frontend
- Enable gzip compression (already configured in nginx)
- Use CDN for static assets
- Optimize images
- Enable browser caching

### Backend
- Tune Gunicorn workers/threads for your CPU and RAM
- Enable database connection pooling
- Monitor Celery tasks
- Use Redis for session storage

## Security Checklist

- [ ] Change all default passwords
- [ ] Update DJANGO_SECRET_KEY
- [ ] Enable HTTPS only
- [ ] Configure firewall rules
- [ ] Set up fail2ban
- [ ] Enable rate limiting
- [ ] Regular security updates
- [ ] Monitor access logs
- [ ] Configure CORS properly
- [ ] Enable CSRF protection

## Support & Maintenance

For issues and support:
- Check logs: `docker-compose logs -f`
- Review documentation: See DEPLOYMENT.md
- Run health checks
- Monitor resource usage
- Regular backups (automated recommended)

## Scale to Production

For scaling to production:

1. **Use managed database** (AWS RDS, DigitalOcean Managed DB)
2. **Use managed Redis** (AWS ElastiCache, DigitalOcean Managed Redis)
3. **Multiple backend instances** (load balanding with HAProxy)
4. **CDN for static assets** (CloudFront, Cloudflare)
5. **Object storage** (AWS S3 for media files)
6. **Monitoring & Alerting** (Datadog, New Relic, Sentry)
7. **Log aggregation** (ELK Stack, Splunk)
