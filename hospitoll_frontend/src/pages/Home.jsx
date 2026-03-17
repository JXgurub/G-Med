import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ClinicCard from '../components/ClinicCard'
import PharmacyCard from '../components/PharmacyCard'
import { usePharmacy } from '../context/PharmacyContext'
import { clinicsApi, clinicDepartmentsApi, siteSettingsApi, resolveMediaUrl } from '../services/api'
import { getPreferredLoginPath, hasPreferredLoginPortal } from '../utils/loginPortalPreference'
import './Home.css'

const PHARMACY_PRESCRIPTION_KEY = 'gmed-pharmacy-prescription-search'

const normalizeSearchText = (value) => String(value || '').toLowerCase().replace(/\s+/g, ' ').trim()

const splitSearchTerms = (value) => {
  if (Array.isArray(value)) {
    return Array.from(new Set(value.map((item) => String(item || '').trim()).filter(Boolean)))
  }

  return Array.from(
    new Set(
      String(value || '')
        .split(/[\n,;]+/)
        .map((item) => item.trim())
        .filter(Boolean)
    )
  )
}

const getMedicineName = (medicine) => String(medicine?.name || medicine?.medicine_name || '').trim()

const analyzePharmacyPrescription = (pharmacy, requestedMedicines = []) => {
  const medicines = Array.isArray(pharmacy?.medicines) ? pharmacy.medicines : []
  const requested = splitSearchTerms(requestedMedicines)

  const found = []
  const missing = []
  let total = 0

  requested.forEach((requestedMedicine) => {
    const normalizedRequested = normalizeSearchText(requestedMedicine)
    const matchedMedicine = medicines.find((medicine) => {
      const normalizedName = normalizeSearchText(getMedicineName(medicine))
      if (!normalizedName || !normalizedRequested) return false
      return normalizedName.includes(normalizedRequested) || normalizedRequested.includes(normalizedName)
    })

    if (!matchedMedicine || Number(matchedMedicine.stock || 0) <= 0) {
      missing.push(requestedMedicine)
      return
    }

    const price = Number(matchedMedicine.price || 0)
    total += price
    found.push({
      requestedName: requestedMedicine,
      medicineName: getMedicineName(matchedMedicine),
      price,
      stock: Number(matchedMedicine.stock || 0),
    })
  })

  return {
    requested,
    found,
    missing,
    foundCount: found.length,
    missingCount: missing.length,
    total,
  }
}

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
  const [prescriptionSearch, setPrescriptionSearch] = useState(null)

  useEffect(() => {
    if (typeof window === 'undefined') return
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true
    if (!isStandalone || !hasPreferredLoginPortal()) return

    const targetPath = getPreferredLoginPath()
    if (targetPath && targetPath !== window.location.pathname) {
      navigate(targetPath, { replace: true })
    }
  }, [navigate])

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

  useEffect(() => {
    if (typeof window === 'undefined') return

    try {
      const raw = window.localStorage.getItem(PHARMACY_PRESCRIPTION_KEY)
      if (!raw) return
      const parsed = JSON.parse(raw)
      const medicines = splitSearchTerms(parsed?.medicines)
      if (medicines.length === 0) return

      setPrescriptionSearch({
        ...parsed,
        medicines,
      })
      setPharmacySearchQuery(medicines.join(', '))
    } catch (error) {
      console.warn('Prescription search data could not be restored')
    }
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') return
    if (window.location.hash !== '#pharmacy-section') return

    const timeoutId = window.setTimeout(() => {
      document.getElementById('pharmacy-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 120)

    return () => window.clearTimeout(timeoutId)
  }, [prescriptionSearch])

  const handlePatientClick = () => {
    navigate('/patient-login')
  }

  const clearPrescriptionSearch = () => {
    setPrescriptionSearch(null)
    setPharmacySearchQuery('')
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(PHARMACY_PRESCRIPTION_KEY)
    }
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

  const pharmacySearchTerms = splitSearchTerms(pharmacySearchQuery).map(normalizeSearchText).filter(Boolean)

  const pharmaciesWithPrescription = pharmacies.map((pharmacy) => ({
    ...pharmacy,
    prescriptionMatch: analyzePharmacyPrescription(pharmacy, prescriptionSearch?.medicines || []),
  }))

  const filteredPharmacies = pharmaciesWithPrescription.filter((pharmacy) => {
    if (pharmacySearchTerms.length === 0) return true

    const address = normalizeSearchText(pharmacy.address)
    const city = normalizeSearchText(pharmacy.city)
    const name = normalizeSearchText(pharmacy.name)
    const medicineNames = (pharmacy.medicines || []).map((medicine) => normalizeSearchText(getMedicineName(medicine)))

    return pharmacySearchTerms.some((term) => (
      name.includes(term) ||
      address.includes(term) ||
      city.includes(term) ||
      medicineNames.some((medicineName) => medicineName.includes(term))
    ))
  })

  const rankedPharmacies = [...filteredPharmacies].sort((firstPharmacy, secondPharmacy) => {
    if (prescriptionSearch?.medicines?.length) {
      if (secondPharmacy.prescriptionMatch.foundCount !== firstPharmacy.prescriptionMatch.foundCount) {
        return secondPharmacy.prescriptionMatch.foundCount - firstPharmacy.prescriptionMatch.foundCount
      }

      if (firstPharmacy.prescriptionMatch.missingCount !== secondPharmacy.prescriptionMatch.missingCount) {
        return firstPharmacy.prescriptionMatch.missingCount - secondPharmacy.prescriptionMatch.missingCount
      }

      if (firstPharmacy.prescriptionMatch.total !== secondPharmacy.prescriptionMatch.total) {
        return firstPharmacy.prescriptionMatch.total - secondPharmacy.prescriptionMatch.total
      }
    }

    return String(firstPharmacy.name || '').localeCompare(String(secondPharmacy.name || ''), 'uz')
  })

  const bestPrescriptionPharmacy = prescriptionSearch?.medicines?.length ? rankedPharmacies[0] : null

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
      <section className="pharmacy-section" id="pharmacy-section">
        <div className="container">
          <div className="section-header">
            <h2>💊 Dorixonalar</h2>
            <div className="section-actions">
              <input
                type="text"
                placeholder="Dorixona, shahar yoki dori nomini qidiring..."
                value={pharmacySearchQuery}
                onChange={(e) => setPharmacySearchQuery(e.target.value)}
                className="search-input-small"
              />
            </div>
          </div>

          {prescriptionSearch?.medicines?.length ? (
            <div className="pharmacy-prescription-panel">
              <div className="pharmacy-prescription-main">
                <span className="pharmacy-prescription-kicker">Bemor kartasidan yuborilgan resept</span>
                <h3>{prescriptionSearch.diagnosis || 'Dorilar ro\'yxati dorixonaga yuborildi'}</h3>
                <p>
                  {prescriptionSearch.complaint
                    ? `Shikoyat: ${prescriptionSearch.complaint}`
                    : 'Dorilar ro\'yxati Home sahifadagi dorixona qidiruviga uzatildi.'}
                </p>
                <div className="pharmacy-prescription-tags">
                  {prescriptionSearch.medicines.map((medicine) => (
                    <span key={medicine} className="pharmacy-prescription-tag">{medicine}</span>
                  ))}
                </div>
              </div>

              <div className="pharmacy-prescription-side">
                <div className="pharmacy-prescription-metrics">
                  <div className="pharmacy-prescription-metric">
                    <span>Eng mos dorixona</span>
                    <strong>{bestPrescriptionPharmacy?.name || 'Topilmadi'}</strong>
                  </div>
                  <div className="pharmacy-prescription-metric">
                    <span>Topilgan dorilar</span>
                    <strong>{bestPrescriptionPharmacy?.prescriptionMatch?.foundCount || 0}/{prescriptionSearch.medicines.length}</strong>
                  </div>
                  <div className="pharmacy-prescription-metric">
                    <span>Jami summa</span>
                    <strong>{Number(bestPrescriptionPharmacy?.prescriptionMatch?.total || 0).toLocaleString('uz-UZ')} so'm</strong>
                  </div>
                </div>

                <button type="button" className="pharmacy-prescription-clear" onClick={clearPrescriptionSearch}>
                  Resept qidiruvini tozalash
                </button>
              </div>

              {bestPrescriptionPharmacy ? (
                <div className="pharmacy-prescription-breakdown">
                  <div className="pharmacy-breakdown-block">
                    <span className="pharmacy-breakdown-title">Olinayotgan dorilar</span>
                    <div className="pharmacy-breakdown-tags success">
                      {bestPrescriptionPharmacy.prescriptionMatch.found.length > 0 ? bestPrescriptionPharmacy.prescriptionMatch.found.map((medicine) => (
                        <span key={`${bestPrescriptionPharmacy.id}-${medicine.requestedName}`} className="pharmacy-breakdown-tag">
                          {medicine.medicineName} · {medicine.price.toLocaleString('uz-UZ')} so'm
                        </span>
                      )) : <span className="pharmacy-breakdown-empty">Topilgan dori yo'q</span>}
                    </div>
                  </div>
                  <div className="pharmacy-breakdown-block">
                    <span className="pharmacy-breakdown-title">Yo'q dorilar</span>
                    <div className="pharmacy-breakdown-tags danger">
                      {bestPrescriptionPharmacy.prescriptionMatch.missing.length > 0 ? bestPrescriptionPharmacy.prescriptionMatch.missing.map((medicine) => (
                        <span key={`${bestPrescriptionPharmacy.id}-missing-${medicine}`} className="pharmacy-breakdown-tag">
                          {medicine}
                        </span>
                      )) : <span className="pharmacy-breakdown-empty">Barcha dorilar topildi</span>}
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="pharmacy-grid">
            {rankedPharmacies.length > 0 ? (
              rankedPharmacies.map(pharmacy => (
                <PharmacyCard
                  key={pharmacy.id}
                  compact
                  requestedMedicines={prescriptionSearch?.medicines || []}
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
              pharmaciesWithPrescription.map(pharmacy => (
                <PharmacyCard
                  key={pharmacy.id}
                  compact
                  requestedMedicines={prescriptionSearch?.medicines || []}
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
