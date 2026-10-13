import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAdmin } from '../context/AdminContext'
import { useClinic } from '../context/ClinicContext'
import { useDoctor } from '../context/DoctorContext'
import { usePatient } from '../context/PatientContext'
import { usePharmacy } from '../context/PharmacyContext'
import PasswordInput from '../components/PasswordInput'
import './Login.css'

const Login = () => {
  const navigate = useNavigate()
  const { loginAdmin } = useAdmin()
  const { loginClinicOwner } = useClinic()
  const { loginDoctor } = useDoctor()
  const { loginPatient } = usePatient()
  const { loginPharmacy } = usePharmacy()

  const [formData, setFormData] = useState({
    email: '',
    password: ''
  })
  const [role, setRole] = useState('doctor')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (role === 'patient') {
        const result = await loginPatient(formData.email, formData.password)
        if (result.success) {
          navigate('/patient')
          return
        }
        setError(result.error || 'Kirishda xatolik')
        return
      }

      let result = { success: false, error: 'Kirishda xatolik' }
      if (role === 'admin') result = await loginAdmin(formData.email, formData.password)
      if (role === 'clinic') result = await loginClinicOwner(formData.email, formData.password)
      if (role === 'doctor') result = await loginDoctor(formData.email, formData.password)
      if (role === 'pharmacy') result = await loginPharmacy(formData.email, formData.password)

      if (result.success) {
        if (role === 'admin') navigate('/admin-dashboard')
        if (role === 'clinic') navigate('/clinic-dashboard')
        if (role === 'doctor') navigate('/doctor-dashboard')
        if (role === 'pharmacy') navigate('/pharmacy-owner-dashboard')
        return
      }

      setError(result.error || 'Kirishda xatolik')
    } catch (err) {
      setError(err.message || 'Kirishda xatolik')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login">
      <div className="login-container">
        <div className="login-card">
          <h1>Login</h1>
          <p className="login-subtitle">Welcome back to G-MED</p>
          
          <form onSubmit={handleSubmit} className="login-form">
            <div className="form-group">
              <label htmlFor="role">Rol</label>
              <select
                id="role"
                name="role"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                <option value="doctor">Doktor</option>
                <option value="clinic">Klinika egasi</option>
                <option value="pharmacy">Dorixona egasi</option>
                <option value="admin">Admin</option>
                <option value="patient">Bemor</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="email">{role === 'patient' ? 'Pasport ID' : 'Email'}</label>
              <input
                type={role === 'patient' ? 'text' : 'email'}
                id="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                placeholder={role === 'patient' ? 'AA1234567' : 'Enter your email'}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="password">Password</label>
              <PasswordInput
                id="password"
                name="password"
                value={formData.password}
                onChange={handleChange}
                placeholder="Enter your password"
                required
              />
            </div>

            {error && <div className="error-message">{error}</div>}

            <button type="submit" className="btn-login" disabled={loading}>
              {loading ? 'Kirish...' : 'Login'}
            </button>
          </form>

          <div className="login-footer">
            <div className="link-section">
              <p className="section-title">Dorixona:</p>
              <p><Link to="/pharmacy-search" className="link pharmacy-link">🔍 Dori qidirish</Link></p>
            </div>
            <p className="note">Barcha loginlar backend bilan ishlaydi</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Login
