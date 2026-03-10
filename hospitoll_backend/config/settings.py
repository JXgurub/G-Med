import os
from pathlib import Path
from datetime import timedelta
from decouple import config
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = config('DEBUG', default=False, cast=bool)
SECRET_KEY = config('DJANGO_SECRET_KEY', default='')

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-development-key-change-in-production'
    else:
        raise ImproperlyConfigured('DJANGO_SECRET_KEY must be set when DEBUG=False')

if not DEBUG and SECRET_KEY in {
    'your-secret-key-change-in-production',
    'your-very-secret-key-change-in-production',
    'your-super-secret-key-change-this-in-production-with-a-long-random-string',
    'django-insecure-development-key-change-in-production',
}:
    raise ImproperlyConfigured('DJANGO_SECRET_KEY must be a strong random value in production')

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=lambda v: [s.strip() for s in v.split(',')])

# Application definition
INSTALLED_APPS = [
    # Daphne for ASGI support (must be before django.contrib.*)
    'daphne',
    
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    'channels',
    'django_celery_beat',
    'django_celery_results',
    
    # Local apps
    'apps.users',
    'apps.clinics',
    'apps.doctors',
    'apps.patients',
    'apps.pharmacies',
    'apps.medical',
    'apps.subscriptions',
    'apps.payments',
    'apps.search',
    'apps.analytics',
    'apps.site_settings',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    # Custom security and monitoring middleware
    'core.error_logging.ErrorLoggingMiddleware',
    'core.security.SecurityHeadersMiddleware',
    'core.security.InputSanitizationMiddleware',
    'core.security.AuthenticationSecurityMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database
# For local development, using SQLite (default)
# For production, ensure DB_ENGINE='postgresql' in .env with PostgreSQL running
DB_ENGINE = config('DB_ENGINE', default='sqlite').lower()

if DB_ENGINE == 'postgresql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME', default='hospitoll_db'),
            'USER': config('DB_USER', default='hospitoll_user'),
            'PASSWORD': config('DB_PASSWORD', default=''),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
            'CONN_MAX_AGE': config('DB_CONN_MAX_AGE', default=60, cast=int),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'uz'
TIME_ZONE = 'Asia/Tashkent'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
os.makedirs(STATIC_ROOT, exist_ok=True)
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'users.CustomUser'

# Django REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'anon': '120/hour',
        'user': '1200/hour',
        'auth': '20/minute',
        'password_reset': '5/hour',
        'password_reset_request': '5/hour',
        'password_reset_verify': '30/hour',
        'password_reset_confirm': '20/hour',
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Hospitoll API',
    'DESCRIPTION': 'Hospitoll backend API schema',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

SPECTACULAR_DISABLE_WARNINGS = config('SPECTACULAR_DISABLE_WARNINGS', default=not DEBUG, cast=bool)
if SPECTACULAR_DISABLE_WARNINGS:
    SILENCED_SYSTEM_CHECKS = [
        'drf_spectacular.W001',
        'drf_spectacular.W002',
    ]

# JWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
}

# CORS Configuration
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001',
    cast=lambda v: [s.strip() for s in v.split(',')]
)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='',
    cast=lambda v: [s.strip() for s in v.split(',') if s.strip()]
)

if not CSRF_TRUSTED_ORIGINS and not DEBUG:
    CSRF_TRUSTED_ORIGINS = [origin for origin in CORS_ALLOWED_ORIGINS if origin.startswith('https://')]

# Email Configuration
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@hospitoll.uz')
SERVER_EMAIL = config('SERVER_EMAIL', default='noreply@hospitoll.uz')

# Send emails asynchronously using Celery
SEND_EMAILS_ASYNC = config('SEND_EMAILS_ASYNC', default=True, cast=bool)

# Frontend URL for generating links in emails/Telegram messages
# Vite dev server in this repo runs on port 3000 (see hospitoll_frontend/vite.config.js)
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:3000')

# ============================================================================
# TELEGRAM BOT
# ============================================================================

TELEGRAM_BOT_TOKEN = config('TELEGRAM_BOT_TOKEN', default='')
TELEGRAM_BOT_USERNAME = config('TELEGRAM_BOT_USERNAME', default='hosptol_bot')
TELEGRAM_WEBHOOK_SECRET = config('TELEGRAM_WEBHOOK_SECRET', default='')
ADMIN_TELEGRAM_URL = config('ADMIN_TELEGRAM_URL', default='')

# Celery Configuration
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ACKS_LATE = config('CELERY_TASK_ACKS_LATE', default=True, cast=bool)
CELERY_TASK_REJECT_ON_WORKER_LOST = config('CELERY_TASK_REJECT_ON_WORKER_LOST', default=True, cast=bool)
CELERY_WORKER_PREFETCH_MULTIPLIER = config('CELERY_WORKER_PREFETCH_MULTIPLIER', default=1, cast=int)
CELERY_WORKER_MAX_TASKS_PER_CHILD = config('CELERY_WORKER_MAX_TASKS_PER_CHILD', default=200, cast=int)
CELERY_WORKER_CONCURRENCY = config('CELERY_WORKER_CONCURRENCY', default=2, cast=int)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# ============================================================================
# CACHING
# ============================================================================

CACHE_LOCATION = config('CACHE_LOCATION', default='')
USE_REDIS_CACHE = config('USE_REDIS_CACHE', default=False, cast=bool)

if USE_REDIS_CACHE and CACHE_LOCATION:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': CACHE_LOCATION,
            'OPTIONS': {
                'socket_connect_timeout': 5,
                'socket_timeout': 5,
            }
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'hospitoll-default-cache',
        }
    }

# Cache settings
CACHE_TIMEOUT = config('CACHE_TIMEOUT', default=300, cast=int)

# Celery Beat Schedule
from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    # Subscription management
    'check-and-deactivate-expired-subscriptions': {
        'task': 'apps.subscriptions.tasks.check_and_deactivate_expired_subscriptions',
        'schedule': crontab(hour=0, minute=0),  # Every day at midnight
    },
    'send-subscription-expiry-reminders-batch': {
        'task': 'core.tasks.send_subscription_expiry_reminders_batch',
        'schedule': crontab(hour=9, minute=0),  # Every day at 9 AM
    },
    # Appointment reminders
    'send-upcoming-appointment-reminders': {
        'task': 'core.tasks.send_upcoming_appointment_reminders',
        'schedule': crontab(hour=8, minute=0),  # Every day at 8 AM
    },
    # Invoice management
    'send-overdue-invoice-reminders': {
        'task': 'core.tasks.send_overdue_invoice_reminders',
        'schedule': crontab(hour=10, minute=0, day_of_week='0,2,4'),  # Mon, Wed, Fri at 10 AM
    },
    # Backup tasks
    'create-daily-backup': {
        'task': 'core.backup_manager.create_daily_backup',
        'schedule': crontab(hour=2, minute=0),  # Every day at 2 AM
    },
    'create-weekly-backup': {
        'task': 'core.backup_manager.create_weekly_backup',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Every Sunday at 3 AM
    },
}

# Django Channels Configuration (WebSocket)
ASGI_APPLICATION = 'config.asgi.application'
CHANNEL_REDIS_URL = config('CHANNEL_REDIS_URL', default='redis://127.0.0.1:6379/2')
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [CHANNEL_REDIS_URL],
        },
    },
}

# Logging
APP_LOG_LEVEL = config('APP_LOG_LEVEL', default='DEBUG' if DEBUG else 'INFO')
CORE_LOG_LEVEL = config('CORE_LOG_LEVEL', default='DEBUG' if DEBUG else 'INFO')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'json': {
            '()': 'core.error_logging.StructuredFormatter'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'app.log'),
            'formatter': 'verbose',
        },
        'error_file': {
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'errors.log'),
            'level': 'ERROR',
            'formatter': 'json',
        },
        'security_file': {
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'security.log'),
            'formatter': 'json',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console', 'file', 'error_file'],
            'level': APP_LOG_LEVEL,
            'propagate': False,
        },
        'core': {
            'handlers': ['console', 'file', 'error_file', 'security_file'],
            'level': CORE_LOG_LEVEL,
            'propagate': False,
        },
        'django.security': {
            'handlers': ['security_file'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# Click Payment Gateway Configuration
CLICK_MERCHANT_ID = config('CLICK_MERCHANT_ID', default='')
CLICK_SERVICE_ID = config('CLICK_SERVICE_ID', default='')
CLICK_SECRET_KEY = config('CLICK_SECRET_KEY', default='')
CLICK_TEST_MODE = config('CLICK_TEST_MODE', default=True, cast=bool)
CLICK_TEST_URL = config('CLICK_TEST_URL', default='https://sandbox.click.uz')
CLICK_MERCHANT_NAME = config('CLICK_MERCHANT_NAME', default='Hospitoll')

# Payment Settings
PAYMENT_CALLBACK_URL = config('PAYMENT_CALLBACK_URL', default='http://localhost:8000/api/v1/payments/click-callback/')
PAYMENT_RETURN_URL = config('PAYMENT_RETURN_URL', default='http://localhost:3000/payment/success')
PAYMENT_SUCCESS_CALLBACK = config('PAYMENT_SUCCESS_CALLBACK', default='http://localhost:3000/payment/success')
PAYMENT_FAILURE_CALLBACK = config('PAYMENT_FAILURE_CALLBACK', default='http://localhost:3000/payment/failed')

# Stripe Settings (Fallback payment method)
STRIPE_PUBLIC_KEY = config('STRIPE_PUBLIC_KEY', default='')
STRIPE_SECRET_KEY = config('STRIPE_SECRET_KEY', default='')
STRIPE_WEBHOOK_SECRET = config('STRIPE_WEBHOOK_SECRET', default='')

# Invoice Settings
INVOICE_NUMBER_PREFIX = config('INVOICE_NUMBER_PREFIX', default='INV')
INVOICE_PAYMENT_TERMS_DEFAULT = config('INVOICE_PAYMENT_TERMS_DEFAULT', default='Due upon receipt')

# Subscription Auto-Payment
AUTO_PAY_ENABLED = config('AUTO_PAY_ENABLED', default=False, cast=bool)
AUTO_PAY_RETRY_ATTEMPTS = config('AUTO_PAY_RETRY_ATTEMPTS', default=3, cast=int)
AUTO_PAY_RETRY_INTERVAL = config('AUTO_PAY_RETRY_INTERVAL', default=3, cast=int)  # Days between retries

# ============================================================================
# ERROR TRACKING & MONITORING (SENTRY)
# ============================================================================

SENTRY_DSN = config('SENTRY_DSN', default=None)

if SENTRY_DSN and not DEBUG:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
        ],
        traces_sample_rate=0.1,  # 10% of transactions
        send_default_pii=False,
        environment=config('ENVIRONMENT', default='development'),
    )

# ============================================================================
# BACKUP CONFIGURATION
# ============================================================================

BACKUP_DIR = os.path.join(BASE_DIR, 'backups')
BACKUP_RETENTION_DAYS = config('BACKUP_RETENTION_DAYS', default=30, cast=int)

# S3 Backup (Optional)
USE_S3_BACKUP = config('USE_S3_BACKUP', default=False, cast=bool)
if USE_S3_BACKUP:
    AWS_STORAGE_BUCKET_NAME = config('AWS_BACKUP_BUCKET', default='')
    AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='us-east-1')

# ============================================================================
# SECURITY CONFIGURATION
# ============================================================================

# CSRF Settings
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=not DEBUG, cast=bool)
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Strict'

# Session Settings
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=not DEBUG, cast=bool)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 86400  # 24 hours

# Security Headers
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=not DEBUG, cast=bool)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=31536000 if not DEBUG else 0, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=not DEBUG, cast=bool)
SECURE_HSTS_PRELOAD = config('SECURE_HSTS_PRELOAD', default=not DEBUG, cast=bool)
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_SECURITY_POLICY = {
    'default-src': ["'self'"],
    'script-src': ["'self'", "'unsafe-inline'"],
    'style-src': ["'self'", "'unsafe-inline'"],
}

# Admin URL Security (Disable in production if possible)
ADMIN_URL = config('ADMIN_URL', default='admin/')

# ============================================================================
# ADMINS & NOTIFICATIONS
# ============================================================================

ADMINS = [
    ('Hospitoll Admin', 'admin@hospitoll.uz'),
]

MANAGERS = ADMINS
