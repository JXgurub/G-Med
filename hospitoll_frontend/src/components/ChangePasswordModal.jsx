import { useState } from 'react'
import PasswordInput from './PasswordInput'
import './ChangePasswordModal.css'

const ChangePasswordModal = ({ isOpen, clinic, onClose, onSubmit, isLoading }) => {
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    setError('')

    // Validation
    if (!password || !confirmPassword) {
      setError('Barcha maydonlarni to\'ldiring')
      return
    }

    if (password.length < 6) {
      setError('Parol kamida 6 ta belgidan iborat bo\'lishi kerak')
      return
    }

    if (password !== confirmPassword) {
      setError('Parollar mos kelmadi')
      return
    }

    onSubmit(password)
    setPassword('')
    setConfirmPassword('')
  }

  const handleClose = () => {
    setPassword('')
    setConfirmPassword('')
    setError('')
    onClose()
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Parolni O'zgartirish</h2>
          <button className="modal-close" onClick={handleClose}>✕</button>
        </div>

        <div className="modal-body">
          <div className="clinic-info">
            <div className="info-badge">{clinic?.id}</div>
            <div className="info-text">
              <p className="info-label">Klinika:</p>
              <p className="info-value">{clinic?.name}</p>
            </div>
          </div>

          {error && <div className="error-message">{error}</div>}

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label>Yangi Parol *</label>
              <PasswordInput
                placeholder="Yangi parolni kiriting"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isLoading}
                required
              />
            </div>

            <div className="form-group">
              <label>Parolni Tasdiqlang *</label>
              <PasswordInput
                placeholder="Parolni qayta kiriting"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                disabled={isLoading}
                required
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
                className="btn-submit"
                disabled={isLoading}
              >
                {isLoading ? 'Saqlanmoqda...' : 'Saqlash'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

export default ChangePasswordModal
