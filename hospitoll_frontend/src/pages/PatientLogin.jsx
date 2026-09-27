import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePatient } from '../context/PatientContext'
import { authApi } from '../services/api'
import PasswordInput from '../components/PasswordInput'
import './PatientLogin.css'

const PatientLogin = () => {
  const navigate = useNavigate()
  const { loginPatient } = usePatient()
  const [phoneNumber, setPhoneNumber] = useState('+998')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [registrationToken, setRegistrationToken] = useState('')
  const [registrationCode, setRegistrationCode] = useState('')
  const [botLink, setBotLink] = useState('')
  const [isRegistering, setIsRegistering] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setMessage('')
    setLoading(true)

    try {
      if (isRegistering) {
        if (!registrationToken) {
          if (password !== passwordConfirm) {
            setError('Parollar mos emas')
            return
          }

          const response = await authApi.patientRegister({
            first_name: firstName,
            last_name: lastName,
            phone_number: phoneNumber,
          })
          setRegistrationToken(response.token)
          setBotLink(response.bot_link)
          setMessage(response.detail)
          return
        }

        await authApi.patientRegisterVerify(registrationToken, registrationCode, password, passwordConfirm)
        const loginResult = await loginPatient(phoneNumber, password)
        if (loginResult.success) navigate('/patient')
        else setMessage("Ro'yxatdan o'tdingiz. Telefon raqam va parol bilan kiring.")
        return
      }

      const result = await loginPatient(phoneNumber, password)
      if (result.success) {
        navigate('/patient')
      } else {
        setError(result.error)
      }
    } catch (submitError) {
      const responseData = submitError?.response?.data
      const validationMessage = responseData && typeof responseData === 'object'
        ? Object.values(responseData).flat().join(' ')
        : ''
      setError(validationMessage || submitError?.message || 'Serverga ulanishda xatolik yuz berdi')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="patient-login-page">
      <div className="patient-login-card">
        <div className="patient-login-header">
          <div className="login-badge">{isRegistering ? "Bemor ro'yxati" : 'Bemor kirishi'}</div>
          <h1>{isRegistering ? "Bemor sifatida ro'yxatdan o'tish" : 'Bemor sahifasiga kirish'}</h1>
          <p>{isRegistering ? 'Hisob yaratish uchun ma’lumotlarni kiriting' : 'Telefon raqam va parol orqali'}</p>
        </div>

        <form className="patient-login-form" onSubmit={handleSubmit}>
          {isRegistering && (
            <>
              <label className="patient-login-field">
                <span>Ism</span>
                <input value={firstName} onChange={(e) => setFirstName(e.target.value)} required disabled={Boolean(registrationToken)} />
              </label>

              <label className="patient-login-field">
                <span>Familiya</span>
                <input value={lastName} onChange={(e) => setLastName(e.target.value)} required disabled={Boolean(registrationToken)} />
              </label>
            </>
          )}

          <label className="patient-login-field">
            <span>Telefon raqam</span>
            <input
              type="tel"
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(e.target.value.replace(/\s+/g, ''))}
              placeholder="+998901234567"
              required
              disabled={isRegistering && Boolean(registrationToken)}
            />
          </label>

          <label className="patient-login-field">
            <span>Parol</span>
            <PasswordInput
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              minLength={6}
              required
              disabled={isRegistering && Boolean(registrationToken)}
            />
          </label>

          {isRegistering && (
            <label className="patient-login-field">
              <span>Parolni takrorlang</span>
              <PasswordInput
                value={passwordConfirm}
                onChange={(e) => setPasswordConfirm(e.target.value)}
                placeholder="••••••••"
                minLength={6}
                required
                disabled={Boolean(registrationToken)}
              />
            </label>
          )}

          {isRegistering && registrationToken && (
            <>
              <a className="patient-login-bot-link" href={botLink} target="_blank" rel="noreferrer">
                Telegram botni ochish
              </a>
              <label className="patient-login-field">
                <span>Telegram tasdiqlash kodi</span>
                <input
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  pattern="[0-9]{6}"
                  maxLength={6}
                  value={registrationCode}
                  onChange={(e) => setRegistrationCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="6 xonali kod"
                  required
                />
              </label>
            </>
          )}

          {error && <div className="patient-login-error">{error}</div>}
          {message && <div className="patient-login-message">{message}</div>}

          <button type="submit" className="patient-login-button" disabled={loading}>
            {loading ? 'Tekshirilmoqda...' : isRegistering ? (registrationToken ? 'Kodni tasdiqlash' : 'Telegram kodini so‘rash') : 'Kirish'}
          </button>

          {!isRegistering && (
            <button
              type="button"
              className="patient-login-forgot"
              onClick={() => navigate('/patient-forgot-password')}
              disabled={loading}
            >
              Parolni unutdingizmi?
            </button>
          )}

          <button
            type="button"
            className="patient-login-switch"
            onClick={() => {
              setIsRegistering((current) => !current)
              setError('')
              setMessage('')
              setRegistrationToken('')
              setRegistrationCode('')
              setBotLink('')
            }}
            disabled={loading}
          >
            {isRegistering ? 'Hisobingiz bormi? Kirish' : "Ro'yxatdan o'tish"}
          </button>
        </form>

        <div className="patient-login-footer">
          <div className="demo-card">
            <p>{isRegistering ? (registrationToken ? 'Botni ochib Start bosing, yuborilgan kodni kiriting' : 'Telefon raqamingiz hisobingizga kirish uchun ishlatiladi') : 'Bemor hisobiga telefon raqam va parol orqali kiring'}</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default PatientLogin
