import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { receptionStaffApi } from '../services/api'
import './ReceptionLogin.css'

const ReceptionLogin = () => {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (event) => {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      const response = await receptionStaffApi.login({ email, password })
      localStorage.setItem('reception_session_token', response.token)
      localStorage.setItem('reception_staff', JSON.stringify({
        ...response.staff,
        clinic_id: response.staff?.clinic_id || response.staff?.clinic,
      }))
      navigate('/reception-dashboard', { replace: true })
    } catch (requestError) {
      setError(requestError?.response?.data?.detail || requestError?.message || 'Email yoki parol noto\'g\'ri.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="reception-login-page">
      <section className="reception-login-card">
        <div className="reception-login-mark">⌂</div>
        <h1>Qabulxona kirish</h1>
        <p>Klinikadagi qabul xonasi xodimlari uchun</p>
        <form onSubmit={handleSubmit}>
          <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required autoComplete="username" /></label>
          <label>Parol<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required autoComplete="current-password" /></label>
          {error && <div className="reception-login-error">{error}</div>}
          <button type="submit" disabled={loading}>{loading ? 'Tekshirilmoqda...' : 'Kirish'}</button>
        </form>
      </section>
    </main>
  )
}

export default ReceptionLogin
