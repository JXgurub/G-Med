import { useState } from 'react'
import './PharmacyCard.css'

const PharmacyCard = ({ pharmacy, compact = false }) => {
  const [showMedicines, setShowMedicines] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  const formatWorkingHours = (value) => {
    const source = String(value || '').trim()
    const match = source.match(/(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})/)
    if (!match) return source || '09:00 - 20:00'
    const normalize = (time) => {
      const [hourStr, minuteStr] = String(time).split(':')
      const hour = Number(hourStr)
      const minute = Number(minuteStr)
      if (Number.isNaN(hour) || Number.isNaN(minute)) return time
      return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
    }
    return `${normalize(match[1])} - ${normalize(match[2])}`
  }

  const getOpenStatus = (workingHours) => {
    const source = formatWorkingHours(workingHours)
    const match = source.match(/(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})/)
    if (!match) return { isOpen: null, label: 'Ish vaqti ko‘rsatilmagan' }

    const toMinutes = (time) => {
      const [hour, minute] = time.split(':').map(Number)
      return (hour * 60) + minute
    }

    const now = new Date()
    const currentMinutes = (now.getHours() * 60) + now.getMinutes()
    const startMinutes = toMinutes(match[1])
    const endMinutes = toMinutes(match[2])

    let isOpen
    if (endMinutes <= startMinutes) {
      isOpen = currentMinutes >= startMinutes || currentMinutes <= endMinutes
    } else {
      isOpen = currentMinutes >= startMinutes && currentMinutes <= endMinutes
    }

    return { isOpen, label: isOpen ? 'Hozir ochiq' : 'Hozir yopiq' }
  }

  const formatPhoneDisplay = (value) => {
    const raw = String(value || '').replace(/\s+/g, '')
    const match = raw.match(/^(\+998)(\d{2})(\d{3})(\d{2})(\d{2})$/)
    if (!match) return value || '-'
    return `${match[1]} ${match[2]} ${match[3]} ${match[4]} ${match[5]}`
  }

  const workingHoursDisplay = formatWorkingHours(pharmacy.workingHours)
  const openStatus = getOpenStatus(workingHoursDisplay)
  const phoneDisplay = formatPhoneDisplay(pharmacy.phone)

  const getInitials = (name) => {
    const words = String(name || '').trim().split(/\s+/).filter(Boolean)
    if (words.length === 0) return 'PH'
    return words.slice(0, 2).map((word) => word[0]?.toUpperCase() || '').join('')
  }

  const handleCall = () => {
    if (pharmacy.phone) {
      const phoneDisplay = pharmacy.phone.replace(/(\+998)(\d{2})(\d{3})(\d{2})(\d{2})/, '$1 $2 $3 $4 $5')
      alert(`📞 Dorixona raqami:\n\n${phoneDisplay}\n\n(Qo'ng'iroq qilish uchun OK bosing)`)
      window.location.href = `tel:${pharmacy.phone}`
    } else {
      alert('Telefon raqam mavjud emas')
    }
  }

  const handleShowMedicines = () => {
    setShowMedicines(true)
  }

  const handleCardKeyDown = (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      handleShowMedicines()
    }
  }

  const handleCloseMedicines = () => {
    setShowMedicines(false)
    setSearchQuery('')
  }

  // Generate stars based on rating
  const renderStars = (rating) => {
    const stars = []
    const fullStars = Math.floor(rating || 0)
    const hasHalfStar = (rating || 0) % 1 !== 0
    
    for (let i = 0; i < fullStars; i++) {
      stars.push(
        <svg key={i} width="14" height="14" viewBox="0 0 14 14" fill="#FFA500">
          <path d="M7 0l1.89 4.77L14 5.68l-3.5 3.83L11.35 14 7 11.61 2.65 14 3.5 9.51 0 5.68l5.11-.91z"/>
        </svg>
      )
    }
    
    if (hasHalfStar) {
      stars.push(
        <svg key="half" width="14" height="14" viewBox="0 0 14 14" fill="#FFA500">
          <path d="M7 0l1.89 4.77L14 5.68l-3.5 3.83L11.35 14 7 11.61V0z"/>
        </svg>
      )
    }
    
    return stars
  }

  return (
    <>
      <div
        className={`pharmacy-card${compact ? ' compact' : ''}${pharmacy.logoUrl ? ' has-logo-bg' : ''}`}
        onClick={handleShowMedicines}
        onKeyDown={handleCardKeyDown}
        role="button"
        tabIndex={0}
        aria-label={`${pharmacy.name || 'Dorixona'} dorilar ro'yxatini ochish`}
        style={pharmacy.logoUrl ? { '--pharmacy-bg-image': `url(${pharmacy.logoUrl})` } : undefined}
      >
        <div className="pharmacy-card-header">
          <div className="pharmacy-icon-wrapper">
            {pharmacy.logoUrl ? (
              <img src={pharmacy.logoUrl} alt={pharmacy.name} className="pharmacy-logo-image" />
            ) : (
              <span className="pharmacy-initials">{getInitials(pharmacy.name)}</span>
            )}
          </div>
          <div className="pharmacy-header-info">
            <h3>{pharmacy.name}</h3>
            <div className="pharmacy-specialty-row">
              <span className="pharmacy-specialty-icon" aria-hidden="true">💊</span>
              <p className="pharmacy-specialty">Dorixona</p>
            </div>
          </div>
          <div className={`pharmacy-open-status${openStatus.isOpen === true ? ' open' : openStatus.isOpen === false ? ' closed' : ''}`}>
            {openStatus.label}
          </div>
        </div>

        <div className="pharmacy-rating-panel">
          <span className="pharmacy-rating-number">{Number(pharmacy.rating || 0).toFixed(1)}</span>
          <div className="pharmacy-rating-stars">{renderStars(pharmacy.rating || 0)}</div>
          <span className="pharmacy-rating-location">
            {pharmacy.totalRatings > 0 ? `(${pharmacy.totalRatings} baho)` : 'Baho yo\'q'}
          </span>
        </div>

        <div className="pharmacy-card-content">
          <div className="pharmacy-info-item">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M8 14s6-4 6-8c0-3.314-2.686-6-6-6S2 2.686 2 6c0 4 6 8 6 8z" stroke="currentColor" strokeWidth="1.5"/>
              <circle cx="8" cy="6" r="2" stroke="currentColor" strokeWidth="1.5"/>
            </svg>
            <div className="pharmacy-info-content">
              <span className="pharmacy-info-label">Manzil</span>
              <span className="pharmacy-info-value">{pharmacy.address || pharmacy.city || '-'}</span>
            </div>
          </div>

          <div className="pharmacy-info-item">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M8 4v4l3 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            <div className="pharmacy-info-content">
              <span className="pharmacy-info-label">Ish vaqti</span>
              <span className="pharmacy-info-value">{workingHoursDisplay}</span>
            </div>
          </div>

          <div className="pharmacy-info-item">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M14.5 11v2a1.5 1.5 0 01-1.635 1.495 12.85 12.85 0 01-5.48-1.95 11.625 11.625 0 01-3.8-3.8 12.85 12.85 0 01-1.95-5.51A1.5 1.5 0 013.13 1.5h2a1.5 1.5 0 011.5 1.29c.095.72.27 1.425.525 2.1a1.5 1.5 0 01-.337 1.583l-.8.8a12 12 0 003.8 3.8l.8-.8a1.5 1.5 0 011.583-.338c.675.255 1.38.43 2.1.525a1.5 1.5 0 011.29 1.52z" stroke="currentColor" strokeWidth="1.5"/>
            </svg>
            <div className="pharmacy-info-content">
              <span className="pharmacy-info-label">Telefon</span>
              <span className="pharmacy-info-value">{phoneDisplay}</span>
            </div>
          </div>

          <div className="pharmacy-medicines-badge">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <rect x="4" y="4" width="10" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M7 4V2M11 4V2M4 7h10" stroke="currentColor" strokeWidth="1.5"/>
            </svg>
            <span className="medicines-count">{pharmacy.medicines?.length || 0} ta dori mavjud</span>
          </div>
        </div>

        <div className="pharmacy-card-actions" onClick={(e) => e.stopPropagation()}>
          <button className="pharmacy-btn-call" onClick={handleCall}>
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path d="M16.5 12.5v2.25a1.5 1.5 0 01-1.635 1.495 14.85 14.85 0 01-6.48-2.31 14.625 14.625 0 01-4.5-4.5 14.85 14.85 0 01-2.31-6.51A1.5 1.5 0 012.25 1.5h2.25a1.5 1.5 0 011.5 1.29c.095.72.27 1.425.525 2.1a1.5 1.5 0 01-.337 1.583l-.953.952a12 12 0 004.5 4.5l.952-.952a1.5 1.5 0 011.583-.338c.675.255 1.38.43 2.1.525a1.5 1.5 0 011.29 1.52z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <span>Qo'ng'iroq</span>
          </button>
        </div>

        <div className="pharmacy-hint">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M7 7h3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <span>Dorilar ro'yxatini ko'rish uchun bosing</span>
        </div>
      </div>

      {/* Medicines Modal */}
      {showMedicines && (
        <div className="medicines-modal-overlay" onClick={handleCloseMedicines}>
          <div className="medicines-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{pharmacy.name} - Dorilar ro'yxati</h3>
              <button className="btn-close" onClick={handleCloseMedicines}>✕</button>
            </div>
            
            {/* Search Input */}
            <div className="modal-search">
              <input
                type="text"
                placeholder="🔍 Dori nomini qidiring..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            <div className="modal-body">
              {pharmacy.medicines && pharmacy.medicines.length > 0 ? (
                (() => {
                  const filteredMedicines = pharmacy.medicines.filter(medicine => {
                    const name = (medicine.name || medicine.medicine_name || '').toLowerCase()
                    const category = (medicine.category || '').toLowerCase()
                    const query = searchQuery.toLowerCase()
                    return name.includes(query) || category.includes(query)
                  })

                  if (filteredMedicines.length === 0) {
                    return (
                      <div className="empty-medicines">
                        <div className="empty-icon">🔍</div>
                        <p>"{searchQuery}" - qidiruviga natija topilmadi</p>
                      </div>
                    )
                  }

                  return (
                    <div className="medicines-list">
                      {filteredMedicines.map((medicine, index) => (
                        <div key={index} className="medicine-item">
                          <div className="medicine-icon">💊</div>
                          <div className="medicine-details">
                            <h4>{medicine.name || medicine.medicine_name || 'Noma\'lum dori'}</h4>
                            <div className="medicine-info">
                              <span className="medicine-category">{medicine.category || 'Boshqa'}</span>
                              {medicine.stock !== undefined && (
                                <span className="medicine-stock">
                                  Omborda: {medicine.stock} dona
                                </span>
                              )}
                            </div>
                          </div>
                          {medicine.price && (
                            <div className="medicine-price">
                              {Number(medicine.price).toLocaleString('uz-UZ')} so'm
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )
                })()
              ) : (
                <div className="empty-medicines">
                  <div className="empty-icon">💊</div>
                  <p>Hozircha dorilar mavjud emas</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  )
}

export default PharmacyCard
