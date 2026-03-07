import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useClinic } from '../context/ClinicContext'
import PasswordInput from '../components/PasswordInput'
import './ClinicOwnerLogin.css'

const ClinicOwnerLogin = () => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const { loginClinicOwner } = useClinic()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    const result = await loginClinicOwner(email, password)
    if (result.success) {
      navigate('/clinic-dashboard')
    } else {
      setError(result.error)
    }
    setLoading(false)
  }

  const handleBackToLogin = () => {
    navigate('/login')
  }

  return (
    <div className="clinic-owner-login-page">
      <div className="login-container">
        <div className="login-card">
          <div className="login-header">
            <div className="logo-icon">G</div>
            <h1>Klinika Egasi Portali</h1>
            <p>O'z klinikangizga kirishingiz</p>
          </div>

          <form onSubmit={handleSubmit} className="login-form" autoComplete="on">
            <div className="form-group">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                placeholder="clinic@example.uz"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loading}
                autoComplete="email"
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
                autoComplete="current-password"
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
          </form>

          <button className="btn-back" onClick={handleBackToLogin}>
            ← Orqaga
          </button>
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

export default ClinicOwnerLogin
