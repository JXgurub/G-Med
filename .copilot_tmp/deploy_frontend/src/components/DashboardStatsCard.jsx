import './DashboardStatsCard.css'

const DashboardStatsCard = ({ icon, label, value, trend = null, color = 'primary' }) => {
  return (
    <div className={`stats-card stats-card-${color}`}>
      <div className="stats-header">
        <div className="stats-icon">{icon}</div>
        {trend && (
          <div className={`stats-trend ${trend > 0 ? 'positive' : trend < 0 ? 'negative' : ''}`}>
            <span>{trend > 0 ? '+' : ''}{trend}%</span>
          </div>
        )}
      </div>
      <div className="stats-content">
        <p className="stats-label">{label}</p>
        <p className="stats-value">{value}</p>
      </div>
    </div>
  )
}

export default DashboardStatsCard
