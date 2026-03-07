import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePatient } from '../context/PatientContext'
import PasswordInput from '../components/PasswordInput'
import './PatientLogin.css'

const PatientLogin = () => {
  const navigate = useNavigate()
  const { loginPatient } = usePatient()
  const [passportId, setPassportId] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const result = await loginPatient(passportId, password)
      if (result.success) {
        navigate('/patient')
      } else {
        setError(result.error)
      }
    } catch (error) {
      setError('Serverga ulanishda xatolik yuz berdi')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="patient-login-page">
      <div className="patient-login-card">
        <div className="patient-login-header">
          <div className="login-badge">Bemor kirishi</div>
          <h1>Bemor sahifasiga kirish</h1>
          <p>Pasport ID va parol orqali</p>
        </div>

        <form className="patient-login-form" onSubmit={handleSubmit}>
          <label className="patient-login-field">
            <span>Pasport ID</span>
            <input
              type="text"
              value={passportId}
              onChange={(e) => setPassportId(e.target.value.replace(/\s+/g, '').toUpperCase())}
              placeholder="AA1234567"
              required
            />
          </label>

          <label className="patient-login-field">
            <span>Parol</span>
            <PasswordInput
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </label>

          {error && <div className="patient-login-error">{error}</div>}

          <button type="submit" className="patient-login-button" disabled={loading}>
            {loading ? 'Tekshirilmoqda...' : 'Kirish'}
          </button>

          <button
            type="button"
            className="patient-login-forgot"
            onClick={() => navigate('/patient-forgot-password')}
            disabled={loading}
          >
            Parolni unutdingizmi?
          </button>
        </form>

        <div className="patient-login-footer">
          <div className="demo-card">
            <p>Bemor hisobidan foydalanish uchun shifokor sizga pasport ID va parol beradi</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default PatientLogin
