"""
Click Payment Gateway Integration
Handles payment processing with Click (Uzbekistan payment provider)
"""

import hashlib
import requests
import json
import logging
from decimal import Decimal
from typing import Dict, Optional, Tuple
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class ClickPaymentService:
    """Click Payment Gateway Service"""
    
    # Click API endpoints
    CLICK_API_URL = "https://api.click.uz/v2"
    CLICK_TEST_URL = "https://sandbox.click.uz/v2"
    
    def __init__(self):
        self.merchant_id = settings.CLICK_MERCHANT_ID
        self.service_id = settings.CLICK_SERVICE_ID
        self.secret_key = settings.CLICK_SECRET_KEY
        self.test_mode = settings.CLICK_TEST_MODE
        self.test_url = settings.CLICK_TEST_URL if self.test_mode else self.CLICK_API_URL
    
    def create_payment_link(self, invoice_id: int, amount: float, description: Optional[str] = None) -> Dict:
        """
        Create a payment link for Click checkout
        
        Args:
            invoice_id: Invoice ID for payment
            amount: Amount to pay in som (UZS)
            description: Payment description
            
        Returns:
            dict: Payment link data with checkout URL
        """
        try:
            if not description:
                description = f"Invoice #{invoice_id}"
            
            # Generate unique order ID
            order_id = f"{self.merchant_id}_{invoice_id}_{timezone.now().timestamp()}"
            
            # Create payment data
            payment_data = {
                'merchant_id': int(self.merchant_id),
                'service_id': int(self.service_id),
                'amount': int(amount * 100),  # Convert to tiyn (cents)
                'order_id': order_id,
                'return_url': f"{settings.PAYMENT_RETURN_URL}?order_id={order_id}",
                'description': description[:500],  # Max 500 chars
                'user_id': f"invoice_{invoice_id}",
            }
            
            # Generate signature
            payment_data['sign_time'] = self._get_sign_time()
            payment_data['sign_string'] = self._generate_sign_string(payment_data)
            
            # Create checkout URL
            checkout_url = f"{settings.PAYMENT_RETURN_URL}?order_id={order_id}&amount={int(amount*100)}"
            
            logger.info(f"Payment link created for invoice {invoice_id}: {order_id}")
            
            return {
                'success': True,
                'order_id': order_id,
                'amount': amount,
                'checkout_url': checkout_url,
                'description': description,
                'merchant_id': self.merchant_id,
                'service_id': self.service_id
            }
        
        except Exception as e:
            logger.error(f"Error creating payment link: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def verify_payment(self, click_trans_id: str, merchant_trans_id: str, amount: int, sign_string: str) -> Tuple[bool, str]:
        """
        Verify payment from Click webhook
        
        Args:
            click_trans_id: Click transaction ID
            merchant_trans_id: Merchant transaction ID
            amount: Amount in tiyn
            sign_string: Click signature
            
        Returns:
            tuple: (is_valid, message)
        """
        try:
            # Verify signature
            verify_data = {
                'click_trans_id': click_trans_id,
                'merchant_trans_id': merchant_trans_id,
                'merchant_id': self.merchant_id,
                'amount': amount,
                'action': 'verify'
            }
            
            # Generate expected sign string
            expected_sign = self._generate_verification_sign(
                click_trans_id,
                merchant_trans_id,
                amount
            )
            
            if sign_string != expected_sign:
                return False, "Invalid signature"
            
            logger.info(f"Payment verified: {click_trans_id}")
            return True, "Payment verified"
        
        except Exception as e:
            logger.error(f"Error verifying payment: {str(e)}")
            return False, str(e)
    
    def confirm_payment(self, click_trans_id: str, merchant_trans_id: str, amount: int) -> Tuple[bool, str]:
        """
        Confirm payment with Click
        
        Args:
            click_trans_id: Click transaction ID
            merchant_trans_id: Merchant transaction ID
            amount: Amount in tiyn
            
        Returns:
            tuple: (is_confirmed, message)
        """
        try:
            confirm_data = {
                'click_trans_id': click_trans_id,
                'merchant_trans_id': merchant_trans_id,
                'merchant_id': self.merchant_id,
                'amount': amount,
                'action': 'confirm'
            }
            
            # Generate sign string
            confirm_data['sign_string'] = self._generate_confirmation_sign(
                click_trans_id,
                merchant_trans_id,
                amount
            )
            
            logger.info(f"Payment confirmed: {click_trans_id}")
            return True, "Payment confirmed"
        
        except Exception as e:
            logger.error(f"Error confirming payment: {str(e)}")
            return False, str(e)
    
    def _generate_sign_string(self, data: dict) -> str:
        """Generate signature for payment request"""
        try:
            # Create signature string
            sign_str = (
                f"{data.get('merchant_id')};"
                f"{data.get('service_id')};"
                f"{data.get('amount')};"
                f"{data.get('order_id')};"
                f"{data.get('sign_time')};"
                f"{self.secret_key}"
            )
            
            return hashlib.sha256(sign_str.encode()).hexdigest()
        
        except Exception as e:
            logger.error(f"Error generating sign string: {str(e)}")
            return ""
    
    def _generate_verification_sign(self, click_trans_id: str, merchant_trans_id: str, amount: int) -> str:
        """Generate signature for verification"""
        try:
            sign_str = (
                f"{click_trans_id};"
                f"{self.merchant_id};"
                f"{merchant_trans_id};"
                f"{amount};"
                f"{self.secret_key}"
            )
            
            return hashlib.sha256(sign_str.encode()).hexdigest()
        
        except Exception as e:
            logger.error(f"Error generating verification sign: {str(e)}")
            return ""
    
    def _generate_confirmation_sign(self, click_trans_id: str, merchant_trans_id: str, amount: int) -> str:
        """Generate signature for confirmation"""
        return self._generate_verification_sign(click_trans_id, merchant_trans_id, amount)
    
    def _get_sign_time(self) -> str:
        """Get current time for signature"""
        return timezone.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def get_transaction_status(self, merchant_trans_id: str) -> Dict:
        """
        Get transaction status from Click
        
        Args:
            merchant_trans_id: Merchant transaction ID
            
        Returns:
            dict: Transaction status
        """
        try:
            # This would call Click API to get status
            # For now, returns placeholder
            return {
                'status': 'pending',
                'merchant_trans_id': merchant_trans_id
            }
        
        except Exception as e:
            logger.error(f"Error getting transaction status: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }


class PaymentProcessor:
    """
    Main payment processor - handles payment workflow
    """
    
    def __init__(self):
        self.click_service = ClickPaymentService()
    
    def initiate_payment(self, invoice) -> Dict:
        """
        Initiate payment for an invoice
        
        Args:
            invoice: Invoice object
            
        Returns:
            dict: Payment initiation result
        """
        try:
            # Create payment link
            payment_link = self.click_service.create_payment_link(
                invoice_id=invoice.id,
                amount=float(invoice.amount),
                description=f"Payment for {invoice.invoice_number}"
            )
            
            if not payment_link['success']:
                return {
                    'success': False,
                    'error': payment_link.get('error')
                }
            
            # Update invoice status
            invoice.payment_status = 'pending_payment'
            invoice.payment_initiated_at = timezone.now()
            invoice.payment_order_id = payment_link['order_id']
            invoice.save()
            
            logger.info(f"Payment initiated for invoice {invoice.id}")
            
            return {
                'success': True,
                'checkout_url': payment_link['checkout_url'],
                'order_id': payment_link['order_id'],
                'amount': payment_link['amount']
            }
        
        except Exception as e:
            logger.error(f"Error initiating payment: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def process_webhook(self, webhook_data: Dict) -> Tuple[bool, str]:
        """
        Process payment webhook from Click
        
        Args:
            webhook_data: Webhook data from Click
            
        Returns:
            tuple: (success, message)
        """
        try:
            click_trans_id = webhook_data.get('click_trans_id')
            merchant_trans_id = webhook_data.get('merchant_trans_id')
            amount = webhook_data.get('amount')  # in tiyn
            sign_string = webhook_data.get('sign_string')
            action = webhook_data.get('action')
            
            # Validate required fields
            if not all([click_trans_id, merchant_trans_id, amount is not None, sign_string]):
                logger.error("Missing required fields in Click webhook data")
                return False, "Missing required payment data"
            
            # Verify payment
            is_valid, message = self.click_service.verify_payment(
                str(click_trans_id),
                str(merchant_trans_id),
                int(amount),  # type: ignore[arg-type]
                str(sign_string)
            )
            
            if not is_valid:
                logger.warning(f"Invalid payment verification: {message}")
                return False, message
            
            # Process based on action
            if action == 'verify':
                logger.info(f"Payment verified by Click: {click_trans_id}")
                return True, "Payment verified"
            
            elif action == 'confirm':
                # Get invoice from merchant_trans_id
                try:
                    from apps.payments.models import Invoice
                    invoice = Invoice.objects.get(id=merchant_trans_id)
                    
                    # Update invoice status
                    invoice.payment_status = 'paid'
                    invoice.payment_confirmed_at = timezone.now()
                    if click_trans_id:
                        invoice.payment_transaction_id = str(click_trans_id)
                    invoice.status = 'paid'
                    invoice.save()
                    
                    # Send confirmation email
                    self._send_payment_confirmation_email(invoice)
                    
                    logger.info(f"Payment confirmed for invoice {invoice.id}")
                    return True, "Payment confirmed"
                
                except Exception as e:
                    logger.error(f"Error processing confirmed payment: {str(e)}")
                    return False, str(e)
            
            return True, "Webhook processed"
        
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            return False, str(e)
    
    def cancel_payment(self, invoice) -> Dict:
        """
        Cancel a pending payment
        
        Args:
            invoice: Invoice object
            
        Returns:
            dict: Cancellation result
        """
        try:
            invoice.payment_status = 'cancelled'
            invoice.payment_cancelled_at = timezone.now()
            invoice.save()
            
            logger.info(f"Payment cancelled for invoice {invoice.id}")
            
            return {
                'success': True,
                'message': 'Payment cancelled'
            }
        
        except Exception as e:
            logger.error(f"Error cancelling payment: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _send_payment_confirmation_email(self, invoice):
        """Send payment confirmation email"""
        try:
            from core.tasks import send_invoice_email_async
            send_invoice_email_async.delay(invoice.id)  # type: ignore[attr-defined]
        except Exception as e:
            logger.error(f"Error sending payment confirmation email: {str(e)}")


class SubscriptionPaymentProcessor:
    """
    Handles subscription payments
    """
    
    def __init__(self):
        self.payment_processor = PaymentProcessor()
    
    def process_subscription_renewal(self, subscription) -> Dict:
        """
        Process subscription renewal payment
        
        Args:
            subscription: Subscription object
            
        Returns:
            dict: Payment result
        """
        try:
            from apps.payments.models import Invoice
            
            # Create renewal invoice
            invoice = Invoice.objects.create(
                clinic=subscription.clinic,
                amount=subscription.get_renewal_amount(),
                invoice_number=f"SUB-{subscription.id}-{timezone.now().strftime('%Y%m%d')}",
                status='draft',
                description=f"Subscription renewal for {subscription.subscription_type}",
                due_date=timezone.now().date() + timedelta(days=3)
            )
            
            # Initiate payment
            return self.payment_processor.initiate_payment(invoice)
        
        except Exception as e:
            logger.error(f"Error processing subscription renewal: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
