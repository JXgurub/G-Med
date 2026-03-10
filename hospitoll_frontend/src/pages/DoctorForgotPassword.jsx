import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../services/api'
import PasswordInput from '../components/PasswordInput'
import { normalizeEmailWithDefaultDomain } from '../utils/helpers'
import './DoctorForgotPassword.css'

const ADMIN_TELEGRAM_URL = 'https://t.me/G_Med_group'
const CODE_MAX_SECONDS = 120

const onlyDigits = (value) => String(value || '').replace(/\D+/g, '')

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

const DoctorForgotPassword = () => {
  const navigate = useNavigate()
  const [step, setStep] = useState('identity') // identity | code | new_password

  const [passportId, setPassportId] = useState('')
  const [birthDate, setBirthDate] = useState('')
  const [pinfl, setPinfl] = useState('')
  const [code, setCode] = useState('')
  const [token, setToken] = useState('')
  const [newEmail, setNewEmail] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  const [loading, setLoading] = useState(false)
  const [resendLoading, setResendLoading] = useState(false)
  const [codeExpiresIn, setCodeExpiresIn] = useState(0)
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

  useEffect(() => {
    if (codeExpiresIn <= 0) return undefined
    const timer = setInterval(() => {
      setCodeExpiresIn((prev) => Math.max(0, Number(prev || 0) - 1))
    }, 1000)
    return () => clearInterval(timer)
  }, [codeExpiresIn])

  const startCodeCountdown = (secondsFromApi) => {
    const safeSeconds = asNonNegativeInt(secondsFromApi, CODE_MAX_SECONDS)
    const capped = Math.min(CODE_MAX_SECONDS, safeSeconds || CODE_MAX_SECONDS)
    setCodeExpiresIn(capped)
  }

  const handleResendCode = async () => {
    if (!passportId || !birthDate || !pinfl) return
    setError('')
    setInfo('')
    try {
      setResendLoading(true)
      const res = await authApi.doctorPasswordResetRequest(passportId, birthDate, pinfl)
      setCode('')
      startCodeCountdown(res?.expires_in)
      setInfo(res?.detail || 'Kod qayta yuborildi')
    } catch (err) {
      const serverDetail = err?.response?.data?.detail
      setError(serverDetail || err?.message || 'Kodni qayta yuborishda xatolik yuz berdi')
    } finally {
      setResendLoading(false)
    }
  }

  const canSubmit = useMemo(() => {
    if (loading || resendLoading) return false
    if (step === 'identity') {
      return onlyDigits(passportId).length >= 5 && Boolean(birthDate) && onlyDigits(pinfl).length === 14
    }
    if (step === 'code') {
      return Boolean(
        code &&
        token === '' &&
        passportId &&
        birthDate &&
        pinfl &&
        lockState.blockedSeconds === 0 &&
        codeExpiresIn > 0
      )
    }
    if (step === 'new_password') return Boolean(token && newPassword && confirmPassword)
    return false
  }, [step, loading, resendLoading, passportId, birthDate, pinfl, code, token, newPassword, confirmPassword, lockState.blockedSeconds, codeExpiresIn])

  const countdownSeconds = Math.max(0, Number(codeExpiresIn || 0), Number(lockState.blockedSeconds || 0))

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setInfo('')

    try {
      setLoading(true)

      if (step === 'identity') {
        const res = await authApi.doctorPasswordResetRequest(passportId, birthDate, pinfl)
        setInfo(res?.detail || 'Kod Telegram botga yuborildi')
        setCode('')
        setToken('')
        startCodeCountdown(res?.expires_in)
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
        if (codeExpiresIn <= 0) {
          setError('Kod muddati tugadi. Qayta yuborish tugmasini bosing.')
          return
        }
        const res = await authApi.doctorPasswordResetVerify(passportId, birthDate, pinfl, code)
        if (!res?.token) {
          setError('Kod notogri yoki eskirgan')
          return
        }
        setToken(res.token)
        setStep('new_password')
        setCodeExpiresIn(0)
        setInfo('Kod tasdiqlandi. Endi yangi email/parol kiriting.')
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
          setError('Parol kamida 6 ta belgidan iborat bolishi kerak')
          return
        }
        if (newPassword !== confirmPassword) {
          setError('Parollar mos emas')
          return
        }
        const normalizedEmail = normalizeEmailWithDefaultDomain(newEmail)
        const res = await authApi.doctorPasswordResetConfirm(token, newPassword, normalizedEmail)
        setInfo(res?.detail || 'Email va parol yangilandi')
        setTimeout(() => navigate('/doctor-login'), 900)
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
        const detailLower = String(serverData?.detail || '').toLowerCase()
        if (detailLower.includes('eskirgan') || detailLower.includes('muddati tugagan')) {
          setCodeExpiresIn(0)
        }
      }

      const serverDetail = err?.response?.data?.detail
      const botLink = err?.response?.data?.bot_link
      const hint = err?.response?.data?.link_hint
      if (botLink) {
        setError(`${serverDetail || 'Xatolik'} ${hint ? ` ${hint}` : ''}`)
        setInfo(`Bot manzili: ${botLink}`)
      } else {
        setError(serverDetail || err?.message || 'Xatolik yuz berdi')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="doctor-forgot-page">
      <div className="doctor-forgot-card">
        <div className="doctor-forgot-header">
          <div className="badge">Doktor parolini tiklash</div>
          <h1>Parolni unutdingizmi?</h1>
          <p>Iltimos so'ralgan barcha malumotlarni e'tibor va aniq kiriting. Hamma malumotlaringgiz to'g'ri bo'lsa biz sizga telegram orqali bir martalik kod yuboramiz.</p>
        </div>

        <form className="doctor-forgot-form" onSubmit={onSubmit}>
          {step === 'identity' && (
            <>
              <label className="field">
                <span>Passport ID</span>
                <input
                  type="text"
                  value={passportId}
                  onChange={(e) => setPassportId(e.target.value.toUpperCase())}
                  placeholder="AA1234567"
                  required
                />
              </label>

              <label className="field">
                <span>Tug'ilgan sana</span>
                <input
                  type="date"
                  value={birthDate}
                  onChange={(e) => setBirthDate(e.target.value)}
                  required
                />
              </label>

              <label className="field">
                <span>PINFL (JSHSHIR)</span>
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  value={pinfl}
                  onChange={(e) => setPinfl(e.target.value.replace(/\D+/g, ''))}
                  maxLength={14}
                  placeholder="12345678901234"
                  required
                />
              </label>
            </>
          )}

          {step === 'code' && (
            <>
              <label className="field">
                <span>Bir martalik kod</span>
                <div className="code-input-wrap">
                  <input
                    className="code-input"
                    type="text"
                    inputMode="numeric"
                    value={code}
                    onChange={(e) => setCode(e.target.value.replace(/\D+/g, ''))}
                    placeholder="123456"
                    required
                  />
                  <span className={`code-countdown ${countdownSeconds <= 0 ? 'expired' : ''} ${lockState.blockedSeconds > 0 ? 'blocked' : ''}`}>
                    {formatDuration(countdownSeconds)}
                  </span>
                </div>
              </label>
            </>
          )}

          {step === 'new_password' && (
            <>
              <label className="field">
                <span>Yangi email (ixtiyoriy)</span>
                <input
                  type="email"
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  onBlur={(e) => setNewEmail(normalizeEmailWithDefaultDomain(e.target.value))}
                  placeholder="doctor@gmail.com"
                />
              </label>

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

          {step === 'code' && countdownSeconds <= 0 && (
            <button
              type="button"
              className="btn-secondary"
              onClick={handleResendCode}
              disabled={loading || resendLoading}
            >
              {resendLoading ? 'Qayta yuborilmoqda...' : 'Kodni qayta yuborish'}
            </button>
          )}

          <button className="btn" type="submit" disabled={!canSubmit}>
            {loading ? 'Kutilmoqda...' : step === 'identity' ? 'Kod yuborish' : step === 'code' ? 'Kod tasdiqlash' : 'Yangilash'}
          </button>
        </form>

        <a className="admin-telegram-btn" href={ADMIN_TELEGRAM_URL} target="_blank" rel="noreferrer">
          Admin Telegrami
        </a>

        <button className="btn-back" type="button" onClick={() => navigate('/doctor-login')}>
          Orqaga
        </button>
      </div>
    </div>
  )
}

export default DoctorForgotPassword
