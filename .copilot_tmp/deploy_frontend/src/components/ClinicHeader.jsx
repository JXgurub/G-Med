import { useNavigate } from 'react-router-dom'
import { resolveMediaUrl } from '../services/api'
import './ClinicHeader.css'

const ClinicHeader = ({ clinic }) => {
  const navigate = useNavigate()

  const handleBook = () => {
    alert(`${clinic.name} ga qabulga yozilish - tez orada amalga oshiriladi`)
  }

  const handlePatient = () => {
    navigate('/')
  }

  const renderStars = (rating) => {
    const stars = []
    const fullStars = Math.floor(rating)
    
    for (let i = 0; i < fullStars; i++) {
      stars.push(
        <svg key={i} width="18" height="18" viewBox="0 0 16 16" fill="#FFA500">
          <path d="M8 0l2.163 5.455L16 6.5l-4 4.386L13.09 16 8 13.273 2.91 16 4 10.886 0 6.5l5.837-1.045z"/>
        </svg>
      )
    }
    
    return stars
  }

  return (
    <div className="clinic-header">
      {resolveMediaUrl(clinic.bannerImage) && (
        <div
          className="clinic-header-banner"
          aria-hidden="true"
          style={{ backgroundImage: `url(${resolveMediaUrl(clinic.bannerImage)})` }}
        />
      )}
      <div className="clinic-header-content">
        <div className="clinic-header-left">
          <div className="clinic-header-icon">
            <svg width="60" height="60" viewBox="0 0 60 60" fill="none">
              <rect width="60" height="60" rx="12" fill="#e3f2fd"/>
              <path d="M30 12C22 12 16 18 16 26c0 4 2 8 4 10l2 8c0 2 2 4 4 4h8v-4h4v4h8c2 0 4-2 4-4l2-8c2-2 4-6 4-10 0-8-6-14-14-14z" fill="#1e6fd7"/>
            </svg>
          </div>
          <div className="clinic-header-info">
            <h1>{clinic.name}</h1>
            {clinic.testLogin && (
              <div className="clinic-test-badge">
                <span className="test-badge-label">🧪 Test Login:</span>
                <code className="test-badge-id">{clinic.testLogin.id}</code>
                <span className="test-badge-separator">|</span>
                <code className="test-badge-password">{clinic.testLogin.password}</code>
              </div>
            )}
            <div className="clinic-rating">
              <div className="rating-stars">{renderStars(clinic.rating)}</div>
              <span className="rating-text">{clinic.rating} ({clinic.reviewCount} sharh)</span>
            </div>
          </div>
        </div>

        <div className="clinic-header-actions">
          <button className="btn-book" onClick={handleBook}>
            Qabulga yozilish
          </button>
          <button className="btn-patient" onClick={handlePatient}>
            Men bemorman
          </button>
        </div>
      </div>

      <div className="clinic-details">
        <div className="detail-item">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M10 17c4 0 7-2 7-5V9c0-3-3-5-7-5S3 6 3 9v3c0 3 3 5 7 5z" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M14 6l3-3m-10 0L4 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <div>
            <p className="detail-label">Manzil</p>
            <p className="detail-value">{clinic.address}</p>
          </div>
        </div>

        <div className="detail-item">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M17.5 12.5v2.25a1.5 1.5 0 01-1.635 1.495 14.85 14.85 0 01-6.48-2.31 14.625 14.625 0 01-4.5-4.5 14.85 14.85 0 01-2.31-6.51A1.5 1.5 0 012.25 1.5h2.25a1.5 1.5 0 011.5 1.29c.095.72.27 1.425.525 2.1a1.5 1.5 0 01-.337 1.583l-.953.952a12 12 0 004.5 4.5l.952-.952a1.5 1.5 0 011.583-.338c.675.255 1.38.43 2.1.525a1.5 1.5 0 011.29 1.52z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <div>
            <p className="detail-label">Telefon</p>
            <p className="detail-value">{clinic.phone}</p>
          </div>
        </div>

        <div className="detail-item">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M10 6v4l3 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <div>
            <p className="detail-label">Ishlash vaqti</p>
            <p className="detail-value">{clinic.workingHours}</p>
          </div>
        </div>

        <div className="detail-item">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M10 18c4.418 0 8-3.582 8-8s-3.582-8-8-8-8 3.582-8 8 3.582 8 8 8z" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M10 6v4l3 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <div>
            <p className="detail-label">Tashkentda joylashuvi</p>
            <p className="detail-value">{clinic.city}</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ClinicHeader
