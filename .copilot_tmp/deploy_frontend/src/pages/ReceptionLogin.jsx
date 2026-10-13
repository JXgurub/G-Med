import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { receptionStaffApi } from '../services/api'
import './ReceptionLogin.css'

const ReceptionLogin = () => {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [deferredInstallPrompt, setDeferredInstallPrompt] = useState(null)
  const [installed, setInstalled] = useState(() => window.matchMedia('(display-mode: standalone)').matches)
  const [installHelp, setInstallHelp] = useState('')

  useEffect(() => {
    const handleInstallPrompt = (event) => {
      event.preventDefault()
      setDeferredInstallPrompt(event)
    }
    const handleInstalled = () => {
      setInstalled(true)
      setDeferredInstallPrompt(null)
      setInstallHelp("Qabulxona ilovasi kompyuterga o'rnatildi.")
    }

    window.addEventListener('beforeinstallprompt', handleInstallPrompt)
    window.addEventListener('appinstalled', handleInstalled)
    return () => {
      window.removeEventListener('beforeinstallprompt', handleInstallPrompt)
      window.removeEventListener('appinstalled', handleInstalled)
    }
  }, [])

  const handleInstall = async () => {
    if (!deferredInstallPrompt) {
      setInstallHelp("Chrome menyusidan 'Install G-MED' ni tanlang.")
      return
    }
    deferredInstallPrompt.prompt()
    const choice = await deferredInstallPrompt.userChoice
    if (choice?.outcome !== 'accepted') {
      setInstallHelp("O'rnatish bekor qilindi.")
    }
    setDeferredInstallPrompt(null)
  }

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
        {!installed && (
          <button type="button" className="reception-install-button" onClick={handleInstall}>
            Kompyuterga o'rnatish
          </button>
        )}
        {installHelp && <div className="reception-install-help">{installHelp}</div>}
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
