"""
Celery tasks for subscriptions app.
Handles subscription-related background operations.
"""

from celery import shared_task
from django.utils import timezone
from .models import Subscription
from core.utils.email_service import EmailService
import logging

logger = logging.getLogger(__name__)


@shared_task
def check_and_deactivate_expired_subscriptions():
    """
    Periodically check for expired subscriptions and deactivate them.
    This should run every day via Celery Beat.
    """
    try:
        expired_count = 0
        subscriptions = Subscription.objects.filter(status='active')
        
        for subscription in subscriptions:
            if subscription.auto_deactivate_if_expired():
                expired_count += 1
                logger.info(f"Deactivated subscription: {subscription.id}")
        
        logger.info(f"Total deactivated subscriptions: {expired_count}")
        return {'deactivated': expired_count}
    except Exception as e:
        logger.error(f"Error deactivating subscriptions: {str(e)}")
        raise


@shared_task
def send_subscription_expiry_reminders():
    """
    Send reminders for subscriptions expiring in 3 days.
    This should run daily via Celery Beat.
    """
    try:
        reminder_count = 0
        subscriptions = Subscription.objects.filter(status='active')
        
        for subscription in subscriptions:
            days_remaining = subscription.days_remaining()
            
            if days_remaining and days_remaining <= 3 and days_remaining > 0:
                # Send reminder notification via email
                if subscription.subscriber_type == 'clinic' and subscription.clinic:
                    clinic = subscription.clinic
                    owner = clinic.owner
                    
                    # Send email to clinic owner
                    EmailService.send_subscription_expiry_warning(
                        clinic_email=owner.email,
                        clinic_name=clinic.name,
                        days_remaining=days_remaining,
                        renewal_link=f"http://localhost:3000/clinic-owner/subscription"  # Update with actual URL
                    )
                    
                    reminder_count += 1
                    logger.info(f"Sent expiry reminder for clinic subscription: {subscription.id}")
                
                elif subscription.subscriber_type == 'pharmacy' and subscription.pharmacy:
                    pharmacy = subscription.pharmacy
                    owner = pharmacy.owner
                    
                    # Send email to pharmacy owner
                    EmailService.send_subscription_expiry_warning(
                        clinic_email=owner.email,
                        clinic_name=pharmacy.name,
                        days_remaining=days_remaining,
                        renewal_link=f"http://localhost:3000/pharmacy-owner/subscription"  # Update with actual URL
                    )
                    
                    reminder_count += 1
                    logger.info(f"Sent expiry reminder for pharmacy subscription: {subscription.id}")
        
        logger.info(f"Total expiry reminders sent: {reminder_count}")
        return {'reminders_sent': reminder_count}
    except Exception as e:
        logger.error(f"Error sending subscription expiry reminders: {str(e)}")
        raise


@shared_task
def trial_to_pending_payment():
    """
    Convert trial subscriptions to pending_payment when trial ends.
    This should run daily via Celery Beat.
    """
    try:
        converted_count = 0
        now = timezone.now()
        
        trial_subscriptions = Subscription.objects.filter(
            status='trial',
            trial_end_date__lt=now
        )
        
        for subscription in trial_subscriptions:
            subscription.status = 'pending_payment'
            subscription.save()
            converted_count += 1
            logger.info(f"Converted subscription {subscription.id} to pending_payment")
        
        logger.info(f"Total conversions: {converted_count}")
        return {'converted': converted_count}
    except Exception as e:
        logger.error(f"Error converting subscriptions: {str(e)}")
        raise
