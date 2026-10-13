import DashboardStatsCard from './DashboardStatsCard'
import './DashboardStats.css'

const DashboardStats = () => {
  const stats = [
    {
      id: 'patients',
      label: "Bugun ko'rib chiqilgan bemorlar",
      value: '24',
      trend: 12,
      color: 'primary',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" strokeWidth="2" stroke="currentColor">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
          <circle cx="9" cy="7" r="4"></circle>
          <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
          <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
        </svg>
      )
    },
    {
      id: 'doctors',
      label: 'Faol doktorlar',
      value: '8',
      trend: 0,
      color: 'secondary',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" strokeWidth="2" stroke="currentColor">
          <path d="M6 9a6 6 0 1 0 12 0A6 6 0 0 0 6 9z"></path>
          <line x1="12" y1="5" x2="12" y2="13"></line>
          <line x1="8" y1="9" x2="16" y2="9"></line>
        </svg>
      )
    },
    {
      id: 'appointments',
      label: "Bugungi qabullar",
      value: '15',
      trend: 8,
      color: 'success',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" strokeWidth="2" stroke="currentColor">
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
          <line x1="16" y1="2" x2="16" y2="6"></line>
          <line x1="8" y1="2" x2="8" y2="6"></line>
          <line x1="3" y1="10" x2="21" y2="10"></line>
        </svg>
      )
    },
    {
      id: 'revenue',
      label: "Bugungi daromad",
      value: '1,250,000',
      trend: 5,
      color: 'warning',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" strokeWidth="2" stroke="currentColor">
          <line x1="12" y1="1" x2="12" y2="23"></line>
          <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
        </svg>
      )
    }
  ]

  return (
    <section className="dashboard-stats">
      <h2 className="stats-title">Bugungi ko'rsatkich</h2>
      <div className="stats-grid">
        {stats.map((stat) => (
          <DashboardStatsCard
            key={stat.id}
            icon={stat.icon}
            label={stat.label}
            value={stat.value}
            trend={stat.trend}
            color={stat.color}
          />
        ))}
      </div>
    </section>
  )
}

export default DashboardStats
