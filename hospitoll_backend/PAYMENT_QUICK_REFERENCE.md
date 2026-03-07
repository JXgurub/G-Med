# Payment System Quick Reference Guide

## 🔗 API Endpoints

### Invoice Payment Management

| Method | Endpoint | Purpose | Auth |
|--------|----------|---------|------|
| POST | `/api/v1/payments/invoice-payments/{id}/initiate-payment/` | Start payment | JWT |
| GET | `/api/v1/payments/invoice-payments/{id}/payment-status/` | Check status | JWT |
| POST | `/api/v1/payments/invoice-payments/{id}/cancel-payment/` | Cancel payment | JWT |

### Subscription Management

| Method | Endpoint | Purpose | Auth |
|--------|----------|---------|------|
| POST | `/api/v1/payments/renew-subscription/` | Renew subscription | JWT |

### Webhooks (Unauthenticated)

| Method | Endpoint | Purpose | Auth |
|--------|----------|---------|------|
| POST | `/api/v1/payments/click-webhook/` | Click payment webhook | Signature |
| GET | `/api/v1/payments/callback/` | Payment callback redirect | None |

## 🗄️ Database Schema

### Invoice Model (Enhanced Fields)

```sql
-- New payment tracking fields
payment_status        VARCHAR(50)    -- Status of payment
payment_order_id      VARCHAR(255)   -- Click order ID
payment_transaction_id VARCHAR(255)  -- Click transaction ID
payment_method        VARCHAR(50)    -- Payment method used
payment_initiated_at  DATETIME       -- When payment started
payment_confirmed_at  DATETIME       -- When payment was confirmed
payment_cancelled_at  DATETIME       -- When payment was cancelled
amount               DECIMAL(15,2)   -- Payment amount
description          TEXT            -- Payment description
```

## 🔄 Payment Status States

```
not_initiated → initiated → pending_payment → completed → paid
                                           └→ failed → (retry)
                                           └→ cancelled
```

## 📋 Configuration (.env)

```dotenv
# Click Payment Gateway
CLICK_MERCHANT_ID=your_merchant_id
CLICK_SERVICE_ID=your_service_id
CLICK_SECRET_KEY=your_secret_key
CLICK_TEST_MODE=True
CLICK_MERCHANT_NAME=Hospitoll

# Stripe (Optional Fallback)
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...

# URLs
PAYMENT_RETURN_URL=http://localhost:3000/payment/success
PAYMENT_CALLBACK_URL=http://localhost:8000/api/v1/payments/click-callback/

# Invoice Settings
INVOICE_NUMBER_PREFIX=INV
INVOICE_PAYMENT_TERMS_DEFAULT=Due upon receipt

# Subscription Auto-Pay
AUTO_PAY_ENABLED=False
AUTO_PAY_RETRY_ATTEMPTS=3
AUTO_PAY_RETRY_INTERVAL=3
```

## 🚀 Frontend Integration

### Using PaymentService

```javascript
import PaymentService from '@/services/PaymentService';

// Initiate payment
const result = await PaymentService.initiatePayment(invoiceId);
// → { success: true, checkout_url: "...", order_id: "..." }

// Get status
const status = await PaymentService.getPaymentStatus(invoiceId);
// → { invoice_id: 1, payment_status: "completed", ... }

// Format amount
const formatted = PaymentService.formatAmount(50000);
// → "50,000 so'm"
```

### Using usePayment Hook

```javascript
import { usePayment } from '@/hooks/usePayment';

function Component() {
  const {
    loading,
    error,
    paymentStatus,
    initiatePayment,
    redirectToPayment
  } = usePayment({ autoPolling: true });

  const handlePay = async () => {
    await initiatePayment(invoiceId);
    redirectToPayment();
  };

  return <button onClick={handlePay}>Pay Now</button>;
}
```

### Using PaymentCheckout Component

```javascript
import PaymentCheckout from '@/components/PaymentCheckout';

function InvoicePage() {
  return (
    <PaymentCheckout
      invoiceId={1}
      amount={50000}
      invoiceNumber="INV-001"
      onSuccess={(status) => {
        console.log('Payment successful!', status);
        navigate('/invoices');
      }}
      onCancel={() => {
        navigate('/invoices');
      }}
    />
  );
}
```

## 🎯 Celery Tasks

### Available Tasks

```python
from core.payment_tasks import *

# Process payment confirmation
process_payment_confirmation(invoice_id, transaction_id)

# Send confirmation email
send_payment_confirmation_email(invoice_id)

# Retry failed payment
retry_failed_payment(invoice_id)

# Check overdue invoices
check_overdue_invoices()

# Send overdue reminder
send_overdue_invoice_reminder(invoice_id)

# Process subscription payment
process_subscription_payment(subscription_id)

# Update subscription status
update_subscription_status(subscription_id)

# Generate monthly invoices
generate_monthly_invoices()
```

### Task Scheduling (Celery Beat)

```python
CELERY_BEAT_SCHEDULE = {
    'check-overdue-invoices': {
        'task': 'core.payment_tasks.check_overdue_invoices',
        'schedule': crontab(hour=9, minute=0),
    },
    'generate-monthly-invoices': {
        'task': 'core.payment_tasks.generate_monthly_invoices',
        'schedule': crontab(day_of_month=1, hour=0, minute=0),
    },
}
```

## 🔐 Security

### Signature Verification

```python
# Click verifies with:
sign_string = SHA256(click_trans_id;merchant_id;merchant_trans_id;amount;secret_key)

# We verify the same way and compare
expected = _generate_verification_sign(click_trans_id, merchant_trans_id, amount)
if received_signature != expected:
    return error("Invalid signature")
```

### CSRF Protection

```python
# Webhook is CSRF-exempt (safe - signed by Click)
@csrf_exempt
def click_webhook(request):
    ...

# API endpoints are CSRF-protected
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def renew_subscription(request):
    ...
```

## 🧪 Testing Checklist

### Manual Payment Test

```bash
# 1. Create test invoice
curl -X POST http://localhost:8000/api/v1/invoices/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount": 50000, "invoice_number": "TEST-001"}'

# 2. Initiate payment
curl -X POST http://localhost:8000/api/v1/payments/invoice-payments/1/initiate-payment/ \
  -H "Authorization: Bearer $TOKEN"

# 3. Open checkout URL in browser (from response)

# 4. Use test card:
#    Card: 9999000000000000
#    Expiry: 12/25
#    CVV: 999

# 5. Let Click redirect back to callback URL

# 6. Check invoice status
curl -X GET http://localhost:8000/api/v1/payments/invoice-payments/1/payment-status/ \
  -H "Authorization: Bearer $TOKEN"
```

### Check Status Values

```python
# Payment status values
'not_initiated'     # Payment never started
'initiated'         # Payment initiated, awaiting Click
'pending_payment'   # Awaiting user payment on Click
'completed'         # Payment completed/confirmed
'failed'            # Payment failed
'cancelled'         # Payment cancelled by user
'paid'              # Final paid state
```

## 📊 Monitoring Queries

### Check Recent Payments

```python
>>> from apps.payments.models import Invoice
>>> Invoice.objects.filter(
...     payment_status__in=['completed', 'paid']
... ).order_by('-payment_confirmed_at')[:10]
```

### Find Overdue Invoices

```python
>>> from django.utils import timezone
>>> from datetime import timedelta
>>> overdue_date = timezone.now().date() - timedelta(days=1)
>>> Invoice.objects.filter(
...     status__in=['issued', 'overdue'],
...     due_date__lt=overdue_date,
...     payment_status__in=['not_initiated', 'initiated']
... )
```

### Payment Success Rate

```python
>>> from django.utils import timezone
>>> from datetime import timedelta
>>> today = timezone.now().date()
>>> total = Invoice.objects.filter(payment_initiated_at__date=today).count()
>>> success = Invoice.objects.filter(
...     payment_initiated_at__date=today,
...     payment_status__in=['completed', 'paid']
... ).count()
>>> print(f"Success rate: {success}/{total} = {success/total*100:.1f}%")
```

## 🐛 Common Issues & Solutions

### Issue: Payment Not Confirmed
**Solution:** Check Click webhook is configured and firewall allows Click IPs
```bash
tail -f logs/security.log | grep webhook
```

### Issue: Invalid Signature
**Solution:** Verify secret key matches Click merchant settings
```python
>>> from django.conf import settings
>>> settings.CLICK_SECRET_KEY == "your_actual_secret"
```

### Issue: Invoice Not Updating
**Solution:** Check Celery worker is running
```bash
celery -A config worker -l info
```

### Issue: Webhook Not Received
**Solution:** Check URL configuration in Click merchant panel
Required URL: `{domain}/api/v1/payments/click-webhook/`

## 🚀 Production Deployment

### Pre-Deployment

- [ ] Real Click credentials obtained
- [ ] CLICK_TEST_MODE changed to False
- [ ] Production URLs configured
- [ ] Database migration tested
- [ ] Celery worker configured
- [ ] Email backend configured
- [ ] HTTPS certificate installed
- [ ] Payment logs directory created

### Post-Deployment

- [ ] Test with Click sandbox first
- [ ] Upgrade to production credentials
- [ ] Monitor first 10 payments closely
- [ ] Check email notifications work
- [ ] Verify webhook receipt in logs
- [ ] Set up alerts for failed payments
- [ ] Document payment support procedures

## 📖 Documentation Files

| File | Purpose |
|------|---------|
| `PAYMENT_IMPLEMENTATION.md` | Complete integration guide (4000+ lines) |
| `PAYMENT_SYSTEM_SUMMARY.md` | System overview and file inventory |
| `PAYMENT_TEST_REPORT.md` | Test execution results |
| Core Python files | `core/payment_service.py`, `core/payment_tasks.py` |
| Frontend files | `PaymentService.js`, `usePayment.js`, `PaymentCheckout.jsx` |

## 📞 Support

### For Issues With:

**Click Integration:**
- Check Click documentation: https://click.uz/docs
- Verify merchant credentials
- Check webhook logs

**Payment Processing:**
- Review `core/payment_service.py`
- Check `core/payment_tasks.py` for async issues
- Verify database migrations applied

**Frontend Payment UI:**
- Check `PaymentService.js` for API calls
- Review `usePayment.js` for state management
- See `PaymentCheckout.jsx` for UI logic

## 🔗 Related Systems

- **Email System:** `core/tasks.py` (payment emails)
- **Error Logging:** `core/error_logging.py` (payment errors)
- **WebSocket:** `core/consumers.py` (real-time payment updates)
- **Backup:** `core/backup_manager.py` (payment data backup)

---

**Last Updated:** 2024
**Status:** ✅ Production Ready
**Test Coverage:** Click sandbox verified
**Documentation:** Complete
