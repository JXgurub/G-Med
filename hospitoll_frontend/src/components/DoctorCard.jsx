import './DoctorCard.css'

const DoctorCard = ({ doctor }) => {
  const handleBook = () => {
    alert(`${doctor.name} bilan uchrashuvga yozilish`)
  }

  const renderStars = (rating) => {
    const stars = []
    const fullStars = Math.floor(rating)
    
    for (let i = 0; i < fullStars; i++) {
      stars.push(
        <svg key={i} width="14" height="14" viewBox="0 0 16 16" fill="#FFA500">
          <path d="M8 0l2.163 5.455L16 6.5l-4 4.386L13.09 16 8 13.273 2.91 16 4 10.886 0 6.5l5.837-1.045z"/>
        </svg>
      )
    }
    
    return stars
  }

  return (
    <div className="doctor-card">
      <div className="doctor-avatar">
        <div className="avatar-placeholder">
          {doctor.fullName.charAt(0)}
        </div>
      </div>
      <div className="doctor-info">
        <h4>{doctor.fullName}</h4>
        <p className="doctor-specialization">{doctor.specialization}</p>
        <div className="doctor-rating">
          <div className="rating-stars">{renderStars(doctor.rating)}</div>
          <span className="rating-value">{doctor.rating}</span>
        </div>
      </div>
      <button className="btn-doctor-book" onClick={handleBook}>
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <path d="M16.5 12.5v2.25a1.5 1.5 0 01-1.635 1.495 14.85 14.85 0 01-6.48-2.31 14.625 14.625 0 01-4.5-4.5 14.85 14.85 0 01-2.31-6.51A1.5 1.5 0 012.25 1.5h2.25a1.5 1.5 0 011.5 1.29c.095.72.27 1.425.525 2.1a1.5 1.5 0 01-.337 1.583l-.953.952a12 12 0 004.5 4.5l.952-.952a1.5 1.5 0 011.583-.338c.675.255 1.38.43 2.1.525a1.5 1.5 0 011.29 1.52z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </button>
    </div>
  )
}

export default DoctorCard
