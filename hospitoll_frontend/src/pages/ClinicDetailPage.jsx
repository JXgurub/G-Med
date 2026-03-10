import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { clinicsApi, doctorsApi, medicalApi, resolveMediaUrl } from '../services/api'
import './ClinicDetailPage.css'

const ClinicDetailPage = () => {
  const { clinicId } = useParams()
  const navigate = useNavigate()
  const [clinic, setClinic] = useState(null)
  const [doctors, setDoctors] = useState([])
  const [specialtyGroups, setSpecialtyGroups] = useState({})
  const [loading, setLoading] = useState(true)
  const [activeSpecialty, setActiveSpecialty] = useState(null)
  const [bookingOpen, setBookingOpen] = useState(false)
  const [selectedDoctor, setSelectedDoctor] = useState(null)
  const [selectedSpecialtyPriceId, setSelectedSpecialtyPriceId] = useState(null)
  const [selectedDate, setSelectedDate] = useState(() => new Date().toISOString().split('T')[0])
  const [availableSlots, setAvailableSlots] = useState([])
  const [selectedSlot, setSelectedSlot] = useState(null)
  const [bookingForm, setBookingForm] = useState({
    firstName: '',
    lastName: '',
    passportId: '',
    phone: '+998'
  })
  const [bookingLoading, setBookingLoading] = useState(false)
  const [bookingMessage, setBookingMessage] = useState(null)

  useEffect(() => {
    loadClinicDetails()
  }, [clinicId])

  const loadClinicDetails = async () => {
    try {
      setLoading(true)
      
      // Fetch clinic details
      const clinicData = await clinicsApi.getById(clinicId)
      setClinic(clinicData)
      
      // Fetch doctors with their specialty prices
      const doctorsData = await doctorsApi.getAll({ clinic: clinicId })
      const doctorsList = doctorsData?.results || doctorsData || []
      setDoctors(doctorsList)
      
      // Group doctors by specialties
      const groups = {}
      doctorsList.forEach(doctor => {
        if (doctor.specialty_prices && doctor.specialty_prices.length > 0) {
          doctor.specialty_prices.forEach(sp => {
            const specName = sp.specialization.name
            if (!groups[specName]) {
              groups[specName] = {
                specialization: sp.specialization,
                doctors: []
              }
            }
            groups[specName].doctors.push({
              doctor: doctor,
              price: sp.consultation_fee,
              specialtyPriceId: sp.id
            })
          })
        }
      })
      
      setSpecialtyGroups(groups)
      // Set first specialty as active
      if (Object.keys(groups).length > 0) {
        setActiveSpecialty(Object.keys(groups)[0])
      }
    } catch (error) {
      console.error('Error loading clinic details:', error)
      alert('Klinika ma\'lumotlarini yuklashda xatolik')
    } finally {
      setLoading(false)
    }
  }

  const getSpecialtyIcon = (specName) => {
    if (specName.includes('Kardio')) return '❤️'
    if (specName.includes('Nevro')) return '🧠'
    if (specName.includes('Terapevt')) return '🩺'
    if (specName.includes('Pediatr')) return '👶'
    if (specName.includes('Stomatolog') || specName.includes('Dentist')) return '🦷'
    if (specName.includes('Oftalmolog')) return '👁️'
    if (specName.includes('LOR') || specName.includes('ENT')) return '👂'
    if (specName.includes('Dermatolog')) return '🧴'
    if (specName.includes('Ortoped')) return '🦴'
    if (specName.includes('Ginekolog')) return '👩‍⚕️'
    return '⚕️'
  }

  const handleCallClinic = () => {
    if (clinic?.phone_number) {
      window.location.href = `tel:${clinic.phone_number}`
    }
  }

  const fetchAvailability = async (doctorId, date) => {
    try {
      const slots = await doctorsApi.getAvailability({ doctor: doctorId, date })
      setAvailableSlots(Array.isArray(slots) ? slots : [])
    } catch (error) {
      console.error('Error loading availability:', error)
      setAvailableSlots([])
    }
  }

  const openBooking = async (doctorData, specialtyPriceId = null) => {
    setSelectedDoctor(doctorData)
    setSelectedSpecialtyPriceId(specialtyPriceId)
    setSelectedSlot(null)
    setBookingMessage(null)
    const today = new Date().toISOString().split('T')[0]
    setSelectedDate(today)
    setBookingOpen(true)
    await fetchAvailability(doctorData.id, today)
  }

  const handleDateChange = async (event) => {
    const nextDate = event.target.value
    setSelectedDate(nextDate)
    setSelectedSlot(null)
    if (selectedDoctor?.id) {
      await fetchAvailability(selectedDoctor.id, nextDate)
    }
  }

  const submitBooking = async () => {
    if (!selectedDoctor || !selectedSlot) {
      setBookingMessage('Iltimos, bo\'sh vaqtni tanlang')
      return
    }
    if (!bookingForm.firstName || !bookingForm.lastName || !bookingForm.passportId) {
      setBookingMessage('Ism, familiya va pasport ID majburiy')
      return
    }

    setBookingLoading(true)
    setBookingMessage(null)
    try {
      const result = await medicalApi.bookOnline({
        clinic: clinicId,
        doctor: selectedDoctor.id,
        specialty_price_id: selectedSpecialtyPriceId,
        slot_id: selectedSlot.id,
        first_name: bookingForm.firstName,
        last_name: bookingForm.lastName,
        passport_id: bookingForm.passportId,
        phone_number: bookingForm.phone
      })
      if (result?.telegram_bot_link) {
        // Redirect to Telegram for confirmation
        window.location.href = result.telegram_bot_link
        return
      }
      setBookingMessage(`Muvaffaqiyatli! Sizning navbat raqamingiz: ${result.queue_number}`)
    } catch (error) {
      setBookingMessage(error.message || 'Navbat olishda xatolik')
    } finally {
      setBookingLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="clinic-loading">
        <div className="loading-spinner"></div>
        <p>Yuklanmoqda...</p>
      </div>
    )
  }

  if (!clinic) {
    return (
      <div className="clinic-error">
        <div className="error-icon">😕</div>
        <h2>Klinika topilmadi</h2>
        <button className="btn-primary" onClick={() => navigate('/')}>
          Bosh sahifaga qaytish
        </button>
      </div>
    )
  }

  const totalDoctors = doctors.length
  const totalSpecialties = Object.keys(specialtyGroups).length
  const clinicBannerUrl = resolveMediaUrl(clinic.banner_image)

  return (
    <div className="clinic-detail-page">
      {/* Hero Section */}
      <div
        className={`clinic-hero ${clinicBannerUrl ? 'has-banner' : ''}`}
        style={clinicBannerUrl ? { backgroundImage: `url(${clinicBannerUrl})` } : undefined}
      >
          <div className="clinic-hero-bg"></div>
          <div className="clinic-hero-content">
            <button className="btn-back-hero" onClick={() => navigate('/')}>
              <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                <path d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z"/>
              </svg>
              Orqaga
            </button>
            
            <div className="clinic-main-info">
              <div className="clinic-badge">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                  <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 3c1.93 0 3.5 1.57 3.5 3.5S13.93 13 12 13s-3.5-1.57-3.5-3.5S10.07 6 12 6zm7 13H5v-.23c0-.62.28-1.2.76-1.58C7.47 15.82 9.64 15 12 15s4.53.82 6.24 2.19c.48.38.76.97.76 1.58V19z" fill="white"/>
                </svg>
                <span>Tibbiyot muassasasi</span>
              </div>
              
              <h1 className="clinic-name">{clinic.name}</h1>
              
              <div className="clinic-meta">
                {clinic.rating > 0 && (
                  <div className="meta-item rating-meta">
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="#FFD700">
                      <path d="M10 0l2.163 5.455L18 6.5l-4 4.386L15.09 17 10 14.273 4.91 17 6 10.886 2 6.5l5.837-1.045z"/>
                    </svg>
                    <span>{clinic.rating.toFixed(1)}</span>
                  </div>
                )}
                <div className="meta-item">
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M10 18s8-5.5 8-10a8 8 0 10-16 0c0 4.5 8 10 8 10z"/>
                    <circle cx="10" cy="8" r="2.5"/>
                  </svg>
                  <span>{clinic.address}</span>
                </div>
                <div className="meta-item">
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M18 13v2.5a2 2 0 01-2.18 2 19 19 0 01-8.5-3 18 18 0 01-6-6 19 19 0 01-3-8.5A2 2 0 014.5 0H7a2 2 0 012 1.72c.1.9.33 1.77.7 2.6a2 2 0 01-.45 2.11L8 7.7a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.83.37 1.7.6 2.6.7A2 2 0 0118 13z"/>
                  </svg>
                  <span>{clinic.phone_number}</span>
                </div>
              </div>

              <div className="clinic-stats">
                <div className="stat-card">
                  <div className="stat-icon stat-icon-doctors">
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                    </svg>
                  </div>
                  <div className="stat-info">
                    <div className="stat-value">{totalDoctors}</div>
                    <div className="stat-label">Shifokor</div>
                  </div>
                </div>
                
                <div className="stat-card">
                  <div className="stat-icon stat-icon-specialties">
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M19.5 3H4.5C3.67 3 3 3.67 3 4.5v15c0 .83.67 1.5 1.5 1.5h15c.83 0 1.5-.67 1.5-1.5v-15c0-.83-.67-1.5-1.5-1.5zM12 7c1.1 0 2 .9 2 2s-.9 2-2 2-2-.9-2-2 .9-2 2-2zm4 10H8v-1c0-1.33 2.67-2 4-2s4 .67 4 2v1z"/>
                    </svg>
                  </div>
                  <div className="stat-info">
                    <div className="stat-value">{totalSpecialties}</div>
                    <div className="stat-label">Yo'nalish</div>
                  </div>
                </div>

                <button className="btn-call-clinic" onClick={handleCallClinic}>
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z"/>
                  </svg>
                  Qo'ng'iroq qilish
                </button>
              </div>
            </div>
        </div>

      </div>


      {bookingOpen && (
        <div className="booking-modal">
          <div className="booking-modal-backdrop" onClick={() => setBookingOpen(false)}></div>
          <div className="booking-modal-card">
            <div className="booking-modal-header">
              <div>
                <h3>Qabulga yozilish</h3>
                <p>
                  {selectedDoctor?.user
                    ? `${selectedDoctor.user.first_name || ''} ${selectedDoctor.user.last_name || ''}`.trim()
                    : 'Doktor'}
                </p>
              </div>
              <button className="booking-close" onClick={() => setBookingOpen(false)}>×</button>
            </div>

            <div className="booking-modal-body">
              <div className="booking-section">
                <label>Sana</label>
                <input type="date" value={selectedDate} onChange={handleDateChange} />
              </div>

              <div className="booking-section">
                <label>Bo'sh vaqtlar</label>
                <div className="booking-slots">
                  {availableSlots.length === 0 && (
                    <div className="booking-empty">Bo'sh vaqtlar topilmadi</div>
                  )}
                  {availableSlots.map((slot) => (
                    <button
                      key={slot.id}
                      className={`booking-slot ${selectedSlot?.id === slot.id ? 'active' : ''}`}
                      onClick={() => setSelectedSlot(slot)}
                    >
                      {slot.start_time.slice(0, 5)} - {slot.end_time.slice(0, 5)}
                    </button>
                  ))}
                </div>
              </div>

              <div className="booking-fields-grid">
                <div className="booking-section">
                  <label>Ism</label>
                  <input
                    type="text"
                    value={bookingForm.firstName}
                    onChange={(e) => setBookingForm({ ...bookingForm, firstName: e.target.value })}
                    placeholder="Ism"
                  />
                </div>

                <div className="booking-section">
                  <label>Familiya</label>
                  <input
                    type="text"
                    value={bookingForm.lastName}
                    onChange={(e) => setBookingForm({ ...bookingForm, lastName: e.target.value })}
                    placeholder="Familiya"
                  />
                </div>

                <div className="booking-section">
                  <label>Pasport ID</label>
                  <input
                    type="text"
                    value={bookingForm.passportId}
                    onChange={(e) => setBookingForm({ ...bookingForm, passportId: e.target.value.replace(/\s+/g, '').toUpperCase() })}
                    placeholder="AA1234567"
                  />
                </div>

                <div className="booking-section">
                  <label>Telefon (ixtiyoriy)</label>
                  <input
                    type="tel"
                    value={bookingForm.phone}
                    onChange={(e) => setBookingForm({ ...bookingForm, phone: e.target.value })}
                    placeholder="+998 90 123 45 67"
                  />
                </div>
              </div>

              {bookingMessage && <div className="booking-message">{bookingMessage}</div>}
            </div>

            <div className="booking-modal-footer">
              <button className="booking-submit" onClick={submitBooking} disabled={bookingLoading}>
                {bookingLoading ? 'Yuborilmoqda...' : 'Navbatni olish'}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Specialties Section */}
      <div className="clinic-content">
          <div className="section-header">
            <h2>Klinikadagi shifokorlar va yo'nalishlar</h2>
            <p>Quyida klinikamizda mavjud bo'lgan barcha yo'nalishlar va shifokorlar haqida ma'lumot</p>
          </div>

          {Object.keys(specialtyGroups).length > 0 ? (
            <div className="specialties-grid">
              {/* Specialty Tabs */}
              <div className="specialty-tabs">
                {Object.keys(specialtyGroups).map((specName) => (
                  <button
                    key={specName}
                    className={`specialty-tab ${activeSpecialty === specName ? 'active' : ''}`}
                    onClick={() => setActiveSpecialty(specName)}
                  >
                    <span className="tab-icon">{getSpecialtyIcon(specName)}</span>
                    <span className="tab-text">
                      <span className="tab-name">{specName}</span>
                      <span className="tab-count">{specialtyGroups[specName].doctors.length} shifokor</span>
                    </span>
                  </button>
                ))}
              </div>

              {/* Active Specialty Content */}
              <div className="specialty-content">
                {activeSpecialty && specialtyGroups[activeSpecialty] && (
                  <div className="specialty-details">
                    <div className="specialty-title">
                      <span className="specialty-emoji">{getSpecialtyIcon(activeSpecialty)}</span>
                      <div>
                        <h3>{activeSpecialty}</h3>
                        {specialtyGroups[activeSpecialty].specialization.description && (
                          <p className="specialty-description">
                            {specialtyGroups[activeSpecialty].specialization.description}
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="doctors-grid">
                      {specialtyGroups[activeSpecialty].doctors.map((docData, idx) => {
                        const doctor = docData.doctor
                        const fullName = doctor.user 
                          ? `${doctor.user.first_name || ''} ${doctor.user.last_name || ''}`.trim()
                          : 'Doktor'
                        
                        return (
                          <div key={`${doctor.id}-${idx}`} className="doctor-card-modern">
                            <div className="doctor-card-header">
                              <div className="doctor-avatar-large">
                                {resolveMediaUrl(doctor.profile_image) ? (
                                  <img src={resolveMediaUrl(doctor.profile_image)} alt={fullName} className="doctor-avatar-large-image" />
                                ) : (
                                  <span>{fullName.split(' ').map(n => n[0]).join('')}</span>
                                )}
                              </div>
                              <div className="doctor-badge">Shifokor</div>
                            </div>
                            
                            <div className="doctor-card-body">
                              <h4 className="doctor-name">{fullName}</h4>
                              
                              <div className="doctor-info-grid">
                                <div className="info-chip">
                                  <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                                    <path d="M8 1a3 3 0 00-3 3v1H4a2 2 0 00-2 2v6a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-1V4a3 3 0 00-3-3zm1 4V4a1 1 0 10-2 0v1h2z"/>
                                  </svg>
                                  <span>{doctor.years_of_experience} yil tajriba</span>
                                </div>
                                
                                {doctor.rating > 0 && (
                                  <div className="info-chip rating-chip">
                                    <svg width="16" height="16" viewBox="0 0 16 16" fill="#FFD700">
                                      <path d="M8 0l1.732 4.364L14 5.09l-3 3.287L11.927 13 8 10.727 4.073 13 5 8.377l-3-3.287 4.268-.726z"/>
                                    </svg>
                                    <span>{doctor.rating.toFixed(1)}/5</span>
                                  </div>
                                )}
                              </div>

                              <div className="doctor-price-modern">
                                <span className="price-label-modern">Konsultatsiya narxi</span>
                                <span className="price-amount-modern">{parseFloat(docData.price).toLocaleString()} so'm</span>
                              </div>

                              <button
                                className="btn-appointment"
                                onClick={() => openBooking(doctor, docData.specialtyPriceId)}
                              >
                                <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2">
                                  <rect x="3" y="4" width="12" height="12" rx="2" ry="2"/>
                                  <line x1="9" y1="1" x2="9" y2="4"/>
                                  <line x1="15" y1="1" x2="15" y2="4"/>
                                  <line x1="3" y1="8" x2="15" y2="8"/>
                                </svg>
                                Qabulga yozilish
                              </button>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="no-services-modern">
              <div className="no-services-icon">🏥</div>
              <h3>Hozircha yo'nalishlar topilmadi</h3>
              <p>Klinikada shifokorlar yoki yo'nalishlar mavjud emas</p>
            </div>
          )}
        </div>
      </div>
  )
}

export default ClinicDetailPage
