"""
Analytics App - Real-time metrics and reporting for Hospitoll clinics

This app provides:
- Real-time analytics and metrics
- Revenue tracking and reporting
- Doctor performance analytics
- Patient statistics and trends
- System health monitoring
- Mobile-responsive dashboards

Usage:
    from apps.analytics.views import AnalyticsViewSet
    from core.analytics_service import AnalyticsService

    # Get clinic overview
    overview = AnalyticsService.get_clinic_overview(clinic_id=1, days=30)

    # Use in API
    GET /api/v1/analytics/dashboard/?clinic_id=1
"""

default_app_config = 'apps.analytics.apps.AnalyticsConfig'
