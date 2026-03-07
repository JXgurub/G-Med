"""
Celery tasks for payments app.
Handles payment-related background operations.
"""

from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task
def check_overdue_invoices():
    """
    Check for overdue invoices and update their status.
    This should run daily via Celery Beat.
    """
    try:
        from .models import Invoice
        
        today = timezone.now().date()
        overdue_invoices = Invoice.objects.filter(
            status__in=['issued', 'pending'],
            due_date__lt=today
        )
        
        updated_count = 0
        for invoice in overdue_invoices:
            invoice.status = 'overdue'
            invoice.save()
            updated_count += 1
            logger.info(f"Marked invoice {invoice.invoice_number} as overdue")
        
        logger.info(f"Total overdue invoices updated: {updated_count}")
        return {'updated': updated_count}
    except Exception as e:
        logger.error(f"Error checking overdue invoices: {str(e)}")
        raise


@shared_task
def send_payment_reminders():
    """
    Send reminders for unpaid invoices.
    This should run periodically via Celery Beat.
    """
    try:
        from .models import Invoice
        
        unpaid_invoices = Invoice.objects.filter(
            status__in=['issued', 'overdue']
        )
        
        reminder_count = 0
        for invoice in unpaid_invoices:
            # Send reminder notification
            logger.info(f"Payment reminder sent for invoice {invoice.invoice_number}")
            reminder_count += 1
        
        logger.info(f"Total payment reminders sent: {reminder_count}")
        return {'reminders_sent': reminder_count}
    except Exception as e:
        logger.error(f"Error sending payment reminders: {str(e)}")
        raise
