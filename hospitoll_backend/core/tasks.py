"""
Celery tasks for core/shared functionality.
Central location for email and notification tasks used across the app.
"""

from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.conf import settings
from core.utils.email_service import EmailService
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)
User = get_user_model()


# ============================================================================
# APPOINTMENT EMAIL TASKS
# ============================================================================

@shared_task
def send_appointment_reminder_async(appointment_id: int) -> dict:
    """
    Send appointment reminder email to patient (async via Celery).
    
    Args:
        appointment_id: Appointment ID
        
    Returns:
        dict: Task result with status
    """
    try:
        from apps.medical.models import Appointment
        
        appointment = Appointment.objects.select_related(
            'patient__user',
            'doctor__user',
            'doctor__clinic'
        ).get(id=appointment_id)
        
        appointment_data = {
            'patient_email': appointment.patient.user.email,
            'patient_name': appointment.patient.user.get_full_name() or appointment.patient.user.username,
            'doctor_name': appointment.doctor.user.get_full_name() or appointment.doctor.user.username,  # type: ignore[union-attr]
            'appointment_date': appointment.scheduled_date.strftime('%d.%m.%Y'),
            'appointment_time': appointment.scheduled_date.strftime('%H:%M'),
            'clinic_name': appointment.doctor.clinic.name if appointment.doctor.clinic else 'Hospitoll',  # type: ignore[union-attr]
        }
        
        success = EmailService.send_appointment_reminder(appointment_data)
        
        if success:
            logger.info(f"Appointment reminder sent for appointment {appointment_id}")
            return {'status': 'sent', 'appointment_id': appointment_id}
        else:
            logger.warning(f"Failed to send reminder for appointment {appointment_id}")
            return {'status': 'failed', 'appointment_id': appointment_id}
            
    except Exception as e:
        logger.error(f"Error sending appointment reminder for {appointment_id}: {str(e)}")
        raise


@shared_task
def send_upcoming_appointment_reminders() -> dict:
    """
    Send reminders for all appointments scheduled tomorrow.
    This should run daily via Celery Beat (recommended 8 AM).
    
    Returns:
        dict: Summary of reminders sent
    """
    try:
        from apps.medical.models import Appointment
        
        tomorrow = timezone.now().date() + timedelta(days=1)
        tomorrow_start = timezone.make_aware(
            timezone.datetime.combine(tomorrow, timezone.datetime.min.time())
        )
        tomorrow_end = timezone.make_aware(
            timezone.datetime.combine(tomorrow, timezone.datetime.max.time())
        )
        
        appointments = Appointment.objects.filter(
            status='scheduled',
            scheduled_date__range=[tomorrow_start, tomorrow_end]
        ).select_related('patient__user', 'doctor__user', 'doctor__clinic')
        
        reminder_count = 0
        for appointment in appointments:
            try:
                send_appointment_reminder_async.delay(appointment.id)  # type: ignore[attr-defined]
                reminder_count += 1
            except Exception as e:
                logger.error(f"Error queuing reminder for appointment {appointment.id}: {str(e)}")
        
        logger.info(f"Queued {reminder_count} appointment reminders for tomorrow")
        return {'reminders_queued': reminder_count, 'date': str(tomorrow)}
        
    except Exception as e:
        logger.error(f"Error in send_upcoming_appointment_reminders: {str(e)}")
        raise


# ============================================================================
# PASSWORD RESET EMAIL TASKS
# ============================================================================

@shared_task
def send_password_reset_email_async(user_id: int, reset_link: str) -> dict:
    """
    Send password reset email (async via Celery).
    
    Args:
        user_id: User ID
        reset_link: Password reset link to include in email
        
    Returns:
        dict: Task result with status
    """
    try:
        user = User.objects.get(id=user_id)
        
        success = EmailService.send_password_reset(
            user_email=user.email,
            user_name=user.get_full_name() or user.username,
            reset_link=reset_link
        )
        
        if success:
            logger.info(f"Password reset email sent to {user.email}")
            return {'status': 'sent', 'user_id': user_id}
        else:
            logger.warning(f"Failed to send password reset email to {user.email}")
            return {'status': 'failed', 'user_id': user_id}
            
    except Exception as e:
        logger.error(f"Error sending password reset email for user {user_id}: {str(e)}")
        raise


# ============================================================================
# SUBSCRIPTION EMAIL TASKS
# ============================================================================

@shared_task
def send_subscription_expiry_warning_async(subscription_id: int) -> dict:
    """
    Send subscription expiry warning email (async via Celery).
    
    Args:
        subscription_id: Subscription ID
        
    Returns:
        dict: Task result with status
    """
    try:
        from apps.subscriptions.models import Subscription
        
        subscription = Subscription.objects.select_related(
            'clinic__owner'
        ).get(id=subscription_id)
        
        days_remaining = subscription.days_remaining()
        
        if not days_remaining or days_remaining <= 0:
            logger.warning(f"Subscription {subscription_id} is already expired")
            return {'status': 'skipped', 'reason': 'already_expired'}
        
        renewal_link = f"{settings.FRONTEND_URL}/clinic/subscription/renew/{subscription.id}/"
        
        success = EmailService.send_subscription_expiry_warning(
            clinic_email=subscription.clinic.owner.email,  # type: ignore[union-attr]
            clinic_name=subscription.clinic.name,  # type: ignore[union-attr]
            days_remaining=days_remaining,
            renewal_link=renewal_link
        )
        
        if success:
            logger.info(f"Subscription expiry warning sent for subscription {subscription_id}")
            return {'status': 'sent', 'subscription_id': subscription_id, 'days_remaining': days_remaining}
        else:
            logger.warning(f"Failed to send expiry warning for subscription {subscription_id}")
            return {'status': 'failed', 'subscription_id': subscription_id}
            
    except Exception as e:
        logger.error(f"Error sending subscription expiry warning for {subscription_id}: {str(e)}")
        raise


@shared_task
def send_subscription_expiry_reminders_batch() -> dict:
    """
    Send expiry reminders for subscriptions expiring in 1-3 days.
    This should run daily via Celery Beat (recommended 9 AM).
    
    Returns:
        dict: Summary of reminders sent
    """
    try:
        from apps.subscriptions.models import Subscription
        
        subscriptions = Subscription.objects.filter(
            status='active'
        ).select_related('clinic__owner')
        
        reminder_count = 0
        for subscription in subscriptions:
            days_remaining = subscription.days_remaining()
            
            # Send reminder if expiring in 1-3 days
            if days_remaining and 1 <= days_remaining <= 3:
                try:
                    send_subscription_expiry_warning_async.delay(subscription.id)  # type: ignore[attr-defined]
                    reminder_count += 1
                except Exception as e:
                    logger.error(f"Error queuing expiry reminder for subscription {subscription.id}: {str(e)}")
        
        logger.info(f"Queued {reminder_count} subscription expiry reminders")
        return {'reminders_queued': reminder_count}
        
    except Exception as e:
        logger.error(f"Error in send_subscription_expiry_reminders_batch: {str(e)}")
        raise


# ============================================================================
# INVOICE EMAIL TASKS
# ============================================================================

@shared_task
def send_invoice_email_async(invoice_id: int) -> dict:
    """
    Send invoice email to recipient (async via Celery).
    
    Args:
        invoice_id: Invoice ID
        
    Returns:
        dict: Task result with status
    """
    try:
        from apps.payments.models import Invoice
        
        invoice = Invoice.objects.select_related('clinic', 'patient', 'pharmacy').get(id=invoice_id)
        
        # Prepare invoice data
        invoice_items = []
        
        # Since Invoice doesn't have items relationship, use invoice description and amount
        invoice_items.append({
            'description': invoice.description or f'Invoice #{invoice.invoice_number}',
            'quantity': 1,
            'price': float(invoice.amount)
        })
        total_amount = float(invoice.amount)
        
        invoice_data = {
            'invoice_number': invoice.invoice_number,
            'amount': total_amount,
            'date': invoice.created_at.strftime('%d.%m.%Y'),
            'items': invoice_items,
            'payment_link': f"{settings.FRONTEND_URL}/payment/{invoice.id}/"
        }
        
        # Determine recipient based on invoice type
        if invoice.patient:
            recipient_email = invoice.patient.user.email  # type: ignore[union-attr]
            recipient_name = invoice.patient.user.get_full_name() or invoice.patient.user.username  # type: ignore[union-attr]
        elif invoice.clinic:
            recipient_email = invoice.clinic.owner.email  # type: ignore[union-attr]
            recipient_name = invoice.clinic.name  # type: ignore[union-attr]
        elif invoice.pharmacy:
            recipient_email = invoice.pharmacy.email  # type: ignore[union-attr]
            recipient_name = invoice.pharmacy.name  # type: ignore[union-attr]
        else:
            logger.error(f"Invoice {invoice_id} has no recipient (no patient, clinic, or pharmacy)")
            return {'status': 'failed', 'invoice_id': invoice_id, 'reason': 'no_recipient'}
        
        success = EmailService.send_invoice_email(
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            invoice_data=invoice_data
        )
        
        if success:
            logger.info(f"Invoice email sent for invoice {invoice_id}")
            return {'status': 'sent', 'invoice_id': invoice_id}
        else:
            logger.warning(f"Failed to send invoice email for {invoice_id}")
            return {'status': 'failed', 'invoice_id': invoice_id}
            
    except Exception as e:
        logger.error(f"Error sending invoice email for {invoice_id}: {str(e)}")
        raise


@shared_task
def send_overdue_invoice_reminders() -> dict:
    """
    Send reminder emails for overdue invoices.
    This should run every 3 days via Celery Beat.
    
    Returns:
        dict: Summary of reminders sent
    """
    try:
        from apps.payments.models import Invoice
        
        overdue_invoices = Invoice.objects.filter(
            status='overdue'
        ).select_related('patient', 'clinic', 'pharmacy').order_by('-due_date')[:10]  # Limit to 10 per run
        
        reminder_count = 0
        for invoice in overdue_invoices:
            try:
                send_invoice_email_async.delay(invoice.id)  # type: ignore[attr-defined]
                reminder_count += 1
            except Exception as e:
                logger.error(f"Error queuing reminder for invoice {invoice.id}: {str(e)}")
        
        logger.info(f"Queued {reminder_count} overdue invoice reminders")
        return {'reminders_queued': reminder_count}
        
    except Exception as e:
        logger.error(f"Error in send_overdue_invoice_reminders: {str(e)}")
        raise


# ============================================================================
# NOTIFICATION EMAIL TASKS (GENERIC)
# ============================================================================

@shared_task
def send_welcome_email(user_id: int) -> dict:
    """
    Send welcome email to new user.
    
    Args:
        user_id: User ID
        
    Returns:
        dict: Task result with status
    """
    try:
        user = User.objects.get(id=user_id)
        
        user_role = user.get_role_display()  # type: ignore[attr-defined]
        user_name = user.get_full_name() or user.username
        
        subject = f"Hospitoll'ga Xush Kelibsiz - {user_role}"
        
        plain_text = f"""
Assalomu alaykim {user_name},

Hospitoll platformasiga ro'yxatdan o'tganingiz uchun rahmat!

Endi siz {user_role} sifatida platformamizdan foydalanishni boshlashingiz mumkin.

Qandaydir savol bo'lsa, biz bilan bog'laning: support@hospitoll.uz

Hospitoll jamiyati
        """
        
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; direction: rtl;">
                <h2>Hospitoll'ga Xush Kelibsiz! 👋</h2>
                <p>Assalomu alaykim {user_name},</p>
                
                <p>Hospitoll platformasiga ro'yxatdan o'tganingiz uchun rahmat!</p>
                
                <p>Endi siz <strong>{user_role}</strong> sifatida platformamizdan foydalanish uchun tayyor.</p>
                
                <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p><strong>Tahal boshlash uchun:</strong></p>
                    <ul>
                        <li>Profilengizni to'ldiring</li>
                        <li>Xizmatlarni o'rganib chiqing</li>
                        <li>FAQ bo'limiga qarang</li>
                    </ul>
                </div>
                
                <p style="margin-top: 20px; color: #666;">
                    Qandaydir savol bo'lsa, biz bilan bog'laning: <a href="mailto:support@hospitoll.uz">support@hospitoll.uz</a>
                </p>
                
                <p style="margin-top: 30px; color: #999; font-size: 12px;">
                    Hospitoll jamiyati
                </p>
            </body>
        </html>
        """
        
        success = EmailService.send_email(
            subject=subject,
            recipient_list=[user.email],
            plain_text=plain_text,
            html_content=html_content
        )
        
        if success:
            logger.info(f"Welcome email sent to {user.email}")
            return {'status': 'sent', 'user_id': user_id}
        else:
            logger.warning(f"Failed to send welcome email to {user.email}")
            return {'status': 'failed', 'user_id': user_id}
            
    except Exception as e:
        logger.error(f"Error sending welcome email for user {user_id}: {str(e)}")
        raise
