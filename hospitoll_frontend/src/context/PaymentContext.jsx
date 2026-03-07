import { createContext, useContext, useState, useCallback } from 'react'
import { api } from '../services/api'

const PaymentContext = createContext()

export const usePayment = () => {
  const context = useContext(PaymentContext)
  if (!context) {
    throw new Error('usePayment must be used within PaymentProvider')
  }
  return context
}

export const PaymentProvider = ({ children }) => {
  const [payments, setPayments] = useState([])
  const [invoices, setInvoices] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [currentPayment, setCurrentPayment] = useState(null)

  // Fetch user's payments
  const fetchPayments = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.request('/payments/payments/my_payments/')
      if (response.success) {
        setPayments(response.payments)
      } else {
        setError(response.error)
      }
    } catch (err) {
      setError(err.message)
      console.error('Error fetching payments:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  // Fetch invoices
  const fetchInvoices = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.request('/payments/invoices/')
      if (Array.isArray(response)) {
        setInvoices(response)
      } else if (response.results) {
        setInvoices(response.results)
      } else {
        setInvoices([])
      }
    } catch (err) {
      setError(err.message)
      console.error('Error fetching invoices:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  // Create payment
  const createPayment = useCallback(async (paymentData) => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.request('/payments/payments/create_payment/', {
        method: 'POST',
        body: JSON.stringify(paymentData),
      })

      if (response.success) {
        setCurrentPayment(response.payment)
        return response
      } else {
        setError(response.error)
        throw new Error(response.error)
      }
    } catch (err) {
      setError(err.message)
      console.error('Error creating payment:', err)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  // Cancel payment
  const cancelPayment = useCallback(async (paymentId) => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.request(`/payments/payments/${paymentId}/cancel_payment/`, {
        method: 'POST',
      })

      if (response.success) {
        setPayments(payments.map(p => p.id === paymentId ? response.payment : p))
        return response
      } else {
        setError(response.error)
        throw new Error(response.error)
      }
    } catch (err) {
      setError(err.message)
      console.error('Error cancelling payment:', err)
      throw err
    } finally {
      setLoading(false)
    }
  }, [payments])

  // Create invoice from payment
  const createInvoice = useCallback(async (paymentId) => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.request('/payments/invoices/create_from_payment/', {
        method: 'POST',
        body: JSON.stringify({ payment_id: paymentId }),
      })

      if (response.success) {
        setInvoices([...invoices, response.invoice])
        return response
      } else {
        setError(response.error)
        throw new Error(response.error)
      }
    } catch (err) {
      setError(err.message)
      console.error('Error creating invoice:', err)
      throw err
    } finally {
      setLoading(false)
    }
  }, [invoices])

  // Send invoice email
  const sendInvoiceEmail = useCallback(async (invoiceId) => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.request(`/payments/invoices/${invoiceId}/send_email/`, {
        method: 'POST',
      })

      if (response.success) {
        return response
      } else {
        setError(response.error)
        throw new Error(response.error)
      }
    } catch (err) {
      setError(err.message)
      console.error('Error sending invoice email:', err)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  const value = {
    payments,
    invoices,
    loading,
    error,
    currentPayment,
    fetchPayments,
    fetchInvoices,
    createPayment,
    cancelPayment,
    createInvoice,
    sendInvoiceEmail,
    setError,
  }

  return (
    <PaymentContext.Provider value={value}>
      {children}
    </PaymentContext.Provider>
  )
}
