# Search & Caching Implementation - Verification Checklist

Complete checklist for verifying that full-text search and caching systems are properly implemented and working.

---

## ✅ BACKEND SETUP

### Infrastructure

- [ ] Redis installed and running
  ```bash
  redis-cli ping
  # Expected: PONG
  ```

- [ ] Redis accessible on correct port (default 6379)
  ```bash
  redis-cli -h 127.0.0.1 -p 6379 ping
  ```

- [ ] Separate Redis databases configured
  ```bash
  redis-cli SELECT 0  # Celery DB
  redis-cli SELECT 1  # Cache DB
  redis-cli DBSIZE
  ```

- [ ] Redis persistence enabled (optional but recommended)
  ```bash
  # Check redis.conf for save settings
  # Default: save "" (no save) to "save 900 1" (save after 1 change in 15 min)
  ```

### Python Packages

- [ ] `django-redis` installed (version 5.3.0+)
  ```bash
  pip list | grep django-redis
  ```

- [ ] `redis` package installed (version 4.5.0+)
  ```bash
  pip list | grep redis
  ```

- [ ] `psycopg2-binary` installed (for PostgreSQL support)
  ```bash
  pip list | grep psycopg2
  ```

### Django Configuration

- [ ] `apps.search` added to INSTALLED_APPS
  ```bash
  grep "apps.search" config/settings.py
  ```

- [ ] CACHES configured with RedisCache backend
  ```bash
  grep -A 10 "CACHES = {" config/settings.py
  # Should show:
  # 'BACKEND': 'django.core.cache.backends.redis.RedisCache',
  # 'LOCATION': 'redis://127.0.0.1:6379/1',
  ```

- [ ] CACHE_TIMEOUT set (default 300 seconds)
  ```bash
  grep "CACHE_TIMEOUT" config/settings.py
  ```

- [ ] cache URLs configured in urls.py
  ```bash
  grep "api/v1/" config/urls.py | grep search
  ```

### Environment Variables

- [ ] .env has CACHE_LOCATION variable
  ```bash
  grep CACHE_LOCATION .env
  ```

- [ ] .env has CACHE_TIMEOUT variable
  ```bash
  grep CACHE_TIMEOUT .env
  ```

### Core Files Created

- [ ] `core/search_service.py` exists (450+ lines)
  ```bash
  wc -l core/search_service.py
  # Should show > 450
  ```

- [ ] `core/cache_service.py` exists (480+ lines)
  ```bash
  wc -l core/cache_service.py
  # Should show > 480
  ```

- [ ] `apps/search/views.py` exists (370+ lines)
  ```bash
  wc -l apps/search/views.py
  # Should show > 370
  ```

- [ ] `apps/search/urls.py` exists
  ```bash
  cat apps/search/urls.py | head -20
  ```

- [ ] `apps/search/apps.py` exists
  ```bash
  cat apps/search/apps.py
  ```

### Database & Migrations

- [ ] Migrations run successfully
  ```bash
  python manage.py migrate
  # Should say: No changes detected
  ```

- [ ] No migration errors for search app
  ```bash
  python manage.py showmigrations apps.search
  ```

- [ ] Django shell test passes
  ```bash
  python manage.py shell
  >>> from django.core.cache import cache
  >>> cache.set('test', 'value', 60)
  >>> print(cache.get('test'))
  'value'
  >>> exit()
  ```

---

## ✅ BACKEND API ENDPOINTS

### Service Layer Tests

- [ ] FullTextSearchService imports without errors
  ```bash
  python manage.py shell
  >>> from core.search_service import FullTextSearchService
  >>> print("✓ Import successful")
  ```

- [ ] CacheService imports without errors
  ```bash
  python manage.py shell
  >>> from core.cache_service import CacheService
  >>> print("✓ Import successful")
  ```

- [ ] Can execute basic search
  ```bash
  python manage.py shell
  >>> from core.search_service import FullTextSearchService
  >>> results = FullTextSearchService.search('test', ['doctors'], limit=10)
  >>> print(f"Found {results['total_count']} results")
  ```

- [ ] Can cache and retrieve data
  ```bash
  python manage.py shell
  >>> from core.cache_service import CacheService
  >>> CacheService.set('test:key', {'data': 123}, timeout=60)
  >>> CacheService.get('test:key')
  {'data': 123}
  ```

### HTTP Endpoints

- [ ] GET `/api/v1/search/` endpoint exists
  ```bash
  curl -v http://localhost:8000/api/v1/search/
  # Should return 401 (unauthorized) or search results
  ```

- [ ] GET `/api/v1/search/suggestions/` endpoint exists
  ```bash
  curl -v http://localhost:8000/api/v1/search/suggestions/?q=test
  ```

- [ ] GET `/api/v1/search/doctors/` endpoint exists
  ```bash
  curl -v http://localhost:8000/api/v1/search/doctors/
  ```

- [ ] GET `/api/v1/search/specialties/` endpoint exists
  ```bash
  curl -v http://localhost:8000/api/v1/search/specialties/
  ```

- [ ] GET `/api/v1/search/doctors/{id}/availability/` endpoint exists
  ```bash
  curl -v http://localhost:8000/api/v1/search/doctors/1/availability/?date=2024-02-20
  ```

- [ ] POST `/api/v1/cache/clear/` endpoint exists (admin)
  ```bash
  curl -X POST http://localhost:8000/api/v1/cache/clear/
  # Should return 401 or 403 (unless admin) or success
  ```

- [ ] POST `/api/v1/cache/invalidate/` endpoint exists (admin)
  ```bash
  curl -X POST http://localhost:8000/api/v1/cache/invalidate/ \
    -H "Content-Type: application/json" \
    -d '{"patterns":["doctors:*"]}'
  ```

- [ ] GET `/api/v1/cache/stats/` endpoint exists (admin)
  ```bash
  curl http://localhost:8000/api/v1/cache/stats/
  ```

### Authenticated Requests

- [ ] Search endpoint works with authentication
  ```bash
  TOKEN="$(curl -X POST http://localhost:8000/api/token/ \
    -H "Content-Type: application/json" \
    -d '{"username":"user","password":"pass"}' | jq -r '.access')"
  
  curl -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8000/api/v1/search/?q=test"
  ```

- [ ] Results returned in correct format
  ```bash
  # Response should include:
  # - query
  # - results (with doctors, clinics, etc.)
  # - total_count
  # - cached (boolean)
  # - execution_time_ms
  ```

---

## ✅ FRONTEND SETUP

### File Structure

- [ ] `src/services/SearchService.js` exists
  ```bash
  wc -l src/services/SearchService.js
  # Should show > 200
  ```

- [ ] `src/hooks/useSearch.js` exists
  ```bash
  wc -l src/hooks/useSearch.js
  # Should show > 300
  ```

- [ ] `src/components/SearchBar.jsx` exists
  ```bash
  wc -l src/components/SearchBar.jsx
  # Should show > 150
  ```

- [ ] `src/components/SearchResults.jsx` exists
  ```bash
  wc -l src/components/SearchResults.jsx
  # Should show > 150
  ```

- [ ] `src/pages/SearchDemo.jsx` exists
  ```bash
  wc -l src/pages/SearchDemo.jsx
  # Should show > 200
  ```

### Imports & Dependencies

- [ ] All necessary npm packages installed
  ```bash
  npm list axios debounce
  # Should show both packages
  ```

- [ ] SearchService.js imports work
  ```bash
  grep -E "^import|^export" src/services/SearchService.js
  ```

- [ ] useSearch hook imports work
  ```bash
  grep -E "^import|^export" src/hooks/useSearch.js
  ```

- [ ] SearchBar component imports work
  ```bash
  grep -E "^import|^export" src/components/SearchBar.jsx
  ```

### Frontend Testing

- [ ] No TypeScript/syntax errors in SearchService
  ```bash
  # Try importing in Node
  node -e "require('./src/services/SearchService.js')" 2>&1 | grep -i error || echo "✓ No errors"
  ```

- [ ] React components compile without errors
  ```bash
  npm run build 2>&1 | grep -i error | head -5
  ```

- [ ] Demo page renders in browser
  ```bash
  npm run dev
  # Navigate to /search in browser
  ```

---

## ✅ INTEGRATION TESTS

### Service Layer

- [ ] Run backend tests
  ```bash
  python test_search_functionality.py
  # Expected output shows all tests passing
  ```

- [ ] SearchServiceTests pass (5+ tests)
  ```bash
  python manage.py test test_search_functionality.SearchServiceTests -v 2
  ```

- [ ] CacheServiceTests pass (6+ tests)
  ```bash
  python manage.py test test_search_functionality.CacheServiceTests -v 2
  ```

- [ ] CacheInvalidationTests pass (3+ tests)
  ```bash
  python manage.py test test_search_functionality.CacheInvalidationTests -v 2
  ```

### Frontend Hooks

- [ ] useSearch hook works in component
  ```bash
  # Create test component with useSearch hook
  # Verify no console errors
  ```

- [ ] useDoctorSearch hook works
  ```bash
  # Create test component with useDoctorSearch hook
  # Test filter changes
  ```

- [ ] useMultiModelSearch hook works
  ```bash
  # Create test component with useMultiModelSearch hook
  # Test model selection
  ```

- [ ] useAutocompleteSearch hook works
  ```bash
  # Create test component with useAutocompleteSearch hook
  # Verify debouncing works
  ```

### End-to-End

- [ ] User can search for doctor
  ```
  1. Open /search page in browser
  2. Type "john" in search box
  3. Wait 300ms for debounce
  4. See results appear
  ```

- [ ] User can filter by specialty
  ```
  1. Open doctor search page
  2. Select specialty dropdown
  3. Results update with filtered doctors
  ```

- [ ] User can see suggestions
  ```
  1. Type partial text like "jo" in search
  2. See autocomplete suggestions dropdown
  3. Click suggestion to search
  ```

- [ ] Results display correctly
  ```
  1. Search completes
  2. Results show organized by model
  3. Each result has correct information
  4. Click result works
  ```

---

## ✅ PERFORMANCE VERIFICATION

### Search Performance

- [ ] First search < 200ms
  ```bash
  time curl -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8000/api/v1/search/?q=john" \
    | head -c 1
  # Real time should be < 200ms
  ```

- [ ] Cached search < 10ms
  ```bash
  # Run same search twice, second should be much faster
  time curl -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8000/api/v1/search/?q=john" | head -c 1
  ```

- [ ] Suggestions < 50ms
  ```bash
  time curl -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8000/api/v1/search/suggestions/?q=jo" | head -c 1
  ```

- [ ] Doctor availability < 100ms
  ```bash
  time curl -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8000/api/v1/search/doctors/1/availability/?date=2024-02-20" | head -c 1
  ```

### Cache Effectiveness

- [ ] Cache hit rate > 50%
  ```bash
  # Make same search 10 times, check response headers or stats
  redis-cli SELECT 1
  redis-cli DBSIZE
  # Should show > 20 keys (searches being cached)
  ```

- [ ] Pattern deletion works
  ```bash
  redis-cli SELECT 1
  redis-cli KEYS "doctors:*" | wc -l
  # Should show > 0
  
  # Call API to invalidate
  curl -X POST http://localhost:8000/api/v1/cache/invalidate-doctors/
  
  redis-cli KEYS "doctors:*" | wc -l
  # Should show 0
  ```

### Memory Usage

- [ ] Redis memory usage reasonable
  ```bash
  redis-cli INFO memory | grep used_memory_human
  # Should be < 100MB for cache DB
  ```

- [ ] No memory leaks in frontend
  ```bash
  # Open DevTools > Performance
  # Do multiple searches
  # Memory should remain stable
  ```

---

## ✅ DATABASE COMPATIBILITY

### PostgreSQL (Recommended)

- [ ] Full-text search works with PostgreSQL
  ```bash
  # If using PostgreSQL, verify:
  python manage.py shell
  >>> from django.contrib.postgres.search import SearchVector, SearchQuery
  >>> from apps.doctors.models import Doctor
  >>> Doctor.objects.annotate(search=SearchVector('first_name')).exists()
  True
  ```

- [ ] SearchRank ordering works
  ```bash
  # Search results should be ordered by relevance
  # Top results should match query best
  ```

### SQLite (Fallback)

- [ ] Fallback query works with SQLite
  ```bash
  # If using SQLite, verify searches use icontains:
  python manage.py shell
  >>> from apps.doctors.models import Doctor
  >>> Doctor.objects.filter(first_name__icontains='john').exists()
  ```

---

## ✅ DOCUMENTATION

### Backend Documentation

- [ ] `SEARCH_API_DOCUMENTATION.md` exists
  ```bash
  ls -lh hospitoll_backend/SEARCH_API_DOCUMENTATION.md
  # Should be > 10KB
  ```

- [ ] `SEARCH_SETUP_GUIDE.md` exists
  ```bash
  ls -lh hospitoll_backend/SEARCH_SETUP_GUIDE.md
  # Should be > 15KB
  ```

- [ ] `SEARCH_QUICK_START.md` exists
  ```bash
  ls -lh hospitoll_backend/SEARCH_QUICK_START.md
  # Should be > 5KB
  ```

### Frontend Documentation

- [ ] `SEARCH_INTEGRATION_EXAMPLES.jsx` exists
  ```bash
  ls -lh hospitoll_frontend/SEARCH_INTEGRATION_EXAMPLES.jsx
  # Should be > 10KB
  ```

---

## ✅ DEPLOYMENT READINESS

### Code Quality

- [ ] No syntax errors in Python files
  ```bash
  python -m py_compile core/search_service.py
  python -m py_compile core/cache_service.py
  python -m py_compile apps/search/views.py
  # Should complete without errors
  ```

- [ ] No console errors in frontend
  ```bash
  npm run lint 2>&1 | head -10
  # Should show no errors (or only warnings)
  ```

### Security

- [ ] Search endpoints require authentication (non-admin)
  ```bash
  curl -v "http://localhost:8000/api/v1/search/?q=test"
  # Should return 401 or redirect
  ```

- [ ] Cache endpoints require admin permission
  ```bash
  curl -v -X POST "http://localhost:8000/api/v1/cache/clear/"
  # Should return 403 (non-admin)
  ```

- [ ] No sensitive data logged
  ```bash
  grep -r "password\|token\|secret" core/search_service.py apps/search/
  # Should return no matches
  ```

### Configuration

- [ ] No hardcoded credentials
  ```bash
  grep -r "redis://" --exclude=*.md config/
  # Should only show in settings.py, not hardcoded
  ```

- [ ] .env properly configured
  ```bash
  cat .env | grep -E "CACHE_|REDIS_"
  # Should show environment variables
  ```

---

## ✅ MONITORING & OBSERVABILITY

### Logging

- [ ] Search queries can be logged
  ```python
  # Add to search_service.py if needed
  import logging
  logger = logging.getLogger(__name__)
  logger.info(f"Search executed: {query}")
  ```

- [ ] Cache operations can be logged
  ```python
  # Add to cache_service.py if needed
  logger.debug(f"Cache hit: {key}")
  logger.debug(f"Cache miss: {key}")
  ```

### Error Handling

- [ ] Search gracefully handles empty results
  ```bash
  curl -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8000/api/v1/search/?q=zzzzzzzzzz"
  # Should return 200 with empty results, not 500
  ```

- [ ] Cache handles Redis disconnection
  ```bash
  # Stop Redis
  redis-cli SHUTDOWN
  
  # Try search
  curl -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8000/api/v1/search/?q=test"
  # Should still work (cache disabled but search works)
  ```

---

## ✅ USER ACCEPTANCE TESTING

### Functionality

- [ ] User can search for doctors by name
- [ ] User can search for clinics
- [ ] User can search for appointments
- [ ] User can filter doctors by specialty
- [ ] User can see doctor availability
- [ ] User can get autocomplete suggestions
- [ ] Search results display with correct information
- [ ] User can click results to navigate

### Performance

- [ ] Searches feel responsive (< 200ms)
- [ ] Autocomplete populates quickly (< 50ms)
- [ ] No lag when typing multiple characters
- [ ] Multiple simultaneous searches don't cause issues

### User Experience

- [ ] Search box visible and accessible
- [ ] Error messages are clear
- [ ] Loading indicators show progress
- [ ] Results are well-organized
- [ ] Mobile experience is good

---

## ✅ FINAL VERIFICATION

```bash
# Run this checklist script
cat << 'EOF' > verify_search.sh
#!/bin/bash

echo "🔍 Search & Caching System Verification"
echo "========================================"

# 1. Redis
echo "1. Redis Status:"
redis-cli ping && echo "✓ Redis running" || echo "✗ Redis not running"

# 2. Python packages
echo "2. Python Packages:"
pip list | grep -q django-redis && echo "✓ django-redis installed" || echo "✗ django-redis missing"
pip list | grep -q redis && echo "✓ redis installed" || echo "✗ redis missing"

# 3. Django config
echo "3. Django Configuration:"
grep -q "apps.search" config/settings.py && echo "✓ apps.search in INSTALLED_APPS" || echo "✗ apps.search not configured"
grep -q "CACHES" config/settings.py && echo "✓ CACHES configured" || echo "✗ CACHES not configured"

# 4. Core files
echo "4. Core Files:"
[ -f core/search_service.py ] && echo "✓ search_service.py exists" || echo "✗ search_service.py missing"
[ -f core/cache_service.py ] && echo "✓ cache_service.py exists" || echo "✗ cache_service.py missing"
[ -f apps/search/views.py ] && echo "✓ search/views.py exists" || echo "✗ search/views.py missing"

# 5. Cache test
echo "5. Cache Test:"
python manage.py shell << 'PYTHON'
try:
    from django.core.cache import cache
    cache.set('verify', 'ok', 60)
    if cache.get('verify') == 'ok':
        print("✓ Cache working")
    else:
        print("✗ Cache not working")
except Exception as e:
    print(f"✗ Cache error: {e}")
PYTHON

# 6. Search service test
echo "6. Search Service Test:"
python manage.py shell << 'PYTHON'
try:
    from core.search_service import FullTextSearchService
    results = FullTextSearchService.search('test', ['doctors'], limit=5)
    print(f"✓ Search working ({results['total_count']} results)")
except Exception as e:
    print(f"✗ Search error: {e}")
PYTHON

echo "========================================"
echo "✅ Verification Complete!"
EOF

chmod +x verify_search.sh
./verify_search.sh
```

---

## Summary

- **Total Checklist Items**: 100+
- **Critical Items** (must have): 30
- **Important Items** (should have): 40
- **Optional Items** (nice to have): 30+

**Implementation Status Target**: 95% of items checked ✓

---

Last Updated: 2024-02-20
For help: See SEARCH_SETUP_GUIDE.md or SEARCH_API_DOCUMENTATION.md
