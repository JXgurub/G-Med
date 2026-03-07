import { useState, useEffect } from 'react'
import { formatCurrencyInput, parseCurrencyInput } from '../utils/currency'
import './SetPaymentAmountModal.css'

const SetPaymentAmountModal = ({ isOpen, clinic, onClose, onSubmit, isLoading }) => {
  const [amount, setAmount] = useState('')
  const [amountClearedOnFocus, setAmountClearedOnFocus] = useState(false)
  const [description, setDescription] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (clinic?.amount) {
      setAmount(formatCurrencyInput(clinic.amount))
      setAmountClearedOnFocus(false)
    }
  }, [clinic])

  const handleSubmit = (e) => {
    e.preventDefault()
    setError('')

    // Validation
    if (!amount) {
      setError('Miqdor kiritilishi shart')
      return
    }

    const amountNum = parseCurrencyInput(amount)
    if (isNaN(amountNum) || amountNum <= 0) {
      setError('Miqdor 0 dan katta bo\'lishi kerak')
      return
    }

    onSubmit({
      amount: amountNum,
      description: description.trim() || ''
    })
    
    setAmount('')
    setAmountClearedOnFocus(false)
    setDescription('')
  }

  const handleClose = () => {
    setAmount('')
    setAmountClearedOnFocus(false)
    setDescription('')
    setError('')
    onClose()
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal-content payment-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>To'lov Miqdori O'rnatish</h2>
          <button className="modal-close" onClick={handleClose}>✕</button>
        </div>

        <div className="modal-body">
          <div className="clinic-info">
            <div className="info-badge amount">💰</div>
            <div className="info-text">
              <p className="info-label">Klinika:</p>
              <p className="info-value">{clinic?.name}</p>
            </div>
          </div>

          {clinic?.amount && (
            <div className="current-amount">
              <span className="current-label">Joriy Miqdor:</span>
              <span className="current-value">{clinic.amount.toLocaleString()} so'm</span>
            </div>
          )}

          {error && <div className="error-message">{error}</div>}

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label>To'lov Miqdori (so'm) *</label>
              <div className="input-group">
                <input
                  type="text"
                  inputMode="numeric"
                  placeholder="100000"
                  value={amount}
                  onChange={(e) => setAmount(formatCurrencyInput(e.target.value))}
                  onFocus={() => {
                    if (amountClearedOnFocus || !amount) {
                      return
                    }
                    setAmount('')
                    setAmountClearedOnFocus(true)
                  }}
                  disabled={isLoading}
                  required
                />
                <span className="currency">so'm</span>
              </div>
            </div>

            <div className="form-group">
              <label>Izoh (ixtiyoriy)</label>
              <textarea
                placeholder="Masalan: Oylik abonement to'lovi"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={isLoading}
                rows="3"
              />
            </div>

            <div className="form-actions">
              <button 
                type="button" 
                className="btn-cancel"
                onClick={handleClose}
                disabled={isLoading}
              >
                Bekor qilish
              </button>
              <button 
                type="submit" 
                className="btn-submit success"
                disabled={isLoading}
              >
                {isLoading ? 'Saqlanmoqda...' : 'O\'rnatish'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

export default SetPaymentAmountModal
