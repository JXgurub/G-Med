"""
Payment Processing Endpoints
REST API for payment operations
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from decimal import Decimal
import logging
import json

from apps.payments.models import Invoice
from apps.payments.serializers import InvoiceSerializer
from core.payment_service import PaymentProcessor, SubscriptionPaymentProcessor
from core.permissions import IsClinicAdmin

logger = logging.getLogger(__name__)


class PaymentInitiationSerializer:
    """Serializer-like class for payment workflows"""
    
    @staticmethod
    def validate_invoice_payment(invoice):
        """Validate invoice can be paid"""
        if invoice.status == 'paid':
            return False, "Invoice already paid"
        if invoice.status == 'cancelled':
            return False, "Invoice is cancelled"
        if invoice.amount <= 0:
            return False, "Invalid invoice amount"
        return True, "Valid"


class InvoicePaymentViewSet(viewsets.ModelViewSet):
    """
    Invoice payment operations
    
    Endpoints:
    - GET /invoices/ - List invoices
    - POST /invoices/{id}/initiate-payment/ - Start payment process
    - POST /invoices/{id}/cancel-payment/ - Cancel pending payment
    - GET /invoices/{id}/payment-status/ - Get payment status
    """
    
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):  # type: ignore[override]
        """Filter invoices by user's clinic"""
        user = self.request.user
        if hasattr(user, 'clinic'):
            return Invoice.objects.filter(clinic=user.clinic)  # type: ignore[attr-defined]
        return Invoice.objects.none()
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def initiate_payment(self, request, pk=None):
        """
        Initiate payment for invoice
        
        POST /invoices/{id}/initiate-payment/
        """
        try:
            invoice = self.get_object()
            
            # Validate payment
            is_valid, message = PaymentInitiationSerializer.validate_invoice_payment(invoice)
            if not is_valid:
                return Response(
                    {'error': message},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Process payment
            processor = PaymentProcessor()
            result = processor.initiate_payment(invoice)
            
            if result['success']:
                return Response(
                    {
                        'success': True,
                        'checkout_url': result['checkout_url'],
                        'order_id': result['order_id'],
                        'amount': result['amount'],
                        'message': 'Payment initiated successfully'
                    },
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {'error': result.get('error', 'Payment initiation failed')},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        except Invoice.DoesNotExist:
            return Response(
                {'error': 'Invoice not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error initiating payment: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def cancel_payment(self, request, pk=None):
        """
        Cancel pending payment
        
        POST /invoices/{id}/cancel-payment/
        """
        try:
            invoice = self.get_object()
            
            if invoice.payment_status not in ['pending_payment', 'initiated']:
                return Response(
                    {'error': 'Payment cannot be cancelled in current state'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Cancel payment
            processor = PaymentProcessor()
            result = processor.cancel_payment(invoice)
            
            return Response(result, status=status.HTTP_200_OK)
        
        except Invoice.DoesNotExist:
            return Response(
                {'error': 'Invoice not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error cancelling payment: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def payment_status(self, request, pk=None):
        """
        Get payment status for invoice
        
        GET /invoices/{id}/payment-status/
        """
        try:
            invoice = self.get_object()
            
            return Response(
                {
                    'invoice_id': invoice.id,
                    'invoice_number': invoice.invoice_number,
                    'amount': str(invoice.amount),
                    'status': invoice.status,
                    'payment_status': invoice.payment_status,
                    'payment_initiated_at': invoice.payment_initiated_at,
                    'payment_confirmed_at': invoice.payment_confirmed_at,
                    'payment_transaction_id': invoice.payment_transaction_id
                },
                status=status.HTTP_200_OK
            )
        
        except Invoice.DoesNotExist:
            return Response(
                {'error': 'Invoice not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error getting payment status: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@csrf_exempt
@require_http_methods(["POST"])
def click_webhook(request):
    """
    Handle Click payment webhook
    
    POST /api/payments/click-webhook/
    
    Webhook data:
    {
        "click_trans_id": "string",
        "merchant_trans_id": "string",
        "amount": int (in tiyn),
        "action": "verify|confirm",
        "error": "0|1",
        "sign_string": "string"
    }
    """
    try:
        # Parse request data
        if request.content_type == 'application/json':
            webhook_data = json.loads(request.body)
        else:
            webhook_data = request.POST
        
        # Process webhook
        processor = PaymentProcessor()
        success, message = processor.process_webhook(webhook_data)
        
        # Click expects XML response
        if success:
            response_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<response>
    <click_trans_id>{}</click_trans_id>
    <merchant_trans_id>{}</merchant_trans_id>
    <merchant_id>{}</merchant_id>
    <error>0</error>
    <error_note>Success</error_note>
</response>'''.format(
                webhook_data.get('click_trans_id'),
                webhook_data.get('merchant_trans_id'),
                webhook_data.get('merchant_id')
            )
        else:
            response_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<response>
    <click_trans_id>{}</click_trans_id>
    <merchant_trans_id>{}</merchant_trans_id>
    <merchant_id>{}</merchant_id>
    <error>1</error>
    <error_note>{}</error_note>
</response>'''.format(
                webhook_data.get('click_trans_id'),
                webhook_data.get('merchant_trans_id'),
                webhook_data.get('merchant_id'),
                message
            )
        
        return Response(response_xml, content_type='application/xml', status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error processing Click webhook: {str(e)}")
        return Response(
            {
                'error': 1,
                'error_note': str(e)
            },
            status=status.HTTP_200_OK,
            content_type='application/xml'
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_callback(request):
    """
    Handle payment callback (redirect from Click)
    
    GET /api/payments/callback/?order_id=xxx&status=xxx
    
    Query parameters:
    - order_id: Payment order ID
    - status: Payment status (pending, completed, failed)
    """
    try:
        order_id = request.GET.get('order_id')
        status_param = request.GET.get('status', 'pending')
        
        # Find invoice by order ID
        try:
            invoice = Invoice.objects.get(payment_order_id=order_id)
        except Invoice.DoesNotExist:
            return Response(
                {'error': 'Invoice not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update status based on callback
        if status_param == 'success':
            invoice.payment_status = 'completed'
            message = 'Payment successful'
        elif status_param == 'cancelled':
            invoice.payment_status = 'cancelled'
            message = 'Payment cancelled'
        else:
            invoice.payment_status = 'pending'
            message = 'Payment pending'
        
        invoice.save()
        
        return Response(
            {
                'success': True,
                'invoice_id': invoice.id,
                'status': invoice.payment_status,
                'message': message
            },
            status=status.HTTP_200_OK
        )
    
    except Exception as e:
        logger.error(f"Error processing payment callback: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def renew_subscription(request):
    """
    Initiate subscription renewal payment
    
    POST /api/payments/renew-subscription/
    
    Request body:
    {
        "subscription_id": int
    }
    """
    try:
        subscription_id = request.data.get('subscription_id')
        
        from apps.subscriptions.models import Subscription
        
        try:
            subscription = Subscription.objects.get(id=subscription_id)
        except Subscription.DoesNotExist:
            return Response(
                {'error': 'Subscription not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verify user owns subscription
        clinic = getattr(request.user, 'clinic', None)
        if subscription.clinic != clinic:
            return Response(
                {'error': 'Unauthorized'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Process renewal
        processor = SubscriptionPaymentProcessor()
        result = processor.process_subscription_renewal(subscription)
        
        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(
                result,
                status=status.HTTP_400_BAD_REQUEST
            )
    
    except Exception as e:
        logger.error(f"Error renewing subscription: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
