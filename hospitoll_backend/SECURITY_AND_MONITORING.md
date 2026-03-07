# Error Logging, Backup System & Security Audit
## Hospitoll Backend - Setup & Usage Guide

---

## 📋 Overview

Implemented comprehensive error tracking, automated backup system, and security hardening:

### ✅ Features Implemented:

1. **Error Logging & Monitoring**
   - Sentry integration for production error tracking
   - JSON structured logging to files
   - Error alerting to admins
   - Security event logging

2. **Automated Backup System**
   - Daily database backups
   - Weekly full backups (database + media)
   - Automatic cleanup of old backups
   - Manual backup management commands
   - SQLite & PostgreSQL support

3. **Security Hardening**
   - Security headers (CSP, X-Frame-Options, etc.)
   - Rate limiting (IP & user-based)
   - CSRF protection enhancement
   - SQL injection & XSS prevention
   - Input sanitization
   - Authentication security monitoring

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd hospitoll_backend
pip install -r requirements.txt
```

### 2. Configure Environment

Update `.env` file:

```bash
# Error Tracking (Sentry)
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id

# Backup Settings
BACKUP_RETENTION_DAYS=30
USE_S3_BACKUP=False

# Environment
ENVIRONMENT=development
```

### 3. Create Log Directory

```bash
mkdir -p logs
```

---

## 📊 Error Logging

### Configuration

**File:** `core/error_logging.py`

**Features:**
- Automatic exception catching
- Structured JSON logging
- Error analytics
- Critical error alerts to admins

### Usage

#### Logging Errors in Code

```python
from core.error_logging import ErrorLogger

# Log simple error
ErrorLogger.log_error(
    error_type='api_error',
    message='User not found',
    context={'user_id': 123},
    severity='warning'
)

# Log exception
try:
    # some operation
    pass
except Exception as e:
    ErrorLogger.log_exception(e, context={'operation': 'create_user'})
```

#### Using Decorator

```python
from core.error_logging import api_error_handler
from rest_framework.views import APIView

class MyAPIView(APIView):
    @api_error_handler
    def post(self, request):
        # Errors are automatically logged
        return Response({'success': True})
```

### Log Files

- `logs/app.log` - General application logs
- `logs/errors.log` - Error logs (JSON format)
- `logs/security.log` - Security events (JSON format)

### Sentry Integration (Production)

1. Create Sentry account: https://sentry.io
2. Create Django project
3. Copy DSN to `.env`:
   ```
   SENTRY_DSN=https://xxx@sentry.io/xxx
   ```
4. Restart Django - errors will be tracked automatically

---

## 🔐 Backup System

### Manual Backups

```bash
# Create full backup (database + media)
python manage.py backup --full

# Database only
python manage.py backup --db-only

# Media files only
python manage.py backup --media-only

# List all backups
python manage.py backup --list

# Delete old backups (older than 30 days)
python manage.py backup --cleanup 30
```

### Automated Backups (Celery)

**Schedule:**
- Daily backup: **2:00 AM** (UTC+5)
- Weekly backup: **Sunday 3:00 AM** (UTC+5)

**Configure in Celery Beat:**

```bash
# Terminal 1 - Start Celery Worker
celery -A config worker -l info

# Terminal 2 - Start Celery Beat (for scheduled tasks)
celery -A config beat -l info
```

### Programmatic Backup

```python
from core.backup_manager import BackupManager

# Create backup
backup_info = BackupManager.create_full_backup('my_backup')

# List backups
backups = BackupManager.list_backups()

# Cleanup old backups
BackupManager.delete_old_backups(retention_days=30)

# Restore from backup
BackupManager.restore_database_backup('db_backup_20260214_020000')
```

### Backup Location

- Default: `hospitoll_backend/backups/`
- Database backup: `.sql` or `.dump` file
- Media backup: `.zip` file
- Manifest: `_manifest.json` file

### Example Manifest Structure

```json
{
  "backup_name": "full_backup_20260214_020000",
  "timestamp": "2026-02-14T02:00:00.000000",
  "database": {
    "name": "full_backup_20260214_020000_db",
    "size_mb": 15.5,
    "type": "database"
  },
  "media": {
    "name": "full_backup_20260214_020000_media",
    "size_mb": 45.2,
    "type": "media"
  },
  "total_size_mb": 60.7
}
```

---

## 🛡️ Security Hardening

### 1. Security Headers

Automatically added to all responses:

```
Content-Security-Policy: default-src 'self'; script-src 'self'...
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Strict-Transport-Security: max-age=31536000 (HTTPS only)
```

### 2. Rate Limiting

**By IP Address:**
```python
from core.security import rate_limit_by_ip

@rate_limit_by_ip(limit=100, window=3600)
def my_view(request):
    return Response({'data': 'hello'})
```

**By User:**
```python
from core.security import rate_limit_by_user

@rate_limit_by_user(limit=200, window=3600)
def my_view(request):
    if not request.user.is_authenticated:
        return Response({'error': 'Unauthorized'}, status=401)
    return Response({'data': 'hello'})
```

### 3. Input Sanitization

Automatically checks for:
- SQL injection patterns
- XSS (script tags, JavaScript)
- Suspicious characters

**Example Detection:**
- `' OR '1'='1`  → Blocked
- `<script>alert('xss')</script>` → Blocked
- `; DROP TABLE users;` → Blocked

### 4. CSRF Protection

- Automatic CSRF token validation
- Secure cookie flags (HttpOnly, Secure, SameSite)
- CSRF validation for state-changing requests

### 5. Authentication Security

- Session tracking
- Suspicious login detection
- IP/User-agent monitoring
- 24-hour session retention

### Security Configuration (.env)

```bash
# Change admin URL from default for security
ADMIN_URL=secret_admin_url/

# CSRF cookies are HttpOnly, Secure, SameSite=Strict
# Session cookies are HttpOnly, Secure, SameSite=Lax
# Sessions expire after 24 hours
```

---

## 📈 Monitoring & Analytics

### Error Dashboard

View logs in real-time:

```bash
# Watch error logs
tail -f logs/errors.log

# Watch security logs
tail -f logs/security.log

# Search for errors
grep "ERROR" logs/errors.log | jq '.'
```

### Error Rate Metrics

Track error patterns:

```bash
# Count errors by type
grep "error_type" logs/errors.log | jq '.error_type' | sort | uniq -c

# Find critical errors (last 24h)
grep "critical" logs/errors.log | jq '.timestamp'
```

### Rate Limiting Status

```python
from core.security import RateLimiter

# Check if rate limited
is_limited = RateLimiter.is_rate_limited('user:123', limit=100, window=3600)

# Get remaining requests
remaining = RateLimiter.get_remaining_requests('user:123', limit=100)
print(f"Remaining requests: {remaining}")
```

---

## 🔍 API Endpoints (Optional)

### Error Status Endpoint

```python
# In your API urls.py
path('api/admin/errors/summary/', ErrorSummaryView.as_view())
path('api/admin/errors/list/', ErrorListView.as_view())
path('api/admin/backups/', BackupListView.as_view())
```

---

## 🧪 Testing

### Test Error Logging

```bash
# Use Django shell
python manage.py shell
```

```python
from core.error_logging import ErrorLogger

# Log an error
ErrorLogger.log_error(
    'test_error',
    'This is a test error',
    {'test': True},
    'warning'
)

# Check logs
exit()
```

```bash
cat logs/errors.log | tail -5
```

### Test Rate Limiting

```python
# In Python shell
from core.security import RateLimiter

for i in range(105):
    is_limited = RateLimiter.is_rate_limited('test_user', limit=100, window=3600)
    if is_limited:
        print(f"Rate limited at request {i+1}")
        break
```

### Test Backup System

```bash
# Create backup
python manage.py backup --full

# List backups
python manage.py backup --list

# Check backup files
ls -la backups/

# Restore backup
# python manage.py backup --restore db_backup_20260214_020000
```

---

## 📝 Production Checklist

- [ ] Enable Sentry DSN in `.env`
- [ ] Change `ADMIN_URL` from default
- [ ] Set `DEBUG=False` in `.env`
- [ ] Configure email alerts for critical errors
- [ ] Setup S3 for backup storage (`USE_S3_BACKUP=True`)
- [ ] Enable HTTPS (SSL certificates)
- [ ] Configure firewall rules
- [ ] Setup monitoring for backup success
- [ ] Test backup restore procedure
- [ ] Document admin change procedures

---

## ⚠️ Common Issues

### 1. Logs Directory Not Found
```bash
mkdir -p logs && chmod 755 logs
```

### 2. Sentry Not Capturing Errors
- Check `SENTRY_DSN` is set correctly
- Ensure `DEBUG=False` in production
- Verify `ENVIRONMENT` variable is set

### 3. Backup Fails
- Check disk space: `df -h`
- Verify database credentials
- For PostgreSQL: Ensure `pg_dump` is installed

### 4. Rate Limiting Not Working
- Check Redis is running: `redis-cli ping`
- Verify `CELERY_BROKER_URL` is correct
- Clear Redis cache if needed: `redis-cli FLUSHDB`

---

## 📞 Support

For issues or questions:
- Check Django logs: `logs/app.log`
- Check error logs: `logs/errors.log`
- Check security logs: `logs/security.log`
- Enable debug mode in `.env` for development

---

## 🎯 Next Steps

1. **Deploy to production** with Sentry
2. **Setup automated backups** to S3/Cloud storage
3. **Configure email alerts** for critical errors
4. **Monitor security logs** regularly
5. **Test backup restoration** monthly
6. **Review error trends** weekly

---

**Status:** ✅ PRODUCTION READY  
**Last Updated:** Feb 14, 2026  
**Version:** 1.0.0
