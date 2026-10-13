import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import './ClinicCard.css'

const ClinicCard = ({ clinic, compact = false }) => {
  const navigate = useNavigate()
  const [selectedDepartmentId, setSelectedDepartmentId] = useState(null)

  const visibleDepartments = useMemo(() => {
    const items = Array.isArray(clinic.departments) ? clinic.departments : []
    return items.filter((department) => department && department.is_active !== false)
  }, [clinic.departments])

  const selectedDepartment = useMemo(() => {
    if (!selectedDepartmentId) return null
    return visibleDepartments.find((department) => String(department.id) === String(selectedDepartmentId)) || null
  }, [selectedDepartmentId, visibleDepartments])

  const formatWorkingHours = (value) => {
    const source = String(value || '').trim()
    const match = source.match(/(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})/)
    if (!match) return source || '09:00 - 18:00'

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
    if (!match) {
      return { isOpen: null, label: 'Ish vaqti ko‘rsatilmagan' }
    }

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

    return {
      isOpen,
      label: isOpen ? 'Hozir ochiq' : 'Hozir yopiq'
    }
  }

  const formatPhoneDisplay = (value) => {
    const raw = String(value || '').replace(/\s+/g, '')
    const match = raw.match(/^(\+998)(\d{2})(\d{3})(\d{2})(\d{2})$/)
    if (!match) return value || '-'
    return `${match[1]} ${match[2]} ${match[3]} ${match[4]} ${match[5]}`
  }

  const workingHoursDisplay = formatWorkingHours(clinic.workingHours)
  const openStatus = getOpenStatus(workingHoursDisplay)
  const phoneDisplay = formatPhoneDisplay(clinic.phone)

  const getInitials = (name) => {
    const words = String(name || '').trim().split(/\s+/).filter(Boolean)
    if (words.length === 0) return 'CL'
    return words.slice(0, 2).map((word) => word[0]?.toUpperCase() || '').join('')
  }

  const handleViewClinic = () => {
    navigate(`/clinic/${clinic.id}`)
  }

  const handleCall = () => {
    if (clinic.phone) {
      const phoneDisplay = clinic.phone.replace(/(\+998)(\d{2})(\d{3})(\d{2})(\d{2})/, '$1 $2 $3 $4 $5')
      alert(`📞 Klinika raqami:\n\n${phoneDisplay}\n\n(Qo'ng'iroq qilish uchun OK bosing)`)
      window.location.href = `tel:${clinic.phone}`
    } else {
      alert('Telefon raqam mavjud emas')
    }
  }

  // Generate stars based on rating
  const renderStars = (rating) => {
    const stars = []
    const fullStars = Math.floor(rating)
    const hasHalfStar = rating % 1 !== 0
    
    for (let i = 0; i < fullStars; i++) {
      stars.push(
        <svg key={i} width="16" height="16" viewBox="0 0 16 16" fill="#FFA500">
          <path d="M8 0l2.163 5.455L16 6.5l-4 4.386L13.09 16 8 13.273 2.91 16 4 10.886 0 6.5l5.837-1.045z"/>
        </svg>
      )
    }
    
    if (hasHalfStar) {
      stars.push(
        <svg key="half" width="16" height="16" viewBox="0 0 16 16" fill="#FFA500">
          <path d="M8 0l2.163 5.455L16 6.5l-4 4.386L13.09 16 8 13.273V0z"/>
        </svg>
      )
    }
    
    return stars
  }

  // Get icon based on specialty
  const getSpecialtyIcon = (specialty) => {
    if (specialty.includes('Kardio')) {
      return (
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
          <rect width="40" height="40" rx="8" fill="#fee2e2"/>
          <path d="M20 12c3 0 5 2 5 4.5S20 26 20 26s-8-8-8-9.5S17 12 20 12z" fill="#ef4444" stroke="#dc2626" strokeWidth="1.5"/>
        </svg>
      )
    } else if (specialty.includes('Dent')) {
      return (
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
          <rect width="40" height="40" rx="8" fill="#dbeafe"/>
          <path d="M18 12v4h2v-4c0-1 .5-2 1.5-2s1.5 1 1.5 2v4h2v-4c0-2-1-3-3-3s-4 1-4 3z" fill="#3b82f6" stroke="#1d4ed8" strokeWidth="1"/>
          <rect x="16" y="18" width="8" height="9" rx="1" fill="#60a5fa" stroke="#3b82f6" strokeWidth="1"/>
          <circle cx="18" cy="22" r="0.5" fill="#1d4ed8"/>
          <circle cx="20" cy="22" r="0.5" fill="#1d4ed8"/>
          <circle cx="22" cy="22" r="0.5" fill="#1d4ed8"/>
        </svg>
      )
    } else if (specialty.includes('Otorin')) {
      return (
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
          <rect width="40" height="40" rx="8" fill="#fef3c7"/>
          <path d="M26 16c0-3-2-5-5-5s-5 2-5 5v6c0 1-.5 2-1 2h-2c-.5 0-1 .5-1 1v4c0 1 1 2 2 2h12c1 0 2-1 2-2v-4c0-.5-.5-1-1-1h-2c-.5 0-1-1-1-2v-6z" fill="#f59e0b" stroke="#d97706" strokeWidth="1.2"/>
        </svg>
      )
    } else if (specialty.includes('Oila')) {
      return (
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
          <rect width="40" height="40" rx="8" fill="#dcfce7"/>
          <circle cx="13" cy="12" r="2.5" fill="#10b981" stroke="#059669" strokeWidth="1"/>
          <circle cx="27" cy="12" r="2.5" fill="#10b981" stroke="#059669" strokeWidth="1"/>
          <circle cx="20" cy="8" r="2" fill="#10b981" stroke="#059669" strokeWidth="1"/>
          <path d="M12 16c-1.5 0-2.5 1-2.5 2.5v8c0 1.5 1 2 1 2h2c0-.5.5-1.5 1-1.5v-5c0-1 1-1.5 1.5-1.5h1.5V16H12z" fill="#6ee7b7" stroke="#10b981" strokeWidth="1"/>
          <path d="M28 16c1.5 0 2.5 1 2.5 2.5v8c0 1.5-1 2-1 2h-2c0-.5-.5-1.5-1-1.5v-5c0-1-1-1.5-1.5-1.5h-1.5V16h4z" fill="#6ee7b7" stroke="#10b981" strokeWidth="1"/>
          <path d="M18 15c-1.5 0-2.5 1-2.5 2.5v8c0 1.5 1 2 1 2h9c0 0 1 0 1-2v-8c0-1.5-1-2.5-2.5-2.5h-6z" fill="#6ee7b7" stroke="#10b981" strokeWidth="1"/>
        </svg>
      )
    } else if (specialty.includes('Pediatriya')) {
      return (
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
          <rect width="40" height="40" rx="8" fill="#fce7f3"/>
          <circle cx="20" cy="11" r="2.5" fill="#ec4899" stroke="#be185d" strokeWidth="1"/>
          <path d="M16 16c-1.5 0-2.5 1-2.5 2.5v9c0 1.5 1 2 1 2h11c0 0 1 0 1-2v-9c0-1.5-1-2.5-2.5-2.5h-8z" fill="#f472b6" stroke="#ec4899" strokeWidth="1.2"/>
        </svg>
      )
    } else if (specialty.includes('Gineko')) {
      return (
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
          <rect width="40" height="40" rx="8" fill="#f3e8ff"/>
          <circle cx="20" cy="20" r="8" fill="none" stroke="#8b5cf6" strokeWidth="2.5"/>
          <path d="M20 16v8M16 20h8" stroke="#8b5cf6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      )
    } else {
      return (
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
          <rect width="40" height="40" rx="8" fill="#cffafe"/>
          <circle cx="20" cy="12" r="2.5" fill="#06b6d4" stroke="#0891b2" strokeWidth="1"/>
          <path d="M14 17c-1.5 0-2.5 1.5-2.5 3v8c0 1.5 1 2 1 2h15c0 0 1 0 1-2v-8c0-1.5-1-3-2.5-3h-12z" fill="#22d3ee" stroke="#06b6d4" strokeWidth="1.2"/>
        </svg>
      )
    }
  }

  return (
    <div
      className={`clinic-card${compact ? ' compact' : ''}${clinic.logoUrl ? ' has-clinic-logo-bg' : ''}`}
      style={clinic.logoUrl ? { '--clinic-bg-image': `url(${clinic.logoUrl})` } : undefined}
    >
      <div className="clinic-card-header">
        <div className="clinic-icon">
          {clinic.logoUrl ? (
            <img src={clinic.logoUrl} alt={clinic.name} className="clinic-logo-image" />
          ) : (
            <span className="clinic-initials">{getInitials(clinic.name)}</span>
          )}
        </div>
        <div className="clinic-header-info">
          <h3>{clinic.name}</h3>
          <div className="clinic-specialty-row">
            <span className="clinic-specialty-icon" aria-hidden="true">{getSpecialtyIcon(clinic.specialty || 'Umumiy')}</span>
            <p className="clinic-specialty">{clinic.specialty}</p>
          </div>
        </div>
        <div className={`clinic-open-status${openStatus.isOpen === true ? ' open' : openStatus.isOpen === false ? ' closed' : ''}`}>
          {openStatus.label}
        </div>
      </div>

      <div className="clinic-rating">
        <span className="rating-number">{Number(clinic.rating || 0).toFixed(1)}</span>
        <div className="rating-stars">{renderStars(clinic.rating)}</div>
        <span className="rating-location">
          {clinic.totalRatings > 0 ? `(${clinic.totalRatings} baho)` : 'Baho yo\'q'}
        </span>
      </div>

      {visibleDepartments.length > 0 && (
        <div className="clinic-departments">
          <div className="section-title">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M7 1L1 3.5v2.8c0 3.5 2.1 5.6 5.6 7 3.5-1.4 5.6-3.5 5.6-7V3.5L7 1z" stroke="currentColor" strokeWidth="1.2" fill="none"/>
            </svg>
            <span>Yo'nalishlar:</span>
          </div>
          <div className="badges-container">
            {visibleDepartments.slice(0, 3).map((dept) => (
              <button
                key={dept.id}
                type="button"
                className={`department-badge${String(selectedDepartmentId) === String(dept.id) ? ' is-active' : ''}`}
                onClick={() => {
                  setSelectedDepartmentId((current) => (String(current) === String(dept.id) ? null : dept.id))
                }}
              >
                {dept.name}
              </button>
            ))}
            {visibleDepartments.length > 3 && (
              <span className="department-badge more">+{visibleDepartments.length - 3}</span>
            )}
          </div>
          {selectedDepartment && (
            <div className="clinic-department-preview">
              <div className="clinic-department-preview-title">{selectedDepartment.name}</div>
              <p className="clinic-department-preview-description">
                {(selectedDepartment.description || '').trim() || 'Bu yo\'nalish uchun tavsif kiritilmagan'}
              </p>
            </div>
          )}
        </div>
      )}

      <div className="clinic-info">
        <div className="info-item">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 14s6-4 6-8c0-3.314-2.686-6-6-6S2 2.686 2 6c0 4 6 8 6 8z" stroke="currentColor" strokeWidth="1.5"/>
            <circle cx="8" cy="6" r="2" stroke="currentColor" strokeWidth="1.5"/>
          </svg>
          <div className="info-content">
            <span className="info-label">Manzil</span>
            <span className="info-value">{clinic.location || '-'}</span>
          </div>
        </div>
        <div className="info-item">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M8 4v4l3 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <div className="info-content">
            <span className="info-label">Ish vaqti</span>
            <span className="info-value">{workingHoursDisplay}</span>
          </div>
        </div>
        <div className="info-item">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M14.5 11v2a1.5 1.5 0 01-1.635 1.495 12.85 12.85 0 01-5.48-1.95 11.625 11.625 0 01-3.8-3.8 12.85 12.85 0 01-1.95-5.51A1.5 1.5 0 013.13 1.5h2a1.5 1.5 0 011.5 1.29c.095.72.27 1.425.525 2.1a1.5 1.5 0 01-.337 1.583l-.8.8a12 12 0 003.8 3.8l.8-.8a1.5 1.5 0 011.583-.338c.675.255 1.38.43 2.1.525a1.5 1.5 0 011.29 1.52z" stroke="currentColor" strokeWidth="1.5"/>
          </svg>
          <div className="info-content">
            <span className="info-label">Telefon</span>
            <span className="info-value">{phoneDisplay}</span>
          </div>
        </div>
      </div>

      <div className="clinic-actions">
        <button className="clinic-btn-view" onClick={handleViewClinic} title="Klinika batafsil ko'rish">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M10 3.5C6 3.5 2.73 5.61 1 8.75c1.73 3.14 5 5.25 9 5.25s7.27-2.11 9-5.25c-1.73-3.14-5-5.25-9-5.25z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            <circle cx="10" cy="8.75" r="2.5" stroke="currentColor" strokeWidth="1.5"/>
          </svg>
          <span>Batafsil</span>
        </button>
        <button className="clinic-btn-call" onClick={handleCall} title="Klinikaga qo'ng'iroq qilish">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M18.5 13.5v2.5a1.67 1.67 0 01-1.82 1.66 16.5 16.5 0 01-7.2-2.57 16.25 16.25 0 01-5-5 16.5 16.5 0 01-2.57-7.24A1.67 1.67 0 014.58 1h2.5a1.67 1.67 0 011.67 1.43c.1.8.3 1.58.58 2.33.22.6.1 1.3-.37 1.76l-1.06 1.06a13.33 13.33 0 005 5l1.06-1.06c.46-.47 1.17-.59 1.76-.37.75.28 1.53.48 2.33.58a1.67 1.67 0 011.43 1.69z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <span>Qo'ng'iroq</span>
        </button>
      </div>
    </div>
  )
}

export default ClinicCard
