import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../services/api'
import PasswordInput from '../components/PasswordInput'
import { normalizeEmailWithDefaultDomain } from '../utils/helpers'
import './DoctorForgotPassword.css'

const ADMIN_TELEGRAM_URL = 'https://t.me/JXgroup_bot'
const CODE_MAX_SECONDS = 120
const BOT_LINK_HIDE_SECONDS = 3600
const BOT_LINK_HIDE_STORAGE_KEY = 'pharmacy_reset_bot_link_hidden_until'

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

const PharmacyOwnerForgotPassword = () => {
  const navigate = useNavigate()
  const [step, setStep] = useState('identity')

  const [pharmacyNumber, setPharmacyNumber] = useState('')
  const [passportId, setPassportId] = useState('')
  const [phoneNumber, setPhoneNumber] = useState('')
  const [code, setCode] = useState('')
  const [token, setToken] = useState('')
  const [newEmail, setNewEmail] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  const [loading, setLoading] = useState(false)
  const [resendLoading, setResendLoading] = useState(false)
  const [codeExpiresIn, setCodeExpiresIn] = useState(0)
  const [botLink, setBotLink] = useState('')
  const [botSessionNote, setBotSessionNote] = useState('')
  const [botLinkHiddenUntil, setBotLinkHiddenUntil] = useState(0)
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

  useEffect(() => {
    const storedUntil = Number(window.localStorage.getItem(BOT_LINK_HIDE_STORAGE_KEY) || 0)
    if (Number.isFinite(storedUntil) && storedUntil > Date.now()) {
      setBotLinkHiddenUntil(storedUntil)
    }
  }, [])

  useEffect(() => {
    if (!botLinkHiddenUntil || botLinkHiddenUntil <= Date.now()) return undefined
    const timeoutMs = botLinkHiddenUntil - Date.now()
    const timer = setTimeout(() => {
      setBotLinkHiddenUntil(0)
      window.localStorage.removeItem(BOT_LINK_HIDE_STORAGE_KEY)
    }, timeoutMs)
    return () => clearTimeout(timer)
  }, [botLinkHiddenUntil])

  const startCodeCountdown = (secondsFromApi) => {
    const safeSeconds = asNonNegativeInt(secondsFromApi, CODE_MAX_SECONDS)
    const capped = Math.min(CODE_MAX_SECONDS, safeSeconds || CODE_MAX_SECONDS)
    setCodeExpiresIn(capped)
  }

  const countdownSeconds = Math.max(0, Number(codeExpiresIn || 0), Number(lockState.blockedSeconds || 0))
  const isCodeExpired = codeExpiresIn <= 0
  const attemptsUsed = Math.max(0, Number(lockState.attemptsLimit || 0) - Number(lockState.attemptsLeft || 0))
  const attemptsLimit = Number(lockState.attemptsLimit || 0)
  const isBotButtonVisible = Boolean(step === 'code' && botLink && Date.now() >= Number(botLinkHiddenUntil || 0))

  const canSubmit = useMemo(() => {
    if (loading || resendLoading) return false
    if (step === 'identity') {
      return Boolean(pharmacyNumber.trim() && onlyDigits(passportId).length >= 5 && onlyDigits(phoneNumber).length >= 9)
    }
    if (step === 'code') {
      if (!pharmacyNumber || !passportId || !phoneNumber || token !== '' || lockState.blockedSeconds > 0) return false
      return isCodeExpired ? true : Boolean(code)
    }
    if (step === 'new_password') {
      return Boolean(token && newPassword && confirmPassword)
    }
    return false
  }, [step, loading, resendLoading, pharmacyNumber, passportId, phoneNumber, code, token, newPassword, confirmPassword, lockState.blockedSeconds, isCodeExpired])

  const handleOpenBot = () => {
    if (!botLink) return
    const hiddenUntil = Date.now() + (BOT_LINK_HIDE_SECONDS * 1000)
    setBotLinkHiddenUntil(hiddenUntil)
    window.localStorage.setItem(BOT_LINK_HIDE_STORAGE_KEY, String(hiddenUntil))
    window.location.href = botLink
  }

  const handleResendCode = async () => {
    if (!pharmacyNumber || !passportId || !phoneNumber) return

    setError('')
    setInfo('')
    try {
      setResendLoading(true)
      const res = await authApi.pharmacyPasswordResetRequest(pharmacyNumber, passportId, phoneNumber)
      setCode('')
      setToken('')
      startCodeCountdown(res?.expires_in)
      setBotLink(String(res?.bot_link || botLink || ''))
      setBotSessionNote(String(res?.bot_note || botSessionNote || ''))
      setInfo(res?.detail || 'Kod qayta yuborildi')
    } catch (err) {
      const serverDetail = err?.response?.data?.detail
      setError(serverDetail || err?.message || 'Kodni qayta yuborishda xatolik yuz berdi')
    } finally {
      setResendLoading(false)
    }
  }

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setInfo('')

    try {
      setLoading(true)

      if (step === 'identity') {
        const res = await authApi.pharmacyPasswordResetRequest(pharmacyNumber, passportId, phoneNumber)
        setBotLink(String(res?.bot_link || ''))
        setBotSessionNote(String(res?.bot_note || ''))
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
        if (isCodeExpired) {
          await handleResendCode()
          return
        }

        const res = await authApi.pharmacyPasswordResetVerify(pharmacyNumber, passportId, phoneNumber, code)
        if (!res?.token) {
          setCode('')
          setError("Kod noto'g'ri yoki eskirgan.")
          return
        }

        setToken(res.token)
        setCodeExpiresIn(0)
        setLockState({
          attemptsLeft: null,
          attemptsLimit: 5,
          blockedSeconds: 0,
          supportRequired: false,
          adminTelegram: '',
        })
        setInfo("Kod tasdiqlandi. Endi yangi email yoki parol kiriting.")
        setStep('new_password')
        return
      }

      if (step === 'new_password') {
        if (newPassword.length < 6) {
          setError("Parol kamida 6 ta belgidan iborat bo'lishi kerak")
          return
        }
        if (newPassword !== confirmPassword) {
          setError('Parollar mos emas')
          return
        }

        const normalizedEmail = normalizeEmailWithDefaultDomain(newEmail)
        const res = await authApi.pharmacyPasswordResetConfirm(token, newPassword, normalizedEmail)
        setInfo(res?.detail || 'Email va parol muvaffaqiyatli yangilandi')
        setTimeout(() => navigate('/pharmacy-owner-login'), 900)
      }
    } catch (err) {
      const serverData = err?.response?.data || {}

      if (step === 'code') {
        const attemptsLeft = asNonNegativeInt(serverData?.attempts_left, null)
        const attemptsLimitValue = asNonNegativeInt(serverData?.attempts_limit, 5)
        const blockedSeconds = asNonNegativeInt(serverData?.blocked_seconds, 0)

        setLockState((prev) => ({
          ...prev,
          attemptsLeft: attemptsLeft === null ? prev.attemptsLeft : attemptsLeft,
          attemptsLimit: attemptsLimitValue || prev.attemptsLimit || 5,
          blockedSeconds,
          supportRequired: Boolean(serverData?.support_required),
          adminTelegram: String(serverData?.admin_telegram || ''),
        }))

        const detailLower = String(serverData?.detail || '').toLowerCase()
        if (detailLower.includes('eskirgan') || detailLower.includes('muddati tugagan')) {
          setCodeExpiresIn(0)
        }

        setCode('')
      }

      const serverDetail = serverData?.detail || err?.message || 'Xatolik yuz berdi'
      const responseBotLink = serverData?.bot_link
      const hint = serverData?.link_hint

      if (responseBotLink) {
        setError(`${serverDetail}${hint ? ` ${hint}` : ''}`)
        setBotLink(String(responseBotLink))
        setInfo(`Bot manzili: ${responseBotLink}`)
      } else {
        setError(serverDetail)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="doctor-forgot-page">
      <div className="doctor-forgot-card">
        <div className="doctor-forgot-header">
          <div className="badge">Dorixona parolini tiklash</div>
          <h1>Parolni unutdingizmi?</h1>
          <p>Iltimos, so'ralgan barcha ma'lumotlarni aniq kiriting. Ma'lumotlar to'g'ri bo'lsa, sizga Telegram orqali bir martalik kod yuboramiz.</p>
        </div>

        <form className="doctor-forgot-form" onSubmit={onSubmit}>
          {step === 'identity' && (
            <>
              <label className="field">
                <span>Dorixona raqami</span>
                <input
                  type="text"
                  value={pharmacyNumber}
                  onChange={(e) => setPharmacyNumber(e.target.value.toUpperCase())}
                  placeholder="PHR-ABC1234567"
                  required
                />
              </label>

              <label className="field">
                <span>Pasport ID</span>
                <input
                  type="text"
                  value={passportId}
                  onChange={(e) => setPassportId(e.target.value.toUpperCase())}
                  placeholder="AA1234567"
                  required
                />
              </label>

              <label className="field">
                <span>Telefon raqami</span>
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
                <div className="attempts-inline">{attemptsUsed}/{attemptsLimit}</div>
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
                  placeholder="pharmacy.owner@gmail.com"
                />
              </label>

              <label className="field">
                <span>Yangi parol</span>
                <PasswordInput
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="********"
                  required
                />
              </label>

              <label className="field">
                <span>Yangi parol (takror)</span>
                <PasswordInput
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="********"
                  required
                />
              </label>
            </>
          )}

          {step === 'code' && botSessionNote && (
            <div className="message info">{botSessionNote}</div>
          )}

          {error && <div className="message error">{error}</div>}
          {info && <div className="message info">{info}</div>}

          {isBotButtonVisible && (
            <button
              type="button"
              className="btn-secondary"
              onClick={handleOpenBot}
              disabled={loading || resendLoading}
            >
              Botga o'tish
            </button>
          )}

          <button className="btn" type="submit" disabled={!canSubmit}>
            {loading || resendLoading
              ? 'Kutilmoqda...'
              : step === 'identity'
                ? 'Kod yuborish'
                : step === 'code'
                  ? (isCodeExpired ? 'Kodni qayta yuborish' : 'Kodni tasdiqlash')
                  : 'Parolni yangilash'}
          </button>
        </form>

        <a className="admin-telegram-btn" href={ADMIN_TELEGRAM_URL} target="_blank" rel="noreferrer">
          Admin Telegrami
        </a>

        <button className="btn-back" type="button" onClick={() => navigate('/pharmacy-owner-login')}>
          Orqaga
        </button>
      </div>
    </div>
  )
}

export default PharmacyOwnerForgotPassword
