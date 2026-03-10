import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../services/api'
import PasswordInput from '../components/PasswordInput'
import './PatientForgotPassword.css'

const asNonNegativeInt = (value, fallback = null) => {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return fallback
  return Math.max(0, Math.floor(parsed))
}

const formatDuration = (seconds) => {
  const safe = Math.max(0, Number(seconds || 0))
  const hrs = Math.floor(safe / 3600)
  const mins = Math.floor((safe % 3600) / 60)
  const secs = safe % 60
  if (hrs > 0) {
    return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
  }
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

const PatientForgotPassword = () => {
  const navigate = useNavigate()
  const [step, setStep] = useState('phone') // phone | code | new_password

  const [passportId, setPassportId] = useState('')
  const [phoneNumber, setPhoneNumber] = useState('+998')
  const [code, setCode] = useState('')
  const [token, setToken] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [lockState, setLockState] = useState({
    attemptsLeft: null,
    attemptsLimit: 5,
    blockedSeconds: 0,
    supportRequired: false,
    adminTelegram: '',
  })

  useEffect(() => {
    if (lockState.blockedSeconds <= 0) return undefined
    const timer = setInterval(() => {
      setLockState((prev) => ({
        ...prev,
        blockedSeconds: Math.max(0, Number(prev.blockedSeconds || 0) - 1),
      }))
    }, 1000)
    return () => clearInterval(timer)
  }, [lockState.blockedSeconds])

  const canSubmit = useMemo(() => {
    if (loading) return false
    if (step === 'phone') return Boolean(phoneNumber && passportId)
    if (step === 'code') return Boolean(phoneNumber && passportId && code && lockState.blockedSeconds === 0)
    if (step === 'new_password') return Boolean(token && newPassword && confirmPassword)
    return false
  }, [step, loading, phoneNumber, passportId, code, token, newPassword, confirmPassword, lockState.blockedSeconds])

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setInfo('')

    try {
      setLoading(true)

      if (step === 'phone') {
        const res = await authApi.patientPasswordResetRequest(phoneNumber, passportId)
        setInfo(res?.detail || 'Kod Telegram botga yuborildi')
        setLockState({
          attemptsLeft: 5,
          attemptsLimit: 5,
          blockedSeconds: 0,
          supportRequired: false,
          adminTelegram: '',
        })
        setStep('code')
        return
      }

      if (step === 'code') {
        const res = await authApi.patientPasswordResetVerify(phoneNumber, code, passportId)
        if (!res?.token) {
          setError('Kod noto\'g\'ri yoki eskirgan')
          return
        }
        setToken(res.token)
        setStep('new_password')
        setLockState({
          attemptsLeft: null,
          attemptsLimit: 5,
          blockedSeconds: 0,
          supportRequired: false,
          adminTelegram: '',
        })
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
      const serverData = err?.response?.data || {}
      if (step === 'code') {
        const attemptsLeft = asNonNegativeInt(serverData?.attempts_left, null)
        const attemptsLimit = asNonNegativeInt(serverData?.attempts_limit, 5)
        const blockedSeconds = asNonNegativeInt(serverData?.blocked_seconds, 0)

        setLockState((prev) => ({
          ...prev,
          attemptsLeft: attemptsLeft === null ? prev.attemptsLeft : attemptsLeft,
          attemptsLimit: attemptsLimit || prev.attemptsLimit || 5,
          blockedSeconds,
          supportRequired: Boolean(serverData?.support_required),
          adminTelegram: String(serverData?.admin_telegram || ''),
        }))
      }
      setError(serverData?.detail || err?.message || 'Xatolik yuz berdi')
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
          <p>Pasport ID va telefon orqali Telegram botga bir martalik kod yuboramiz</p>
        </div>

        <form className="patient-forgot-form" onSubmit={onSubmit}>
          {step === 'phone' && (
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
                <span>Telefon raqam</span>
                <input
                  type="tel"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  placeholder="+998901234567"
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
                <span>Telefon raqam</span>
                <input type="tel" value={phoneNumber} disabled />
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

          {step === 'code' && lockState.attemptsLeft !== null && (
            <div className="message info">
              Urinishlar: {Math.max(0, (lockState.attemptsLimit || 0) - (lockState.attemptsLeft || 0))}/{lockState.attemptsLimit || 0}. Qolgan urinish: {lockState.attemptsLeft || 0}
            </div>
          )}

          {step === 'code' && lockState.blockedSeconds > 0 && (
            <div className="message error">
              Qayta urinishgacha: {formatDuration(lockState.blockedSeconds)}
            </div>
          )}

          {step === 'code' && lockState.supportRequired && (
            <div className="message info">
              Endi adminga murojaat qiling.
              {lockState.adminTelegram ? (
                <>
                  {' '}
                  <a href={lockState.adminTelegram} target="_blank" rel="noreferrer">{lockState.adminTelegram}</a>
                </>
              ) : null}
            </div>
          )}

          <button className="btn" type="submit" disabled={!canSubmit}>
            {loading ? 'Kutilmoqda...' : step === 'phone' ? 'Kod yuborish' : step === 'code' ? 'Kod tasdiqlash' : 'Parolni yangilash'}
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


