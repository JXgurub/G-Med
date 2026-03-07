import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useClinic } from '../context/ClinicContext'
import DashboardSidebar from '../components/DashboardSidebar'
import './DirectionsPage.css'

const DirectionsPage = () => {
  const navigate = useNavigate()
  const {
    clinicOwner,
    clinicDepartments,
    clinicServices,
    clinicDoctors,
    loading,
    addDepartment,
    updateDepartment,
    deleteDepartment
  } = useClinic()

  const [showAddDepartment, setShowAddDepartment] = useState(false)
  const [editingDepartmentId, setEditingDepartmentId] = useState(null)
  const [departmentForm, setDepartmentForm] = useState({
    name: ''
  })

  // Check authentication
  useEffect(() => {
    if (!clinicOwner) {
      navigate('/clinic-owner-login')
    }
  }, [clinicOwner, navigate])

  // Handle form submission
  const handleSubmitDepartment = async (e) => {
    e.preventDefault()
    
    if (!clinicOwner?.id) {
      alert('Klinika ma\'lumotlari topilmadi')
      return
    }

    try {
      if (editingDepartmentId) {
        // Update existing department
        await updateDepartment(clinicOwner.id, editingDepartmentId, departmentForm)
        alert('Yo\'nalish muvaffaqiyatli yangilandi!')
      } else {
        // Create new department
        await addDepartment(clinicOwner.id, departmentForm)
        alert('Yangi yo\'nalish qo\'shildi!')
      }
      
      // Reset form
      setDepartmentForm({ name: '' })
      setShowAddDepartment(false)
      setEditingDepartmentId(null)
    } catch (error) {
      console.error('Department operation error:', error)
      alert(editingDepartmentId ? 'Yo\'nalishni yangilashda xatolik' : 'Yo\'nalish qo\'shishda xatolik')
    }
  }

  // Handle edit department
  const handleEditDepartment = (department) => {
    setEditingDepartmentId(department.id)
    setDepartmentForm({
      name: department.name
    })
    setShowAddDepartment(true)
  }

  // Handle delete department
  const handleDeleteDepartment = async (departmentId) => {
    if (!window.confirm('Ushbu yo\'nalishni o\'chirishni xohlaysizmi?')) {
      return
    }

    try {
      await deleteDepartment(clinicOwner.id, departmentId)
      alert('Yo\'nalish o\'chirildi!')
    } catch (error) {
      console.error('Delete department error:', error)
      alert('Yo\'nalishni o\'chirishda xatolik')
    }
  }

  // Cancel editing
  const handleCancelForm = () => {
    setShowAddDepartment(false)
    setEditingDepartmentId(null)
    setDepartmentForm({ name: '' })
  }

  // Get services for a specific department
  const getServicesForDepartment = (departmentId) => {
    return clinicServices.filter(service => service.department === departmentId)
  }

  // Get doctor name by ID
  const getDoctorName = (doctorId) => {
    if (!doctorId) return null
    const doctor = clinicDoctors.find(d => d.id === doctorId)
    return doctor ? `Dr. ${doctor.fullName}` : null
  }

  if (loading) {
    return (
      <div className="directions-page">
        <DashboardSidebar />
        <div className="directions-content">
          <div className="loading-spinner">Yuklanmoqda...</div>
        </div>
      </div>
    )
  }

  if (!clinicOwner) {
    return null
  }

  return (
    <div className="directions-page">
      <DashboardSidebar />
      <div className="directions-content">
        <div className="directions-header">
          <div className="header-left">
            <h1>Klinika yo'nalishlari</h1>
            <p className="subtitle">
              {(clinicOwner.name || clinicOwner.clinicName || 'Klinikangiz')} ning ixtisoslashuvlarini boshqaring
            </p>
          </div>
          <button
            className="btn btn-primary"
            onClick={() => setShowAddDepartment(true)}
          >
            ➕ Yangi yo'nalish qo'shish
          </button>
        </div>

        {/* Add/Edit Department Form */}
        {showAddDepartment && (
          <div className="form-modal-overlay" onClick={handleCancelForm}>
            <div className="form-modal" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h3>{editingDepartmentId ? 'Yo\'nalishni tahrirlash' : 'Yangi yo\'nalish qo\'shish'}</h3>
                <button className="btn-close" onClick={handleCancelForm}>✕</button>
              </div>
              <form onSubmit={handleSubmitDepartment} className="department-form">
                <div className="form-group">
                  <label htmlFor="dept-name">Yo'nalish nomi *</label>
                  <input
                    id="dept-name"
                    type="text"
                    placeholder="Masalan: Stomatologiya, Ginekologiya, Kardiologiya"
                    value={departmentForm.name}
                    onChange={(e) => setDepartmentForm({ ...departmentForm, name: e.target.value })}
                    required
                  />
                </div>
                <div className="form-actions">
                  <button type="button" className="btn btn-secondary" onClick={handleCancelForm}>
                    Bekor qilish
                  </button>
                  <button type="submit" className="btn btn-primary">
                    {editingDepartmentId ? 'Saqlash' : 'Qo\'shish'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Departments Grid */}
        <div className="departments-container">
          {clinicDepartments.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">🏥</div>
              <h3>Yo'nalishlar yo'q</h3>
              <p>Klinikangiz uchun birinchi yo'nalishni qo'shing</p>
              <button
                className="btn btn-primary"
                onClick={() => setShowAddDepartment(true)}
              >
                ➕ Birinchi yo'nalishni qo'shish
              </button>
            </div>
          ) : (
            clinicDepartments.map((department) => {
              const departmentServices = getServicesForDepartment(department.id)
              return (
                <div key={department.id} className="department-card">
                  <div className="department-header">
                    <div className="department-info">
                      <h3>{department.name}</h3>
                    </div>
                    <div className="department-actions">
                      <button
                        className="btn-icon btn-edit"
                        onClick={() => handleEditDepartment(department)}
                        title="Tahrirlash"
                      >
                        ✏️
                      </button>
                      <button
                        className="btn-icon btn-delete"
                        onClick={() => handleDeleteDepartment(department.id)}
                        title="O'chirish"
                      >
                        🗑️
                      </button>
                    </div>
                  </div>

                  {/* Services under this department */}
                  {departmentServices.length > 0 && (
                    <div className="department-services">
                      <h4 className="services-title">Xizmatlar ({departmentServices.length})</h4>
                      <ul className="services-mini-list">
                        {departmentServices.map((service) => (
                          <li key={service.id} className="service-mini-item">
                            <span className="service-name">{service.name}</span>
                            <span className="service-price">
                              {Number(service.price).toLocaleString('uz-UZ')} so'm
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}

export default DirectionsPage
