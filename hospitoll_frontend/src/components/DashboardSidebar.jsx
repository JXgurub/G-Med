import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useClinic } from '../context/ClinicContext'
import './DashboardSidebar.css'

const DashboardSidebar = () => {
  const [isOpen, setIsOpen] = useState(true)
  const location = useLocation()
  const navigate = useNavigate()
  const { clinicOwner, logoutClinicOwner } = useClinic()

  const menuItems = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      icon: (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <rect x="2" y="2" width="7" height="7" stroke="currentColor" strokeWidth="1.5"/>
          <rect x="11" y="2" width="7" height="7" stroke="currentColor" strokeWidth="1.5"/>
          <rect x="2" y="11" width="7" height="7" stroke="currentColor" strokeWidth="1.5"/>
          <rect x="11" y="11" width="7" height="7" stroke="currentColor" strokeWidth="1.5"/>
        </svg>
      ),
      href: '/clinic-dashboard'
    },
    {
      id: 'directions',
      label: 'Yo\'nalishlar',
      icon: (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <path d="M10 2L2 6v4c0 5 3 8 8 10 5-2 8-5 8-10V6l-8-4z" stroke="currentColor" strokeWidth="1.5" fill="none"/>
          <path d="M10 7v6M7 10h6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
        </svg>
      ),
      href: '/clinic-dashboard/directions'
    },
    {
      id: 'appointments',
      label: 'Xisobotlar',
      icon: (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <rect x="3" y="4" width="14" height="13" rx="1" stroke="currentColor" strokeWidth="1.5"/>
          <path d="M3 8h14" stroke="currentColor" strokeWidth="1.5"/>
          <path d="M6 4v-2M14 4v-2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          <circle cx="7" cy="11" r="1" fill="currentColor"/>
          <circle cx="13" cy="11" r="1" fill="currentColor"/>
          <circle cx="7" cy="15" r="1" fill="currentColor"/>
          <circle cx="13" cy="15" r="1" fill="currentColor"/>
        </svg>
      ),
      href: '/clinic-dashboard/appointments'
    },
    {
      id: 'settings',
      label: 'Sozlamalar',
      icon: (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <circle cx="10" cy="10" r="2.5" stroke="currentColor" strokeWidth="1.5"/>
          <path d="M10 3v-1M10 18v-1M6.34 4.34l-0.7-0.7M13.66 15.66l-0.7-0.7M4.34 6.34l-0.7 0.7M15.66 13.66l-0.7 0.7M3 10H2M18 10h-1M4.34 13.66l-0.7-0.7M15.66 6.34l-0.7 0.7M6.34 15.66l-0.7 0.7M13.66 4.34l-0.7 0.7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
        </svg>
      ),
      href: '/clinic-dashboard/settings'
    }
  ]

  const isActive = (href) => location.pathname === href

  return (
    <div className={`dashboard-sidebar ${isOpen ? 'open' : 'collapsed'}`}>
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <img src="/gmed-logo.svg" alt="G-MED logo" className="sidebar-logo-image" />
          {isOpen && <h2>G-MED</h2>}
        </div>
        <button
          className="sidebar-toggle"
          onClick={() => setIsOpen(!isOpen)}
          title={isOpen ? 'Yopish' : 'Ochish'}
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M3 6h14M3 10h14M3 14h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </button>
      </div>

      <nav className="sidebar-nav">
        {menuItems.map((item) => (
          <Link
            key={item.id}
            to={item.href}
            className={`nav-item ${isActive(item.href) ? 'active' : ''}`}
            title={!isOpen ? item.label : ''}
          >
            <span className="nav-icon">{item.icon}</span>
            {isOpen && <span className="nav-label">{item.label}</span>}
          </Link>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="user-profile">
          <div className="user-avatar">
            {clinicOwner?.ownerName?.charAt(0) || 'D'}
          </div>
          {isOpen && (
            <div className="user-info">
              <p className="user-name">{clinicOwner?.ownerName || 'Dr. Karimov'}</p>
              <p className="user-role">Klinika egasi</p>
            </div>
          )}
        </div>
        <button 
          className="btn-logout"
          onClick={() => {
            logoutClinicOwner()
            navigate('/clinic-owner-login')
          }}
          title="Chiqish"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
            <polyline points="16 17 21 12 16 7"></polyline>
            <line x1="21" y1="12" x2="9" y2="12"></line>
          </svg>
          {isOpen && <span>Chiqish</span>}
        </button>
      </div>
    </div>
  )
}

export default DashboardSidebar
