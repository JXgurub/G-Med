import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../services/api'
import PasswordInput from '../components/PasswordInput'
import './PatientForgotPassword.css'

const PatientForgotPassword = () => {
  const navigate = useNavigate()
  const [step, setStep] = useState('email') // email | code | new_password

  const [passportId, setPassportId] = useState('')
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [token, setToken] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')

  const canSubmit = useMemo(() => {
    if (loading) return false
    if (step === 'email') return Boolean(email && passportId)
    if (step === 'code') return Boolean(email && passportId && code)
    if (step === 'new_password') return Boolean(token && newPassword && confirmPassword)
    return false
  }, [step, loading, email, passportId, code, token, newPassword, confirmPassword])

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setInfo('')

    try {
      setLoading(true)

      if (step === 'email') {
        const res = await authApi.patientPasswordResetRequest(email, passportId)
        setInfo(res?.detail || 'Kod emailingizga yuborildi')
        setStep('code')
        return
      }

      if (step === 'code') {
        const res = await authApi.patientPasswordResetVerify(email, code, passportId)
        if (!res?.token) {
          setError('Kod noto\'g\'ri yoki eskirgan')
          return
        }
        setToken(res.token)
        setStep('new_password')
        return
      }

      if (step === 'new_password') {
        if (newPassword.length < 6) {
          setError('Parol kamida 6 ta belgidan iborat bo\u2018lishi kerak')
          return
        }
        if (newPassword !== confirmPassword) {
          setError('Parollar mos emas')
          return
        }

        const res = await authApi.patientPasswordResetConfirm(token, newPassword)
        setInfo(res?.detail || 'Parol muvaffaqiyatli yangilandi')
        setTimeout(() => navigate('/patient-login'), 700)
      }
    } catch (err) {
      setError(err?.message || 'Xatolik yuz berdi')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="patient-forgot-page">
      <div className="patient-forgot-card">
        <div className="patient-forgot-header">
          <div className="badge">Parolni tiklash</div>
          <h1>Parolni unutdingizmi?</h1>
          <p>Pasport ID va email orqali bir martalik kod yuboramiz</p>
        </div>

        <form className="patient-forgot-form" onSubmit={onSubmit}>
          {step === 'email' && (
            <>
              <label className="field">
                <span>Pasport ID</span>
                <input
                  type="text"
                  value={passportId}
                  onChange={(e) => setPassportId(e.target.value.toUpperCase().replace(/\s+/g, ''))}
                  placeholder="AA1234567"
                  required
                />
              </label>
              <label className="field">
                <span>Email</span>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="patient@example.com"
                  required
                />
              </label>
            </>
          )}

          {step === 'code' && (
            <>
              <label className="field">
                <span>Pasport ID</span>
                <input type="text" value={passportId} disabled />
              </label>
              <label className="field">
                <span>Email</span>
                <input type="email" value={email} disabled />
              </label>
              <label className="field">
                <span>Bir martalik kod</span>
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="123456"
                  inputMode="numeric"
                  required
                />
              </label>
            </>
          )}

          {step === 'new_password' && (
            <>
              <label className="field">
                <span>Yangi parol</span>
                <PasswordInput
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                />
              </label>
              <label className="field">
                <span>Yangi parol (takror)</span>
                <PasswordInput
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                />
              </label>
            </>
          )}

          {error && <div className="message error">{error}</div>}
          {info && <div className="message info">{info}</div>}

          <button className="btn" type="submit" disabled={!canSubmit}>
            {loading ? 'Kutilmoqda...' : step === 'email' ? 'Kod yuborish' : step === 'code' ? 'Kod tasdiqlash' : 'Parolni yangilash'}
          </button>
        </form>

        <button className="back" type="button" onClick={() => navigate('/patient-login')}>
          ← Orqaga
        </button>
      </div>
    </div>
  )
}

export default PatientForgotPassword


