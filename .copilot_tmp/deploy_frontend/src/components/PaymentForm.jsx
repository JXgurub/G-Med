import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePayment } from '../context/PaymentContext'
import { useClinic } from '../context/ClinicContext'
import { usePharmacy } from '../context/PharmacyContext'
import { formatCurrencyInput, parseCurrencyInput } from '../utils/currency'
import './PaymentForm.css'

const PaymentForm = ({
  defaultType = null,
  lockType = false,
  defaultAmount = null,
  defaultDescription = null,
  title = "To'lov Yaratish"
}) => {
  const navigate = useNavigate()
  const { createPayment, loading, error, setError } = usePayment()
  const { clinicOwner } = useClinic()
  const { currentPharmacy } = usePharmacy()
  const userRole = localStorage.getItem('user_role')

  const [formData, setFormData] = useState({
    payment_type: defaultType || 'consultation',
    amount: formatCurrencyInput(defaultAmount || ''),
    description: defaultDescription || '',
  })

  const [localError, setLocalError] = useState(null)
  const [success, setSuccess] = useState(false)
  const [autoFilled, setAutoFilled] = useState(false)
  const [amountClearedOnFocus, setAmountClearedOnFocus] = useState(false)

  const PAYMENT_TYPES = [
    { value: 'consultation', label: 'Maslahat (Консультация)' },
    { value: 'service', label: 'Xizmat (Услуга)' },
    { value: 'medicine', label: 'Dori (Лекарство)' },
    { value: 'test', label: 'Sinov (Анализ)' },
    { value: 'subscription', label: 'Obuna (Подписка)' },
  ]

  const resolveSubscriptionDefaults = () => {
    if (userRole === 'clinic' && clinicOwner) {
      return {
        amount: Number(clinicOwner.amount || 0),
        description: clinicOwner.payment_description || 'Klinika obuna to\'lovi'
      }
    }
    if (userRole === 'pharmacy' && currentPharmacy) {
      return {
        amount: Number(currentPharmacy.amount || 0),
        description: currentPharmacy.payment_description || 'Dorixona obuna to\'lovi'
      }
    }
    return { amount: 0, description: '' }
  }

  useEffect(() => {
    if (formData.payment_type !== 'subscription') {
      return
    }

    if (defaultAmount !== null || defaultDescription !== null) {
      return
    }

    const defaults = resolveSubscriptionDefaults()
    if (autoFilled) {
      return
    }

    const currentAmount = parseCurrencyInput(formData.amount)
    if ((currentAmount <= 0 && defaults.amount > 0) || !formData.description.trim()) {
      setFormData(prev => ({
        ...prev,
        amount: defaults.amount > 0 ? formatCurrencyInput(defaults.amount) : prev.amount,
        description: defaults.description || prev.description
      }))
      setAmountClearedOnFocus(false)
      setAutoFilled(true)
    }
  }, [clinicOwner, currentPharmacy, formData.payment_type, formData.amount, formData.description, userRole, autoFilled, defaultAmount, defaultDescription])

  const handleInputChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: name === 'amount' ? formatCurrencyInput(value) : value,
    }))
    setLocalError(null)
  }

  const validateForm = () => {
    const amountNum = parseCurrencyInput(formData.amount)
    if (!amountNum || amountNum <= 0) {
      setLocalError("Miqdor 0 dan ko'p bo'lishi kerak")
      return false
    }
    if (!formData.description.trim()) {
      setLocalError('Tavsif kiritish shart')
      return false
    }
    if (formData.payment_type === 'subscription' && amountNum <= 0) {
      setLocalError('Obuna uchun to\'lov miqdori admin tomonidan belgilanmagan')
      return false
    }
    return true
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLocalError(null)

    if (!validateForm()) {
      return
    }

    try {
      const amountNum = parseCurrencyInput(formData.amount)
      const result = await createPayment({
        payment_type: formData.payment_type,
        amount: amountNum,
        description: formData.description,
      })

      if (result.payment_url) {
        setSuccess(true)
        // Redirect to Click payment gateway
        setTimeout(() => {
          window.location.href = result.payment_url
        }, 2000)
      }
    } catch (err) {
      setLocalError(err.message || 'To\'lovni yaratishda xatolik')
    }
  }

  return (
    <div className="payment-form-container">
      <div className="payment-form">
        <h2>{title}</h2>

        {(localError || error) && (
          <div className="alert alert-error">
            {localError || error}
            <button className="alert-close" onClick={() => {
              setLocalError(null)
              setError(null)
            }}>×</button>
          </div>
        )}

        {success && (
          <div className="alert alert-success">
            To'lov muvaffaqiyatli yaratildi! Click ga yo'naltirilmoqda...
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {!lockType && (
            <div className="form-group">
              <label htmlFor="payment_type">To'lovni turi</label>
              <select
                id="payment_type"
                name="payment_type"
                value={formData.payment_type}
                onChange={handleInputChange}
                disabled={loading}
              >
                {PAYMENT_TYPES.map(type => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="form-group">
            <label htmlFor="amount">Miqdor (so'm)</label>
            <input
              id="amount"
              type="text"
              inputMode="numeric"
              name="amount"
              value={formData.amount}
              onChange={handleInputChange}
              onFocus={() => {
                if (amountClearedOnFocus || !formData.amount) {
                  return
                }
                setFormData((prev) => ({ ...prev, amount: '' }))
                setAmountClearedOnFocus(true)
              }}
              placeholder="150000"
              disabled={loading}
              required
            />
            <small className="form-help">Minimal miqdor: 1,000 so'm</small>
            {formData.payment_type === 'subscription' && (userRole === 'clinic' || userRole === 'pharmacy') && (
              <small className="form-help">Obuna to'lovi admin tomonidan belgilanadi.</small>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="description">Tavsif</label>
            <textarea
              id="description"
              name="description"
              value={formData.description}
              onChange={handleInputChange}
              placeholder="Masalan: Doktor konsultatsiyasi"
              rows="4"
              disabled={loading}
              required
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading || success}
          >
            {loading ? 'Kutilmoqda...' : success ? 'Click ga o\'tilmoqda...' : 'To\'lovni boshlash'}
          </button>
        </form>

        <div className="payment-info">
          <h3>Click API orqali to'lov</h3>
          <ul>
            <li>✅ Xavfsiz to'lov - HTTPS shifrlangan</li>
            <li>✅ Barcha bank kartalari qabul qilinadi</li>
            <li>✅ Darhol tasdiqlash</li>
            <li>✅ Qabul qilish to'lovlar Uzbekiston so'mda</li>
          </ul>
        </div>
      </div>
    </div>
  )
}

export default PaymentForm
