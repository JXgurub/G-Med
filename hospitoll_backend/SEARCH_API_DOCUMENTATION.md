# Search API Documentation

Full-text search API with caching and filtering capabilities across multiple models.

## Base URL

```
/api/v1/search/
```

## Authentication

All endpoints require authentication via JWT token in Authorization header:

```
Authorization: Bearer {token}
```

## Rate Limits

- **Standard users**: 100 requests/minute
- **Authenticated users**: 500 requests/minute
- **Admin users**: No limit

---

## Endpoints

### 1. Full-Text Search Across All Models

**Endpoint**: `GET /api/v1/search/`

Search across all available models (doctors, clinics, patients, appointments, medical records, pharmacies).

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `q` | string | ✓ | - | Search query (minimum 3 characters) |
| `models` | string | | all | Comma-separated model types: `doctors,clinics,patients,appointments,medical_records,pharmacies` |
| `limit` | integer | | 20 | Results per model type (max 100) |
| `offset` | integer | | 0 | Pagination offset |

#### Request Example

```bash
curl -X GET "http://localhost:8000/api/v1/search/?q=john&models=doctors,clinics&limit=10"
```

#### Response

```json
{
  "success": true,
  "query": "john",
  "results": {
    "doctors": {
      "count": 5,
      "items": [
        {
          "id": 1,
          "name": "John Smith",
          "specialty": "Cardiology",
          "clinic": "St. Mary Hospital",
          "phone": "+998701234567",
          "qualification": "MD, Board Certified",
          "bio": "Experienced cardiologist with 15 years of practice"
        }
      ]
    },
    "clinics": {
      "count": 3,
      "items": [
        {
          "id": 1,
          "name": "John's Medical Center",
          "location": "123 Main St",
          "doctors_count": 12,
          "phone": "+998701234567",
          "description": "Modern medical facility"
        }
      ]
    }
  },
  "total_count": 8,
  "cached": false,
  "execution_time_ms": 145
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Request status |
| `query` | string | Actual search query used |
| `results` | object | Results grouped by model type |
| `total_count` | integer | Total number of results |
| `cached` | boolean | Whether result was from cache |
| `execution_time_ms` | integer | Query execution time |

#### Error Responses

**400 Bad Request** - Invalid query

```json
{
  "error": "Query must be at least 3 characters long",
  "query_length": 2
}
```

**422 Unprocessable Entity** - Invalid model

```json
{
  "error": "Invalid model type",
  "valid_models": ["doctors", "clinics", "patients", "appointments", "medical_records", "pharmacies"]
}
```

---

### 2. Get Search Suggestions

**Endpoint**: `GET /api/v1/search/suggestions/`

Get autocomplete suggestions for a specific model type.

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `q` | string | ✓ | - | Search query (minimum 2 characters) |
| `model` | string | | all | Model type to search in |
| `limit` | integer | | 10 | Max suggestions to return |

#### Request Example

```bash
curl -X GET "http://localhost:8000/api/v1/search/suggestions/?q=jo&model=doctors&limit=10"
```

#### Response

```json
{
  "success": true,
  "query": "jo",
  "model": "doctors",
  "suggestions": [
    "John Smith - Cardiology",
    "John Doe - Neurology",
    "Jonathan Miller - Orthopedics"
  ],
  "count": 3,
  "cached": true
}
```

#### Error Responses

**400 Bad Request** - Query too short

```json
{
  "error": "Query must be at least 2 characters long",
  "query_length": 1
}
```

---

### 3. Search Doctors with Filters

**Endpoint**: `GET /api/v1/search/doctors/`

Search for doctors with optional filtering by clinic and specialty.

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | string | | Search query |
| `clinic_id` | integer | | Filter by clinic |
| `specialty_id` | integer | | Filter by specialty |
| `available_only` | boolean | | Show only available doctors |
| `limit` | integer | | Results limit (default: 20) |

#### Request Example

```bash
curl -X GET "http://localhost:8000/api/v1/search/doctors/?q=john&specialty_id=1&available_only=true"
```

#### Response

```json
{
  "success": true,
  "query": "john",
  "filters": {
    "specialty_id": 1,
    "available_only": true
  },
  "results": {
    "doctors": {
      "count": 3,
      "items": [
        {
          "id": 1,
          "name": "John Smith",
          "specialty": "Cardiology",
          "clinic": "St. Mary Hospital",
          "phone": "+998701234567",
          "available": true,
          "rating": 4.8,
          "reviews_count": 145
        }
      ]
    }
  },
  "total_count": 3
}
```

---

### 4. Get Doctor Availability

**Endpoint**: `GET /api/v1/search/doctors/{id}/availability/`

Get availability for a specific doctor on a given date.

#### URL Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | integer | Doctor ID |

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `date` | string | ✓ | Date in format YYYY-MM-DD |

#### Request Example

```bash
curl -X GET "http://localhost:8000/api/v1/search/doctors/1/availability/?date=2024-02-20"
```

#### Response

```json
{
  "success": true,
  "doctor_id": 1,
  "doctor_name": "John Smith",
  "date": "2024-02-20",
  "available_slots": [
    {
      "time": "09:00",
      "duration_minutes": 30,
      "available": true
    },
    {
      "time": "09:30",
      "duration_minutes": 30,
      "available": true
    },
    {
      "time": "10:00",
      "duration_minutes": 30,
      "available": false
    }
  ],
  "total_slots": 16,
  "available_slots_count": 14
}
```

#### Error Responses

**404 Not Found** - Doctor not found

```json
{
  "error": "Doctor not found",
  "doctor_id": 999
}
```

**400 Bad Request** - Invalid date format

```json
{
  "error": "Invalid date format. Use YYYY-MM-DD",
  "received": "20-02-2024"
}
```

---

### 5. Get All Specialties

**Endpoint**: `GET /api/v1/search/specialties/`

Get list of all available doctor specialties.

#### Request Example

```bash
curl -X GET "http://localhost:8000/api/v1/search/specialties/"
```

#### Response

```json
{
  "success": true,
  "specialties": [
    {
      "id": 1,
      "name": "Cardiology",
      "description": "Heart and cardiovascular system",
      "doctors_count": 12
    },
    {
      "id": 2,
      "name": "Neurology",
      "description": "Nervous system disorders",
      "doctors_count": 8
    }
  ],
  "total_count": 15,
  "cached": true
}
```

---

## Cache Management Endpoints

### Admin Only Endpoints

These endpoints require `IsAdminUser` permission.

#### 1. Invalidate Cache Patterns

**Endpoint**: `POST /api/v1/cache/invalidate/`

Invalidate cache by patterns (supports wildcards).

#### Request Body

```json
{
  "patterns": ["doctors:*", "clinics:detail:1", "search:*"]
}
```

#### Response

```json
{
  "success": true,
  "patterns": ["doctors:*", "clinics:detail:1", "search:*"],
  "keys_deleted": 45,
  "execution_time_ms": 123
}
```

#### 2. Clear All Cache

**Endpoint**: `POST /api/v1/cache/clear/`

Clear entire cache backend.

#### Request

```bash
curl -X POST "http://localhost:8000/api/v1/cache/clear/"
```

#### Response

```json
{
  "success": true,
  "message": "Cache cleared successfully",
  "execution_time_ms": 89
}
```

#### 3. Get Cache Statistics

**Endpoint**: `GET /api/v1/cache/stats/`

Get cache backend information and statistics.

#### Response

```json
{
  "success": true,
  "backend": "django_redis.cache.RedisCache",
  "location": "redis://127.0.0.1:6379/1",
  "status": "connected",
  "stats": {
    "total_keys": 2341,
    "memory_usage_mb": 45.2,
    "connected_clients": 5,
    "used_memory_human": "45.23MB"
  }
}
```

#### 4. Shortcut: Invalidate Doctor Cache

**Endpoint**: `POST /api/v1/cache/invalidate-doctors/`

Quickly invalidate all doctor-related caches.

#### Request Body (Optional)

```json
{
  "doctor_id": 5
}
```

#### Response

```json
{
  "success": true,
  "message": "Doctor cache invalidated",
  "patterns": ["doctors:*", "appointments:*", "availability:*"],
  "keys_deleted": 28
}
```

#### 5. Shortcut: Invalidate Clinic Cache

**Endpoint**: `POST /api/v1/cache/invalidate-clinics/`

#### 6. Shortcut: Invalidate Appointment Cache

**Endpoint**: `POST /api/v1/cache/invalidate-appointments/`

---

## Search Response Formats

### Doctor Result

```json
{
  "id": 1,
  "name": "John Smith",
  "specialty": "Cardiology",
  "clinic": "St. Mary Hospital",
  "phone": "+998701234567",
  "qualification": "MD, Board Certified",
  "bio": "Experienced cardiologist",
  "rating": 4.8,
  "photo_url": "https://..."
}
```

### Clinic Result

```json
{
  "id": 1,
  "name": "St. Mary Hospital",
  "location": "123 Main St, Tashkent",
  "doctors_count": 45,
  "phone": "+998701234567",
  "email": "contact@stmary.uz",
  "description": "Modern hospital with 100+ doctors"
}
```

### Patient Result

```json
{
  "id": 1,
  "name": "Jane Doe",
  "phone": "+998701234567",
  "email": "jane@example.com",
  "age": 35,
  "passport_number": "AA123456"
}
```

### Appointment Result

```json
{
  "id": 1,
  "doctor": "John Smith",
  "patient": "Jane Doe",
  "date": "2024-02-20",
  "time": "10:00",
  "status": "scheduled",
  "clinic": "St. Mary Hospital",
  "notes": "Regular checkup"
}
```

### Medical Record Result

```json
{
  "id": 1,
  "patient": "Jane Doe",
  "doctor": "John Smith",
  "date": "2024-02-20",
  "diagnosis": "Hypertension",
  "symptoms": "Headache, dizziness",
  "treatment_plan": "Medication and diet",
  "notes": "Follow-up in 2 weeks"
}
```

### Pharmacy Result

```json
{
  "id": 1,
  "name": "Central Pharmacy",
  "location": "456 Oak Ave, Tashkent",
  "phone": "+998701234567",
  "working_hours": "08:00-22:00"
}
```

---

## Caching Strategy

### Cache Timeouts

| Data Type | Timeout | Pattern |
|-----------|---------|---------|
| Doctors List | 3600s (1 hour) | `doctors:list*` |
| Doctor Detail | 1800s (30 min) | `doctors:detail:*` |
| Clinics List | 3600s (1 hour) | `clinics:list*` |
| Clinic Detail | 1800s (30 min) | `clinics:detail:*` |
| Appointments | 300s (5 min) | `appointments:*` |
| Availability | 600s (10 min) | `availability:*` |
| Search Results | 900s (15 min) | `search:*` |
| Patient Records | 1800s (30 min) | `patient_records:*` |
| Statistics | 3600s (1 hour) | `statistics:*` |

### Cache Invalidation

Caches are automatically invalidated when:

- A doctor is created/updated/deleted → Clears: `doctors:*`, `appointments:*`, `availability:*`
- A clinic is created/updated/deleted → Clears: `clinics:*`, `doctors:*`
- An appointment is created/updated/deleted → Clears: `appointments:*`, `availability:*`
- Patient record is updated → Clears: `patient_records:*`

---

## Usage Examples

### JavaScript/Fetch

```javascript
// Basic search
const response = await fetch(
  '/api/v1/search/?q=john&models=doctors&limit=10',
  {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  }
);
const data = await response.json();
console.log(data.results.doctors);

// Autocomplete
const suggestions = await fetch(
  '/api/v1/search/suggestions/?q=jo&model=doctors',
  { headers: { 'Authorization': `Bearer ${token}` } }
).then(r => r.json());

// Doctor availability
const availability = await fetch(
  '/api/v1/search/doctors/1/availability/?date=2024-02-20',
  { headers: { 'Authorization': `Bearer ${token}` } }
).then(r => r.json());
```

### React Hook Usage

```javascript
import { useSearch } from '@/hooks/useSearch';

function MyComponent() {
  const { results, loading, performSearch } = useSearch();

  const handleSearch = async (query) => {
    await performSearch(query);
  };

  return (
    <div>
      <input onChange={(e) => handleSearch(e.target.value)} />
      {loading && <p>Loading...</p>}
      {results && <p>Found {results.total_count} results</p>}
    </div>
  );
}
```

### Python/Requests

```python
import requests

token = "your_jwt_token"
headers = {"Authorization": f"Bearer {token}"}

# Search
response = requests.get(
    "http://localhost:8000/api/v1/search/?q=john&models=doctors",
    headers=headers
)
results = response.json()

# Doctor availability
response = requests.get(
    "http://localhost:8000/api/v1/search/doctors/1/availability/?date=2024-02-20",
    headers=headers
)
availability = response.json()
```

---

## Error Handling

All error responses follow this format:

```json
{
  "error": "Error message",
  "error_code": "INVALID_QUERY",
  "details": {}
}
```

### Common Error Codes

| Code | Status | Description |
|------|--------|-------------|
| `INVALID_QUERY` | 400 | Query too short or invalid |
| `INVALID_MODEL` | 422 | Unknown model type |
| `NOT_FOUND` | 404 | Resource doesn't exist |
| `PERMISSION_DENIED` | 403 | User lacks permission |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |

---

## Performance Tips

1. **Use specific models** to reduce query scope:
   ```
   ?models=doctors,clinics  # Faster than all models
   ```

2. **Limit results** appropriately:
   ```
   ?limit=10  # Instead of 100
   ```

3. **Use specialty filter** for doctor searches:
   ```
   ?q=john&specialty_id=1  # Faster than full search
   ```

4. **Check cache stats** periodically:
   ```
   GET /api/v1/cache/stats/
   ```

5. **Clear cache** when making bulk updates:
   ```
   POST /api/v1/cache/invalidate/ with patterns
   ```

---

## Pagination

For large result sets, use `offset` and `limit`:

```
GET /api/v1/search/?q=test&limit=20&offset=0  # Page 1
GET /api/v1/search/?q=test&limit=20&offset=20  # Page 2
```

Response includes:

```json
{
  "results": {...},
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 145,
    "pages": 8
  }
}
```

---

## WebSocket Real-time Search (Coming Soon)

Live search updates via WebSocket:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/search/');
ws.onopen = () => ws.send(JSON.stringify({ query: 'john', models: ['doctors'] }));
ws.onmessage = (e) => console.log(JSON.parse(e.data).results);
```

---

## Version

API Version: **1.0.0**

Last Updated: 2024-02-20

---

For support, contact: api-support@hospitoll.uz
