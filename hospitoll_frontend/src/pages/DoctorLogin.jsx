import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDoctor } from '../context/DoctorContext'
import PasswordInput from '../components/PasswordInput'
import './DoctorLogin.css'

const DoctorLogin = () => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const { loginDoctor } = useDoctor()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    const result = await loginDoctor(email, password)
    if (result.success) {
      navigate('/doctor-dashboard')
    } else {
      setError(result.error)
    }
    setLoading(false)
  }

  const handleBackToLogin = () => {
    navigate('/login')
  }

  return (
    <div className="doctor-login-page">
      <div className="login-container">
        <div className="login-card">
          <div className="login-header">
            <div className="logo-icon">📋</div>
            <h1>Doktor Portal</h1>
            <p>O'z hisob qaydnomasiga kirishingiz</p>
          </div>

          <form onSubmit={handleSubmit} className="login-form">
            <div className="form-group">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                placeholder="doctor@example.uz"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
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

            {error && <div className="error-message">{error}</div>}

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

export default DoctorLogin
