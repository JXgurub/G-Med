"""
Analytics API Views
REST endpoints for analytics and dashboard data
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from core.analytics_service import AnalyticsService
from core.permissions import IsClinicOwner, IsDoctor


class AnalyticsViewSet(viewsets.ViewSet):
    """Analytics API endpoints"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def clinic_overview(self, request):
        """GET /api/v1/analytics/clinic-overview/?clinic_id=1&days=30"""
        clinic_id = request.query_params.get('clinic_id')
        days = int(request.query_params.get('days', 30))

        if not clinic_id:
            return Response({'error': 'clinic_id required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = AnalyticsService.get_clinic_overview(clinic_id, days)
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def clinic_metrics(self, request):
        """GET /api/v1/analytics/clinic-metrics/?clinic_id=1&date_range=month"""
        clinic_id = request.query_params.get('clinic_id')
        date_range = request.query_params.get('date_range', 'month')

        if not clinic_id:
            return Response({'error': 'clinic_id required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = AnalyticsService.get_clinic_metrics(clinic_id, date_range)
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def doctor_performance(self, request):
        """GET /api/v1/analytics/doctor-performance/?doctor_id=1&days=30"""
        doctor_id = request.query_params.get('doctor_id')
        days = int(request.query_params.get('days', 30))

        if not doctor_id:
            return Response({'error': 'doctor_id required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = AnalyticsService.get_doctor_performance(doctor_id, days)
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def doctor_schedule(self, request):
        """GET /api/v1/analytics/doctor-schedule/?doctor_id=1&date=2024-02-20"""
        doctor_id = request.query_params.get('doctor_id')
        date = request.query_params.get('date')

        if not doctor_id or not date:
            return Response({'error': 'doctor_id and date required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            schedule = AnalyticsService.get_doctor_schedule(doctor_id, date)
            return Response({'success': True, 'schedule': schedule})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def patient_statistics(self, request):
        """GET /api/v1/analytics/patient-statistics/?clinic_id=1&days=30"""
        clinic_id = request.query_params.get('clinic_id')
        days = int(request.query_params.get('days', 30))

        if not clinic_id:
            return Response({'error': 'clinic_id required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = AnalyticsService.get_patient_statistics(clinic_id, days)
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def revenue_analytics(self, request):
        """GET /api/v1/analytics/revenue/?clinic_id=1&date_range=month"""
        clinic_id = request.query_params.get('clinic_id')
        date_range = request.query_params.get('date_range', 'month')

        if not clinic_id:
            return Response({'error': 'clinic_id required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = AnalyticsService.get_revenue_analytics(clinic_id, date_range)
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def subscriptions(self, request):
        """GET /api/v1/analytics/subscriptions/?clinic_id=1"""
        clinic_id = request.query_params.get('clinic_id')

        if not clinic_id:
            return Response({'error': 'clinic_id required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = AnalyticsService.get_subscription_analytics(clinic_id)
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def appointment_trends(self, request):
        """GET /api/v1/analytics/trends/appointments/?clinic_id=1&days=30"""
        clinic_id = request.query_params.get('clinic_id')
        days = int(request.query_params.get('days', 30))

        if not clinic_id:
            return Response({'error': 'clinic_id required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = AnalyticsService.get_appointment_trends(clinic_id, days)
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def revenue_trends(self, request):
        """GET /api/v1/analytics/trends/revenue/?clinic_id=1&months=12"""
        clinic_id = request.query_params.get('clinic_id')
        months = int(request.query_params.get('months', 12))

        if not clinic_id:
            return Response({'error': 'clinic_id required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = AnalyticsService.get_revenue_trends(clinic_id, months)
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def system_health(self, request):
        """GET /api/v1/analytics/system-health/?clinic_id=1"""
        clinic_id = request.query_params.get('clinic_id')

        if not clinic_id:
            return Response({'error': 'clinic_id required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = AnalyticsService.get_system_health(clinic_id)
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """GET /api/v1/analytics/dashboard/?clinic_id=1
        Get complete dashboard data in single request
        """
        clinic_id = request.query_params.get('clinic_id')

        if not clinic_id:
            return Response({'error': 'clinic_id required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            dashboard_data = {
                'overview': AnalyticsService.get_clinic_overview(clinic_id),
                'metrics': AnalyticsService.get_clinic_metrics(clinic_id),
                'patients': AnalyticsService.get_patient_statistics(clinic_id),
                'revenue': AnalyticsService.get_revenue_analytics(clinic_id),
                'trends': AnalyticsService.get_appointment_trends(clinic_id),
                'health': AnalyticsService.get_system_health(clinic_id),
            }
            return Response({'success': True, 'dashboard': dashboard_data})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
