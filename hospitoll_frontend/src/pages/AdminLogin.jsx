import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAdmin } from '../context/AdminContext'
import PasswordInput from '../components/PasswordInput'
import './AdminLogin.css'

const AdminLogin = () => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const { loginAdmin } = useAdmin()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    const result = await loginAdmin(email, password)
    if (result.success) {
      navigate('/admin-dashboard')
    } else {
      setError(result.error)
    }
    setLoading(false)
  }

  const handleBackToLogin = () => {
    navigate('/login')
  }

  return (
    <div className="admin-login-page">
      <div className="login-container">
        <div className="admin-badge">
          <span>🔐 ADMIN PORTAL</span>
        </div>

        <div className="login-card">
          <div className="login-header">
            <div className="logo-icon">👨‍💼</div>
            <h1>Admin Panel</h1>
            <p>Tizim boshqaruviga kirish</p>
          </div>

          <form onSubmit={handleSubmit} className="login-form">
            <div className="form-group">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                placeholder="admin@example.uz"
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
              {loading ? 'Kirish...' : 'Admin Panelga Kirish'}
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

export default AdminLogin
