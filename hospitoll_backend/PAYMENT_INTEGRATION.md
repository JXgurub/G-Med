# Payment Integration Documentation

## Overview

Payment integration for the Hospitoll platform using the **Click API** payment gateway. This enables clinics, pharmacies, and medical facilities to accept online payments in UZS (Uzbek Som).

## Architecture

### Components

1. **Click Payment Service** (`core/utils/click_payment.py`)
   - Handles all Click API interactions
   - Manages invoice creation and payment verification
   - Validates webhook signatures using HMAC-SHA256
   - Supports both test and production modes

2. **Payment Views** (`apps/payments/views.py`)
   - `PaymentViewSet`: Main payment operations
   - `InvoiceViewSet`: Invoice management
   - Handles Click webhook callbacks (CSRF-exempt)

3. **Serializers** (`apps/payments/serializers.py`)
   - `PaymentSerializer`: Payment data validation and serialization
   - `InvoiceSerializer`: Invoice details and calculations

4. **Models** (`apps/payments/models.py`)
   - `Payment`: Transaction records
   - `Invoice`: Billing documents

5. **Email Service** (`core/utils/email_service.py`)
   - Sends invoice emails with HTML templates
   - Supports Uzbek language
   - Async processing via Celery

## Configuration

### Environment Variables Required

```bash
# Click API Credentials
CLICK_MERCHANT_ID=<your_merchant_id>
CLICK_SERVICE_ID=<your_service_id>
CLICK_SECRET_KEY=<your_secret_key>
CLICK_MERCHANT_NAME="Hospitoll"

# Payment URLs
PAYMENT_CALLBACK_URL=https://yourdomain.com/api/v1/payments/payments/click-callback/
PAYMENT_RETURN_URL=https://yourdomain.com/payments/success?invoice_id=

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
DEFAULT_FROM_EMAIL=noreply@hospitoll.uz

# Redis (for Celery)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### Settings Configuration

All payment settings are configured in `config/settings.py`:

```python
# Click API Configuration
CLICK_MERCHANT_ID = config('CLICK_MERCHANT_ID', default='')
CLICK_SERVICE_ID = config('CLICK_SERVICE_ID', default='')
CLICK_SECRET_KEY = config('CLICK_SECRET_KEY', default='')
CLICK_MERCHANT_NAME = config('CLICK_MERCHANT_NAME', default='Hospitoll')
CLICK_TEST_MODE = config('CLICK_TEST_MODE', default=not DEBUG)
CLICK_TEST_URL = 'https://sandbox.click.uz/services/pay'
CLICK_MERCHANT_URL = 'https://merchant.click.uz/services/pay'

# Payment URLs
PAYMENT_CALLBACK_URL = config('PAYMENT_CALLBACK_URL', default='http://localhost:8000/api/v1/payments/callback/')
PAYMENT_RETURN_URL = config('PAYMENT_RETURN_URL', default='http://localhost:8000/payment/return/')
```

## API Endpoints

### Payment Endpoints

#### Create Payment
```http
POST /api/v1/payments/payments/create_payment/
Content-Type: application/json
Authorization: Bearer <token>

{
    "payment_type": "consultation",
    "amount": 150000,
    "description": "Doctor consultation",
    "appointment_id": "uuid" (optional)
}

Response:
{
    "success": true,
    "payment": {
        "id": "uuid",
        "status": "pending",
        "amount": 150000,
        ...
    },
    "payment_url": "https://sandbox.click.uz/services/pay?invoice_id=..."
}
```

#### Get User's Payments
```http
GET /api/v1/payments/payments/my_payments/
Authorization: Bearer <token>

Response:
{
    "success": true,
    "payments": [
        {
            "id": "uuid",
            "status": "confirmed",
            "amount": 150000,
            ...
        }
    ]
}
```

#### Cancel Payment
```http
POST /api/v1/payments/payments/{id}/cancel_payment/
Authorization: Bearer <token>

Response:
{
    "success": true,
    "payment": {
        "id": "uuid",
        "status": "cancelled",
        ...
    }
}
```

### Invoice Endpoints

#### List Invoices
```http
GET /api/v1/payments/invoices/
Authorization: Bearer <token>
```

#### Create Invoice from Payment
```http
POST /api/v1/payments/invoices/create_from_payment/
Content-Type: application/json
Authorization: Bearer <token>

{
    "payment_id": "uuid"
}

Response:
{
    "success": true,
    "invoice": {
        "id": "uuid",
        "invoice_number": "INV-xxx",
        "net_amount": 150000,
        ...
    }
}
```

#### Send Invoice Email
```http
POST /api/v1/payments/invoices/{id}/send_email/
Authorization: Bearer <token>

Response:
{
    "success": true,
    "message": "Invoice sent successfully"
}
```

### Webhook Endpoint

#### Click Payment Callback
```http
POST /api/v1/payments/payments/click_callback/
X-Click-Signature: hmac_value

{
    "click_trans_id": 2345678,
    "service_id": 2341,
    "click_payme_id": 3123215,
    "merchant_trans_id": "payment-uuid",
    "merchant_id": 13255,
    "amount": 150000,
    "action": 1,
    "error": 0,
    "error_note": "Success",
    "status": 1,
    "sign_time": "20210917134433"
}

Response (on success):
{
    "error": 0,
    "error_note": "Success"
}

Response (on error):
{
    "error": -1,
    "error_note": "error message"
}
```

## Payment Flow

### 1. Payment Creation
- User initiates payment via mobile/web app
- System creates Payment record in DB
- Click invoice is generated via API
- Payment link is returned to user

### 2. Payment via Click
- User scans QR code or clicks payment link
- Redirected to Click payment gateway (sandbox/production)
- User enters card details and confirms
- Click processes payment

### 3. Click Callback
- Click sends webhook to `PAYMENT_CALLBACK_URL`
- Signature is verified using HMAC-SHA256
- Payment status is updated in database
- Invoice is generated if needed
- Email notification is sent to patient

### 4. Payment Confirmation
- Payment record status: `pending` → `confirmed`
- Invoice created with issued date
- Invoice email sent to patient
- Frontend shows success page

## Payment Status Values

- **pending**: Payment created, waiting for user to complete
- **confirmed**: Payment completed successfully
- **failed**: Payment declined or error occurred
- **cancelled**: Payment cancelled by user or admin

## Invoice Status Values

- **draft**: Invoice not yet issued
- **issued**: Invoice issued and ready for payment
- **paid**: Invoice paid
- **overdue**: Payment not received by due date

## Celery Tasks

### Subscription Expiry Reminders

**Task**: `apps.subscriptions.tasks.send_subscription_expiry_reminders()`
**Schedule**: Daily at 9:00 AM
**Function**: Sends email reminders to clinic/pharmacy owners whose subscriptions expire in 3 days

### Check and Deactivate Expired Subscriptions

**Task**: `apps.subscriptions.tasks.check_and_deactivate_expired_subscriptions()`
**Schedule**: Daily at 00:00 (midnight)
**Function**: Deactivates subscriptions past their due date

## Testing

### Setup Test Environment

1. **Install Dependencies**
```bash
pip install -r requirements.txt
```

2. **Configure Test Credentials**
Create `.env` file in project root:
```
CLICK_MERCHANT_ID=your_test_merchant_id
CLICK_SERVICE_ID=your_test_service_id
CLICK_SECRET_KEY=your_test_secret_key
CLICK_TEST_MODE=True
```

3. **Start Redis (for Celery)**
```bash
redis-server
```

4. **Start Celery Worker**
```bash
celery -A config worker -l info
```

5. **Start Django Development Server**
```bash
python manage.py runserver
```

### Test Payment Flow

1. **Create Payment**
```bash
curl -X POST http://localhost:8000/api/v1/payments/payments/create_payment/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "payment_type": "consultation",
    "amount": 150000,
    "description": "Test payment"
  }'
```

2. **Get Payment Link**
   - Copy `payment_url` from response
   - Use Click Sandbox: https://sandbox.click.uz/services/pay

3. **Simulate Click Callback**
```bash
curl -X POST http://localhost:8000/api/v1/payments/payments/click_callback/ \
  -H "Content-Type: application/json" \
  -H "X-Click-Signature: <hmac_signature>" \
  -d '{
    "click_trans_id": 2345678,
    "service_id": 2341,
    "click_payme_id": 3123215,
    "merchant_trans_id": "payment-uuid",
    "merchant_id": 13255,
    "amount": 150000,
    "action": 1,
    "error": 0,
    "error_note": "Success",
    "status": 1,
    "sign_time": "20210917134433"
  }'
```

## Error Handling

### Common Errors

| Error | Status | Cause | Solution |
|-------|--------|-------|----------|
| Invalid payment amount | 400 | Amount ≤ 0 | Use positive amount |
| Payment not found | 404 | Invalid payment ID | Verify payment exists |
| Invalid merchant | -4 | Wrong credentials | Check CLICK_MERCHANT_ID |
| Signature verification failed | -3 | Invalid webhook signature | Verify CLICK_SECRET_KEY |
| Payment already processed | -2 | Duplicate callback | Idempotent handling |

### Logging

All payment operations are logged to `hospitoll_backend/logs/` with detailed information:
- Payment creation
- Click API calls
- Webhook callbacks
- Email sending
- Error details

## Security Considerations

1. **Webhook Verification**: All Click callbacks are verified using HMAC-SHA256
2. **CSRF Exemption**: Webhook endpoint is exempt from CSRF (required for external webhooks)
3. **Permission Check**: Payment endpoints require authentication
4. **Amount Validation**: Minimum payment amounts are enforced
5. **Transaction ID**: Unique transaction IDs prevent duplicate processing

## Production Checklist

- [ ] Update `CLICK_TEST_MODE` to `False`
- [ ] Set production Click credentials
- [ ] Configure `PAYMENT_CALLBACK_URL` to production domain
- [ ] Configure `PAYMENT_RETURN_URL` to production domain
- [ ] Setup Redis for production
- [ ] Configure email backend (SendGrid or SMTP)
- [ ] Setup Celery Beat scheduler
- [ ] Add SSL certificate for payment domain
- [ ] Test payment flow with real transactions
- [ ] Monitor webhook delivery and error logs

## Troubleshooting

### Payments stuck in pending state
- Check if Click API is reachable
- Verify webhook endpoint is accessible
- Check logs for callback errors
- Verify CLICK_SECRET_KEY is correct

### Email not sending
- Check email configuration in settings
- Verify sender email credentials
- Check logs for email errors
- Test with simpler email content

### Click callback not received
- Verify PAYMENT_CALLBACK_URL is public and accessible
- Check firewall/router settings
- Verify application is running
- Test webhook delivery in Click dashboard

## References

- [Click API Documentation](https://click.uz/docs)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [Celery Documentation](https://docs.celeryproject.io/)
