# Payment Frontend UI Documentation

## Overview

Complete frontend payment UI implementation for the Hospitoll platform with React, including payment forms, history tracking, and success/error pages.

## Components Created

### 1. PaymentContext (`src/context/PaymentContext.jsx`)

**Purpose**: Centralized state management for payment operations

**Features**:
- Manages payment and invoice data
- Handles async API calls
- Provides error handling and loading states
- Memoized callbacks for performance

**Hooks**:
```javascript
const {
  payments,              // Array of user's payments
  invoices,              // Array of user's invoices
  loading,               // Loading state
  error,                 // Error message
  currentPayment,        // Currently processing payment
  fetchPayments,         // Load payments
  fetchInvoices,         // Load invoices
  createPayment,         // Create new payment
  cancelPayment,         // Cancel pending payment
  createInvoice,         // Generate invoice from payment
  sendInvoiceEmail,      // Send invoice via email
  setError,              // Clear error
} = usePayment()
```

### 2. PaymentForm Component (`src/components/PaymentForm.jsx`)

**Purpose**: Form for creating new payments

**Features**:
- Payment type selection (consultation, service, medicine, test, subscription)
- Amount input with validation (min 1,000 som)
- Description textarea
- Error handling and success feedback
- Auto-redirect to Click payment gateway
- Loading states

**Props**: None (uses PaymentContext internally)

**Usage**:
```jsx
import PaymentForm from '../components/PaymentForm'

function MyPage() {
  return <PaymentForm />
}
```

### 3. PaymentHistory Component (`src/components/PaymentHistory.jsx`)

**Purpose**: Display payment and invoice history with tabbed interface

**Features**:
- Two tabs: Payments and Invoices
- Tabular view for payments with date, type, description, amount, status
- Grid view for invoices with details and actions
- Send invoice via email functionality
- Status badges (pending, confirmed, paid, issued, etc.)
- Responsive design

**Props**: None (uses PaymentContext internally)

**Usage**:
```jsx
import PaymentHistory from '../components/PaymentHistory'

function HistoryPage() {
  return <PaymentHistory />
}
```

### 4. PaymentSuccess Page (`src/pages/PaymentSuccess.jsx`)

**Purpose**: Display payment success/failure confirmation

**Features**:
- Shows success or failure status with icon
- Displays payment details when available
- Status badge with color coding
- Action buttons to return to dashboard or view history
- Tips section with relevant information

**Props**: Uses URL search params (`invoice_id`, `status`)

**Usage**:
```jsx
// Route: /payment/success?invoice_id=xxx&status=success
import PaymentSuccess from '../pages/PaymentSuccess'

// In App.jsx
<Route path="/payment/success" element={<PaymentSuccess />} />
```

### 5. PaymentPage (`src/pages/PaymentPage.jsx`)

**Purpose**: Main payment page wrapper

**Features**:
- Renders PaymentForm component
- Clean container layout

**Usage**:
```jsx
// Route: /payment
import PaymentPage from '../pages/PaymentPage'

// In App.jsx
<Route path="/payment" element={<PaymentPage />} />
```

## Styling Files

All components have corresponding CSS files with responsive design:

- `PaymentForm.css` - Form styling with gradient background
- `PaymentHistory.css` - Table and grid layouts responsive
- `PaymentSuccess.css` - Success/failure card layouts
- `PaymentPage.css` - Page container

## Integration in App.jsx

**PaymentProvider**: Wraps entire app to provide payment context

**Routes Added**:
```jsx
<Route path="/payment" element={<PaymentPage />} />
<Route path="/payment/success" element={<PaymentSuccess />} />
<Route path="/payment-history" element={<PaymentHistory />} />
```

## Usage Examples

### Create Payment
```jsx
const { createPayment } = usePayment()

const handlePayment = async () => {
  try {
    const result = await createPayment({
      payment_type: 'consultation',
      amount: 150000,
      description: 'Doctor consultation'
    })
    // result.payment_url contains Click gateway link
    window.location.href = result.payment_url
  } catch (error) {
    console.error(error)
  }
}
```

### View Payment History
```jsx
import PaymentHistory from '../components/PaymentHistory'

export default function HistoryPage() {
  return <PaymentHistory />
}
```

### Send Invoice Email
```jsx
const { sendInvoiceEmail } = usePayment()

const handleSendEmail = async (invoiceId) => {
  try {
    await sendInvoiceEmail(invoiceId)
    alert('Email sent successfully')
  } catch (error) {
    alert('Failed to send email')
  }
}
```

## API Endpoints Used

### From PaymentContext

```javascript
// Create payment
POST /api/v1/payments/payments/create_payment/
body: { payment_type, amount, description }
response: { success, payment, payment_url }

// Get user's payments
GET /api/v1/payments/payments/my_payments/
response: { success, payments }

// Get invoices
GET /api/v1/payments/invoices/
response: Array of invoices

// Create invoice from payment
POST /api/v1/payments/invoices/create_from_payment/
body: { payment_id }
response: { success, invoice }

// Send invoice email
POST /api/v1/payments/invoices/{id}/send_email/
response: { success, message }

// Cancel payment
POST /api/v1/payments/payments/{id}/cancel_payment/
response: { success, payment }
```

## Styling Features

### Colors
- Primary: Purple gradient (`#667eea` to `#764ba2`)
- Success: Green (`#4caf50`, `#2e7d32`)
- Error: Red (`#f44336`, `#c62828`)
- Warning: Orange (`#ff9800`, `#f57c00`)

### Responsive Breakpoints
- Desktop: Full width grid
- Tablet (max-width: 768px): 2-column layout
- Mobile (max-width: 600px): Single column, optimized forms

### Components
- Form inputs with focus states and validation
- Status badges with color coding
- Gradient backgrounds and shadows
- Loading states with disabled controls
- Smooth transitions and hover effects

## Payment Flow Diagram

```
User initiates payment
    ↓
PaymentForm component
    ↓
Create payment API call (createPayment)
    ↓
Payment record created in backend
Click invoice generated
    ↓
Get payment_url from response
    ↓
Redirect to Click payment gateway
    ↓
User completes payment in Click
    ↓
Click sends webhook to backend
    ↓
Backend updates payment status to 'confirmed'
    ↓
User redirected to PaymentSuccess page
    ↓
Display success message with payment details
    ↓
Option to view history or return to dashboard
```

## Error Handling

**Frontend Validation**:
- Amount must be > 0
- Description required
- Payment type selection

**API Error Handling**:
- Displays error messages to user
- Catches network errors
- Shows specific error details from backend

**Status Display**:
- pending: Waiting for payment
- confirmed: Payment completed
- failed: Payment failed
- cancelled: User cancelled

## State Management Flow

```
PaymentContext
├── payments: Array
├── invoices: Array
├── loading: Boolean
├── error: String | null
├── currentPayment: Object | null
└── Actions
    ├── fetchPayments()
    ├── fetchInvoices()
    ├── createPayment()
    ├── cancelPayment()
    ├── createInvoice()
    └── sendInvoiceEmail()
```

## Performance Optimizations

1. **Memoized Callbacks**: All context actions use `useCallback` to prevent unnecessary re-renders
2. **Lazy Loading**: Payments/invoices loaded on tab switch
3. **Error State Clearing**: Users can dismiss errors
4. **Conditional Rendering**: Empty states and loading skeletons

## Accessibility Features

- Semantic HTML5 structures
- Form labels properly associated with inputs
- Status badges use color + text (not color alone)
- Keyboard navigation support
- ARIA attributes where needed

## Testing Checklist

- [ ] Create payment form loads without errors
- [ ] Amount validation works (rejects 0 and negative)
- [ ] Description validation works (requires input)
- [ ] Payment type selection options all available
- [ ] Submit button redirects to Click gateway
- [ ] Success page displays when redirected
- [ ] Payment history tab loads and displays payments
- [ ] Invoice history tab loads and displays invoices
- [ ] Send invoice email button works
- [ ] Cancel payment button cancels payment
- [ ] Responsive design works on mobile
- [ ] Error messages display correctly
- [ ] Loading states show during API calls

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile: iOS Safari 14+, Chrome Android 90+

## Dependencies

- React 18+
- React Router DOM 6+
- Context API (built-in)
- Custom API service (`src/services/api.js`)

## Future Enhancements

1. Payment method selection (multiple gateway support)
2. Recurring payment support
3. Refund management
4. Invoice customization
5. Payment reminders
6. Subscription management UI
7. Receipt generation/download
8. Multi-language support
