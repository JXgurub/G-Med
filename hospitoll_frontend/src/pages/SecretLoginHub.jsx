import { Link } from 'react-router-dom'
import './SecretLoginHub.css'
import { getPreferredLoginPortal, setPreferredLoginPortal } from '../utils/loginPortalPreference'

const SecretLoginHub = () => {
  const selectedPortal = getPreferredLoginPortal()

  const onSelect = (portal) => () => {
    setPreferredLoginPortal(portal)
  }

  return (
    <div className="secret-login-page">
      <div className="secret-card">
        <h1 className="secret-title">JXgroup Portal</h1>
        <p className="secret-subtitle">Maxfiy kirish sahifasi</p>

        <div className="secret-actions">
          <Link to="/doctor-login" className={`secret-btn doctor ${selectedPortal === 'doctor' ? 'active' : ''}`} onClick={onSelect('doctor')}>
            Doktor kirish
          </Link>
          <Link to="/admin-login" className={`secret-btn admin ${selectedPortal === 'admin' ? 'active' : ''}`} onClick={onSelect('admin')}>
            Admin kirish
          </Link>
          <Link to="/clinic-owner-login" className={`secret-btn clinic ${selectedPortal === 'clinic' ? 'active' : ''}`} onClick={onSelect('clinic')}>
            Klinika egasi kirish
          </Link>
          <Link to="/pharmacy-owner-login" className={`secret-btn pharmacy ${selectedPortal === 'pharmacy' ? 'active' : ''}`} onClick={onSelect('pharmacy')}>
            Dorixona egasi kirish
          </Link>
        </div>

        <p className="secret-note">Tanlangan portal keyingi kirishlarda avtomatik ochiladi.</p>
      </div>
    </div>
  )
}

export default SecretLoginHub
