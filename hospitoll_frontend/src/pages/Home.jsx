import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ClinicCard from '../components/ClinicCard'
import PharmacyCard from '../components/PharmacyCard'
import { usePharmacy } from '../context/PharmacyContext'
import { clinicsApi, clinicDepartmentsApi, siteSettingsApi, resolveMediaUrl } from '../services/api'
import './Home.css'

const sortClinicsByRating = (items = []) => {
  return [...items].sort((firstClinic, secondClinic) => {
    const firstRating = Number(firstClinic?.rating || 0)
    const secondRating = Number(secondClinic?.rating || 0)
    if (secondRating !== firstRating) {
      return secondRating - firstRating
    }

    const firstTotalRatings = Number(firstClinic?.totalRatings || 0)
    const secondTotalRatings = Number(secondClinic?.totalRatings || 0)
    if (secondTotalRatings !== firstTotalRatings) {
      return secondTotalRatings - firstTotalRatings
    }

    return String(firstClinic?.name || '').localeCompare(String(secondClinic?.name || ''), 'uz')
  })
}

const Home = () => {
  const navigate = useNavigate()
  const [clinics, setClinics] = useState([])
  const { pharmacies } = usePharmacy()
  const [clinicSearchQuery, setClinicSearchQuery] = useState('')
  const [pharmacySearchQuery, setPharmacySearchQuery] = useState('')
  const [homeContact, setHomeContact] = useState(null)

  useEffect(() => {
    const loadClinics = async () => {
      try {
        const data = await clinicsApi.getAll({
          ordering: '-rating,-total_ratings',
          _ts: Date.now(),
        })
        const results = data?.results || data || []
        
        // Load departments for each clinic
        const clinicsWithDepartments = await Promise.all(
          results.map(async (clinic) => {
            let departments = []
            try {
              const deptData = await clinicDepartmentsApi.getAll({ clinic: clinic.id })
              departments = deptData?.results || deptData || []
            } catch (error) {
              // If departments fail to load, just skip
              console.warn(`Could not load departments for clinic ${clinic.id}`)
            }
            
            return {
              id: clinic.id,
              name: clinic.name,
              specialty: 'Umumiy',
              logoUrl: resolveMediaUrl(clinic.logo || clinic.banner_image),
              rating: Number(clinic.rating || 0),
              reviews: clinic.address || '',
              location: clinic.address || '',
              phone: clinic.phone_number || '',
              email: clinic.email || '',
              workingHours: clinic.working_hours || clinic.workingHours || '09:00 - 18:00',
              departments: departments,
              totalRatings: Number(clinic.total_ratings || 0)
            }
          })
        )

        setClinics(sortClinicsByRating(clinicsWithDepartments))
      } catch (error) {
        setClinics([])
      }
    }
    loadClinics()
  }, [])

  useEffect(() => {
    const loadHomeContact = async () => {
      try {
        const data = await siteSettingsApi.getHomeContact()
        setHomeContact(data)
      } catch (error) {
        setHomeContact(null)
      }
    }
    loadHomeContact()
  }, [])

  const handlePatientClick = () => {
    navigate('/patient-login')
  }

  // Filter clinics based on search query and sort by rating (descending)
  const filteredClinics = sortClinicsByRating(
    clinics.filter((clinic) => {
      const query = clinicSearchQuery.toLowerCase()
      return (
        clinic.name.toLowerCase().includes(query) ||
        clinic.location.toLowerCase().includes(query)
      )
    })
  )

  // Filter pharmacies based on search query
  const filteredPharmacies = pharmacies.filter(pharmacy => {
    const query = pharmacySearchQuery.toLowerCase()
    const address = pharmacy.address?.toLowerCase() || ''
    const city = pharmacy.city?.toLowerCase() || ''
    const name = pharmacy.name?.toLowerCase() || ''
    return (
      name.includes(query) ||
      address.includes(query) ||
      city.includes(query)
    )
  })

  return (
    <div className="home">
      {/* Hero Section */}
      <section className="hero-section">
        <div className="hero-overlay"></div>
        <div className="hero-content">
          <div className="hero-container">
            <div className="hero-text">
              <h1 className="hero-title">
                G-MED bilan sog'ligingiz ishonchli<br />
                <span className="hero-title-highlight">Yangi Texnologiyalar</span>
              </h1>
              <p className="hero-subtitle">
                Sizning sog'liqni saqlash hamkoringiz!
              </p>
              <div className="hero-actions">
                <button className="btn-contact" onClick={handlePatientClick}>
                  Men bemorman
                </button>
              </div>
            </div>
            <div className="hero-banner">
              <img src="/images/banners/banner.png" alt="G-MED banner" className="hero-banner-image" />
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="features-section">
        <div className="container">
          <div className="features-grid">
            <div className="feature-card">
              <div className="feature-icon feature-icon-blue">
                <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                  <path d="M5 13.333h30M13.333 5v30" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/>
                </svg>
              </div>
              <div className="feature-content">
                <h3>Keng Tanlov</h3>
                <p>Zamonaviy tibbiyot jihozlari va uskunalar</p>
              </div>
            </div>

            <div className="feature-card">
              <div className="feature-icon feature-icon-green">
                <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                  <path d="M28 12L16 24l-8-8" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <div className="feature-content">
                <h3>Yugori Sifat</h3>
                <p>Eng yugori darajadagi sifatli talablar</p>
              </div>
            </div>

            <div className="feature-card">
              <div className="feature-icon feature-icon-blue">
                <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                  <path d="M8 30h24M20 5v25M20 30v5" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/>
                </svg>
              </div>
              <div className="feature-content">
                <h3>Professional Qo'llab-Quvvatlash</h3>
                <p>Mutaxassislarimizdan 10% yordam</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Clinics Section */}
      <section className="clinics-section">
        <div className="container">
          <div className="section-header">
            <h2>🏥 Klinikalar</h2>
            <div className="section-actions">
              <input
                type="text"
                placeholder="Shahar yoki klinika nomini qidiring..."
                value={clinicSearchQuery}
                onChange={(e) => setClinicSearchQuery(e.target.value)}
                className="search-input-small"
              />
            </div>
          </div>
          <div className="clinics-grid">
            {filteredClinics.length > 0 ? (
              filteredClinics.map(clinic => (
                <ClinicCard key={clinic.id} clinic={clinic} compact />
              ))
            ) : clinicSearchQuery ? (
              <div className="no-results">
                <div className="no-results-icon">
                  <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
                    <circle cx="28" cy="28" r="18" stroke="currentColor" strokeWidth="3"/>
                    <path d="M42 42L56 56" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/>
                  </svg>
                </div>
                <h3 className="no-results-title">Natija topilmadi</h3>
                <p className="no-results-text">
                  <strong>"{clinicSearchQuery}"</strong> bo'yicha klinika topilmadi
                </p>
                <p className="no-results-hint">Boshqa kalit so'zlar bilan qidirib ko'ring</p>
              </div>
            ) : (
              clinics.map(clinic => (
                <ClinicCard key={clinic.id} clinic={clinic} compact />
              ))
            )}
          </div>
        </div>
      </section>

      {/* Pharmacy Section */}
      <section className="pharmacy-section">
        <div className="container">
          <div className="section-header">
            <h2>💊 Dorixonalar</h2>
            <div className="section-actions">
              <input
                type="text"
                placeholder="Dorixona nomi yoki shaharni qidiring..."
                value={pharmacySearchQuery}
                onChange={(e) => setPharmacySearchQuery(e.target.value)}
                className="search-input-small"
              />
            </div>
          </div>
          <div className="pharmacy-grid">
            {filteredPharmacies.length > 0 ? (
              filteredPharmacies.map(pharmacy => (
                <PharmacyCard
                  key={pharmacy.id}
                  compact
                  pharmacy={{
                    ...pharmacy,
                    phone: pharmacy.phone || pharmacy.phone_number || '',
                    workingHours: pharmacy.workingHours || '09:00 - 20:00',
                    rating: pharmacy.rating || 4.5,
                    medicines: pharmacy.medicines || []
                  }}
                />
              ))
            ) : pharmacySearchQuery ? (
              <div className="no-results">
                <div className="no-results-icon">
                  <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
                    <circle cx="28" cy="28" r="18" stroke="currentColor" strokeWidth="3"/>
                    <path d="M42 42L56 56" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/>
                  </svg>
                </div>
                <h3 className="no-results-title">Natija topilmadi</h3>
                <p className="no-results-text">
                  <strong>"{pharmacySearchQuery}"</strong> bo'yicha dorixona topilmadi
                </p>
                <p className="no-results-hint">Boshqa kalit so'zlar bilan qidirib ko'ring</p>
              </div>
            ) : (
              pharmacies.map(pharmacy => (
                <PharmacyCard
                  key={pharmacy.id}
                  compact
                  pharmacy={{
                    ...pharmacy,
                    phone: pharmacy.phone || pharmacy.phone_number || '',
                    workingHours: pharmacy.workingHours || '09:00 - 20:00',
                    rating: pharmacy.rating || 4.5,
                    medicines: pharmacy.medicines || []
                  }}
                />
              ))
            )}
          </div>
        </div>
      </section>

      {/* Contact Section */}
      <section className="home-contact-section">
        <div className="container">
          <div className="home-contact-grid">
            <div className="home-contact-info">
              <h2 className="home-contact-title">Bog'lanish</h2>
              {homeContact?.text ? (
                <p className="home-contact-text">{homeContact.text}</p>
              ) : null}

              <div className="home-contact-items">
                {homeContact?.telegram_link ? (
                  <a className="home-contact-item" href={homeContact.telegram_link} target="_blank" rel="noreferrer">
                    <span className="home-contact-label">Telegram</span>
                    <span className="home-contact-value">{homeContact.telegram_link}</span>
                  </a>
                ) : null}

                {homeContact?.phone_number ? (
                  <a className="home-contact-item" href={`tel:${homeContact.phone_number}`}>
                    <span className="home-contact-label">Telefon</span>
                    <span className="home-contact-value">{homeContact.phone_number}</span>
                  </a>
                ) : null}

                {homeContact?.instagram_link ? (
                  <a className="home-contact-item" href={homeContact.instagram_link} target="_blank" rel="noreferrer">
                    <span className="home-contact-label">Instagram</span>
                    <span className="home-contact-value">{homeContact.instagram_link}</span>
                  </a>
                ) : null}

                {homeContact?.email ? (
                  <a className="home-contact-item" href={`mailto:${homeContact.email}`}>
                    <span className="home-contact-label">Email</span>
                    <span className="home-contact-value">{homeContact.email_display || homeContact.email}</span>
                  </a>
                ) : homeContact?.email_display ? (
                  <a className="home-contact-item" href={`mailto:${homeContact.email_display}`}>
                    <span className="home-contact-label">Email</span>
                    <span className="home-contact-value">{homeContact.email_display}</span>
                  </a>
                ) : null}
              </div>
            </div>

            <div className="home-contact-image">
              {resolveMediaUrl(homeContact?.image) ? (
                <img src={resolveMediaUrl(homeContact?.image)} alt="Bog'lanish" className="home-contact-image-el" />
              ) : (
                <div className="home-contact-image-placeholder">Bog'lanish rasmi</div>
              )}
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}

export default Home
