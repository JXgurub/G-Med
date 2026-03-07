"""
Payment Processing Tasks
Asynchronous tasks for payment operations using Celery
"""

from celery import shared_task
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from apps.payments.models import Invoice
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_payment_confirmation(self, invoice_id, transaction_id):
    """
    Process payment confirmation and update invoice status
    
    Args:
        invoice_id: Invoice ID (UUID or int)
        transaction_id: Click transaction ID
    """
    try:
        invoice = Invoice.objects.get(id=invoice_id)
        
        # Update invoice status
        invoice.payment_status = 'paid'
        invoice.payment_confirmed_at = timezone.now()
        invoice.payment_transaction_id = transaction_id
        invoice.status = 'paid'
        invoice.paid_date = timezone.now().date()
        invoice.save()
        
        # Send confirmation email
        send_payment_confirmation_email.delay(invoice_id)  # type: ignore[attr-defined]
        
        # Update subscription if applicable
        if hasattr(invoice.clinic, 'subscription'):
            update_subscription_status.delay(invoice.clinic.subscription.id)  # type: ignore[union-attr, attr-defined]
        
        logger.info(f"Payment confirmed for invoice {invoice_id}: {transaction_id}")
        return {
            'status': 'success',
            'invoice_id': str(invoice_id),
            'transaction_id': transaction_id
        }
    
    except Invoice.DoesNotExist:
        logger.error(f"Invoice not found: {invoice_id}")
        return {
            'status': 'error',
            'message': 'Invoice not found'
        }
    except Exception as e:
        logger.error(f"Error processing payment confirmation: {str(e)}")
        # Retry after 60 seconds
        raise self.retry(countdown=60, exc=e)


@shared_task
def send_payment_confirmation_email(invoice_id):
    """
    Send payment confirmation email to clinic admin
    
    Args:
        invoice_id: Invoice ID
    """
    try:
        invoice = Invoice.objects.get(id=invoice_id)
        
        # Get clinic admin email
        if invoice.clinic and invoice.clinic.owner:
            admin_email = invoice.clinic.owner.email
            
            subject = f"To'lov tasdiqlandi - Invoice {invoice.invoice_number}"
            
            confirmed_at = invoice.payment_confirmed_at.strftime('%Y-%m-%d %H:%M') if invoice.payment_confirmed_at else 'N/A'
            
            message = f"""
Salom!

Sizning to'lovingiz qabul qilindi.

Faktura raqami: {invoice.invoice_number}
Summa: {invoice.amount:,.0f} som
Sana: {confirmed_at}

Rahmat, Hospitoll.
            """
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [admin_email],
                fail_silently=False
            )
            
            logger.info(f"Payment confirmation email sent to {admin_email}")
    
    except Exception as e:
        logger.error(f"Error sending payment confirmation email: {str(e)}")


@shared_task(bind=True, max_retries=2)
def retry_failed_payment(self, invoice_id):
    """
    Retry processing of failed payment
    
    Args:
        invoice_id: Invoice ID
    """
    try:
        invoice = Invoice.objects.get(id=invoice_id)
        
        if invoice.payment_status == 'failed':
            # Reset payment status to allow retry
            invoice.payment_status = 'initiated'
            invoice.save()
            
            # Send retry notification to clinic admin
            send_payment_retry_notification.delay(invoice_id)  # type: ignore[attr-defined]
            
            logger.info(f"Payment retry initiated for invoice {invoice_id}")
            return {'status': 'retry_initiated'}
    
    except Exception as e:
        logger.error(f"Error retrying payment: {str(e)}")
        raise self.retry(countdown=300, exc=e)


@shared_task
def send_payment_retry_notification(invoice_id):
    """
    Send notification to clinic about payment retry\
    
    Args:
        invoice_id: Invoice ID
    """
    try:
        invoice = Invoice.objects.get(id=invoice_id)
        
        if invoice.clinic and invoice.clinic.owner:
            admin_email = invoice.clinic.owner.email
            
            subject = f"To'lov qayta urinish - Invoice {invoice.invoice_number}"
            
            message = f"""
Salom!

Sizning to'lovingizni qayta urinish uchun yuborildik.

Faktura raqami: {invoice.invoice_number}
Summa: {invoice.amount:,.0f} som

Iltimos, to'lovni qayta bajarishga urinib ko'ring.

Rahmat, Hospitoll.
            """
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [admin_email],
                fail_silently=False
            )
    
    except Exception as e:
        logger.error(f"Error sending payment retry notification: {str(e)}")


@shared_task
def check_overdue_invoices():
    """
    Check for overdue invoices and send reminders
    """
    try:
        from datetime import timedelta
        
        # Find invoices that are unpaid and overdue
        overdue_date = timezone.now().date() - timedelta(days=1)
        
        overdue_invoices = Invoice.objects.filter(
            status__in=['issued', 'overdue'],
            payment_status__in=['not_initiated', 'initiated', 'failed'],
            due_date__lt=overdue_date
        )
        
        for invoice in overdue_invoices:
            # Update status to overdue
            if invoice.status != 'overdue':
                invoice.status = 'overdue'
                invoice.save()
            
            # Send reminder email
            send_overdue_invoice_reminder.delay(invoice.id)  # type: ignore[attr-defined]
        
        logger.info(f"Checked {overdue_invoices.count()} overdue invoices")
        return {'checked': overdue_invoices.count()}
    
    except Exception as e:
        logger.error(f"Error checking overdue invoices: {str(e)}")


@shared_task
def send_overdue_invoice_reminder(invoice_id):
    """
    Send overdue invoice reminder email
    
    Args:
        invoice_id: Invoice ID
    """
    try:
        invoice = Invoice.objects.get(id=invoice_id)
        
        if invoice.clinic and invoice.clinic.owner:
            admin_email = invoice.clinic.owner.email
            
            subject = f"Muddatidan o'tgan faktura - Invoice {invoice.invoice_number}"
            
            if invoice.due_date:
                days_overdue = (timezone.now().date() - invoice.due_date).days
                due_date_str = invoice.due_date.strftime('%Y-%m-%d')
            else:
                days_overdue = 0
                due_date_str = 'N/A'
            
            message = f"""
Salom!

Sizning fakturangiz muddatidan o'tgan.

Faktura raqami: {invoice.invoice_number}
Summa: {invoice.amount:,.0f} som
Muddati tugash sanasi: {due_date_str}
Muddatidan o'tgan kunlar: {days_overdue}

Iltimos, imkon qadar tezroq to'lovni bajaring.

Rahmat, Hospitoll.
            """
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [admin_email],
                fail_silently=False
            )
            
            logger.info(f"Overdue reminder sent to {admin_email}")
    
    except Exception as e:
        logger.error(f"Error sending overdue invoice reminder: {str(e)}")


@shared_task
def process_subscription_payment(subscription_id):
    """
    Process automatic subscription renewal payment
    
    Args:
        subscription_id: Subscription ID
    """
    try:
        from apps.subscriptions.models import Subscription
        from core.payment_service import SubscriptionPaymentProcessor
        
        subscription = Subscription.objects.get(id=subscription_id)
        
        # Check if subscription should be auto-renewed
        if subscription.status != 'active':
            return {'status': 'subscription_inactive'}
        
        # Process renewal
        processor = SubscriptionPaymentProcessor()
        result = processor.process_subscription_renewal(subscription)
        
        if result['success']:
            logger.info(f"Subscription payment processed for subscription {subscription_id}")
            return result
        else:
            logger.error(f"Subscription payment failed: {result.get('error')}")
            return result
    
    except Exception as e:
        logger.error(f"Error processing subscription payment: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }


@shared_task
def update_subscription_status(subscription_id):
    """
    Update subscription status after payment
    
    Args:
        subscription_id: Subscription ID
    """
    try:
        from apps.subscriptions.models import Subscription
        
        subscription = Subscription.objects.get(id=subscription_id)
        
        # Check if latest invoice is paid
        latest_invoice = subscription.clinic.invoices_issued.filter(  # type: ignore[union-attr]
            status='paid'
        ).latest('payment_confirmed_at')
        
        if latest_invoice:
            # Extend subscription end date
            from datetime import timedelta
            subscription.end_date = timezone.now() + timedelta(
                days=subscription.plan.duration_days
            )
            subscription.status = 'active'
            subscription.save()
            
            logger.info(f"Subscription {subscription_id} activated/renewed")
    
    except Exception as e:
        logger.error(f"Error updating subscription status: {str(e)}")


@shared_task
def generate_monthly_invoices():
    """
    Generate monthly invoices for active subscriptions
    """
    try:
        from apps.subscriptions.models import Subscription
        from datetime import timedelta
        
        # Get active subscriptions
        active_subscriptions = Subscription.objects.filter(
            is_active=True,
            billing_cycle='monthly'
        )
        
        created_count = 0
        
        for subscription in active_subscriptions:
            # Check if invoice for current month already exists
            today = timezone.now().date()
            first_day = today.replace(day=1)
            
            existing = Invoice.objects.filter(
                clinic=subscription.clinic,
                issued_date__gte=first_day,
                issued_date__lt=today + timedelta(days=1)
            ).exists()
            
            if not existing:
                # Create new invoice
                amount = subscription.plan.price
                due_date = today + timedelta(days=30)
                
                invoice = Invoice.objects.create(
                    invoice_number=f"INV-{subscription.clinic.id}-{today.strftime('%Y%m%d')}",  # type: ignore[union-attr]
                    clinic=subscription.clinic,
                    amount=amount,
                    status='issued',
                    description=f"Subscription: {subscription.plan.name}",
                    due_date=due_date
                )
                created_count += 1
        
        logger.info(f"Generated {created_count} monthly invoices")
        return {'created': created_count}
    
    except Exception as e:
        logger.error(f"Error generating monthly invoices: {str(e)}")
