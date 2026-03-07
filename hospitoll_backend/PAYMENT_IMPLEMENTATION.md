# Payment System Implementation Guide

## Overview

The Hospitoll payment system is a comprehensive solution for processing payments through Click (Uzbekistan) and Stripe payment gateways. It supports:

- **Subscription payments** - Automatic clinic subscription renewals
- **Invoice payments** - Manual invoice payment processing
- **Subscription auto-pay** - Recurring automatic payments
- **Payment webhooks** - Real-time payment status updates
- **Multiple payment methods** - Click, Stripe, Bank Transfer, Cash
- **Audit trail** - Complete payment history and reconciliation

## Architecture

### Core Components

```
Payment System
├── PaymentService (core/payment_service.py)
│   ├── ClickPaymentService - Click API integration
│   ├── PaymentProcessor - Payment workflow
│   └── SubscriptionPaymentProcessor - Subscription renewals
├── Payment API (apps/payments/payment_views.py)
│   ├── InvoicePaymentViewSet - Invoice payment endpoints
│   ├── click_webhook - Webhook handler
│   ├── payment_callback - Callback handler
│   └── renew_subscription - Subscription renewal
├── Payment Tasks (core/payment_tasks.py)
│   ├── process_payment_confirmation - Async confirmation
│   ├── send_payment_confirmation_email - Email notifications
│   ├── check_overdue_invoices - Overdue checking
│   └── process_subscription_payment - Auto-pay processing
└── Frontend Integration (PaymentService.js, usePayment.js)
    ├── Payment initiation
    ├── Status polling
    └── Callback handling
```

### Data Model

**Invoice Model (Enhanced)**
```python
class Invoice(models.Model):
    # Existing fields...
    amount: Decimal                    # Payment amount
    description: TextField             # Payment description
    
    # Payment processing fields
    payment_status: CharField          # not_initiated, initiated, pending_payment, completed, failed, cancelled, paid
    payment_order_id: CharField        # Click order ID
    payment_transaction_id: CharField  # Click transaction ID
    payment_method: CharField          # click, stripe, cash, transfer
    payment_initiated_at: DateTime     # When payment started
    payment_confirmed_at: DateTime     # When payment was confirmed
    payment_cancelled_at: DateTime     # When payment was cancelled
```

## Integration Guide

### 1. Backend Setup

#### Step 1: Environment Configuration

Add to `.env`:

```dotenv
# Click Payment Gateway (Sandbox)
CLICK_MERCHANT_ID=your_merchant_id
CLICK_SERVICE_ID=your_service_id
CLICK_SECRET_KEY=your_secret_key
CLICK_MERCHANT_NAME=Hospitoll
CLICK_TEST_MODE=True
CLICK_TEST_URL=https://sandbox.click.uz

# Stripe Settings (Optional)
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Payment URLs
PAYMENT_RETURN_URL=http://localhost:3000/payment/success
PAYMENT_CALLBACK_URL=http://localhost:8000/api/v1/payments/click-callback/
PAYMENT_SUCCESS_CALLBACK=http://localhost:3000/payment/success
PAYMENT_FAILURE_CALLBACK=http://localhost:3000/payment/failed

# Subscription Auto-Pay
AUTO_PAY_ENABLED=False
AUTO_PAY_RETRY_ATTEMPTS=3
AUTO_PAY_RETRY_INTERVAL=3
```

#### Step 2: Database Migration

The Invoice model has been enhanced with payment fields:

```bash
python manage.py makemigrations
python manage.py migrate
```

#### Step 3: URL Configuration

URLs are automatically configured in `apps/payments/urls.py`:

```python
# Payment Endpoints
POST   /api/v1/payments/invoice-payments/{id}/initiate-payment/
GET    /api/v1/payments/invoice-payments/{id}/payment-status/
POST   /api/v1/payments/invoice-payments/{id}/cancel-payment/
POST   /api/v1/payments/renew-subscription/

# Webhook Endpoints
POST   /api/v1/payments/click-webhook/
GET    /api/v1/payments/callback/
```

### 2. Frontend Integration

#### Step 1: Install Dependencies

```bash
npm install axios
```

#### Step 2: Import Payment Service and Hooks

```javascript
import PaymentService from '@/services/PaymentService';
import { usePayment } from '@/hooks/usePayment';
```

#### Step 3: Use Payment Hook

```javascript
function PaymentComponent() {
  const {
    loading,
    error,
    paymentStatus,
    checkoutUrl,
    initiatePayment,
    redirectToPayment,
    pollPaymentStatus
  } = usePayment({ autoPolling: true });

  const handlePayment = async (invoiceId) => {
    try {
      const result = await initiatePayment(invoiceId);
      redirectToPayment();
    } catch (err) {
      console.error('Payment failed:', err);
    }
  };

  return (
    <div>
      {error && <div className="error">{error}</div>}
      <button 
        onClick={() => handlePayment(invoiceId)}
        disabled={loading}
      >
        {loading ? 'Processing...' : 'Pay Invoice'}
      </button>
    </div>
  );
}
```

## Payment Flow

### 1. Payment Initiation

```
Client Request
    ↓
initiatePayment(invoiceId)
    ↓
PaymentProcessor.initiate_payment()
    ↓
ClickPaymentService.create_payment_link()
    ↓
Generate Order ID & Signature
    ↓
Create Checkout URL
    ↓
Update Invoice (payment_status = 'pending_payment')
    ↓
Return Checkout URL to Client
    ↓
Redirect to Click Payment Page
```

### 2. Payment Processing (Click Handle)

```
Click Backend
    ↓
User enters card details
    ↓
Process payment
    ↓
Send verification webhook
    ↓
Hospitoll receives 'verify' action
    ↓
ClickPaymentService.verify_payment()
    ↓
Response: 0 (success/pending) or 1 (error)
    ↓
Click sends confirmation webhook
    ↓
Hospitoll receives 'confirm' action
    ↓
process_payment_confirmation task
    ↓
Update Invoice (payment_status = 'paid')
    ↓
Send confirmation email
    ↓
Activate subscription (if applicable)
```

### 3. Payment Confirmation

```
Webhook Received
    ↓
process_webhook()
    ↓
Verify Click signature
    ↓
Check action type (verify/confirm)
    ↓
For 'confirm':
  - Get Invoice from merchant_trans_id
  - Update status to 'paid'
  - Send confirmation email (async)
  - Activate subscription (async)
  ↓
Return XML response (error: 0)
```

## API Reference

### Initiate Payment

**Endpoint:** `POST /api/v1/payments/invoice-payments/{id}/initiate-payment/`

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/payments/invoice-payments/123/initiate-payment/ \
  -H "Authorization: Bearer $TOKEN"
```

**Response (Success):**
```json
{
  "success": true,
  "checkout_url": "https://sandbox.click.uz/pay?...",
  "order_id": "merchant_123_456_1234567890.123",
  "amount": 50000,
  "message": "Payment initiated successfully"
}
```

**Response (Error):**
```json
{
  "error": "Invoice already paid"
}
```

### Get Payment Status

**Endpoint:** `GET /api/v1/payments/invoice-payments/{id}/payment-status/`

**Request:**
```bash
curl -X GET http://localhost:8000/api/v1/payments/invoice-payments/123/payment-status/ \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "invoice_id": 123,
  "invoice_number": "INV-001",
  "amount": "50000.00",
  "status": "paid",
  "payment_status": "completed",
  "payment_initiated_at": "2024-01-15T10:30:00Z",
  "payment_confirmed_at": "2024-01-15T10:35:00Z",
  "payment_transaction_id": "click_trans_123456"
}
```

### Cancel Payment

**Endpoint:** `POST /api/v1/payments/invoice-payments/{id}/cancel-payment/`

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/payments/invoice-payments/123/cancel-payment/ \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "success": true,
  "message": "Payment cancelled"
}
```

### Renew Subscription

**Endpoint:** `POST /api/v1/payments/renew-subscription/`

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/payments/renew-subscription/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"subscription_id": 1}'
```

**Response:**
```json
{
  "success": true,
  "checkout_url": "https://sandbox.click.uz/pay?...",
  "order_id": "merchant_1_sub_1_1234567890.123",
  "amount": 500000
}
```

### Click Webhook

**Endpoint:** `POST /api/v1/payments/click-webhook/`

**Request Headers:**
```
Content-Type: application/x-www-form-urlencoded
```

**Request Body:**
```
click_trans_id=click_123456&
merchant_trans_id=123&
amount=5000000&
action=verify&
error=0&
sign_string=hash123
```

**Response (Success):**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<response>
    <click_trans_id>click_123456</click_trans_id>
    <merchant_trans_id>123</merchant_trans_id>
    <merchant_id>merchant_id</merchant_id>
    <error>0</error>
    <error_note>Success</error_note>
</response>
```

**Response (Error):**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<response>
    <click_trans_id>click_123456</click_trans_id>
    <merchant_trans_id>123</merchant_trans_id>
    <merchant_id>merchant_id</merchant_id>
    <error>1</error>
    <error_note>Invalid signature</error_note>
</response>
```

## Security

### Payment Security

1. **Signature Verification**
   - All Click webhooks are verified using HMAC-SHA256
   - Secret key is stored in environment variables
   - Signatures cannot be forged

2. **Data Validation**
   - Invoice amounts verified against stored amounts
   - Transaction IDs validated
   - Duplicate payments prevented using merchant_trans_id

3. **PCI Compliance**
   - Card details never stored on server
   - All payments processed through Click
   - HTTPS enforced in production
   - Sensitive data not logged

4. **Transaction Audit**
   - All payment events logged with timestamps
   - Complete payment history maintained
   - Transaction IDs stored for reconciliation

### CSRF Protection

All payment endpoints are CSRF-protected:

```python
# Webhook endpoint has CSRF disabled (safe - signed by Click)
@csrf_exempt
def click_webhook(request):
    ...

# Regular API endpoints are CSRF-protected
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def renew_subscription(request):
    ...
```

## Testing

### Test Payment Flow

1. **Initiate Payment:**
```bash
curl -X POST http://localhost:8000/api/v1/payments/invoice-payments/1/initiate-payment/ \
  -H "Authorization: Bearer $TOKEN"
```

2. **Get Response:**
```json
{
  "success": true,
  "checkout_url": "https://sandbox.click.uz/pay/...",
  "order_id": "merchant_1_1_timestamp"
}
```

3. **Open Checkout URL in Browser**
   - Click will show test payment page
   - Use test card: 9999000000000000
   - Use any future expiry date
   - Use any 3-digit CVV

4. **Process Click Test Payment:**
   - Click will send verification webhook
   - Then confirmation webhook
   - Check invoice status: `GET /invoices/{id}/payment-status/`

### Manual Testing

Use the test webhook:

```bash
curl -X POST http://localhost:8000/api/v1/payments/click-webhook/ \
  -d "click_trans_id=test_123&merchant_trans_id=1&amount=5000000&action=verify&error=0&sign_string=..."
```

## Celery Tasks

### Payment Tasks

All payment tasks are configured in `core/payment_tasks.py`:

```python
# Async payment confirmation
process_payment_confirmation(invoice_id, transaction_id)

# Send confirmation emails
send_payment_confirmation_email(invoice_id)

# Retry failed payments
retry_failed_payment(invoice_id)

# Check overdue invoices
check_overdue_invoices()

# Send overdue reminders
send_overdue_invoice_reminder(invoice_id)

# Process subscription auto-pay
process_subscription_payment(subscription_id)
```

### Scheduling

Tasks can be scheduled in Celery Beat:

```python
CELERY_BEAT_SCHEDULE = {
    'check-overdue-invoices': {
        'task': 'core.payment_tasks.check_overdue_invoices',
        'schedule': crontab(hour=9, minute=0),  # Daily at 9 AM
    },
    'process-subscription-renewals': {
        'task': 'core.payment_tasks.process_subscription_payment',
        'schedule': crontab(day_of_month=1, hour=0, minute=0),  # Monthly on 1st
    },
}
```

## Troubleshooting

### Payment Not Received

1. **Check webhook logs:**
```bash
tail -f logs/security.log | grep -i webhook
```

2. **Verify merchant credentials:**
```python
>>> from django.conf import settings
>>> settings.CLICK_MERCHANT_ID
>>> settings.CLICK_SECRET_KEY
```

3. **Check invoice status:**
```python
>>> from apps.payments.models import Invoice
>>> invoice = Invoice.objects.get(id=1)
>>> invoice.payment_status
>>> invoice.payment_transaction_id
```

### Invalid Signature Error

1. **Verify secret key matches:**
   - Check Click merchant settings
   - Compare with `.env` file
   - Regenerate if needed

2. **Check Click test mode:**
```python
>>> from django.conf import settings
>>> settings.CLICK_TEST_MODE
```

### Webhook Not Received

1. **Check webhook configuration in Click admin:**
   - Required URL: `{PAYMENT_CALLBACK_URL}/click-webhook/`
   - Method: POST
   - Active: Yes

2. **Verify firewall allows Click IPs:**
   - Click will send from specific IPs
   - Whitelist in production

3. **Check Django logs:**
```bash
tail -f logs/app.log | grep -i webhook
```

## Production Checklist

- [ ] Update `.env` with real Click merchant credentials
- [ ] Set `CLICK_TEST_MODE=False` in production
- [ ] Configure correct callback URLs (production domain)
- [ ] Set up database backups (invoices are sensitive)
- [ ] Enable Sentry error tracking
- [ ] Configure email backend for payment confirmations
- [ ] Set up Redis for Celery tasks
- [ ] Configure LOG files with proper permissions
- [ ] Enable HTTPS/SSL for all payment endpoints
- [ ] Set up rate limiting on payment endpoints
- [ ] Configure database replication/failover
- [ ] Set up payment reconciliation process
- [ ] Test webhook with production credentials
- [ ] Set up monitoring alerts for failed payments
- [ ] Document payment support procedures
- [ ] Train staff on payment troubleshooting

## Click Sandbox Credentials

For testing, use these sandbox credentials:

```
Merchant ID: (from Click sandbox)
Service ID: (from Click sandbox)
Secret Key: (from Click sandbox)
Test URL: https://sandbox.click.uz/v2
```

**Test Card Details:**
- Card Number: 9999000000000000
- Expiry: 12/25 (any future date)
- CVV: 999 (any 3 digits)

## Additional Resources

- Click Documentation: https://click.uz/docs
- Stripe Documentation: https://stripe.com/docs
- Django REST Framework: https://www.django-rest-framework.org/
- Celery Documentation: https://docs.celeryproject.org/
