import { Link } from 'react-router-dom'
import './SecretLoginHub.css'

const SecretLoginHub = () => {
  return (
    <div className="secret-login-page">
      <div className="secret-card">
        <h1 className="secret-title">JXgroup Portal</h1>
        <p className="secret-subtitle">Maxfiy kirish sahifasi</p>

        <div className="secret-actions">
          <Link to="/admin-login" className="secret-btn admin">Admin kirish</Link>
          <Link to="/clinic-owner-login" className="secret-btn clinic">Klinika egasi kirish</Link>
          <Link to="/pharmacy-owner-login" className="secret-btn pharmacy">Dorixona egasi kirish</Link>
        </div>
      </div>
    </div>
  )
}

export default SecretLoginHub
