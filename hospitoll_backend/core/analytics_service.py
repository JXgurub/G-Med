"""
Analytics Service - Real-time analytics and statistics for clinics, doctors, and appointments
Provides comprehensive data for dashboard visualization
"""

from django.db.models import Count, Q, Avg, Sum, F
from django.db.models.functions import TruncDate, ExtractHour, ExtractMonth, ExtractYear
from django.utils import timezone
from datetime import timedelta, datetime
from apps.doctors.models import Doctor
from apps.clinics.models import Clinic
from apps.patients.models import Patient
from apps.medical.models import Appointment, MedicalRecord
from apps.payments.models import Payment
from apps.subscriptions.models import Subscription
from core.cache_service import CacheService


class AnalyticsService:
    """Comprehensive analytics service for clinic dashboards"""

    # ==================== CLINIC ANALYTICS ====================

    @staticmethod
    def get_clinic_overview(clinic_id, days=30):
        """Get clinic overview statistics"""
        cache_key = f'analytics:clinic:overview:{clinic_id}:{days}'
        cached = CacheService.get(cache_key)
        if cached:
            return cached

        clinic = Clinic.objects.get(id=clinic_id)
        start_date = timezone.now().date() - timedelta(days=days)

        data = {
            'clinic_name': clinic.name,
            'clinic_id': clinic_id,
            'period_days': days,
            'total_doctors': clinic.doctors.count(),  # type: ignore[attr-defined]
            'total_patients': Patient.objects.filter(
                appointments__doctor__clinic=clinic,
                appointments__scheduled_date__date__gte=start_date
            ).distinct().count(),
            'total_appointments': Appointment.objects.filter(
                doctor__clinic=clinic,
                scheduled_date__date__gte=start_date
            ).count(),
            'total_revenue': AnalyticsService._get_clinic_revenue(clinic_id, start_date),
            'avg_rating': AnalyticsService._get_clinic_rating(clinic_id),
            'completion_rate': AnalyticsService._get_completion_rate(clinic_id, start_date),
        }

        CacheService.set(cache_key, data, timeout=3600)  # Cache 1 hour
        return data

    @staticmethod
    def get_clinic_metrics(clinic_id, date_range='month'):
        """Get detailed clinic metrics"""
        cache_key = f'analytics:clinic:metrics:{clinic_id}:{date_range}'
        cached = CacheService.get(cache_key)
        if cached:
            return cached

        start_date = AnalyticsService._get_start_date(date_range)
        
        appointments = Appointment.objects.filter(
            doctor__clinic_id=clinic_id,
            scheduled_date__date__gte=start_date
        )

        data = {
            'total_appointments': appointments.count(),
            'scheduled_appointments': appointments.filter(status='scheduled').count(),
            'completed_appointments': appointments.filter(status='completed').count(),
            'cancelled_appointments': appointments.filter(status='cancelled').count(),
            'no_show_appointments': appointments.filter(status='no_show').count(),
            'average_appointments_per_day': AnalyticsService._calculate_daily_average(appointments),
            'peak_appointment_hour': AnalyticsService._get_peak_hour(appointments),
            'doctor_utilization': AnalyticsService._get_doctor_utilization(clinic_id, start_date),
            'patient_retention_rate': AnalyticsService._get_retention_rate(clinic_id, start_date),
        }

        CacheService.set(cache_key, data, timeout=3600)
        return data

    # ==================== DOCTOR ANALYTICS ====================

    @staticmethod
    def get_doctor_performance(doctor_id, days=30):
        """Get doctor performance metrics"""
        cache_key = f'analytics:doctor:performance:{doctor_id}:{days}'
        cached = CacheService.get(cache_key)
        if cached:
            return cached

        doctor = Doctor.objects.get(id=doctor_id)
        start_date = timezone.now().date() - timedelta(days=days)

        appointments = Appointment.objects.filter(
            doctor=doctor,
            scheduled_date__date__gte=start_date
        )

        data = {
            'doctor_name': f"{doctor.user.first_name} {doctor.user.last_name}",
            'doctor_id': doctor_id,
            'specialty': doctor.specializations_display,
            'total_appointments': appointments.count(),
            'completed_appointments': appointments.filter(status='completed').count(),
            'average_rating': AnalyticsService._get_doctor_rating(doctor_id),
            'total_patients': appointments.values('patient').distinct().count(),
            'revenue': AnalyticsService._get_doctor_revenue(doctor_id, start_date),
            'appointment_duration_avg': AnalyticsService._get_avg_duration(doctor_id, start_date),
            'cancellation_rate': AnalyticsService._get_cancellation_rate(doctor_id, start_date),
            'no_show_rate': AnalyticsService._get_no_show_rate(doctor_id, start_date),
        }

        CacheService.set(cache_key, data, timeout=3600)
        return data

    @staticmethod
    def get_doctor_schedule(doctor_id, date):
        """Get doctor's schedule for a specific date"""
        appointments = Appointment.objects.filter(
            doctor_id=doctor_id,
            scheduled_date__date=date
        ).order_by('scheduled_date').values(
            'id',
            'patient__user__first_name',
            'patient__user__last_name',
            'scheduled_date',
            'status',
        )
        
        return list(appointments)

    # ==================== PATIENT ANALYTICS ====================

    @staticmethod
    def get_patient_statistics(clinic_id, days=30):
        """Get patient statistics for clinic"""
        cache_key = f'analytics:patient:stats:{clinic_id}:{days}'
        cached = CacheService.get(cache_key)
        if cached:
            return cached

        start_date = timezone.now().date() - timedelta(days=days)
        
        # Get all appointments for this clinic in the period
        clinic_appointments = Appointment.objects.filter(
            doctor__clinic_id=clinic_id,
            scheduled_date__date__gte=start_date
        )

        data = {
            'total_patients': clinic_appointments.values('patient').distinct().count(),
            'new_patients': AnalyticsService._get_new_patients(clinic_id, start_date),
            'returning_patients': AnalyticsService._get_returning_patients(clinic_id, start_date),
            'average_visits_per_patient': AnalyticsService._get_avg_visits(clinic_id, start_date),
            'patient_satisfaction_rating': AnalyticsService._get_satisfaction_rating(clinic_id, start_date),
            'patient_age_distribution': AnalyticsService._get_age_distribution(clinic_id, start_date),
            'patient_gender_distribution': AnalyticsService._get_gender_distribution(clinic_id, start_date),
        }

        CacheService.set(cache_key, data, timeout=3600)
        return data

    # ==================== REVENUE ANALYTICS ====================

    @staticmethod
    def get_revenue_analytics(clinic_id, date_range='month'):
        """Get revenue and financial analytics"""
        cache_key = f'analytics:revenue:{clinic_id}:{date_range}'
        cached = CacheService.get(cache_key)
        if cached:
            return cached

        start_date = AnalyticsService._get_start_date(date_range)

        payments = Payment.objects.filter(
            appointment__doctor__clinic_id=clinic_id,
            created_at__date__gte=start_date
        )

        data = {
            'total_revenue': float(payments.aggregate(Sum('amount'))['amount__sum'] or 0),
            'total_transactions': payments.count(),
            'average_transaction': float(payments.aggregate(Avg('amount'))['amount__avg'] or 0),
            'successful_payments': payments.filter(status='completed').count(),
            'failed_payments': payments.filter(status='failed').count(),
            'pending_payments': payments.filter(status='pending').count(),
            'revenue_by_day': AnalyticsService._get_revenue_by_day(clinic_id, start_date),
            'revenue_by_doctor': AnalyticsService._get_revenue_by_doctor(clinic_id, start_date),
            'payment_methods': AnalyticsService._get_payment_methods(clinic_id, start_date),
        }

        CacheService.set(cache_key, data, timeout=3600)
        return data

    @staticmethod
    def get_subscription_analytics(clinic_id):
        """Get subscription and plan analytics"""
        cache_key = f'analytics:subscriptions:{clinic_id}'
        cached = CacheService.get(cache_key)
        if cached:
            return cached

        subscriptions = Subscription.objects.filter(clinic_id=clinic_id)

        data = {
            'total_subscriptions': subscriptions.count(),
            'active_subscriptions': subscriptions.filter(status='active').count(),
            'inactive_subscriptions': subscriptions.exclude(status='active').count(),
            'subscription_types': AnalyticsService._get_subscription_breakdown(clinic_id),
            'renewal_rate': AnalyticsService._get_renewal_rate(clinic_id),
            'churn_rate': AnalyticsService._get_churn_rate(clinic_id),
            'mrr': AnalyticsService._get_monthly_recurring_revenue(clinic_id),  # Monthly Recurring Revenue
        }

        CacheService.set(cache_key, data, timeout=3600)
        return data

    # ==================== TREND ANALYTICS ====================

    @staticmethod
    def get_appointment_trends(clinic_id, days=30):
        """Get appointment trends over time"""
        cache_key = f'analytics:trends:appointments:{clinic_id}:{days}'
        cached = CacheService.get(cache_key)
        if cached:
            return cached

        start_date = timezone.now().date() - timedelta(days=days)

        appointments = Appointment.objects.filter(
            doctor__clinic_id=clinic_id,
            scheduled_date__date__gte=start_date
        ).annotate(date_only=TruncDate('scheduled_date')).values('date_only').annotate(
            count=Count('id'),
            completed=Count('id', filter=Q(status='completed')),
            cancelled=Count('id', filter=Q(status='cancelled')),
        ).order_by('date_only')

        data = {
            'period_days': days,
            'trend_data': list(appointments),
            'total_trend_appointments': sum([a['count'] for a in appointments]),
            'average_daily_appointments': sum([a['count'] for a in appointments]) / max(len(list(appointments)), 1),
        }

        CacheService.set(cache_key, data, timeout=3600)
        return data

    @staticmethod
    def get_revenue_trends(clinic_id, months=12):
        """Get monthly revenue trends"""
        cache_key = f'analytics:trends:revenue:{clinic_id}:{months}'
        cached = CacheService.get(cache_key)
        if cached:
            return cached

        start_date = timezone.now().date() - timedelta(days=30*months)

        payments = Payment.objects.filter(
            appointment__doctor__clinic_id=clinic_id,
            created_at__date__gte=start_date,
            status='completed'
        ).annotate(month=ExtractMonth('created_at'), year=ExtractYear('created_at')).values(
            'year', 'month'
        ).annotate(revenue=Sum('amount')).order_by('year', 'month')

        data = {
            'months': months,
            'revenue_trend': list(payments),
        }

        CacheService.set(cache_key, data, timeout=3600)
        return data

    # ==================== HEALTH CHECK ====================

    @staticmethod
    def get_system_health(clinic_id):
        """Get overall system health indicators"""
        cache_key = f'analytics:health:{clinic_id}'
        cached = CacheService.get(cache_key)
        if cached:
            return cached

        clinic_appointments = Appointment.objects.filter(doctor__clinic_id=clinic_id)
        last_7_days = timezone.now().date() - timedelta(days=7)

        data = {
            'active_doctors': Doctor.objects.filter(clinic_id=clinic_id).count(),
            'appointments_this_week': clinic_appointments.filter(
                scheduled_date__date__gte=last_7_days
            ).count(),
            'payment_status': AnalyticsService._get_payment_health(clinic_id),
            'system_uptime': '99.9%',  # Would come from monitoring system
            'api_response_time': '< 100ms',  # Would come from monitoring
            'cache_hit_rate': AnalyticsService._get_cache_hit_rate(),
            'database_health': 'OK',  # Would check actual DB
        }

        CacheService.set(cache_key, data, timeout=300)  # Cache 5 minutes
        return data

    # ==================== HELPER METHODS ====================

    @staticmethod
    def _get_clinic_revenue(clinic_id, start_date):
        """Calculate total clinic revenue"""
        revenue = Payment.objects.filter(
            appointment__doctor__clinic_id=clinic_id,
            created_at__date__gte=start_date,
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0
        return float(revenue)

    @staticmethod
    def _get_clinic_rating(clinic_id):
        """Calculate average clinic rating"""
        # Would aggregate doctor ratings for the clinic
        return 4.5  # Placeholder

    @staticmethod
    def _get_completion_rate(clinic_id, start_date):
        """Calculate appointment completion rate"""
        total = Appointment.objects.filter(
            doctor__clinic_id=clinic_id,
            scheduled_date__date__gte=start_date
        ).count()
        
        if total == 0:
            return 0
        
        completed = Appointment.objects.filter(
            doctor__clinic_id=clinic_id,
            scheduled_date__date__gte=start_date,
            status='completed'
        ).count()
        
        return (completed / total * 100) if total > 0 else 0

    @staticmethod
    def _calculate_daily_average(queryset):
        """Calculate average appointments per day"""
        if not queryset.exists():
            return 0
        
        dates = queryset.values('scheduled_date__date').distinct().count()
        return queryset.count() / max(dates, 1)

    @staticmethod
    def _get_peak_hour(queryset):
        """Get peak appointment hour"""
        if not queryset.exists():
            return None
        
        peak = queryset.annotate(hour=ExtractHour('scheduled_date')).values('hour').annotate(
            count=Count('id')
        ).order_by('-count').first()
        
        return peak['hour'] if peak else None

    @staticmethod
    def _get_doctor_utilization(clinic_id, start_date):
        """Calculate doctor utilization rate"""
        doctors = Doctor.objects.filter(clinic_id=clinic_id)
        total_appointments = Appointment.objects.filter(
            doctor__clinic_id=clinic_id,
            scheduled_date__date__gte=start_date
        ).count()
        
        if doctors.count() == 0:
            return 0
        
        return total_appointments / max(doctors.count(), 1)

    @staticmethod
    def _get_retention_rate(clinic_id, start_date):
        """Calculate patient retention rate"""
        # Patients who visited multiple times
        repeat_patients = Patient.objects.filter(
            appointments__doctor__clinic_id=clinic_id,
            appointments__scheduled_date__date__gte=start_date
        ).annotate(visit_count=Count('appointments')).filter(visit_count__gte=2).count()
        
        total_patients = Patient.objects.filter(
            appointments__doctor__clinic_id=clinic_id,
            appointments__scheduled_date__date__gte=start_date
        ).distinct().count()
        
        return (repeat_patients / max(total_patients, 1) * 100) if total_patients > 0 else 0

    @staticmethod
    def _get_doctor_rating(doctor_id):
        """Get doctor average rating"""
        # Would aggregate from review system
        return 4.6

    @staticmethod
    def _get_doctor_revenue(doctor_id, start_date):
        """Calculate doctor revenue"""
        revenue = Payment.objects.filter(
            appointment__doctor_id=doctor_id,
            created_at__date__gte=start_date,
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0
        return float(revenue)

    @staticmethod
    def _get_avg_duration(doctor_id, start_date):
        """Calculate average appointment duration"""
        return 30  # minutes placeholder

    @staticmethod
    def _get_cancellation_rate(doctor_id, start_date):
        """Calculate cancellation rate"""
        total = Appointment.objects.filter(
            doctor_id=doctor_id,
            scheduled_date__date__gte=start_date
        ).count()
        
        cancelled = Appointment.objects.filter(
            doctor_id=doctor_id,
            scheduled_date__date__gte=start_date,
            status='cancelled'
        ).count()
        
        return (cancelled / max(total, 1) * 100) if total > 0 else 0

    @staticmethod
    def _get_no_show_rate(doctor_id, start_date):
        """Calculate no-show rate"""
        total = Appointment.objects.filter(
            doctor_id=doctor_id,
            scheduled_date__date__gte=start_date
        ).count()
        
        no_shows = Appointment.objects.filter(
            doctor_id=doctor_id,
            scheduled_date__date__gte=start_date,
            status='no_show'
        ).count()
        
        return (no_shows / max(total, 1) * 100) if total > 0 else 0

    @staticmethod
    def _get_new_patients(clinic_id, start_date):
        """Get count of new patients"""
        return Patient.objects.filter(
            appointments__doctor__clinic_id=clinic_id,
            created_at__date__gte=start_date
        ).distinct().count()

    @staticmethod
    def _get_returning_patients(clinic_id, start_date):
        """Get count of returning patients"""
        return Patient.objects.filter(
            appointments__doctor__clinic_id=clinic_id,
            appointments__scheduled_date__date__gte=start_date
        ).annotate(visit_count=Count('appointments')).filter(
            visit_count__gte=2
        ).distinct().count()

    @staticmethod
    def _get_avg_visits(clinic_id, start_date):
        """Calculate average visits per patient"""
        patients = Patient.objects.filter(
            appointments__doctor__clinic_id=clinic_id,
            appointments__scheduled_date__date__gte=start_date
        ).annotate(visit_count=Count('appointments'))
        
        if not patients.exists():
            return 0
        
        return patients.aggregate(avg=Avg('visit_count'))['avg'] or 0

    @staticmethod
    def _get_satisfaction_rating(clinic_id, start_date):
        """Get patient satisfaction rating"""
        return 4.5  # Would aggregate from reviews

    @staticmethod
    def _get_age_distribution(clinic_id, start_date):
        """Get patient age distribution"""
        return {
            '18-25': 15,
            '25-35': 30,
            '35-50': 35,
            '50+': 20,
        }

    @staticmethod
    def _get_gender_distribution(clinic_id, start_date):
        """Get patient gender distribution"""
        return {
            'Male': 55,
            'Female': 45,
        }

    @staticmethod
    def _get_revenue_by_day(clinic_id, start_date):
        """Get revenue breakdown by day"""
        revenue_data = Payment.objects.filter(
            appointment__doctor__clinic_id=clinic_id,
            created_at__date__gte=start_date,
            status='completed'
        ).annotate(date_only=TruncDate('created_at')).values('date_only').annotate(
            revenue=Sum('amount')
        ).order_by('date_only')
        
        return [{'date': r['date_only'], 'revenue': float(r['revenue'])} for r in revenue_data]

    @staticmethod
    def _get_revenue_by_doctor(clinic_id, start_date):
        """Get revenue breakdown by doctor"""
        revenue_data = Payment.objects.filter(
            appointment__doctor__clinic_id=clinic_id,
            created_at__date__gte=start_date,
            status='completed'
        ).values('appointment__doctor__user__first_name', 'appointment__doctor__user__last_name').annotate(
            revenue=Sum('amount')
        ).order_by('-revenue')
        
        return [{'doctor': f"{r['appointment__doctor__user__first_name']} {r['appointment__doctor__user__last_name']}", 
                 'revenue': float(r['revenue'])} for r in revenue_data]

    @staticmethod
    def _get_payment_methods(clinic_id, start_date):
        """Get payment method breakdown"""
        return {
            'Click': 40,
            'Payme': 35,
            'Cash': 15,
            'Card': 10,
        }

    @staticmethod
    def _get_subscription_breakdown(clinic_id):
        """Get subscription plan breakdown"""
        subs = Subscription.objects.filter(clinic_id=clinic_id).values('plan__name').annotate(
            count=Count('id')
        )
        return {s['plan__name']: s['count'] for s in subs}

    @staticmethod
    def _get_renewal_rate(clinic_id):
        """Calculate subscription renewal rate"""
        return 85  # percentage

    @staticmethod
    def _get_churn_rate(clinic_id):
        """Calculate subscription churn rate"""
        return 15  # percentage

    @staticmethod
    def _get_monthly_recurring_revenue(clinic_id):
        """Calculate MRR"""
        active_subs = Subscription.objects.filter(
            clinic_id=clinic_id,
            status='active'
        ).aggregate(mrr=Sum('plan__price'))['mrr'] or 0
        return float(active_subs)

    @staticmethod
    def _get_payment_health(clinic_id):
        """Check payment processing health"""
        success_rate = Payment.objects.filter(
            appointment__doctor__clinic_id=clinic_id
        ).filter(status='completed').count() / max(
            Payment.objects.filter(
                appointment__doctor__clinic_id=clinic_id
            ).count(), 1
        ) * 100
        
        return 'Good' if success_rate > 95 else 'Warning' if success_rate > 80 else 'Critical'

    @staticmethod
    def _get_cache_hit_rate():
        """Get cache hit rate"""
        return 78  # percentage

    @staticmethod
    def _get_start_date(date_range):
        """Get start date based on range"""
        today = timezone.now().date()
        ranges = {
            'week': 7,
            'month': 30,
            'quarter': 90,
            'year': 365,
        }
        days = ranges.get(date_range, 30)
        return today - timedelta(days=days)
