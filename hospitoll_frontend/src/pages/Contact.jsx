import { useEffect, useState } from 'react'
import { siteSettingsApi } from '../services/api'
import { normalizeEmailWithDefaultDomain } from '../utils/helpers'
import './Contact.css'

const Contact = () => {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [submitStatus, setSubmitStatus] = useState(null)
  const [lead, setLead] = useState({
    name: '',
    phone_number: '+998',
    email: '',
    message: ''
  })

  useEffect(() => {
    const load = async () => {
      try {
        const res = await siteSettingsApi.getHomeContact()
        setData(res)
      } catch (error) {
        setData(null)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const displayEmail = ((data?.email_display || data?.email || '').trim())

  const handleScrollToForm = () => {
    const el = document.getElementById('contact-lead-form')
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  if (loading) {
    return <div className="contact-page"><div className="container">Yuklanyapti...</div></div>
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitStatus(null)
    setSubmitting(true)
    try {
      await siteSettingsApi.createContactLead({
        name: lead.name,
        phone_number: lead.phone_number,
        email: normalizeEmailWithDefaultDomain(lead.email),
        message: lead.message,
      })
      setLead({ name: '', phone_number: '+998', email: '', message: '' })
      setSubmitStatus({ type: 'success', message: "So'rovingiz yuborildi. Tez orada bog'lanamiz ✅" })
    } catch (error) {
      const msg =
        error?.response?.data?.detail ||
        (typeof error?.response?.data === 'string' ? error.response.data : null) ||
        error.message ||
        'Xatolik yuz berdi'
      setSubmitStatus({ type: 'error', message: msg })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="contact-page">
      <section className="contact-hero">
        <div className="container">
          <div className="contact-hero-grid">
            <div className="contact-hero-left">
              <div className="contact-kicker">G-MED • SaaS platforma</div>
              <h1 className="contact-title">Bog'lanish</h1>
              {data?.text ? <p className="contact-subtitle">{data.text}</p> : null}
              <div className="contact-cta-row">
                <button type="button" className="contact-cta-primary" onClick={handleScrollToForm}>
                  Demo so'rash
                </button>
                {data?.telegram_link ? (
                  <a className="contact-cta-secondary" href={data.telegram_link} target="_blank" rel="noreferrer">
                    Telegramga yozish
                  </a>
                ) : (
                  <a
                    className="contact-cta-secondary"
                    href="#contact-lead-form"
                    onClick={(e) => {
                      e.preventDefault()
                      handleScrollToForm()
                    }}
                  >
                    Xabar qoldirish
                  </a>
                )}
              </div>

              <div className="contact-trust">
                <div className="trust-item">
                  <span className="trust-icon" aria-hidden="true">🔒</span>
                  <span className="trust-text">Ma'lumotlar himoyasi</span>
                </div>
                <div className="trust-item">
                  <span className="trust-icon" aria-hidden="true">⚡</span>
                  <span className="trust-text">Tezkor onboarding</span>
                </div>
                <div className="trust-item">
                  <span className="trust-icon" aria-hidden="true">📈</span>
                  <span className="trust-text">Barqaror ishlash</span>
                </div>
                <div className="trust-item">
                  <span className="trust-icon" aria-hidden="true">🛟</span>
                  <span className="trust-text">Qo'llab-quvvatlash</span>
                </div>
              </div>
            </div>

            <div className="contact-hero-right">
              {data?.image ? (
                <img src={data.image} alt="Bog'lanish" className="contact-hero-image" />
              ) : (
                <div className="contact-hero-image-placeholder">Bog'lanish rasmi</div>
              )}
            </div>
          </div>
        </div>
      </section>

      <section className="contact-content">
        <div className="container">
          <div className="contact-grid">
            <div className="contact-card">
              <h2 className="contact-card-title">Aloqa ma'lumotlari</h2>

              <div className="contact-items">
                {data?.telegram_link ? (
                  <a className="contact-item" href={data.telegram_link} target="_blank" rel="noreferrer">
                    <span className="contact-icon" aria-hidden="true">✈️</span>
                    <span className="contact-label">Telegram</span>
                    <span className="contact-value">{data.telegram_link}</span>
                  </a>
                ) : null}

                {data?.phone_number ? (
                  <a className="contact-item" href={`tel:${data.phone_number}`}>
                    <span className="contact-icon" aria-hidden="true">📞</span>
                    <span className="contact-label">Telefon</span>
                    <span className="contact-value">{data.phone_number}</span>
                  </a>
                ) : null}

                {data?.instagram_link ? (
                  <a className="contact-item" href={data.instagram_link} target="_blank" rel="noreferrer">
                    <span className="contact-icon" aria-hidden="true">📷</span>
                    <span className="contact-label">Instagram</span>
                    <span className="contact-value">{data.instagram_link}</span>
                  </a>
                ) : null}

                {displayEmail ? (
                  <a className="contact-item" href={`mailto:${(data?.email || displayEmail).trim()}`}>
                    <span className="contact-icon" aria-hidden="true">✉️</span>
                    <span className="contact-label">Email</span>
                    <span className="contact-value">{displayEmail}</span>
                  </a>
                ) : null}

                {!data?.telegram_link && !data?.phone_number && !data?.instagram_link && !displayEmail ? (
                  <div className="contact-empty">Aloqa ma'lumotlari kiritilmagan</div>
                ) : null}
              </div>

              <div className="contact-mini-cta">
                <div className="contact-mini-cta-title">Tezkor bog'lanish</div>
                <div className="contact-mini-cta-text">
                  Demo yoki hamkorlik bo'yicha so'rov qoldiring — jamoamiz siz bilan aloqaga chiqadi.
                </div>
                <button type="button" className="contact-mini-cta-btn" onClick={handleScrollToForm}>
                  So'rov qoldirish
                </button>
              </div>
            </div>

            <div className="contact-form-card" id="contact-lead-form">
              <h2 className="contact-card-title">Xabar qoldirish</h2>
              <p className="contact-form-subtitle">Klinikangiz/dorixonangiz uchun demo va narx taklifini olishingiz mumkin.</p>

              <form className="contact-form" onSubmit={handleSubmit}>
                <div className="contact-form-row">
                  <div className="contact-field">
                    <label>Ism</label>
                    <input
                      type="text"
                      value={lead.name}
                      onChange={(e) => setLead({ ...lead, name: e.target.value })}
                      placeholder="Ismingiz"
                      autoComplete="name"
                    />
                  </div>
                  <div className="contact-field">
                    <label>Telefon</label>
                    <input
                      type="tel"
                      value={lead.phone_number}
                      onChange={(e) => setLead({ ...lead, phone_number: e.target.value })}
                      placeholder="+998..."
                      autoComplete="tel"
                    />
                  </div>
                </div>

                <div className="contact-field">
                  <label>Email</label>
                  <input
                    type="email"
                    value={lead.email}
                    onChange={(e) => setLead({ ...lead, email: e.target.value })}
                    onBlur={(e) => setLead({ ...lead, email: normalizeEmailWithDefaultDomain(e.target.value) })}
                    placeholder="you@company.uz"
                    autoComplete="email"
                  />
                </div>

                <div className="contact-field">
                  <label>Xabar</label>
                  <textarea
                    value={lead.message}
                    onChange={(e) => setLead({ ...lead, message: e.target.value })}
                    placeholder="Qisqacha izoh (demo, hamkorlik, savollar...)"
                    rows={5}
                    required
                  />
                </div>

                {submitStatus ? (
                  <div className={`contact-form-status ${submitStatus.type}`}>{submitStatus.message}</div>
                ) : null}

                <button className="contact-submit" type="submit" disabled={submitting}>
                  {submitting ? 'Yuborilmoqda...' : 'Yuborish'}
                </button>
              </form>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}

export default Contact
