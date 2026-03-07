import './ClinicServices.css'

const ClinicServices = ({ services }) => {
  const getServiceIcon = (serviceType) => {
    const icons = {
      'Konsultasiya': (
        <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
          <circle cx="16" cy="10" r="4" fill="currentColor"/>
          <path d="M12 16c-2 0-3 2-3 4v6c0 2 1 2 1 2h16c0 0 1 0 1-2v-6c0-2-1-4-3-4h-12z" fill="currentColor"/>
        </svg>
      ),
      'Laboratoriya': (
        <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
          <rect x="6" y="8" width="20" height="18" rx="2" fill="currentColor" opacity="0.3" stroke="currentColor" strokeWidth="1.5"/>
          <line x1="12" y1="8" x2="12" y2="26" stroke="currentColor" strokeWidth="1.5"/>
          <line x1="20" y1="8" x2="20" y2="26" stroke="currentColor" strokeWidth="1.5"/>
          <circle cx="9" cy="12" r="1.5" fill="currentColor"/>
          <circle cx="16" cy="12" r="1.5" fill="currentColor"/>
          <circle cx="23" cy="12" r="1.5" fill="currentColor"/>
        </svg>
      ),
      'Ultrasound': (
        <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
          <path d="M6 16c0-5.523 4.477-10 10-10s10 4.477 10 10" fill="currentColor" opacity="0.3"/>
          <path d="M9 16c0-3.866 3.134-7 7-7s7 3.134 7 7" stroke="currentColor" strokeWidth="1.5"/>
          <path d="M12 16c0-2.209 1.791-4 4-4s4 1.791 4 4" stroke="currentColor" strokeWidth="1.5"/>
        </svg>
      ),
      'Rentgen': (
        <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
          <rect x="6" y="6" width="20" height="20" rx="2" fill="currentColor" opacity="0.2" stroke="currentColor" strokeWidth="1.5"/>
          <circle cx="16" cy="16" r="2" fill="currentColor"/>
          <path d="M16 10v-2M16 24v-2M10 16H8M24 16h2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
        </svg>
      ),
      'Cardio': (
        <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
          <path d="M16 26s-8-6-8-12c0-3 2-5 4-5 1.5 0 3 .5 4 1.5 1-1 2.5-1.5 4-1.5 2 0 4 2 4 5 0 6-8 12-8 12z" fill="currentColor"/>
        </svg>
      ),
      'Reabilitatsiya': (
        <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
          <circle cx="16" cy="8" r="2.5" fill="currentColor"/>
          <path d="M13 12h6v1h-6v-1zM12 14h8v1h-8v-1zM12 16h8v1h-8v-1zM13 18h6v1h-6v-1z" fill="currentColor" opacity="0.3"/>
          <path d="M14 12v8M18 12v8" stroke="currentColor" strokeWidth="1.5"/>
        </svg>
      )
    }
    return icons[serviceType] || icons['Konsultasiya']
  }

  return (
    <section className="clinic-services">
      <div className="container">
        <h2>Xizmatlar</h2>
        <p className="section-subtitle">Bizning klinikalarga taqdim etilgan barcha xizmatlar</p>

        <div className="services-grid">
          {services && services.map((service, index) => (
            <div key={index} className="service-card">
              <div className="service-icon">
                {getServiceIcon(service.name)}
              </div>
              <h3>{service.name}</h3>
              <p>{service.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

export default ClinicServices
