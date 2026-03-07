"""
Utility functions for the Hospitoll platform.
Includes helpers for common operations.
"""

from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg, Count


def calculate_doctor_rating(doctor):
    """
    Calculate average rating for a doctor.
    Updates the doctor's rating field.
    """
    ratings = doctor.ratings.all()
    if ratings.exists():
        avg_rating = ratings.aggregate(Avg('rating'))['rating__avg']
        doctor.rating = avg_rating
        doctor.total_ratings = ratings.count()
        doctor.save(update_fields=['rating', 'total_ratings'])
        return avg_rating
    return 0.0


def calculate_clinic_rating(clinic):
    """
    Calculate average rating for a clinic.
    """
    doctors = clinic.doctors.all()
    if doctors.exists():
        avg_rating = doctors.aggregate(Avg('rating'))['rating__avg']
        clinic.rating = avg_rating
        clinic.total_ratings = doctors.aggregate(Count('ratings'))['ratings__count']
        clinic.save(update_fields=['rating', 'total_ratings'])
        return avg_rating
    return 0.0


def check_and_deactivate_expired_subscriptions():
    """
    Check all subscriptions and deactivate expired ones.
    This should be run periodically via Celery task.
    """
    from apps.subscriptions.models import Subscription
    
    expired_subscriptions = Subscription.objects.filter(
        status='active',
        end_date__lt=timezone.now()
    )
    
    count = 0
    for subscription in expired_subscriptions:
        subscription.auto_deactivate_if_expired()
        count += 1
    
    return count


def activate_clinic_from_payment(subscription):
    """
    Activate a clinic subscription and associated organization.
    """
    if subscription.subscriber_type == 'clinic' and subscription.clinic:
        clinic = subscription.clinic
        clinic.status = 'active'
        clinic.is_blocked = False
        clinic.save()
    elif subscription.subscriber_type == 'pharmacy' and subscription.pharmacy:
        pharmacy = subscription.pharmacy
        pharmacy.status = 'active'
        pharmacy.is_blocked = False
        pharmacy.save()
    
    subscription.activate_by_payment()
    return subscription


def get_doctor_statistics(doctor):
    """
    Get statistics for a doctor.
    """
    from apps.medical.models import Appointment
    from apps.patients.models import PatientDoctorRating
    
    total_appointments = Appointment.objects.filter(doctor=doctor).count()
    completed_appointments = Appointment.objects.filter(
        doctor=doctor,
        status='completed'
    ).count()
    
    ratings = PatientDoctorRating.objects.filter(doctor=doctor)
    avg_rating = ratings.aggregate(Avg('rating'))['rating__avg'] or 0.0
    
    return {
        'total_appointments': total_appointments,
        'completed_appointments': completed_appointments,
        'avg_rating': avg_rating,
        'total_ratings': ratings.count(),
    }


def get_clinic_statistics(clinic):
    """
    Get statistics for a clinic.
    """
    from apps.medical.models import Appointment
    
    total_doctors = clinic.doctors.filter(is_active=True).count()
    total_patients = clinic.patients.filter(is_active=True).count()
    total_appointments = Appointment.objects.filter(clinic=clinic).count()
    
    return {
        'total_doctors': total_doctors,
        'total_patients': total_patients,
        'total_appointments': total_appointments,
    }


def get_patient_age(patient):
    """
    Calculate patient's age from date of birth.
    """
    if patient.date_of_birth:
        today = timezone.now().date()
        return today.year - patient.date_of_birth.year - (
            (today.month, today.day) < (patient.date_of_birth.month, patient.date_of_birth.day)
        )
    return None


def send_subscription_expiry_notification(subscription):
    """
    Send notification when subscription is about to expire.
    This should be integrated with actual notification service.
    """
    subscriber = subscription.get_subscriber()
    days_remaining = subscription.days_remaining()
    
    if days_remaining and days_remaining <= 3:
        # Integration with email/SMS service would go here
        # For now, just a placeholder
        return {
            'subscriber': subscriber.name,
            'days_remaining': days_remaining,
            'message': f'Obunangiz {days_remaining} kundan keyin tugaydi.'
        }
    return None
