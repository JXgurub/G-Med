import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePharmacy } from '../context/PharmacyContext'
import PasswordInput from '../components/PasswordInput'
import { normalizeEmailWithDefaultDomain } from '../utils/helpers'
import { setPreferredLoginPortal } from '../utils/loginPortalPreference'
import './PharmacyOwnerLogin.css'

const PharmacyOwnerLogin = () => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const { loginPharmacy } = usePharmacy()

  useEffect(() => {
    setPreferredLoginPortal('pharmacy')
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    const normalizedEmail = normalizeEmailWithDefaultDomain(email)
    const result = await loginPharmacy(normalizedEmail, password)
    if (result.success) {
      navigate('/pharmacy-owner-dashboard')
    } else {
      setError(result.error)
    }
    setLoading(false)
  }

  return (
    <div className="pharmacy-owner-login-page">
      <div className="login-container">
        <div className="login-card">
          <div className="login-header">
            <div className="logo-icon">💊</div>
            <h1>Dorixona Egasi Portal</h1>
            <p>O'z dorixonaga kirishiniz</p>
          </div>

          <form onSubmit={handleSubmit} className="login-form">
            <div className="form-group">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                placeholder="pharmacy@example.uz"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onBlur={(e) => setEmail(normalizeEmailWithDefaultDomain(e.target.value))}
                disabled={loading}
                autoFocus
              />
            </div>

            <div className="form-group">
              <label htmlFor="password">Parol</label>
              <PasswordInput
                id="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loading}
              />
            </div>

            {error && (
              <div className={error.includes('to\'xtatilgan') || error.includes('yopilgan') ? 'warning-message blocked' : 'error-message'}>
                {error.includes('to\'xtatilgan') || error.includes('yopilgan') ? (
                  <>
                    <div className="warning-icon">⚠️</div>
                    <div className="warning-content">
                      <strong>Kirish cheklangan</strong>
                      <p>{error}</p>
                    </div>
                  </>
                ) : (
                  error
                )}
              </div>
            )}

            <button
              type="submit"
              className="btn-login"
              disabled={loading || !email || !password}
            >
              {loading ? 'Kirish...' : 'Kirish'}
            </button>

            <button
              type="button"
              className="btn-forgot"
              onClick={() => navigate('/pharmacy-owner-forgot-password')}
              disabled={loading}
            >
              Parolni unutdingizmi?
            </button>
          </form>

        </div>

        <div className="login-background">
          <div className="gradient-orb orb-1"></div>
          <div className="gradient-orb orb-2"></div>
          <div className="gradient-orb orb-3"></div>
        </div>
      </div>
    </div>
  )
}

export default PharmacyOwnerLogin
