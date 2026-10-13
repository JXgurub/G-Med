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
            <a href="/analiz-tahlili/" className="navbar-link">AI tahlil</a>
          </li>
          <li>
            <a href="/liza/index.html" className="navbar-link">Liza yordamchi</a>
          </li>
          <li>
            <Link to="/contact" className="navbar-link">Bog'lanish</Link>
          </li>
          <li>
            <Link to="/child-safety" className="navbar-link">Bolalar Xavfsizligi</Link>
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
        <Link to="/child-safety" className="navbar-mobile-safety">
          <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path d="M12 3 19 6v5c0 4.8-2.8 8.2-7 10-4.2-1.8-7-5.2-7-10V6l7-3Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
            <path d="m9 12 2 2 4-4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Bolalar xavfsizligi
        </Link>
        <a href="/liza/index.html" className="navbar-mobile-assistant">Liza yordamchi</a>
      </div>
    </nav>
  )
}

export default Navbar
