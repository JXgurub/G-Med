"""
Serializers for Analytics API
Handles serialization of analytics data
"""

from rest_framework import serializers


class ClinicOverviewSerializer(serializers.Serializer):
    """Serializer for clinic overview analytics"""
    clinic_id = serializers.IntegerField()
    clinic_name = serializers.CharField()
    total_doctors = serializers.IntegerField()
    total_patients = serializers.IntegerField()
    total_appointments = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=10, decimal_places=2)
    avg_rating = serializers.FloatField()
    completion_rate = serializers.FloatField()


class ClinicMetricsSerializer(serializers.Serializer):
    """Serializer for clinic metrics"""
    total_appointments = serializers.IntegerField()
    completed_appointments = serializers.IntegerField()
    cancelled_appointments = serializers.IntegerField()
    daily_average = serializers.FloatField()
    peak_hour = serializers.IntegerField(required=False, allow_null=True)
    doctor_utilization = serializers.FloatField()
    patient_retention_rate = serializers.FloatField()


class DoctorPerformanceSerializer(serializers.Serializer):
    """Serializer for doctor performance metrics"""
    doctor_id = serializers.IntegerField()
    doctor_name = serializers.CharField()
    total_appointments = serializers.IntegerField()
    completed_appointments = serializers.IntegerField()
    cancelled_appointments = serializers.IntegerField()
    rating = serializers.FloatField()
    total_patients = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=10, decimal_places=2)
    avg_appointment_duration = serializers.IntegerField()
    cancellation_rate = serializers.FloatField()


class PatientStatisticsSerializer(serializers.Serializer):
    """Serializer for patient statistics"""
    total_patients = serializers.IntegerField()
    new_patients = serializers.IntegerField()
    returning_patients = serializers.IntegerField()
    avg_visits = serializers.FloatField()
    satisfaction_rating = serializers.FloatField()


class RevenueAnalyticsSerializer(serializers.Serializer):
    """Serializer for revenue analytics"""
    total_revenue = serializers.DecimalField(max_digits=10, decimal_places=2)
    transaction_count = serializers.IntegerField()
    avg_transaction = serializers.DecimalField(max_digits=10, decimal_places=2)
    successful_payments = serializers.IntegerField()
    pending_payments = serializers.IntegerField()
    failed_payments = serializers.IntegerField()


class SubscriptionAnalyticsSerializer(serializers.Serializer):
    """Serializer for subscription analytics"""
    total_subscriptions = serializers.IntegerField()
    active_subscriptions = serializers.IntegerField()
    inactive_subscriptions = serializers.IntegerField()
    renewal_rate = serializers.FloatField()
    churn_rate = serializers.FloatField()
    mrr = serializers.DecimalField(max_digits=10, decimal_places=2)


class TrendItemSerializer(serializers.Serializer):
    """Serializer for trend data points"""
    date = serializers.DateTimeField(required=False)
    date_only = serializers.DateField(required=False)
    year_month = serializers.CharField(required=False)
    value = serializers.IntegerField()
    count = serializers.IntegerField(required=False)


class SystemHealthSerializer(serializers.Serializer):
    """Serializer for system health metrics"""
    active_doctors = serializers.IntegerField()
    appointments_this_week = serializers.IntegerField()
    payment_status = serializers.CharField()
    api_response_time = serializers.CharField()
    cache_hit_rate = serializers.FloatField()


class DashboardSerializer(serializers.Serializer):
    """Serializer for combined dashboard data"""
    overview = ClinicOverviewSerializer()
    metrics = ClinicMetricsSerializer()
    patients = PatientStatisticsSerializer()
    revenue = RevenueAnalyticsSerializer()
    subscriptions = SubscriptionAnalyticsSerializer()
    trends = serializers.DictField()
    health = SystemHealthSerializer()
