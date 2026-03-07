# Analytics System Documentation

## Overview

The Analytics System provides comprehensive data insights for Hospitoll clinics. It includes real-time metrics, trends, revenue tracking, and performance analytics with mobile-responsive visualization.

## Architecture

### Backend Components

#### 1. Analytics Service (`core/analytics_service.py`)
Pure Python service for data aggregation and computation.

**Key Methods:**
- `get_clinic_overview(clinic_id, days=30)` - Clinic performance snapshot
- `get_clinic_metrics(clinic_id, date_range='month')` - Detailed clinic metrics
- `get_doctor_performance(doctor_id, days=30)` - Individual doctor KPIs
- `get_doctor_schedule(doctor_id, date)` - Daily appointment schedule
- `get_patient_statistics(clinic_id, days=30)` - Patient demographics and behavior
- `get_revenue_analytics(clinic_id, date_range='month')` - Financial metrics
- `get_subscription_analytics(clinic_id)` - Subscription insights
- `get_appointment_trends(clinic_id, days=30)` - Appointment trends over time
- `get_revenue_trends(clinic_id, months=12)` - Revenue trends over months
- `get_system_health(clinic_id)` - System status indicators

**Caching Strategy:**
- All complex queries cached with 3600-second (1 hour) TTL
- Cache keys follow pattern: `analytics:{metric_type}:{resource_id}:{parameter}`
- `system_health` cached with 300-second TTL (more frequent updates)

**Database Queries:**
- Uses Django ORM aggregation functions (Count, Sum, Avg)
- Time-based queries with TruncDate, ExtractMonth, ExtractYear
- Optimized with select_related for foreign key relationships

#### 2. Analytics Views (`apps/analytics/views.py`)
REST API endpoints for frontend consumption.

**AnalyticsViewSet:**
- **Base URL:** `/api/v1/analytics/`
- **Authentication:** Requires clinic_id parameter (can be extended with Django permissions)
- **Format:** JSON with `{success: bool, data: {...}}` structure

**Endpoints (11 total):**

| Method | Endpoint | Query Params | Description |
|--------|----------|--------------|-------------|
| GET | `/api/v1/analytics/clinic-overview/` | clinic_id, days | Clinic overview stats |
| GET | `/api/v1/analytics/clinic-metrics/` | clinic_id, date_range | Detailed clinic metrics |
| GET | `/api/v1/analytics/doctor-performance/` | doctor_id, days | Doctor performance KPIs |
| GET | `/api/v1/analytics/doctor-schedule/` | doctor_id, date | Doctor daily schedule |
| GET | `/api/v1/analytics/patient-statistics/` | clinic_id, days | Patient stats & demographics |
| GET | `/api/v1/analytics/revenue/` | clinic_id, date_range | Revenue analytics |
| GET | `/api/v1/analytics/subscriptions/` | clinic_id | Subscription insights |
| GET | `/api/v1/analytics/trends/appointments/` | clinic_id, days | Appointment trends |
| GET | `/api/v1/analytics/trends/revenue/` | clinic_id, months | Revenue trends |
| GET | `/api/v1/analytics/system-health/` | clinic_id | System health metrics |
| GET | `/api/v1/analytics/dashboard/` | clinic_id | Combined dashboard (6 endpoints) |

**Query Parameters:**
- `clinic_id` (required, int) - Clinic identifier
- `doctor_id` (optional, int) - Doctor identifier
- `days` (optional, int, default=30) - Number of days to analyze
- `date_range` (optional, str, default='month') - 'week', 'month', 'quarter', 'year'
- `months` (optional, int, default=12) - Number of months to analyze
- `date` (optional, str) - Date in format YYYY-MM-DD

**Response Format:**
```json
{
  "success": true,
  "data": {
    "clinic_id": 1,
    "total_doctors": 12,
    "total_revenue": 45000.50,
    // ... metric-specific fields
  }
}
```

**Dashboard Endpoint (`/api/v1/analytics/dashboard/`):**
Combines 6 major endpoints for optimized loading:
```json
{
  "success": true,
  "dashboard": {
    "overview": {...},
    "metrics": {...},
    "patients": {...},
    "revenue": {...},
    "trends": {...},
    "health": {...}
  }
}
```

#### 3. Serializers (`apps/analytics/serializers.py`)
Data validation and serialization for API responses.

### Frontend Components

#### 1. AnalyticsDashboard Component
Main container component with tab-based navigation.

**Props:**
- `clinicId` (required, int) - Clinic identifier
- `title` (optional, string, default='Klinika Analitikasi') - Page title

**State:**
- `dashboardData` - Aggregated data from backend
- `loading` - Fetch state boolean
- `error` - Error message string or null
- `dateRange` - Selected range (week/month/quarter/year)
- `activeTab` - Mobile tab selection (overview/metrics/revenue/health)

**Tabs:**
- **Overview** (📊) - Key metrics and indicators
- **Metrics** (📈) - Detailed performance metrics
- **Revenue** (💰) - Financial and payment data
- **Health** (⚙️) - System status indicators

**Features:**
- Auto-refresh every 60 seconds
- Mobile-responsive tab navigation
- Date range selector
- Manual refresh button
- Load/error state handling

#### 2. DashboardCard Component
Reusable metric display card with 5 color variants.

**Props:**
- `title` - Card title
- `value` - Main metric value
- `subtitle` - Optional additional text
- `icon` - Emoji or icon character
- `color` - 'blue'|'green'|'orange'|'purple'|'red'
- `onClick` - Optional click handler

**Features:**
- Colored left border matching metric type
- Hover elevation animation
- Responsive sizing (scales 100% mobile → 25% desktop)
- Dark mode support

#### 3. MetricsGrid Component
8-metric grid display for detailed performance metrics.

**Metrics Displayed:**
1. Jami Qabullar - Total appointments
2. Tugatilgan - Completed appointments
3. Bekor qilingan - Cancelled appointments
4. Ko'rsatilmagan - No-show appointments
5. Kunlik O'rtacha - Average daily appointments
6. Pik Soat - Peak appointment hour
7. Shifokor Foydalanish - Doctor utilization %
8. Bemor Saqlanish - Patient retention %

#### 4. ChartsPanel Component
Multi-chart display for appointment and revenue trends.

**Charts:**
- Appointment trends (line/area chart)
- Revenue by doctor (horizontal bar chart)
- Payment methods (pie chart)
- Quick stats grid (4 KPIs)

**Features:**
- SVG-based rendering (no external charting library)
- Responsive layout
- Interactive data points
- Mobile-optimized display

#### 5. TrendChart Component
Customizable trend visualization component.

**Props:**
- `data` - Array of {label, value} objects
- `title` - Chart title
- `type` - 'line'|'area'
- `color` - Chart color (hex)

**Features:**
- SVG line chart with grid
- Data table with changes
- Summary statistics (average, max, min, total)
- Normalized scaling
- Responsive sizing

#### 6. useAnalytics Hook
React hook for analytics data fetching and caching.

**Usage:**
```javascript
const { data, loading, error, refetch } = useAnalytics(
  clinicId,
  {
    endpoint: 'dashboard',
    refetchInterval: 60000,
    cacheTimeout: 60000,
    enabled: true
  }
);
```

**Features:**
- Client-side caching (1 minute TTL)
- Auto-refresh capability
- Error handling
- Loading states
- Manual refetch

### Responsive Design

#### Breakpoints
- **Desktop** (1024px+) - Full layout, 4 columns
- **Tablet** (768px-1024px) - 2 columns, adjusted spacing
- **Mobile** (< 768px) - 1 column, tab navigation
- **Small Mobile** (< 480px) - Minimal spacing, compact sizing

#### Mobile-First CSS Strategy
- All CSS written for mobile first
- Enhanced with media queries for larger screens
- Touch-friendly targets (40-48px minimum)
- Responsive fonts (11px mobile → 28px desktop)
- Adaptive spacing (8px mobile → 24px desktop)

#### Dark Mode Support
- Full dark mode CSS included in all modules
- Uses `@media (prefers-color-scheme: dark)`
- Adjusted colors for accessibility
- Increased opacity for visibility against dark backgrounds

## API Usage Examples

### Get Clinic Overview
```bash
curl -X GET "http://localhost:8000/api/v1/analytics/clinic-overview/?clinic_id=1&days=30"
```

### Get Revenue Analytics
```bash
curl -X GET "http://localhost:8000/api/v1/analytics/revenue/?clinic_id=1&date_range=month"
```

### Get Full Dashboard
```bash
curl -X GET "http://localhost:8000/api/v1/analytics/dashboard/?clinic_id=1"
```

## Frontend Usage Examples

### Import and Use Dashboard
```javascript
import AnalyticsDashboard from '@/components/AnalyticsDashboard';

function ClinicPage() {
  return (
    <AnalyticsDashboard 
      clinicId={1} 
      title="Oltin Shifa Analitikasi"
    />
  );
}
```

### Use Analytics Hook Directly
```javascript
import useAnalytics from '@/hooks/useAnalytics';

function MetricsView({ clinicId }) {
  const { data, loading, error, refetch } = useAnalytics(
    clinicId,
    { endpoint: 'clinic-metrics' }
  );

  if (loading) return <Loading />;
  if (error) return <Error message={error} />;

  return <MetricsDisplay data={data.metrics} />;
}
```

## Configuration

### Django Settings
```python
# settings.py
INSTALLED_APPS = [
    # ...
    'apps.analytics',
]
```

### URL Configuration
```python
# urls.py
urlpatterns = [
    # ...
    path('api/v1/analytics/', include('apps.analytics.urls')),
]
```

### Cache Configuration
```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
    }
}
```

## Performance Optimization

### Backend
- Database queries use aggregation at SQL level
- Foreign key relationships optimized with select_related
- Complex calculations cached with 3600-second TTL
- System health updates cached with 300-second TTL

### Frontend
- Client-side caching with 1-minute TTL
- Bundle loaded with code splitting
- CSS modules for scope isolation
- Lazy loading for chart components

### Caching Strategy
- `analytics:clinic:overview:{clinic_id}:{days}` - 3600s
- `analytics:clinic:metrics:{clinic_id}:{date_range}` - 3600s
- `analytics:health:{clinic_id}` - 300s
- All other metrics - 3600s

## Testing

### Run Backend Tests
```bash
python manage.py test apps.analytics
```

### Run Specific Test Class
```bash
python manage.py test apps.analytics.tests.AnalyticsServiceTestCase
```

### Run with Coverage
```bash
coverage run --source='apps.analytics' manage.py test apps.analytics
coverage report
```

### Test Categories
1. **Unit Tests** - AnalyticsService methods
2. **API Tests** - REST endpoint validation
3. **Performance Tests** - Response time and caching effectiveness
4. **Integration Tests** - End-to-end data flow

## Troubleshooting

### Issue: Analytics data not updating
**Solution:** Check cache TTL settings, verify Redis connection, check database queries.

### Issue: Slow API responses
**Solution:** Enable caching, verify database indexes, check for N+1 queries with select_related.

### Issue: Mobile layout broken
**Solution:** Check viewport meta tag, verify CSS media queries, test on actual devices.

### Issue: Chart not displaying
**Solution:** Check if data has values, verify chart component props, check browser console for errors.

## Future Enhancements

1. **Real-time Updates** - WebSocket integration for live metrics
2. **Advanced Visualizations** - Heatmaps, Sankey diagrams, KPI gauges
3. **Custom Reports** - PDF export, email scheduling
4. **Anomaly Detection** - Alert on unusual patterns
5. **Predictive Analytics** - Forecast trends using ML models
6. **Role-based Filtering** - Different dashboards for admin/doctor/patient

## Security Considerations

- Clinic ID validation required on all endpoints
- No sensitive data exposed in responses
- Cache keys include resource IDs (no data leakage)
- Implement authentication middleware for future restrictions
- SQL injection prevented with Django ORM
- XSS protection via React component isolation

## Maintenance

### Regular Tasks
- Monitor cache hit rates (target > 80%)
- Review slow query logs
- Update data aggregation logic if schema changes
- Test dashboard on new devices/browsers
- Update documentation with new features

### Monitoring
- Track API response times (target < 1000ms)
- Monitor cache hit rate via system_health endpoint
- Log failed queries for debugging
- Monitor frontend performance with analytics

## Support

For issues or questions:
1. Check KNOWN_ISSUES_AND_TODOS.md
2. Review API documentation
3. Check Analytics class docstrings
4. Run test suite to identify failures
