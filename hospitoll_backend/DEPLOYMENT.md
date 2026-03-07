"""
DEPLOYMENT GUIDE - Production Checklist
Hospitoll Hospital Management System
"""

# PRODUCTION DEPLOYMENT CHECKLIST
PRODUCTION_CHECKLIST = """
PRE-DEPLOYMENT CHECKLIST
========================

SECURITY:
  ☐ Change SECRET_KEY to a strong random string
  ☐ Set DEBUG = False
  ☐ Update ALLOWED_HOSTS with your domain
  ☐ Configure CORS_ALLOWED_ORIGINS
  ☐ Set secure cookies (SECURE_COOKIES = True)
  ☐ Enable HTTPS_ONLY
  ☐ Configure SSL/TLS certificates
  ☐ Set SECURE_SSL_REDIRECT = True
  ☐ Add security headers (HSTS, CSP, etc.)
  ☐ Disable admin panel default URL
  ☐ Configure firewall rules

DATABASE:
  ☐ Use PostgreSQL (not SQLite)
  ☐ Configure connection pooling (pgBouncer)
  ☐ Set up database backups (daily automated)
  ☐ Test point-in-time recovery
  ☐ Configure database monitoring
  ☐ Set up read replicas for scaling
  ☐ Enable database encryption at rest
  ☐ Configure automated failover

CACHING:
  ☐ Set up Redis for caching
  ☐ Configure session backend to Redis
  ☐ Set cache timeout policies
  ☐ Monitor Redis memory usage
  ☐ Set up Redis persistence/RDB backup

LOGGING & MONITORING:
  ☐ Set up centralized logging (ELK, Splunk, etc.)
  ☐ Configure error tracking (Sentry, Rollbar, etc.)
  ☐ Set up performance monitoring (New Relic, Datadog)
  ☐ Configure alerts for critical errors
  ☐ Set up uptime monitoring
  ☐ Configure log rotation
  ☐ Monitor database query performance

APP SERVERS:
  ☐ Use Gunicorn with multiple workers
  ☐ Use Nginx as reverse proxy
  ☐ Configure load balancing
  ☐ Set up health check endpoints
  ☐ Configure graceful shutdown
  ☐ Monitor worker processes

CELERY/BACKGROUND TASKS:
  ☐ Set up Celery workers
  ☐ Configure Celery Beat for scheduled tasks
  ☐ Monitor Celery tasks
  ☐ Set up task timeout policies
  ☐ Configure dead letter queues
  ☐ Monitor Redis/RabbitMQ broker health

FILE STORAGE:
  ☐ Configure AWS S3 for media files
  ☐ Set up CloudFront CDN
  ☐ Configure S3 bucket policies
  ☐ Enable S3 versioning
  ☐ Configure S3 encryption
  ☐ Set up S3 lifecycle policies

STATIC FILES:
  ☐ Collect static files
  ☐ Configure whitenoise
  ☐ Use CDN for static assets
  ☐ Enable gzip compression
  ☐ Configure cache headers

EMAIL/NOTIFICATIONS:
  ☐ Configure SMTP server
  ☐ Set up email service
  ☐ Configure SMS service (optional)
  ☐ Test email delivery
  ☐ Set up email templates

BACKUPS:
  ☐ Set up automated database backups
  ☐ Test backup restoration
  ☐ Set up media file backups to S3
  ☐ Configure backup retention policies
  ☐ Document disaster recovery procedures

PERFORMANCE:
  ☐ Optimize database queries
  ☐ Enable query result caching
  ☐ Configure database indexes
  ☐ Use select_related and prefetch_related
  ☐ Enable gzip compression
  ☐ Configure pagination defaults
  ☐ Implement rate limiting

DOCUMENTATION:
  ☐ Document deployment process
  ☐ Create runbooks for common issues
  ☐ Document API endpoints
  ☐ Document database schema
  ☐ Create emergency contact list

TESTING:
  ☐ Run full test suite
  ☐ Test authentication flows
  ☐ Test payment processing
  ☐ Load testing
  ☐ Security scanning (OWASP)

MIGRATION:
  ☐ Backup production database
  ☐ Run django migrations
  ☐ Verify data integrity
  ☐ Test rollback procedure

POST-DEPLOYMENT:
  ☐ Monitor application logs
  ☐ Verify all services running
  ☐ Test critical user flows
  ☐ Monitor resource usage
  ☐ Performance analysis
"""

# DEPLOYMENT SCRIPTS
DOCKER_COMPOSE = """
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: hospitoll_db
      POSTGRES_USER: hospitoll_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U hospitoll_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  web:
    build: .
    command: gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      - DEBUG=False
      - SECRET_KEY=${SECRET_KEY}
      - DB_ENGINE=postgresql
      - DB_NAME=hospitoll_db
      - DB_USER=hospitoll_user
      - DB_PASSWORD=${DB_PASSWORD}
      - DB_HOST=db
      - CELERY_BROKER_URL=redis://redis:6379/0
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health/"]
      interval: 30s
      timeout: 10s
      retries: 3

  celery:
    build: .
    command: celery -A config worker --loglevel=info
    depends_on:
      - db
      - redis
    environment:
      - DEBUG=False
      - SECRET_KEY=${SECRET_KEY}
      - DB_ENGINE=postgresql
      - DB_NAME=hospitoll_db
      - DB_USER=hospitoll_user
      - DB_PASSWORD=${DB_PASSWORD}
      - DB_HOST=db
      - CELERY_BROKER_URL=redis://redis:6379/0

  celery-beat:
    build: .
    command: celery -A config beat --loglevel=info
    depends_on:
      - db
      - redis
    environment:
      - DEBUG=False
      - SECRET_KEY=${SECRET_KEY}
      - DB_ENGINE=postgresql
      - DB_NAME=hospitoll_db
      - DB_USER=hospitoll_user
      - DB_PASSWORD=${DB_PASSWORD}
      - DB_HOST=db
      - CELERY_BROKER_URL=redis://redis:6379/0

volumes:
  postgres_data:
"""

# NGINX CONFIGURATION
NGINX_CONFIG = """
upstream hospitoll_app {
    server web:8000;
}

server {
    listen 80;
    server_name _;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    # SSL Configuration
    ssl_certificate /etc/ssl/certs/your-cert.crt;
    ssl_certificate_key /etc/ssl/private/your-key.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    
    # Gzip compression
    gzip on;
    gzip_types text/plain text/css text/xml text/javascript 
               application/x-javascript application/xml+rss 
               application/json application/javascript;
    
    # Client request size limit
    client_max_body_size 50M;
    
    # Proxy settings
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
    
    location / {
        proxy_pass http://hospitoll_app;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $host;
        proxy_redirect off;
    }
    
    location /static/ {
        alias /app/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    location /media/ {
        alias /app/media/;
        expires 7d;
    }
}
"""

# SYSTEMD SERVICE CONFIGURATION
SYSTEMD_GUNICORN = """
[Unit]
Description=Hospitoll Gunicorn Application Server
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/opt/hospitoll
Environment="PATH=/opt/hospitoll/venv/bin"
ExecStart=/opt/hospitoll/venv/bin/gunicorn \\
    --workers 4 \\
    --worker-class sync \\
    --bind unix:/run/gunicorn.sock \\
    --timeout 30 \\
    --access-logfile - \\
    --error-logfile - \\
    config.wsgi:application
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

SYSTEMD_CELERY = """
[Unit]
Description=Hospitoll Celery Service
After=network.target

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/opt/hospitoll
Environment="PATH=/opt/hospitoll/venv/bin"
ExecStart=/opt/hospitoll/venv/bin/celery -A config worker --loglevel=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

SYSTEMD_CELERY_BEAT = """
[Unit]
Description=Hospitoll Celery Beat Service
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/hospitoll
Environment="PATH=/opt/hospitoll/venv/bin"
ExecStart=/opt/hospitoll/venv/bin/celery -A config beat --loglevel=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

print(PRODUCTION_CHECKLIST)
print()
print("AVAILABLE CONFIGURATIONS:")
print("1. Docker Compose configuration")
print("2. Nginx reverse proxy configuration")
print("3. Systemd service files for Gunicorn, Celery, and Celery Beat")
# SCHEDULED TASKS - PAYMENT EXPIRY CHECK
# =========================================
# 
# The system automatically suspends clinics and pharmacies if their payment expires after 30 days.
# 
# Command to run manually:
#   python manage.py check_payment_expiry
#
# To schedule this task automatically, add it to your task scheduler:
#
# OPTION 1: Celery Beat (Recommended)
# Add to config/celery_beat.py:
#   from celery.schedules import crontab
#   
#   CELERY_BEAT_SCHEDULE = {
#       'check-payment-expiry': {
#           'task': 'apps.clinics.tasks.check_payment_expiry',
#           'schedule': crontab(hour=0, minute=0),  # Run daily at midnight
#       },
#   }
#
# OPTION 2: Linux Cron (Manual scheduling)
# Add to crontab:
#   0 0 * * * /path/to/venv/bin/python /path/to/manage.py check_payment_expiry >> /var/log/hospital/payment_check.log 2>&1
#
# OPTION 3: Windows Task Scheduler
# Create scheduled task to run:
#   python C:\Hospitoll\hospitoll_backend\manage.py check_payment_expiry
#   Every day at 00:00