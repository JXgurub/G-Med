# Search & Caching System - Quick Start Guide

Fast integration guide for developers using the search and caching systems.

## 🚀 5-Minute Setup

### Backend Setup

```bash
# 1. Install dependencies
pip install django-redis redis

# 2. Start Redis
redis-server

# 3. Verify Redis
redis-cli ping
# Response: PONG

# 4. Update Django settings (already done in config/settings.py)
# Check: INSTALLED_APPS includes 'apps.search'
# Check: CACHES configured

# 5. Run migrations
python manage.py migrate

# 6. Test
python manage.py shell
>>> from core.cache_service import CacheService
>>> CacheService.set('test', 'works')
>>> CacheService.get('test')
'works'
```

### Frontend Setup

```bash
# No additional setup needed - components ready to use
# Import and use directly:

import { useSearch } from '@/hooks/useSearch';
import SearchBar from '@/components/SearchBar';
```

---

## 🔍 Basic Usage

### Backend: Execute Search

```python
from core.search_service import FullTextSearchService

# Search across all models
results = FullTextSearchService.search(
    query='john',
    models=['doctors', 'clinics'],
    limit=20
)

# results structure:
# {
#   'query': 'john',
#   'results': {
#       'doctors': {'items': [...], 'count': 5},
#       'clinics': {'items': [...], 'count': 3}
#   },
#   'total_count': 8
# }
```

### Backend: Use Caching

```python
from core.cache_service import CacheService

# Set cache
CacheService.set('my:key', {'data': 'value'}, timeout=3600)

# Get cache
value = CacheService.get('my:key')

# Delete cache
CacheService.delete('my:key')

# Delete by pattern (supports wildcards)
CacheService.delete_pattern('doctors:*')  # Deletes all doctor caches
```

### Frontend: Use Search Hook

```jsx
import { useSearch } from '@/hooks/useSearch';

function MyComponent() {
  const { 
    query,
    results,
    suggestions,
    loading,
    error,
    handleQueryChange,
    performSearch
  } = useSearch();

  return (
    <div>
      <input
        value={query}
        onChange={(e) => handleQueryChange(e.target.value)}
      />
      {results && <div>Found {results.total_count} results</div>}
      {suggestions.map(s => <div key={s}>{s}</div>)}
    </div>
  );
}
```

### Frontend: Use Search Component

```jsx
import SearchBar from '@/components/SearchBar';
import SearchResults from '@/components/SearchResults';
import { useSearch } from '@/hooks/useSearch';

export function SearchPage() {
  const { results, loading, error, query } = useSearch();

  return (
    <>
      <SearchBar placeholder="Qidiruv..." />
      <SearchResults
        results={results}
        loading={loading}
        error={error}
        query={query}
      />
    </>
  );
}
```

---

## 🎯 API Endpoints

### Search Endpoints

```
GET  /api/v1/search/?q=john&models=doctors&limit=20
GET  /api/v1/search/suggestions/?q=jo&model=doctors
GET  /api/v1/search/doctors/?q=john&specialty_id=1
GET  /api/v1/search/doctors/{id}/availability/?date=2024-02-20
GET  /api/v1/search/specialties/
```

### Admin Cache Endpoints

```
POST /api/v1/cache/invalidate/
  { "patterns": ["doctors:*", "clinics:*"] }

POST /api/v1/cache/clear/

GET  /api/v1/cache/stats/

POST /api/v1/cache/invalidate-doctors/
POST /api/v1/cache/invalidate-clinics/
POST /api/v1/cache/invalidate-appointments/
```

---

## 💡 Common Patterns

### Pattern 1: Search with Filters

```python
# Backend
from core.search_service import FullTextSearchService

def search_doctors_by_specialty(query, specialty_id):
    doctors = FullTextSearchService.search_doctors_by_specialty(specialty_id)
    return [d for d in doctors if query.lower() in d.name.lower()]

# Frontend
const { results, handleQueryChange, handleSpecialtyChange } = useDoctorSearch();

<input onChange={(e) => handleQueryChange(e.target.value)} />
<select onChange={(e) => handleSpecialtyChange(e.target.value)} />
```

### Pattern 2: Cache Frequently Accessed Data

```python
from core.cache_service import CacheService

@CacheService.cache_result(timeout=3600, key_prefix='doctors')
def get_popular_doctors():
    return Doctor.objects.filter(rating__gte=4.5)[:10]
```

### Pattern 3: Invalidate Cache After Update

```python
from core.cache_service import CacheInvalidationService

@CacheInvalidationService.invalidate_cache(['doctors:*', 'clinics:detail:1'])
def update_doctor(doctor_id, data):
    doctor = Doctor.objects.get(id=doctor_id)
    doctor.update(**data)
    return doctor
```

### Pattern 4: Multi-Model Search in Frontend

```jsx
const { results, selectedModels, handleModelChange } = useMultiModelSearch(
  ['doctors', 'clinics', 'appointments']
);

// Results automatically filtered by selected models
```

---

## 📊 Performance Tips

1. **Use specific models** in search:
   ```
   ✓ /api/v1/search/?q=john&models=doctors
   ✗ /api/v1/search/?q=john  (searches all models)
   ```

2. **Cache expensive queries**:
   ```python
   @CacheService.cache_result(timeout=3600)
   def expensive_query():
       return Doctor.objects.select_related(...).prefetch_related(...)
   ```

3. **Batch cache invalidation**:
   ```python
   CacheService.delete_pattern('doctors:*')  # Better than individual deletes
   ```

4. **Use pagination** for large result sets:
   ```
   /api/v1/search/?q=test&limit=20&offset=0
   /api/v1/search/?q=test&limit=20&offset=20
   ```

---

## 🐛 Troubleshooting

### Redis not connecting?

```bash
# Check if Redis running
redis-cli ping

# If not:
redis-server

# Check configuration
grep -i cache config/settings.py
```

### Cache not working?

```python
# Test in Django shell
python manage.py shell

>>> from django.core.cache import cache
>>> cache.set('test', 'value')
>>> cache.get('test')
'value'

# If error, check Redis connection
import redis
redis.Redis(host='localhost', port=6379, db=1).ping()
```

### Search returning no results?

```python
# Test search service
from core.search_service import FullTextSearchService
results = FullTextSearchService.search('test', ['doctors'])

# Check if database has data
from apps.doctors.models import Doctor
Doctor.objects.count()  # Should be > 0

# For PostgreSQL:
# Verify full-text search available
Doctor.objects.raw(
    "SELECT * FROM doctors_doctor WHERE "
    "to_tsvector('english', first_name || ' ' || last_name) @@ "
    "to_tsquery('english', 'test')"
)
```

---

## 📁 File Structure

```
hospitoll_backend/
├── core/
│   ├── search_service.py      # FullTextSearchService
│   └── cache_service.py       # CacheService, decorators
├── apps/search/
│   ├── views.py               # SearchViewSet, CacheManagementViewSet
│   ├── urls.py                # Router registration
│   ├── apps.py
│   └── __init__.py
└── SEARCH_API_DOCUMENTATION.md

hospitoll_frontend/
├── src/
│   ├── services/
│   │   └── SearchService.js   # API client
│   ├── hooks/
│   │   └── useSearch.js       # React hooks (4 variants)
│   ├── components/
│   │   ├── SearchBar.jsx      # Search input + dropdown
│   │   └── SearchResults.jsx  # Results display
│   └── pages/
│       └── SearchDemo.jsx     # Demo/testing page
```

---

## 🧪 Testing

### Run Tests

```bash
# Run all search tests
python test_search_functionality.py

# Or via Django test runner
python manage.py test apps.search
```

### Manual Testing

```bash
# 1. Start server
python manage.py runserver

# 2. Get token
curl -X POST http://localhost:8000/api/token/ \
  -d '{"username":"user","password":"pass"}'

# 3. Store token in shell variable
TOKEN="your_token"

# 4. Test search
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/search/?q=john&models=doctors"

# 5. Test cache clear (admin only)
curl -X POST http://localhost:8000/api/v1/cache/clear/ \
  -H "Authorization: Bearer $TOKEN"
```

---

## 🚀 Next Steps

1. **Verify setup works**: Run tests in Troubleshooting section
2. **Integrate SearchBar**: Add to main navigation
3. **Add search to pages**: Use useSearch hook in components
4. **Monitor performance**: Check cache hit rate
5. **Optimize queries**: Use QueryOptimizationHelper for N+1 fixes

---

## 📚 Full Documentation

- **Detailed API Docs**: [SEARCH_API_DOCUMENTATION.md](./SEARCH_API_DOCUMENTATION.md)
- **Setup Guide**: [SEARCH_SETUP_GUIDE.md](./SEARCH_SETUP_GUIDE.md)

---

## ⚡ Key Features

✅ Full-text search across 6 models
✅ PostgreSQL FTS with SQLite fallback
✅ Redis caching with pattern invalidation
✅ Autocomplete suggestions
✅ Doctor availability search
✅ Specialty filtering
✅ Admin cache management
✅ React hooks for frontend
✅ Ready-to-use UI components
✅ Performance optimized (< 100ms searches)

---

Last Updated: 2024-02-20
Questions? Check SEARCH_API_DOCUMENTATION.md or SEARCH_SETUP_GUIDE.md
