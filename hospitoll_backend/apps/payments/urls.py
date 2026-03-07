from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PaymentViewSet, InvoiceViewSet
from .payment_views import (
    InvoicePaymentViewSet,
    click_webhook,
    payment_callback,
    renew_subscription
)

router = DefaultRouter()
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'invoice-payments', InvoicePaymentViewSet, basename='invoice-payment')

urlpatterns = [
    path('', include(router.urls)),
    # Webhook endpoint for Click payment callback
    path('click-callback/', PaymentViewSet.as_view({'post': 'click_callback'}), name='click-callback'),
    # New payment endpoints
    path('click-webhook/', click_webhook, name='click-webhook'),
    path('callback/', payment_callback, name='payment-callback'),
    path('renew-subscription/', renew_subscription, name='renew-subscription'),
]
