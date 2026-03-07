import { useEffect, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { usePayment } from '../context/PaymentContext'
import './PaymentSuccess.css'

const PaymentSuccess = () => {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { fetchPayments } = usePayment()
  const [payment, setPayment] = useState(null)
  const [loading, setLoading] = useState(true)

  const invoiceId = searchParams.get('invoice_id')
  const status = searchParams.get('status')

  useEffect(() => {
    const loadPayments = async () => {
      try {
        await fetchPayments()
        // Find payment by invoice ID
        if (invoiceId) {
          setPayment({ id: invoiceId, status: status || 'confirmed' })
        }
      } catch (error) {
        console.error('Error loading payment:', error)
      } finally {
        setLoading(false)
      }
    }

    loadPayments()
  }, [invoiceId, fetchPayments, status])

  const isSuccess = status === 'success' || status === 'confirmed' || !status
  const isFailed = status === 'failed' || status === 'cancelled'

  if (loading) {
    return (
      <div className="payment-success-container">
        <div className="loading">Kutilmoqda...</div>
      </div>
    )
  }

  return (
    <div className={`payment-success-container ${isSuccess ? 'success' : 'failed'}`}>
      <div className={`payment-card ${isSuccess ? 'success' : 'failed'}`}>
        <div className={`status-icon ${isSuccess ? 'success' : 'failed'}`}>
          {isSuccess ? '✓' : '✕'}
        </div>

        <h1 className="title">
          {isSuccess ? 'To\'lov Muvaffaqiyatli!' : 'To\'lov Muvaffaqiyatsiz'}
        </h1>

        <p className="message">
          {isSuccess
            ? 'Sizning to\'lovingiz muvaffaqiyatli qayta olindi. Tez orada email-da rozynomalasi yuboriladi.'
            : 'To\'lov o\'tkazilmasdi. Iltimos qayta harakat qilib ko\'ring.'}
        </p>

        {payment && (
          <div className="payment-details">
            <div className="detail-row">
              <span className="label">To\'lov ID:</span>
              <span className="value">{payment.id}</span>
            </div>
            <div className="detail-row">
              <span className="label">Holati:</span>
              <span className={`value status ${payment.status}`}>
                {payment.status === 'confirmed' ? 'Tasdiqlangan' :
                 payment.status === 'pending' ? 'Kutilmoqda' :
                 payment.status === 'failed' ? 'Muvaffaqiyatsiz' : payment.status}
              </span>
            </div>
          </div>
        )}

        <div className="actions">
          <button
            className="btn btn-primary"
            onClick={() => navigate('/patient')}
          >
            Kabinaga qaytish
          </button>

          {isSuccess && (
            <button
              className="btn btn-secondary"
              onClick={() => navigate('/payment-history')}
            >
              To'lov tarixi
            </button>
          )}
        </div>

        <div className="tips">
          <h3>Qo'shimcha ma'lumot</h3>
          <ul>
            {isSuccess ? (
              <>
                <li>✓ To'lov muvaffaqiyatli qayta olindi</li>
                <li>✓ Email-da rozynomalasi yuboriladi</li>
                <li>✓ Tezkor to'lov qayta olish (24 soat ishi bilan)</li>
              </>
            ) : (
              <>
                <li>✕ To'lov qayta olish muvaffaqiyatsiz bo'ldi</li>
                <li>Iltimos koneksiyani tekshiring</li>
                <li>Qayta harakat qilish uchun click qiling</li>
              </>
            )}
          </ul>
        </div>
      </div>
    </div>
  )
}

export default PaymentSuccess
