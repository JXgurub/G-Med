"""
Click API Integration Service for Uzbekistan
Handles payment processing via Click payment gateway
"""

import requests
import hmac
import hashlib
import json
from decimal import Decimal
from typing import Optional, Tuple
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class ClickAPIService:
    """Click payment gateway integration"""
    
    # Click API endpoints
    BASE_URL = "https://api.click.uz"
    INVOICE_CREATE_URL = f"{BASE_URL}/v2/merchant/invoice/create"
    INVOICE_CANCEL_URL = f"{BASE_URL}/v2/merchant/invoice/cancel"
    
    # Test endpoints (for development)
    TEST_BASE_URL = "https://sandbox.click.uz"
    TEST_INVOICE_CREATE_URL = f"{TEST_BASE_URL}/v2/merchant/invoice/create"
    TEST_INVOICE_CANCEL_URL = f"{TEST_BASE_URL}/v2/merchant/invoice/cancel"
    
    def __init__(self):
        """Initialize Click service with credentials"""
        self.merchant_id = settings.CLICK_MERCHANT_ID
        self.merchant_service_id = settings.CLICK_SERVICE_ID
        self.merchant_key = settings.CLICK_SECRET_KEY
        self.is_test = settings.CLICK_TEST_MODE
    
    @staticmethod
    def _generate_signature(data: str, secret_key: str) -> str:
        """Generate HMAC-SHA256 signature for Click API requests"""
        return hmac.new(
            secret_key.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def create_invoice(self, invoice_id: str, amount: float, return_url: str, description: str = "") -> dict:
        """
        Create invoice in Click system
        
        Args:
            invoice_id: Unique invoice identifier (UUID or order ID)
            amount: Amount in UZS (Uzbek Som)
            return_url: URL to redirect after payment
            description: Invoice description
            
        Returns:
            dict: Response from Click API
        """
        try:
            url = self.TEST_INVOICE_CREATE_URL if self.is_test else self.INVOICE_CREATE_URL
            
            # Prepare request data
            data = {
                "merchant_id": self.merchant_id,
                "service_id": self.merchant_service_id,
                "amount": int(amount * 100),  # Convert to tiyin (cents)
                "invoice_id": str(invoice_id),
                "return_url": return_url,
                "description": description or f"Invoice #{invoice_id}",
            }
            
            # Generate signature
            signature_str = f"{self.merchant_id}{self.merchant_service_id}{invoice_id}{amount}"
            signature = self._generate_signature(signature_str, self.merchant_key)
            
            data["sign_string"] = signature
            
            # Make request
            response = requests.post(
                url,
                json=data,
                timeout=10
            )
            
            result = response.json()
            
            if response.status_code == 200 and result.get('success'):
                logger.info(f"Invoice created successfully: {invoice_id}")
                return {
                    'success': True,
                    'invoice_url': result.get('invoice_url'),
                    'invoice_id': result.get('invoice_id'),
                    'click_invoice_id': result.get('click_invoice_id'),
                }
            else:
                logger.error(f"Failed to create invoice: {result}")
                return {
                    'success': False,
                    'error': result.get('error_note', 'Unknown error'),
                }
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error creating invoice: {str(e)}")
            return {
                'success': False,
                'error': f"Request failed: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Error creating invoice: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def verify_webhook_signature(self, data: dict, click_signature: str) -> bool:
        """
        Verify webhook signature from Click
        
        Args:
            data: Request data from Click webhook
            click_signature: Signature from Click header
            
        Returns:
            bool: True if signature is valid
        """
        try:
            # Prepare data for signature verification
            merchant_id = data.get('merchant_id')
            service_id = data.get('service_id')
            click_trans_id = data.get('click_trans_id')
            invoice_id = data.get('merchant_trans_id')
            amount = data.get('amount')
            action = data.get('action')
            error = data.get('error')
            status = data.get('status')
            
            # Signature format for verification
            signature_str = f"{click_trans_id}{self.merchant_key}{invoice_id}{amount}{action}{error}{status}"
            
            calculated_signature = self._generate_signature(signature_str, self.merchant_key)
            
            is_valid = calculated_signature == click_signature
            
            if not is_valid:
                logger.warning(f"Invalid webhook signature for invoice {invoice_id}")
            
            return is_valid
        
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False
    
    def handle_complete_callback(self, data: dict) -> Tuple[bool, str]:
        """
        Handle payment completion callback from Click
        
        Args:
            data: Callback data from Click
            
        Returns:
            tuple: (success, message)
        """
        try:
            invoice_id = data.get('merchant_trans_id')
            click_trans_id = data.get('click_trans_id')
            amount = data.get('amount')
            status = data.get('status')
            
            # Verify signature
            click_signature: Optional[str] = data.get('sign_string')
            if not click_signature or not self.verify_webhook_signature(data, click_signature):
                return False, "Invalid signature"
            
            # Import here to avoid circular imports
            from apps.payments.models import Payment
            from apps.subscriptions.models import Subscription, SubscriptionPlan, SubscriptionPayment
            from core.utils.helpers import activate_clinic_from_payment
            
            # Find payment by invoice ID
            try:
                payment = Payment.objects.get(id=invoice_id)
            except Payment.DoesNotExist:
                logger.error(f"Payment not found for invoice {invoice_id}")
                return False, f"Payment {invoice_id} not found"
            
            # Check amount (convert from tiyin to som)
            if amount and Decimal(str(amount / 100)) != payment.amount:
                logger.error(f"Amount mismatch for payment {invoice_id}")
                return False, "Amount mismatch"
            
            # Update payment status based on Click status
            if status == 1:  # Paid
                payment.status = 'confirmed'
                if click_trans_id:
                    payment.transaction_id = str(click_trans_id)
                payment.paid_date = timezone.now()
                payment.save()

                # If this is a subscription payment, activate subscription for 30 days
                if payment.payment_type == 'subscription':
                    subscription = None
                    subscriber_type = None

                    if payment.clinic:
                        subscriber_type = 'clinic'
                        subscription = getattr(payment.clinic, 'subscription', None)
                    elif payment.pharmacy:
                        subscriber_type = 'pharmacy'
                        subscription = getattr(payment.pharmacy, 'subscription', None)

                    if subscriber_type:
                        if not subscription:
                            plan = (
                                SubscriptionPlan.objects.filter(is_active=True, price=payment.amount)
                                .order_by('sort_order')
                                .first()
                            )
                            if not plan:
                                plan = SubscriptionPlan.objects.filter(is_active=True).order_by('sort_order').first()
                            if not plan:
                                plan = SubscriptionPlan.objects.create(
                                    name=f"Default {payment.amount} SUM",
                                    description="Auto-created plan for subscription payment",
                                    price=payment.amount,
                                    duration_days=30,
                                    is_active=True,
                                )

                            subscription = Subscription.objects.create(
                                subscriber_type=subscriber_type,
                                clinic=payment.clinic if subscriber_type == 'clinic' else None,
                                pharmacy=payment.pharmacy if subscriber_type == 'pharmacy' else None,
                                plan=plan,
                                status='pending_payment'
                            )

                        reference_number = str(payment.id)
                        existing = SubscriptionPayment.objects.filter(
                            subscription=subscription,
                            reference_number=reference_number,
                            status='confirmed'
                        ).first()

                        if not existing:
                            subscription_payment = SubscriptionPayment.objects.create(
                                subscription=subscription,
                                amount=payment.amount,
                                payment_method='card',
                                status='confirmed',
                                transaction_id=str(click_trans_id) if click_trans_id else '',
                                reference_number=reference_number,
                                notes='Click payment'
                            )
                            subscription_payment.paid_date = timezone.now()
                            subscription_payment.save(update_fields=['paid_date'])

                        # Ensure clinic/pharmacy is active and subscription is updated
                        if subscription.status != 'active':
                            activate_clinic_from_payment(subscription)

                logger.info(f"Payment {invoice_id} confirmed via Click transaction {click_trans_id}")
                return True, "Payment confirmed"
            
            elif status == 2:  # Cancelled
                payment.status = 'cancelled'
                if click_trans_id:
                    payment.transaction_id = str(click_trans_id)
                payment.save()
                
                logger.info(f"Payment {invoice_id} cancelled")
                return True, "Payment cancelled"
            
            return False, f"Unknown status: {status}"
        
        except Exception as e:
            logger.error(f"Error handling payment callback: {str(e)}")
            return False, str(e)
    
    @staticmethod
    def generate_payment_link(invoice_id: str, return_url: str) -> str:
        """
        Generate Click payment link for QR code or direct link
        
        Args:
            invoice_id: Invoice ID
            return_url: Return URL after payment
            
        Returns:
            str: Payment URL
        """
        base_url = settings.CLICK_TEST_URL if settings.CLICK_TEST_MODE else "https://click.uz"
        return f"{base_url}/pay/{invoice_id}"
    
    def cancel_invoice(self, invoice_id: str) -> dict:
        """
        Cancel invoice in Click system
        
        Args:
            invoice_id: Click invoice ID to cancel
            
        Returns:
            dict: Response from Click API
        """
        try:
            url = self.TEST_INVOICE_CANCEL_URL if self.is_test else self.INVOICE_CANCEL_URL
            
            data = {
                "merchant_id": self.merchant_id,
                "service_id": self.merchant_service_id,
                "invoice_id": str(invoice_id),
            }
            
            response = requests.post(
                url,
                json=data,
                timeout=10
            )
            
            result = response.json()
            
            if response.status_code == 200:
                logger.info(f"Invoice cancelled: {invoice_id}")
                return {'success': True, 'message': 'Invoice cancelled'}
            else:
                logger.error(f"Failed to cancel invoice: {result}")
                return {'success': False, 'error': result.get('error_note')}
        
        except Exception as e:
            logger.error(f"Error cancelling invoice: {str(e)}")
            return {'success': False, 'error': str(e)}


# Singleton instance
click_service = ClickAPIService()
