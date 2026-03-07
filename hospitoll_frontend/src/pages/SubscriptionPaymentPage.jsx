import PaymentForm from '../components/PaymentForm'
import './PaymentPage.css'

const SubscriptionPaymentPage = () => {
  return (
    <div className="payment-page">
      <PaymentForm
        title="Obuna To'lovi"
        defaultType="subscription"
        lockType={true}
      />
    </div>
  )
}

export default SubscriptionPaymentPage
