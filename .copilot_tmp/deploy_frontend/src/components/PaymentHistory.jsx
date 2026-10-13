import { useEffect, useState } from 'react'
import { usePayment } from '../context/PaymentContext'
import './PaymentHistory.css'

const PaymentHistory = () => {
  const { payments, invoices, loading, fetchPayments, fetchInvoices, sendInvoiceEmail } = usePayment()
  const [activeTab, setActiveTab] = useState('payments')
  const [sendingEmail, setSendingEmail] = useState(null)

  useEffect(() => {
    if (activeTab === 'payments') {
      fetchPayments()
    } else {
      fetchInvoices()
    }
  }, [activeTab, fetchPayments, fetchInvoices])

  const formatPrice = (price) => {
    return new Intl.NumberFormat('uz-UZ', {
      style: 'currency',
      currency: 'UZS',
      minimumFractionDigits: 0,
    }).format(price)
  }

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('uz-UZ', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  }

  const getStatusBadge = (status) => {
    const statusMap = {
      pending: { class: 'badge-pending', label: 'Kutilmoqda' },
      confirmed: { class: 'badge-confirmed', label: 'Tasdiqlangan' },
      paid: { class: 'badge-paid', label: 'To\'landi' },
      issued: { class: 'badge-issued', label: 'Chiqarilgan' },
      failed: { class: 'badge-failed', label: 'Muvaffaqiyatsiz' },
      cancelled: { class: 'badge-cancelled', label: 'Bekor qilingan' },
      overdue: { class: 'badge-overdue', label: 'Muddati o\'tgan' },
    }
    const config = statusMap[status] || { class: 'badge-default', label: status }
    return <span className={`badge ${config.class}`}>{config.label}</span>
  }

  const handleSendEmail = async (invoiceId) => {
    setSendingEmail(invoiceId)
    try {
      await sendInvoiceEmail(invoiceId)
      alert('Email muvaffaqiyatli yuborildi')
    } catch (error) {
      alert('Email yuborishda xatolik: ' + error.message)
    } finally {
      setSendingEmail(null)
    }
  }

  return (
    <div className="payment-history-container">
      <div className="payment-history">
        <h1>To'lov Tarixi</h1>

        <div className="tab-container">
          <button
            className={`tab-button ${activeTab === 'payments' ? 'active' : ''}`}
            onClick={() => setActiveTab('payments')}
          >
            To'lovlar ({payments.length})
          </button>
          <button
            className={`tab-button ${activeTab === 'invoices' ? 'active' : ''}`}
            onClick={() => setActiveTab('invoices')}
          >
            Invoiceslar ({invoices.length})
          </button>
        </div>

        <div className="tab-content">
          {loading && <div className="loading">Yuklanmoqda...</div>}

          {!loading && activeTab === 'payments' && (
            <div className="payments-list">
              {payments.length === 0 ? (
                <div className="empty-state">
                  <p>Hali to'lovlar yo'q</p>
                </div>
              ) : (
                <div className="table-responsive">
                  <table className="payments-table">
                    <thead>
                      <tr>
                        <th>Sana</th>
                        <th>Turi</th>
                        <th>Tavsif</th>
                        <th>Miqdor</th>
                        <th>Holati</th>
                      </tr>
                    </thead>
                    <tbody>
                      {payments.map(payment => (
                        <tr key={payment.id} className="payment-row">
                          <td>{formatDate(payment.created_at)}</td>
                          <td>{payment.payment_type}</td>
                          <td className="description">{payment.description}</td>
                          <td className="amount">{formatPrice(payment.amount)}</td>
                          <td>{getStatusBadge(payment.status)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {!loading && activeTab === 'invoices' && (
            <div className="invoices-list">
              {invoices.length === 0 ? (
                <div className="empty-state">
                  <p>Hali invoiceslar yo'q</p>
                </div>
              ) : (
                <div className="invoices-grid">
                  {invoices.map(invoice => (
                    <div key={invoice.id} className="invoice-card">
                      <div className="invoice-header">
                        <h3>{invoice.invoice_number}</h3>
                        {getStatusBadge(invoice.status)}
                      </div>

                      <div className="invoice-details">
                        <div className="detail">
                          <span className="label">Sana:</span>
                          <span className="value">{formatDate(invoice.issued_date)}</span>
                        </div>
                        <div className="detail">
                          <span className="label">Jami:</span>
                          <span className="value amount">{formatPrice(invoice.total_amount)}</span>
                        </div>
                        <div className="detail">
                          <span className="label">To'lash kerak:</span>
                          <span className="value amount">{formatPrice(invoice.remaining_amount)}</span>
                        </div>
                      </div>

                      <div className="invoice-actions">
                        <button
                          className="btn btn-small btn-primary"
                          onClick={() => handleSendEmail(invoice.id)}
                          disabled={sendingEmail === invoice.id}
                        >
                          {sendingEmail === invoice.id ? 'Yuborilmoqda...' : 'Emailda yuborish'}
                        </button>
                        <a
                          href={`/invoice/${invoice.id}`}
                          className="btn btn-small btn-secondary"
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          Ko'rish
                        </a>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default PaymentHistory
