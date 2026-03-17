import { Link } from 'react-router-dom'
import './Navbar.css'

const Navbar = () => {
  return (
    <nav className="navbar">
      <div className="navbar-container">
        <Link to="/" className="navbar-logo">
          <img src="/gmed-logo.svg" alt="G-MED logo" className="navbar-logo-image" />
          <h1>G-MED</h1>
        </Link>
        <ul className="navbar-menu">
          <li>
            <Link to="/" className="navbar-link">Asosiy</Link>
          </li>
          <li>
            <Link to="/contact" className="navbar-link">Bog'lanish</Link>
          </li>
          <li>
            <Link to="/patient-login" className="navbar-link navbar-link-patient">
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none" style={{marginRight: '0.5rem'}}>
                <path d="M9 9a4 4 0 100-8 4 4 0 000 8zM3 17a6 6 0 0112 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
              Men bemorman
            </Link>
          </li>
        </ul>
      </div>
    </nav>
  )
}

export default Navbar
