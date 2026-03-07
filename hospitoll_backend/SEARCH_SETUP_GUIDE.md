# Search & Caching Implementation Guide

Complete setup and integration guide for full-text search and redis caching systems.

## Prerequisites

- Python 3.8+
- Django 3.2+
- PostgreSQL (recommended) or SQLite
- Redis 6.0+
- Redis GUI (optional): Redis Desktop Manager or redis-cli

---

## 1. Installation and Setup

### 1.1 Install Required Packages

```bash
# Backend packages
pip install django-redis==5.3.0
pip install psycopg2-binary==2.9.6  # For PostgreSQL (optional)
pip install redis==4.5.4

# Frontend packages (if not already installed)
cd hospitoll_frontend
npm install debounce --save
npm install axios --save
```

Check `requirements.txt`:

```bash
# In hospitoll_backend/requirements.txt
django-redis==5.3.0
redis==4.5.4
psycopg2-binary==2.9.6  # Optional for PostgreSQL
```

### 1.2 Redis Installation

#### Windows (WSL2)

```bash
# Install Redis
wsl --install
wsl
sudo apt-get update
sudo apt-get install redis-server

# Start Redis
redis-server

# In another terminal, test connection
redis-cli ping
# Should return: PONG
```

#### macOS

```bash
# Install via Homebrew
brew install redis

# Start Redis (background)
brew services start redis

# Test connection
redis-cli ping
# Should return: PONG
```

#### Linux

```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# Start Redis
sudo systemctl start redis-server

# Test connection
redis-cli ping
```

#### Docker (Recommended for Development)

```bash
# Run Redis in Docker
docker run -d \
  --name hospitoll-redis \
  -p 6379:6379 \
  redis:7-alpine

# Test connection
redis-cli ping
```

### 1.3 Verify Redis Configuration

```bash
# Check Redis info
redis-cli info

# Check database separation
redis-cli SELECT 0  # Celery DB
redis-cli SELECT 1  # Cache DB
redis-cli DBSIZE    # Check current DB size

# Example output
# redis:6379[1]> DBSIZE
# (integer) 2341
```

---

## 2. Django Configuration

### 2.1 Update settings.py

```python
# config/settings.py

INSTALLED_APPS = [
    # ... other apps
    'apps.search',  # ADD THIS
]

# Add CACHES configuration AFTER CELERY settings
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_KEEPALIVE': True,
            'HEALTH_CHECK_INTERVAL': 30,
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'IGNORE_EXCEPTIONS': True,
        }
    }
}

CACHE_TIMEOUT = int(os.getenv('CACHE_TIMEOUT', 300))

# Search Configuration (Optional)
SEARCH_CONFIG = {
    'MIN_QUERY_LENGTH': 3,
    'MAX_RESULTS_PER_MODEL': 100,
    'DEFAULT_LIMIT': 20,
    'CACHE_TIMEOUT': 900,  # 15 minutes
}
```

### 2.2 Update .env

```bash
# .env or .env.local

# Redis Configuration
CACHE_LOCATION=redis://127.0.0.1:6379/1
CACHE_TIMEOUT=300

# Alternative for different Redis host
# CACHE_LOCATION=redis://redis-host:6379/1

# Optional: For Redis with password
# CACHE_LOCATION=redis://:password@redis-host:6379/1
```

### 2.3 Update urls.py

```python
# config/urls.py

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Add search URLs
    path('api/v1/', include('apps.search.urls')),
    
    # ... other URL patterns
]
```

---

## 3. Run Migrations and Verification

### 3.1 Create Search App if Not Exists

```bash
cd hospitoll_backend

# Check if apps/search directory exists
ls apps/search/

# If not, create it
python manage.py startapp search apps/search
```

### 3.2 Run Migrations

```bash
# Make migrations (should show no changes for search app)
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Verify apps.search is installed
python manage.py showmigrations search
```

### 3.3 Verify Installation

```bash
# Test Django setup
python manage.py shell

# In Django shell
>>> from django.core.cache import cache
>>> cache.set('test_key', 'test_value', 60)
>>> cache.get('test_key')
'test_value'
>>> cache.delete('test_key')
>>> print("✓ Cache working!")
```

---

## 4. Database Setup for Search

### 4.1 For PostgreSQL (Recommended)

```sql
-- Connect to your database
psql -U postgres -d hospitoll

-- Verify full-text search support
SELECT * FROM pg_extension WHERE extname = 'uuid-ossp';

-- No action needed - PostgreSQL has FTS built-in
-- SearchVector, SearchQuery, and SearchRank will work automatically
```

### 4.2 For SQLite (Fallback)

If using SQLite, search will automatically use case-insensitive queries:

```python
# Fallback example (in core/search_service.py)
# When PostgreSQL not available:
Doctor.objects.filter(
    Q(first_name__icontains=query) |
    Q(last_name__icontains=query) |
    Q(specialty__name__icontains=query)
)[:limit]
```

---

## 5. Integration with Existing Models

### 5.1 Update Existing ViewSets to Use Cache

```python
# Example: doctors/views.py

from core.cache_service import CacheService, CacheInvalidationService
from rest_framework import viewsets
from rest_framework.decorators import action

class DoctorViewSet(viewsets.ModelViewSet):
    queryset = Doctor.objects.all()
    serializer_class = DoctorSerializer

    def list(self, request, *args, **kwargs):
        """List doctors with caching"""
        # Try cache first
        cache_key = f'doctors:list:{request.query_params.get("clinic_id", "all")}'
        cached = CacheService.get(cache_key)
        if cached:
            return Response(cached)
        
        # Fetch and cache
        response = super().list(request, *args, **kwargs)
        CacheService.set(cache_key, response.data, timeout=3600)
        return response

    def update(self, request, *args, **kwargs):
        """Update doctor and invalidate cache"""
        # Invalidate cache
        CacheInvalidationService.invalidate_doctor_cache(kwargs.get('pk'))
        
        # Update and return
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Delete doctor and invalidate cache"""
        doctor_id = kwargs.get('pk')
        CacheInvalidationService.invalidate_doctor_cache(doctor_id)
        return super().destroy(request, *args, **kwargs)
```

### 5.2 Add Cache Invalidation to Model Signals

```python
# apps/doctors/signals.py

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from core.cache_service import CacheInvalidationService
from .models import Doctor

@receiver(post_save, sender=Doctor)
def invalidate_doctor_cache(sender, instance, created, **kwargs):
    """Invalidate cache when doctor is saved"""
    CacheInvalidationService.invalidate_doctor_cache(instance.id)

@receiver(post_delete, sender=Doctor)
def invalidate_doctor_cache_delete(sender, instance, **kwargs):
    """Invalidate cache when doctor is deleted"""
    CacheInvalidationService.invalidate_doctor_cache(instance.id)

# In apps.py:
# class DoctorsConfig(AppConfig):
#     name = 'apps.doctors'
#     def ready(self):
#         import apps.doctors.signals
```

---

## 6. Testing the Implementation

### 6.1 Run Test Suite

```bash
# Run search tests
python manage.py test test_search_functionality

# Or with verbose output
python test_search_functionality.py

# Example output:
# 🧪 SEARCH AND CACHING TEST SUITE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📋 SearchServiceTests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ✓ Doctor search success: Found 5 results
# ✓ Clinic search success: Found 3 clinics
# ✓ Query length validation works: Query must be at least 3 characters
# ...
# 📊 TEST RESULTS
# Total Tests: 15
# ✅ Passed: 14
# ❌ Failed: 1
# Success Rate: 93.3%
```

### 6.2 Manual API Testing

```bash
# 1. Start development server
python manage.py runserver

# In another terminal:

# 2. Get authentication token
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass"}'

# 3. Store token
TOKEN="your_token_here"

# 4. Test search endpoint
curl -X GET "http://localhost:8000/api/v1/search/?q=john&models=doctors" \
  -H "Authorization: Bearer $TOKEN"

# 5. Test suggestions
curl -X GET "http://localhost:8000/api/v1/search/suggestions/?q=jo" \
  -H "Authorization: Bearer $TOKEN"

# 6. If admin, test cache management
curl -X POST http://localhost:8000/api/v1/cache/clear/ \
  -H "Authorization: Bearer $TOKEN"
```

### 6.3 Test via Django Shell

```bash
python manage.py shell

# Test search service
>>> from core.search_service import FullTextSearchService
>>> results = FullTextSearchService.search('john', models=['doctors'], limit=10)
>>> print(f"Found {results['total_count']} results")

# Test caching
>>> from core.cache_service import CacheService
>>> CacheService.set('test:key', {'data': 'value'}, timeout=3600)
>>> value = CacheService.get('test:key')
>>> print(value)

# Test cache invalidation
>>> from core.cache_service import CacheInvalidationService
>>> CacheInvalidationService.invalidate_doctor_cache(1)
>>> print("✓ Cache invalidated")
```

---

## 7. Frontend Integration

### 7.1 Add Search to Navigation

```jsx
// src/components/Navigation.jsx

import SearchBar from '@/components/SearchBar';
import SearchResults from '@/components/SearchResults';
import { useSearch } from '@/hooks/useSearch';

export function Navigation() {
  const { results, loading, error, query } = useSearch();

  return (
    <nav>
      {/* ... other nav items */}
      <SearchBar
        placeholder="🔍 Shifokor, klinika qidiring..."
        onResultsChange={(r) => console.log(r)}
      />
      <SearchResults 
        results={results}
        loading={loading}
        error={error}
        query={query}
      />
    </nav>
  );
}
```

### 7.2 Add Search Page

```jsx
// src/pages/SearchPage.jsx

import SearchDemo from '@/pages/SearchDemo';

export function SearchPage() {
  return <SearchDemo />;
}

// In router
routes: [
  { path: '/search', element: <SearchPage /> }
]
```

### 7.3 Use Search Hooks in Components

```jsx
import { useDoctorSearch } from '@/hooks/useSearch';

function DoctorFinder() {
  const {
    query,
    results,
    suggestions,
    handleQueryChange,
    performSearch
  } = useDoctorSearch();

  return (
    <div>
      <input
        value={query}
        onChange={(e) => handleQueryChange(e.target.value)}
        placeholder="Shifokor qidiring..."
      />
      {results?.doctors?.items?.map(doctor => (
        <div key={doctor.id}>{doctor.name}</div>
      ))}
    </div>
  );
}
```

---

## 8. Performance Optimization

### 8.1 Cache Warming

```python
# management/commands/warm_cache.py

from django.core.management.base import BaseCommand
from core.cache_service import CacheService
from apps.doctors.models import Doctor
from apps.clinics.models import Clinic

class Command(BaseCommand):
    help = 'Warm up the cache with frequently accessed data'

    def handle(self, *args, **options):
        # Cache all doctors
        doctors = Doctor.objects.select_related('clinic', 'specialty')[:100]
        for doctor in doctors:
            CacheService.set(
                f'doctors:detail:{doctor.id}',
                serialize_doctor(doctor),
                timeout=3600
            )
        
        # Cache all clinics
        clinics = Clinic.objects.all()
        for clinic in clinics:
            CacheService.set(
                f'clinics:detail:{clinic.id}',
                serialize_clinic(clinic),
                timeout=3600
            )
        
        self.stdout.write(
            self.style.SUCCESS('Cache warmed successfully!')
        )

# Run:
# python manage.py warm_cache
```

### 8.2 Monitor Cache Hit Rate

```python
# management/commands/cache_stats.py

from django.core.management.base import BaseCommand
from django.core.cache import cache
import redis

class Command(BaseCommand):
    help = 'Display cache statistics'

    def handle(self, *args, **options):
        # Get Redis connection
        r = redis.Redis(host='localhost', port=6379, db=1)
        
        # Get stats
        info = r.info()
        self.stdout.write(f"Used Memory: {info['used_memory_human']}")
        self.stdout.write(f"Connected Clients: {info['connected_clients']}")
        
        # Get cache size
        size = r.dbsize()
        self.stdout.write(f"Cache Keys: {size}")
```

### 8.3 Cache Expiration Policy

```python
# config/settings.py

# Different timeouts for different data types
CACHE_TIMEOUTS = {
    'doctors_list': 3600,           # 1 hour
    'doctors_detail': 1800,         # 30 minutes
    'appointments': 300,            # 5 minutes - changes frequently
    'availability': 600,            # 10 minutes
    'clinics_list': 3600,           # 1 hour
    'patient_records': 1800,        # 30 minutes
    'search_results': 900,          # 15 minutes
    'statistics': 3600,             # 1 hour
}
```

---

## 9. Troubleshooting

### 9.1 Redis Connection Issues

```bash
# Check if Redis is running
redis-cli ping
# Should return: PONG

# If not:
redis-server  # Start Redis

# Check Redis info
redis-cli info
```

### 9.2 Cache Not Working

```python
# In Django shell
>>> from django.core.cache import cache
>>> cache.set('test', 'value')
Traceback: ConnectionError

# Check settings
>>> from django.conf import settings
>>> print(settings.CACHES)

# Check Redis connectivity
>>> import redis
>>> r = redis.Redis(host='localhost', port=6379, db=1)
>>> r.ping()
True
```

### 9.3 PostgreSQL Full-Text Search Not Working

```python
# Verify FTS support
>>> from django.db import connection
>>> from django.contrib.postgres.search import SearchVector

# Try simple search
>>> from apps.doctors.models import Doctor
>>> Doctor.objects.filter(first_name__icontains='john')

# If error, check PostgreSQL:
psql> SELECT * FROM pg_extension WHERE extname = 'vectors';
```

### 9.4 Clear All Cache When Stuck

```bash
# Via redis-cli
redis-cli SELECT 1
redis-cli FLUSHDB

# Via Django shell
>>> from django.core.cache import cache
>>> cache.clear()
>>> print("✓ Cache cleared")
```

---

## 10. Monitoring and Maintenance

### 10.1 Regular Cache Monitoring

```bash
# Create monitoring script: management/commands/monitor_cache.py

from django.core.management.base import BaseCommand
from django.utils import timezone
import redis
import time

class Command(BaseCommand):
    def handle(self, *args, **options):
        r = redis.Redis(host='localhost', port=6379, db=1)
        
        while True:
            info = r.info()
            print(f"[{timezone.now()}] Keys: {r.dbsize()}, Memory: {info['used_memory_human']}")
            time.sleep(10)

# Run: python manage.py monitor_cache
```

### 10.2 Cache Hit Ratio

```python
# Track cache hits/misses
from django.core.cache import cache

@property
def cache_hit_ratio(self):
    hits = getattr(self, '_cache_hits', 0)
    misses = getattr(self, '_cache_misses', 0)
    total = hits + misses
    if total == 0:
        return 0
    return (hits / total) * 100
```

### 10.3 Scheduled Cache Cleanup

```python
# celery_beat.py or tasks.py

from celery import shared_task
from core.cache_service import CacheInvalidationService
import logging

logger = logging.getLogger(__name__)

@shared_task
def cleanup_old_cache():
    """Clean up old cache entries daily"""
    CacheInvalidationService.invalidate_all()
    logger.info("Cache cleanup completed")

# In celery_beat.py:
# from celery.schedules import crontab
# 
# app.conf.beat_schedule = {
#     'cleanup-cache': {
#         'task': 'tasks.cleanup_old_cache',
#         'schedule': crontab(hour=3, minute=0),  # 3:00 AM daily
#     },
# }
```

---

## 11. Deployment Checklist

- [ ] Redis installed and running in production
- [ ] Redis configured with persistence (RDB/AOF)
- [ ] Redis monitoring enabled
- [ ] Django settings.py INSTALLED_APPS includes 'apps.search'
- [ ] CACHES configured with production Redis URL
- [ ] .env file has correct CACHE_LOCATION
- [ ] Database migrations run (`python manage.py migrate`)
- [ ] Search endpoints tested (`/api/v1/search/`)
- [ ] Cache invalidation working with signals
- [ ] Frontend SearchBar component integrated
- [ ] Search hooks imported in components
- [ ] Tests passing (`python manage.py test apps.search`)
- [ ] Performance benchmarked (< 100ms search response)
- [ ] Monitoring set up for cache hit ratio
- [ ] Redis backup strategy configured

---

## 12. Performance Benchmarks

Expected performance after setup:

| Operation | Latency |
|-----------|---------|
| First search query | 50-150ms |
| Cached search query | < 10ms |
| Cache hit rate (after warmup) | 70-85% |
| Doctor search w/ filters | 30-80ms |
| Suggestions autocomplete | < 20ms |
| Cache invalidation | < 5ms |

---

## 13. Documentation Links

- Django Cache Framework: https://docs.djangoproject.com/en/3.2/topics/cache/
- django-redis: https://github.com/jazzband/django-redis
- PostgreSQL Full-Text Search: https://www.postgresql.org/docs/current/textsearch.html
- Redis Documentation: https://redis.io/documentation
- Search API Documentation: [See SEARCH_API_DOCUMENTATION.md](./SEARCH_API_DOCUMENTATION.md)

---

## Support

For issues or questions:
1. Check Troubleshooting section
2. Review test output
3. Check logs: `tail -f logs/search.log`
4. Contact: api-support@hospitoll.uz

---

Last Updated: 2024-02-20
Version: 1.0.0
