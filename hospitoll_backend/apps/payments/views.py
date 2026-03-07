"""
Payment views for handling payment operations and Click callbacks
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
import logging

from .models import Payment, Invoice
from .serializers import PaymentSerializer, InvoiceSerializer
from core.utils.click_payment import click_service
from core.utils.email_service import EmailService

logger = logging.getLogger(__name__)


class PaymentViewSet(viewsets.ModelViewSet):
    """ViewSet for payment operations"""
    
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_permissions(self):
        """
        Allow unauthenticated access to webhook callbacks
        """
        if self.action == 'click_callback':
            return [permissions.AllowAny()]
        return super().get_permissions()
    
    def perform_create(self, serializer):
        """
        Create a payment and generate Click invoice
        """
        payment = serializer.save()
        
        # Generate Click invoice
        try:
            result = click_service.create_invoice(
                invoice_id=str(payment.id),
                amount=float(payment.amount),
                return_url=settings.PAYMENT_RETURN_URL,
                description=payment.description
            )
            
            if result['success']:
                payment.transaction_id = result.get('click_invoice_id')
                payment.save()
                logger.info(f"Click invoice created for payment {payment.id}")
            else:
                logger.error(f"Failed to create Click invoice: {result.get('error')}")
                payment.status = 'failed'
                payment.notes = f"Click error: {result.get('error')}"
                payment.save()
        
        except Exception as e:
            logger.error(f"Error creating Click invoice: {str(e)}")
            payment.status = 'failed'
            payment.notes = f"Error: {str(e)}"
            payment.save()
    
    @action(detail=False, methods=['post'])
    def create_payment(self, request):
        """
        Create new payment for consultation/service
        
        Request data:
        {
            "payment_type": "consultation",
            "amount": 150000,
            "description": "Doctor consultation",
            "appointment_id": "uuid" (optional)
        }
        """
        try:
            if not settings.CLICK_MERCHANT_ID or not settings.CLICK_SERVICE_ID or not settings.CLICK_SECRET_KEY:
                return Response({
                    'success': False,
                    'error': 'Click sozlanmagan. Merchant ID, Service ID va Secret Key kerak.'
                }, status=status.HTTP_400_BAD_REQUEST)

            data = request.data.copy()
            data['payment_method'] = 'card'  # Default to Click payment
            data['status'] = 'pending'
            
            # Add patient if user is patient
            if hasattr(request.user, 'patient'):
                data['patient'] = request.user.patient.id

            # Add clinic/pharmacy if user is owner
            if hasattr(request.user, 'clinic'):
                data['clinic'] = request.user.clinic.id
            elif hasattr(request.user, 'pharmacy'):
                data['pharmacy'] = request.user.pharmacy.id

            # Normalize subscription payment defaults
            if data.get('payment_type') == 'subscription':
                if hasattr(request.user, 'clinic'):
                    clinic = request.user.clinic
                    if clinic.amount and clinic.amount > 0:
                        data['amount'] = clinic.amount
                    if not data.get('description'):
                        data['description'] = 'Klinika obuna to\'lovi'
                elif hasattr(request.user, 'pharmacy'):
                    pharmacy = request.user.pharmacy
                    if pharmacy.amount and pharmacy.amount > 0:
                        data['amount'] = pharmacy.amount
                    if not data.get('description'):
                        data['description'] = 'Dorixona obuna to\'lovi'
                else:
                    return Response({
                        'success': False,
                        'error': 'Obuna to\'lovi faqat klinika yoki dorixona egalari uchun.'
                    }, status=status.HTTP_400_BAD_REQUEST)

                if not data.get('amount') or Decimal(str(data.get('amount'))) <= 0:
                    return Response({
                        'success': False,
                        'error': 'Obuna uchun to\'lov miqdori admin tomonidan belgilanmagan.'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            
            payment = serializer.instance
            
            # Get Click payment link
            return Response({
                'success': True,
                'payment': serializer.data,
                'payment_url': click_service.generate_payment_link(
                    str(payment.id),
                    settings.PAYMENT_RETURN_URL
                )
            }, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            logger.error(f"Error creating payment: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def my_payments(self, request):
        """
        Get current user's payments
        """
        try:
            if hasattr(request.user, 'patient'):
                payments = Payment.objects.filter(patient=request.user.patient)
            elif hasattr(request.user, 'clinic'):
                payments = Payment.objects.filter(clinic=request.user.clinic)
            else:
                payments = Payment.objects.none()
            
            serializer = self.get_serializer(payments, many=True)
            return Response({
                'success': True,
                'payments': serializer.data
            })
        
        except Exception as e:
            logger.error(f"Error fetching payments: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def click_callback(self, request):
        """
        Handle Click payment callback
        
        This endpoint receives payment confirmation from Click API
        """
        try:
            data = request.data
            
            logger.info(f"Received Click callback for invoice {data.get('merchant_trans_id')}")
            
            # Verify merchant_id and service_id
            if (data.get('merchant_id') != settings.CLICK_MERCHANT_ID or 
                data.get('service_id') != settings.CLICK_SERVICE_ID):
                logger.error("Invalid merchant or service ID in callback")
                return JsonResponse({
                    'error': -4,
                    'error_note': 'Invalid merchant'
                })
            
            # Handle the callback
            success, message = click_service.handle_complete_callback(data)
            
            if success:
                logger.info(f"Payment processed successfully: {message}")
                return JsonResponse({
                    'error': 0,
                    'error_note': 'Success'
                })
            else:
                logger.error(f"Payment processing failed: {message}")
                return JsonResponse({
                    'error': -1,
                    'error_note': message
                })
        
        except Exception as e:
            logger.error(f"Error in Click callback: {str(e)}")
            return JsonResponse({
                'error': -3,
                'error_note': str(e)
            })
    
    @action(detail=True, methods=['post'])
    def cancel_payment(self, request, pk=None):
        """
        Cancel a pending payment
        """
        try:
            payment = self.get_object()
            
            if payment.status != 'pending':
                return Response({
                    'success': False,
                    'error': 'Can only cancel pending payments'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Cancel in Click
            if payment.transaction_id:
                result = click_service.cancel_invoice(payment.transaction_id)
                if not result['success']:
                    logger.error(f"Failed to cancel in Click: {result.get('error')}")
            
            # Mark as cancelled
            payment.status = 'cancelled'
            payment.save()
            
            serializer = self.get_serializer(payment)
            return Response({
                'success': True,
                'payment': serializer.data
            })
        
        except Exception as e:
            logger.error(f"Error cancelling payment: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def admin_create_subscription_payment(self, request):
        """
        Admin: create subscription payment link for clinic/pharmacy owner

        Request data:
        {
            "clinic_id": "uuid" (optional),
            "pharmacy_id": "uuid" (optional),
            "send_email": true (optional)
        }
        """
        try:
            user = request.user
            if not (getattr(user, 'is_administrator', False) or getattr(user, 'is_superuser', False)):
                return Response({
                    'success': False,
                    'error': 'Admin ruxsati talab qilinadi'
                }, status=status.HTTP_403_FORBIDDEN)

            clinic_id = request.data.get('clinic_id')
            pharmacy_id = request.data.get('pharmacy_id')
            send_email = bool(request.data.get('send_email'))

            if not clinic_id and not pharmacy_id:
                return Response({
                    'success': False,
                    'error': 'clinic_id yoki pharmacy_id yuborilishi kerak'
                }, status=status.HTTP_400_BAD_REQUEST)

            clinic = None
            pharmacy = None

            if clinic_id:
                from apps.clinics.models import Clinic
                clinic = Clinic.objects.get(id=clinic_id)
            if pharmacy_id:
                from apps.pharmacies.models import Pharmacy
                pharmacy = Pharmacy.objects.get(id=pharmacy_id)

            amount = None
            description = None
            recipient_email = None

            if clinic:
                amount = clinic.amount
                description = clinic.payment_description or 'Klinika obuna to\'lovi'
                recipient_email = clinic.owner.email
            elif pharmacy:
                amount = pharmacy.amount
                description = pharmacy.payment_description or 'Dorixona obuna to\'lovi'
                recipient_email = pharmacy.owner.email

            if not amount or amount <= 0:
                return Response({
                    'success': False,
                    'error': 'To\'lov miqdori belgilanmagan. Avval admin paneldan miqdorni kiriting.'
                }, status=status.HTTP_400_BAD_REQUEST)

            data = {
                'payment_type': 'subscription',
                'amount': amount,
                'description': description,
                'payment_method': 'card',
                'status': 'pending',
            }

            if clinic:
                data['clinic'] = clinic.id
            if pharmacy:
                data['pharmacy'] = pharmacy.id

            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)

            payment = serializer.instance
            payment_url = click_service.generate_payment_link(
                str(payment.id),
                settings.PAYMENT_RETURN_URL
            )

            if send_email and recipient_email:
                EmailService.send_email(
                    subject='Hospitoll obuna to\'lovi',
                    recipient_list=[recipient_email],
                    plain_text=(
                        'Assalomu alaykum!\n\n'
                        'Obuna to\'lovini amalga oshirish uchun quyidagi havolani bosing:\n'
                        f"{payment_url}\n\n"
                        'Hospitoll jamoasi'
                    ),
                    html_content=(
                        '<div style="font-family: Arial, sans-serif;">'
                        '<h2>Hospitoll obuna to\'lovi</h2>'
                        '<p>Obuna to\'lovini amalga oshirish uchun quyidagi havolani bosing:</p>'
                        f'<p><a href="{payment_url}" style="background:#4CAF50;color:#fff;'
                        'padding:10px 16px;text-decoration:none;border-radius:6px;">'
                        'To\'lovni boshlash</a></p>'
                        f'<p>Agar tugma ishlamasa, havola: {payment_url}</p>'
                        '</div>'
                    )
                )

            return Response({
                'success': True,
                'payment': serializer.data,
                'payment_url': payment_url
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error creating admin subscription payment: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def admin_approve_subscription(self, request):
        """
        Admin: manually approve/extend subscription by 30 days
        
        Request data:
        {
            "clinic_id": "uuid" (optional),
            "pharmacy_id": "uuid" (optional)
        }
        """
        try:
            user = request.user
            if not (getattr(user, 'is_administrator', False) or getattr(user, 'is_superuser', False)):
                return Response({
                    'success': False,
                    'error': 'Admin ruxsati talab qilinadi'
                }, status=status.HTTP_403_FORBIDDEN)

            clinic_id = request.data.get('clinic_id')
            pharmacy_id = request.data.get('pharmacy_id')

            if not clinic_id and not pharmacy_id:
                return Response({
                    'success': False,
                    'error': 'clinic_id yoki pharmacy_id yuborilishi kerak'
                }, status=status.HTTP_400_BAD_REQUEST)

            from apps.subscriptions.models import Subscription
            subscriber = None
            subscriber_type = None

            if clinic_id:
                from apps.clinics.models import Clinic
                subscriber = Clinic.objects.get(id=clinic_id)
                subscriber_type = 'clinic'
            elif pharmacy_id:
                from apps.pharmacies.models import Pharmacy
                subscriber = Pharmacy.objects.get(id=pharmacy_id)
                subscriber_type = 'pharmacy'

            if not subscriber:
                return Response({
                    'success': False,
                    'error': 'Klinika yoki dorixona topilmadi'
                }, status=status.HTTP_404_NOT_FOUND)

            # Get or create subscription
            subscription = None
            try:
                if subscriber_type == 'clinic':
                    subscription = Subscription.objects.get(clinic=subscriber)
                else:
                    subscription = Subscription.objects.get(pharmacy=subscriber)
            except Subscription.DoesNotExist:
                # Create new subscription if doesn't exist
                from apps.subscriptions.models import SubscriptionPlan
                # Get default plan or create one
                plan = SubscriptionPlan.objects.first()
                if not plan:
                    plan = SubscriptionPlan.objects.create(
                        name='Standard',
                        description='Standard obuna',
                        price=getattr(subscriber, 'amount', 100000) or 100000,
                        duration_days=30
                    )
                
                if subscriber_type == 'clinic':
                    subscription = Subscription.objects.create(
                        subscriber_type='clinic',
                        clinic=subscriber,
                        plan=plan,
                        status='pending_payment'
                    )
                else:
                    subscription = Subscription.objects.create(
                        subscriber_type='pharmacy',
                        pharmacy=subscriber,
                        plan=plan,
                        status='pending_payment'
                    )

            # Activate subscription for 30 days
            subscription.activate_by_payment()
            
            # Also update subscriber status to active
            subscriber.status = 'active'  # type: ignore
            subscriber.save()

            return Response({
                'success': True,
                'message': 'Obuna 30 kunga faollashtirildi',
                'subscription': {
                    'status': subscription.status,
                    'end_date': subscription.end_date.isoformat() if subscription.end_date else None,
                    'days_remaining': subscription.days_remaining()
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error approving subscription: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class InvoiceViewSet(viewsets.ModelViewSet):
    """ViewSet for invoice operations"""
    
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def create_from_payment(self, request):
        """
        Create invoice from payment
        """
        try:
            payment_id = request.data.get('payment_id')
            
            payment = Payment.objects.get(id=payment_id)
            
            # Create invoice
            invoice = Invoice.objects.create(
                invoice_number=f"INV-{payment.id}",
                clinic=payment.clinic,
                pharmacy=payment.pharmacy,
                patient=payment.patient,
                total_amount=payment.amount,
                net_amount=payment.amount,
                status='issued'
            )
            
            serializer = self.get_serializer(invoice)
            return Response({
                'success': True,
                'invoice': serializer.data
            }, status=status.HTTP_201_CREATED)
        
        except Payment.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Payment not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error creating invoice: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def send_email(self, request, pk=None):
        """
        Send invoice via email
        """
        try:
            invoice = self.get_object()
            
            if not invoice.patient or not invoice.patient.user.email:
                return Response({
                    'success': False,
                    'error': 'Patient email not found'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Prepare invoice data
            invoice_data = {
                'invoice_number': invoice.invoice_number,
                'amount': float(invoice.net_amount),
                'date': invoice.issued_date.isoformat(),
                'items': [
                    {
                        'description': 'Medical Service',
                        'quantity': 1,
                        'price': float(invoice.net_amount)
                    }
                ],
                'payment_link': settings.PAYMENT_RETURN_URL
            }
            
            # Send email
            success = EmailService.send_invoice_email(
                recipient_email=invoice.patient.user.email,
                recipient_name=invoice.patient.user.get_full_name(),
                invoice_data=invoice_data
            )
            
            if success:
                return Response({
                    'success': True,
                    'message': 'Invoice sent successfully'
                })
            else:
                return Response({
                    'success': False,
                    'error': 'Failed to send invoice'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            logger.error(f"Error sending invoice: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
