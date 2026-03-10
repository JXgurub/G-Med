import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAdmin } from '../context/AdminContext'
import { siteSettingsApi } from '../services/api'
import useSmartAutoRefresh from '../hooks/useSmartAutoRefresh'
import ChangePasswordModal from '../components/ChangePasswordModal'
import SetPaymentAmountModal from '../components/SetPaymentAmountModal'
import PasswordInput from '../components/PasswordInput'
import { normalizeEmailWithDefaultDomain } from '../utils/helpers'
import './AdminDashboard.css'

const DEFAULT_PHONE_PREFIX = '+998'

const generateClinicRegistrationNumber = () => {
  const datePart = new Date().toISOString().slice(2, 10).replace(/-/g, '')
  const randomPart = Math.floor(1000 + Math.random() * 9000)
  return `CLN-${datePart}-${randomPart}`
}

const getDefaultClinicForm = () => ({
  name: '',
  ownerFirstName: '',
  ownerLastName: '',
  ownerPassportId: '',
  email: '',
  phone: DEFAULT_PHONE_PREFIX,
  address: '',
  registrationNumber: generateClinicRegistrationNumber(),
  password: ''
})

const getDefaultPharmacyForm = () => ({
  name: '',
  ownerFirstName: '',
  ownerLastName: '',
  ownerEmail: '',
  ownerPhone: DEFAULT_PHONE_PREFIX,
  pharmacyEmail: '',
  phone: DEFAULT_PHONE_PREFIX,
  address: '',
  registrationNumber: '',
  password: ''
})

const AdminDashboard = () => {
  const navigate = useNavigate()
  const { 
    admin, 
    loading,
    clinics, 
    pharmacies,
    toggleClinicStatus, 
    markClinicPaid, 
    deleteClinic, 
    addClinic,
    togglePharmacyStatus,
    markPharmacyPaid,
    deletePharmacy,
    addPharmacy,
    changeClinicPassword,
    setClinicPaymentAmount,
    changePharmacyPassword,
    setPharmacyPaymentAmount,
    generateClinicPaymentLink,
    generatePharmacyPaymentLink,
    approveClinicSubscription,
    approvePharmacySubscription,
    refreshAdminData,
    logoutAdmin 
  } = useAdmin()
  
  // Modal state
  const [showChangePasswordModal, setShowChangePasswordModal] = useState(false)
  const [showSetAmountModal, setShowSetAmountModal] = useState(false)
  const [selectedClinic, setSelectedClinic] = useState(null)
  const [selectedPharmacy, setSelectedPharmacy] = useState(null)
  const [isLoadingModal, setIsLoadingModal] = useState(false)
  
  // Form state
  const [showAddClinic, setShowAddClinic] = useState(false)
  const [showAddPharmacy, setShowAddPharmacy] = useState(false)
  const [clinicForm, setClinicForm] = useState(() => getDefaultClinicForm())
  const [pharmacyForm, setPharmacyForm] = useState(() => getDefaultPharmacyForm())
  const [searchTerm, setSearchTerm] = useState('')
  const [filterStatus, setFilterStatus] = useState('all')
  const [activeTab, setActiveTab] = useState('clinics')

  // Home contact settings (Bog'lanish)
  const [homeContactLoading, setHomeContactLoading] = useState(false)
  const [homeContactForm, setHomeContactForm] = useState({
    text: '',
    telegram_link: '',
    phone_number: DEFAULT_PHONE_PREFIX,
    instagram_link: '',
    email_display: ''
  })
  const [homeContactImageFile, setHomeContactImageFile] = useState(null)
  const [homeContactImageUrl, setHomeContactImageUrl] = useState('')
  const [homeContactCollapsed, setHomeContactCollapsed] = useState(true)
  const [homeContactSavedAt, setHomeContactSavedAt] = useState(null)

  // Contact leads (messages)
  const [contactLeads, setContactLeads] = useState([])
  const [contactLeadsLoading, setContactLeadsLoading] = useState(false)
  const [selectedLeadId, setSelectedLeadId] = useState(null)
  const [systemAlerts, setSystemAlerts] = useState([])
  const [systemAlertsLoading, setSystemAlertsLoading] = useState(false)
  const [selectedAlertId, setSelectedAlertId] = useState(null)

  const loadSystemAlerts = useCallback(async ({ silent = false } = {}) => {
    try {
      if (!silent) setSystemAlertsLoading(true)
      const data = await siteSettingsApi.adminGetSystemAlerts({ unresolved_only: true, limit: 200 })
      setSystemAlerts(Array.isArray(data) ? data : (data?.results || []))
    } catch (error) {
      console.error('System alerts yuklashda xatolik:', error)
      setSystemAlerts([])
    } finally {
      if (!silent) setSystemAlertsLoading(false)
    }
  }, [])

  const loadLeads = useCallback(async ({ silent = false } = {}) => {
    try {
      if (!silent) setContactLeadsLoading(true)
      const data = await siteSettingsApi.adminGetContactLeads({ limit: 100 })
      setContactLeads(Array.isArray(data) ? data : (data?.results || []))
    } catch (error) {
      console.error('Contact leads yuklashda xatolik:', error)
    } finally {
      if (!silent) setContactLeadsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (loading) return
    if (!admin) {
      navigate('/admin-login')
    }
  }, [admin, loading, navigate])

  useEffect(() => {
    const loadHomeContact = async () => {
      if (!admin) return
      setHomeContactLoading(true)
      try {
        const data = await siteSettingsApi.getHomeContact()
        setHomeContactForm({
          text: data?.text || '',
          telegram_link: data?.telegram_link || '',
          phone_number: data?.phone_number || DEFAULT_PHONE_PREFIX,
          instagram_link: data?.instagram_link || '',
          email_display: (data?.email_display || data?.email || '')
        })
        setHomeContactImageUrl(data?.image || '')
        setHomeContactImageFile(null)
        // Always keep settings collapsed on load/refresh; expand only on explicit edit.
        setHomeContactCollapsed(true)
        setHomeContactSavedAt(null)
      } catch (error) {
        console.error('Home contact settings yuklashda xatolik:', error)
      } finally {
        setHomeContactLoading(false)
      }
    }
    loadHomeContact()
  }, [admin])

  const refreshAdminRealtimeData = useCallback(async () => {
    if (!admin) return

    const tasks = [
      loadLeads({ silent: true }),
      loadSystemAlerts({ silent: true }),
    ]

    if (activeTab !== 'contact' && activeTab !== 'alerts' && typeof refreshAdminData === 'function') {
      tasks.push(refreshAdminData())
    }

    try {
      await Promise.all(tasks)
    } catch (error) {
      console.error('Admin realtime refresh xatoligi:', error)
    }
  }, [admin, activeTab, loadLeads, loadSystemAlerts, refreshAdminData])

  useEffect(() => {
    if (!admin) return
    void refreshAdminRealtimeData()
  }, [admin, refreshAdminRealtimeData])

  useSmartAutoRefresh({
    enabled: Boolean(admin),
    callback: refreshAdminRealtimeData,
    minIntervalMs: 45000,
    maxIntervalMs: 60000,
    immediate: false,
  })

  const unreadLeadsCount = contactLeads.filter((l) => l?.is_read === false).length
  const unresolvedAlertsCount = systemAlerts.filter((a) => a?.is_resolved === false).length

  const handleMarkLeadRead = async (leadId) => {
    try {
      const updated = await siteSettingsApi.adminMarkContactLeadRead(leadId)
      setContactLeads((prev) => prev.map((l) => (l.id === leadId ? updated : l)))
    } catch (error) {
      console.error('Xabarni o\'qildi qilishda xatolik:', error)
    }
  }

  const formatLeadTime = (iso) => {
    if (!iso) return ''
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return ''
    return `${d.toLocaleDateString('uz-UZ')} ${d.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' })}`
  }

  const formatAlertTime = (iso) => {
    if (!iso) return ''
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return ''
    return `${d.toLocaleDateString('uz-UZ')} ${d.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' })}`
  }

  const safeString = (value) => {
    if (value === null || value === undefined) return ''
    if (typeof value === 'string') return value.trim()
    return String(value).trim()
  }

  const getAlertDetails = (alertItem) => {
    const context = alertItem?.context && typeof alertItem.context === 'object' ? alertItem.context : {}
    const fileValue = safeString(context.file || context.filename || context.source_file || context.file_path || context.path)
    const endpointValue = safeString(context.endpoint || context.path || context.url || context.client_url)
    const methodValue = safeString(context.method)
    const statusValue = safeString(context.status || context.status_code)
    const lineValue = safeString(context.line || context.lineno)
    const columnValue = safeString(context.column || context.colno)
    const reasonValue = safeString(context.reason || context.reason_type)
    const userValue = safeString(context.user_id)
    const trace = safeString(alertItem?.traceback)
    const firstTraceLine = trace ? trace.split('\n').map((line) => line.trim()).find(Boolean) || '' : ''

    return {
      reason: safeString(alertItem?.message) || 'Xabar mavjud emas',
      type: safeString(alertItem?.alert_type) || 'system_alert',
      endpoint: endpointValue,
      method: methodValue,
      status: statusValue,
      file: fileValue,
      line: lineValue,
      column: columnValue,
      userId: userValue,
      extraReason: reasonValue,
      firstTraceLine,
      trace,
      context,
    }
  }

  const handleResolveSystemAlert = async (alertId) => {
    try {
      const updated = await siteSettingsApi.adminResolveSystemAlert(alertId)
      setSystemAlerts((prev) => prev.map((a) => (a.id === alertId ? updated : a)))
    } catch (error) {
      console.error('System alertni yopishda xatolik:', error)
    }
  }

  if (loading) {
    return <div style={{ padding: '20px', textAlign: 'center' }}>Yuklanyapti...</div>
  }

  if (!admin) {
    return null
  }

  const handleAddClinic = async (e) => {
    e.preventDefault()
    const clinicEmail = normalizeEmailWithDefaultDomain(clinicForm.email)
    if (
      clinicForm.name &&
      clinicForm.ownerFirstName &&
      clinicForm.ownerLastName &&
      clinicForm.ownerPassportId &&
      clinicEmail &&
      clinicForm.phone &&
      clinicForm.address &&
      clinicForm.registrationNumber &&
      clinicForm.password
    ) {
      try {
        await addClinic({
          name: clinicForm.name,
          owner_first_name: clinicForm.ownerFirstName,
          owner_last_name: clinicForm.ownerLastName,
          owner_passport_id: clinicForm.ownerPassportId,
          owner_email: clinicEmail,
          owner_phone_number: clinicForm.phone,
          owner_password: clinicForm.password,
          email: clinicEmail,
          phone_number: clinicForm.phone,
          address: clinicForm.address,
          registration_number: clinicForm.registrationNumber,
          status: 'active'
        })
        setClinicForm(getDefaultClinicForm())
        setShowAddClinic(false)
        alert('Klinika muvaffaqiyatli qo\'shildi! ✅')
      } catch (error) {
        console.error('Klinika qo\'shish xatosi:', error)
        const errorMsg = error.response?.data?.detail || error.message || 'Klinika qo\'shishda xatolik yuz berdi'
        alert(errorMsg)
      }
    }
  }

  const toggleClinicForm = () => {
    if (!showAddClinic) {
      setClinicForm((prev) => ({
        ...prev,
        phone: prev.phone || DEFAULT_PHONE_PREFIX,
        registrationNumber: prev.registrationNumber || generateClinicRegistrationNumber(),
      }))
    }
    setShowAddClinic((prev) => !prev)
  }

  const togglePharmacyForm = () => {
    if (!showAddPharmacy) {
      setPharmacyForm((prev) => ({
        ...prev,
        ownerPhone: prev.ownerPhone || DEFAULT_PHONE_PREFIX,
        phone: prev.phone || DEFAULT_PHONE_PREFIX,
      }))
    }
    setShowAddPharmacy((prev) => !prev)
  }

  const handleAddPharmacy = async (e) => {
    e.preventDefault()
    const ownerEmail = normalizeEmailWithDefaultDomain(pharmacyForm.ownerEmail)
    const pharmacyEmail = normalizeEmailWithDefaultDomain(pharmacyForm.pharmacyEmail)
    if (
      pharmacyForm.name &&
      pharmacyForm.ownerFirstName &&
      pharmacyForm.ownerLastName &&
      ownerEmail &&
      pharmacyForm.phone &&
      pharmacyForm.address &&
      pharmacyForm.registrationNumber &&
      pharmacyForm.password
    ) {
      try {
        await addPharmacy({
          name: pharmacyForm.name,
          owner_first_name: pharmacyForm.ownerFirstName,
          owner_last_name: pharmacyForm.ownerLastName,
          owner_email: ownerEmail,
          owner_phone_number: pharmacyForm.ownerPhone,
          owner_password: pharmacyForm.password,
          email: pharmacyEmail || ownerEmail,
          phone_number: pharmacyForm.phone,
          address: pharmacyForm.address,
          registration_number: pharmacyForm.registrationNumber,
          status: 'active'
        })
        setPharmacyForm(getDefaultPharmacyForm())
        setShowAddPharmacy(false)
        alert(`Dorixona muvaffaqiyatli qo'shildi! ✅\n\nKirish emaili: ${ownerEmail}`)
      } catch (error) {
        console.error('Dorixona qo\'shish xatosi:', error)
        const errorMsg = error.response?.data?.detail || error.message || 'Dorixona qo\'shishda xatolik yuz berdi'
        alert(errorMsg)
      }
    }
  }

  const handleSaveHomeContact = async (e) => {
    e.preventDefault()
    setHomeContactLoading(true)
    try {
      const formData = new FormData()
      formData.append('text', homeContactForm.text || '')
      formData.append('telegram_link', homeContactForm.telegram_link || '')
      formData.append('phone_number', homeContactForm.phone_number || '')
      formData.append('instagram_link', homeContactForm.instagram_link || '')
      const emailValue = normalizeEmailWithDefaultDomain(homeContactForm.email_display)
      formData.append('email', emailValue)
      formData.append('email_display', emailValue)

      if (homeContactImageFile) {
        formData.append('image', homeContactImageFile)
      }

      const updated = await siteSettingsApi.updateHomeContact(formData)
      setHomeContactImageUrl(updated?.image || homeContactImageUrl)
      setHomeContactImageFile(null)
      setHomeContactSavedAt(new Date())
      setHomeContactCollapsed(true)
      alert("Bog'lanish bo'limi saqlandi! ✅")
    } catch (error) {
      console.error("Bog'lanish bo'limini saqlashda xatolik:", error)
      const errorMsg = error?.response?.data?.detail || error.message || 'Saqlashda xatolik yuz berdi'
      alert(errorMsg)
    } finally {
      setHomeContactLoading(false)
    }
  }

  const formatSavedAt = (dateObj) => {
    if (!dateObj) return ''
    try {
      return dateObj.toLocaleString('uz-UZ')
    } catch {
      return ''
    }
  }
  // Modal Handler Functions
  const handleChangeClinicPassword = async (newPassword) => {
    if (!selectedClinic) return
    setIsLoadingModal(true)
    try {
      await changeClinicPassword(selectedClinic.id, newPassword)
      setShowChangePasswordModal(false)
      setSelectedClinic(null)
      alert(`${selectedClinic.name} ning parol muvaffaqiyatli o'zgartirildi! ✅`)
    } catch (error) {
      console.error('Parol o\'zgartirish xatosi:', error)
      alert('Parolni o\'zgartirishda xatolik yuz berdi')
    } finally {
      setIsLoadingModal(false)
    }
  }

  const handleSetClinicAmount = async (data) => {
    if (!selectedClinic) return
    setIsLoadingModal(true)
    try {
      await setClinicPaymentAmount(selectedClinic.id, data.amount, data.description)
      setShowSetAmountModal(false)
      setSelectedClinic(null)
      alert(`${selectedClinic.name} ning to'lov miqdori muvaffaqiyatli o'rnatildi! ✅`)
    } catch (error) {
      console.error('Miqdor o\'rnatish xatosi:', error)
      alert('Miqdorni o\'rnatishda xatolik yuz berdi')
    } finally {
      setIsLoadingModal(false)
    }
  }

  const handleChangePharmacyPassword = async (newPassword) => {
    if (!selectedPharmacy) return
    setIsLoadingModal(true)
    try {
      await changePharmacyPassword(selectedPharmacy.id, newPassword)
      setShowChangePasswordModal(false)
      setSelectedPharmacy(null)
      alert(`${selectedPharmacy.name} ning parol muvaffaqiyatli o'zgartirildi! ✅`)
    } catch (error) {
      console.error('Parol o\'zgartirish xatosi:', error)
      alert('Parolni o\'zgartirishda xatolik yuz berdi')
    } finally {
      setIsLoadingModal(false)
    }
  }

  const handleSetPharmacyAmount = async (data) => {
    if (!selectedPharmacy) return
    setIsLoadingModal(true)
    try {
      await setPharmacyPaymentAmount(selectedPharmacy.id, data.amount, data.description)
      setShowSetAmountModal(false)
      setSelectedPharmacy(null)
      alert(`${selectedPharmacy.name} ning to'lov miqdori muvaffaqiyatli o'rnatildi! ✅`)
    } catch (error) {
      console.error('Miqdor o\'rnatish xatosi:', error)
      alert('Miqdorni o\'rnatishda xatolik yuz berdi')
    } finally {
      setIsLoadingModal(false)
    }
  }

  const openClinicPasswordModal = (clinic) => {
    setSelectedClinic(clinic)
    setSelectedPharmacy(null)
    setShowChangePasswordModal(true)
  }

  const openClinicAmountModal = (clinic) => {
    setSelectedClinic(clinic)
    setSelectedPharmacy(null)
    setShowSetAmountModal(true)
  }

  const openPharmacyPasswordModal = (pharmacy) => {
    setSelectedPharmacy(pharmacy)
    setSelectedClinic(null)
    setShowChangePasswordModal(true)
  }

  const openPharmacyAmountModal = (pharmacy) => {
    setSelectedPharmacy(pharmacy)
    setSelectedClinic(null)
    setShowSetAmountModal(true)
  }
  const normalizedClinics = clinics.map((clinic) => ({
    ...clinic,
    owner: clinic.owner || clinic.owner_name || clinic.owner_email || '',
    ownerName: clinic.owner_name || '',
    clinicEmail: clinic.email || '',
    city: clinic.city || clinic.address || '',
    phone: clinic.phone || clinic.phone_number || '',
    paid: typeof clinic.paid === 'boolean' ? clinic.paid : clinic.status === 'active',
    amount: clinic.amount || 0,
    paymentDate: clinic.payment_date
  }))

  const normalizedPharmacies = pharmacies.map((pharmacy) => ({
    ...pharmacy,
    owner: pharmacy.owner || pharmacy.owner_name || pharmacy.owner_email || '',
    ownerName: pharmacy.owner_name || '',
    pharmacyEmail: pharmacy.email || '',
    city: pharmacy.city || pharmacy.address || '',
    phone: pharmacy.phone || pharmacy.phone_number || '',
    paid: typeof pharmacy.paid === 'boolean' ? pharmacy.paid : pharmacy.status === 'active',
    amount: pharmacy.amount || 0,
    paymentDate: pharmacy.payment_date
  }))

  const filteredClinics = normalizedClinics.filter(clinic => {
    const matchesSearch = 
      clinic.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      clinic.owner.toLowerCase().includes(searchTerm.toLowerCase()) ||
      clinic.city.toLowerCase().includes(searchTerm.toLowerCase())
    
    const matchesFilter = 
      filterStatus === 'all' ||
      (filterStatus === 'active' && clinic.status === 'active') ||
      (filterStatus === 'suspended' && clinic.status === 'suspended') ||
      (filterStatus === 'unpaid' && !clinic.paid)
    
    return matchesSearch && matchesFilter
  })

  const filteredPharmacies = normalizedPharmacies.filter(pharmacy => {
    const matchesSearch = 
      pharmacy.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      pharmacy.owner.toLowerCase().includes(searchTerm.toLowerCase()) ||
      pharmacy.city.toLowerCase().includes(searchTerm.toLowerCase())
    
    const matchesFilter = 
      filterStatus === 'all' ||
      (filterStatus === 'active' && pharmacy.status === 'active') ||
      (filterStatus === 'suspended' && pharmacy.status === 'suspended') ||
      (filterStatus === 'unpaid' && !pharmacy.paid)
    
    return matchesSearch && matchesFilter
  })

  const formatCompactAmount = (value) => {
    const amount = Number(value) || 0
    if (amount >= 1_000_000_000) {
      const num = (amount / 1_000_000_000).toFixed(1).replace(/\.0$/, '')
      return `${num} mlrd`
    }
    if (amount >= 1_000_000) {
      const num = (amount / 1_000_000).toFixed(1).replace(/\.0$/, '')
      return `${num} mln`
    }
    if (amount >= 1_000) {
      const num = (amount / 1_000).toFixed(1).replace(/\.0$/, '')
      return `${num} ming`
    }
    return amount.toLocaleString()
  }

  const stats = {
    totalClinics: normalizedClinics.length,
    activeClinics: normalizedClinics.filter(c => c.status === 'active').length,
    suspendedClinics: normalizedClinics.filter(c => c.status === 'suspended').length,
    paidClinics: normalizedClinics.filter(c => c.paid).length,
    totalRevenueClinic: normalizedClinics.reduce((sum, c) => sum + (Number(c.amount) || 0), 0),
    totalPharmacies: normalizedPharmacies.length,
    activePharmacies: normalizedPharmacies.filter(p => p.status === 'active').length,
    suspendedPharmacies: normalizedPharmacies.filter(p => p.status === 'suspended').length,
    paidPharmacies: normalizedPharmacies.filter(p => p.paid).length,
    totalRevenuePharmacy: normalizedPharmacies.reduce((sum, p) => sum + (Number(p.amount) || 0), 0)
  }

  return (
    <div className="admin-dashboard">
      {/* Top Bar */}
      <div className="admin-header">
        <div className="header-left">
          <h1>🔐 Admin Panel</h1>
          <p className="header-info">Tizim boshqaruvchi: {admin.email || admin.username}</p>
        </div>
        <button 
          className="btn-logout"
          onClick={() => {
            logoutAdmin()
            navigate('/admin-login')
          }}
        >
          Chiqish →
        </button>
      </div>

      {/* Stats Section */}
      <div className="stats-section">
        {/* Clinic Stats */}
        <div className="stats-category">
          <h3 className="category-title">🏥 Klinikalar Statistikasi</h3>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-icon">🏥</div>
              <div className="stat-info">
                <p className="stat-label">Jami Klinikalar</p>
                <p className="stat-number">{stats.totalClinics}</p>
              </div>
            </div>

            <div className="stat-card active">
              <div className="stat-icon">✅</div>
              <div className="stat-info">
                <p className="stat-label">Faol Klinikalar</p>
                <p className="stat-number">{stats.activeClinics}</p>
              </div>
            </div>

            <div className="stat-card suspended">
              <div className="stat-icon">⛔</div>
              <div className="stat-info">
                <p className="stat-label">Yopilgan Klinikalar</p>
                <p className="stat-number">{stats.suspendedClinics}</p>
              </div>
            </div>

            <div className="stat-card revenue clinic-revenue">
              <div className="stat-icon">💵</div>
              <div className="stat-info">
                <p className="stat-label">Klinikalar Daromadi</p>
                <p className="stat-number">{formatCompactAmount(stats.totalRevenueClinic)} so'm</p>
              </div>
            </div>
          </div>
        </div>

        {/* Pharmacy Stats */}
        <div className="stats-category">
          <h3 className="category-title">💊 Dorixonalar Statistikasi</h3>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-icon">💊</div>
              <div className="stat-info">
                <p className="stat-label">Jami Dorixonalar</p>
                <p className="stat-number">{stats.totalPharmacies}</p>
              </div>
            </div>

            <div className="stat-card active">
              <div className="stat-icon">✅</div>
              <div className="stat-info">
                <p className="stat-label">Faol Dorixonalar</p>
                <p className="stat-number">{stats.activePharmacies}</p>
              </div>
            </div>

            <div className="stat-card suspended">
              <div className="stat-icon">⛔</div>
              <div className="stat-info">
                <p className="stat-label">Yopilgan Dorixonalar</p>
                <p className="stat-number">{stats.suspendedPharmacies}</p>
              </div>
            </div>

            <div className="stat-card revenue pharmacy-revenue">
              <div className="stat-icon">💰</div>
              <div className="stat-info">
                <p className="stat-label">Dorixonalar Daromadi</p>
                <p className="stat-number">{formatCompactAmount(stats.totalRevenuePharmacy)} so'm</p>
              </div>
            </div>
          </div>
        </div>

        {/* Total Revenue */}
        <div className="stats-category">
          <h3 className="category-title">📊 Umumiy Daromad</h3>
          <div className="stats-grid stats-grid-single">
            <div className="stat-card revenue total-revenue">
              <div className="stat-icon">💎</div>
              <div className="stat-info">
                <p className="stat-label">Jami Daromad (Klinikalar + Dorixonalar)</p>
                <p className="stat-number">{formatCompactAmount(stats.totalRevenueClinic + stats.totalRevenuePharmacy)} so'm</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="tab-navigation">
        <button 
          className={`tab-btn ${activeTab === 'clinics' ? 'active' : ''}`}
          onClick={() => setActiveTab('clinics')}
        >
          🏥 Klinikalar ({normalizedClinics.length})
        </button>
        <button 
          className={`tab-btn ${activeTab === 'pharmacies' ? 'active' : ''}`}
          onClick={() => setActiveTab('pharmacies')}
        >
          💊 Dorixonalar ({normalizedPharmacies.length})
        </button>
        <button 
          className={`tab-btn ${activeTab === 'contact' ? 'active' : ''}`}
          onClick={() => setActiveTab('contact')}
        >
          📞 Bog'lanish
          {unreadLeadsCount > 0 ? (
            <span className="tab-badge" aria-label="Yangi xabarlar">
              {unreadLeadsCount}
            </span>
          ) : null}
        </button>
        <button
          className={`tab-btn ${activeTab === 'alerts' ? 'active' : ''}`}
          onClick={() => setActiveTab('alerts')}
        >
          🚨 Xatoliklar
          {unresolvedAlertsCount > 0 ? (
            <span className="tab-badge" aria-label="Yangi xatoliklar">
              {unresolvedAlertsCount}
            </span>
          ) : null}
        </button>
      </div>

      {/* Controls */}
      <div className="controls-section">
        {activeTab !== 'contact' && activeTab !== 'alerts' && (
        <div className="search-box">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="2"/>
            <path d="M12 12l6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          </svg>
          <input
            type="text"
            placeholder={activeTab === 'clinics' ? 'Klinika, egasi yoki shahar bo\'yicha qidiring...' : 'Dorixona, egasi yoki shahar bo\'yicha qidiring...'}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        )}

        {activeTab !== 'contact' && activeTab !== 'alerts' && (
        <div className="filter-buttons">
          {['all', 'active', 'suspended', 'unpaid'].map(status => (
            <button
              key={status}
              className={`filter-btn ${filterStatus === status ? 'active' : ''}`}
              onClick={() => setFilterStatus(status)}
            >
              {status === 'all' ? 'Hammasi' : status === 'active' ? 'Faol' : status === 'suspended' ? 'Vaqtinchalik Yopiq' : 'To\'lanmagan'}
            </button>
          ))}
        </div>
        )}

        {activeTab !== 'contact' && activeTab !== 'alerts' && (
          <button 
            className={`btn-add-clinic`}
            onClick={() => activeTab === 'clinics' ? toggleClinicForm() : togglePharmacyForm()}
          >
            {activeTab === 'clinics' ? (showAddClinic ? '✕ Bekor' : '+ Klinika Qo\'shish') : (showAddPharmacy ? '✕ Bekor' : '+ Dorixona Qo\'shish')}
          </button>
        )}
      </div>

      {/* Home Contact Settings */}
      {activeTab === 'contact' && (
        <div className="add-clinic-form">
          <div className="admin-contact-settings-header">
            <h3>Bosh sahifa: Bog'lanish bo'limi</h3>
            {homeContactCollapsed ? (
              <button type="button" className="admin-contact-settings-toggle" onClick={() => setHomeContactCollapsed(false)}>
                ✏️ Tahrirlash
              </button>
            ) : (
              <button type="button" className="admin-contact-settings-toggle" onClick={() => setHomeContactCollapsed(true)}>
                ✕ Bekor
              </button>
            )}
          </div>

          {homeContactCollapsed ? (
            <div className="admin-contact-settings-collapsed">
              <div className="admin-contact-settings-status">
                Saqlandi ✅ {homeContactSavedAt ? <span className="admin-contact-settings-time">({formatSavedAt(homeContactSavedAt)})</span> : null}
              </div>
              <div className="admin-contact-settings-summary">
                <div><strong>Telegram:</strong> {homeContactForm.telegram_link || '—'}</div>
                <div><strong>Telefon:</strong> {homeContactForm.phone_number || '—'}</div>
                <div><strong>Email:</strong> {homeContactForm.email_display || '—'}</div>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSaveHomeContact}>
              <div className="form-row">
                <div className="form-group">
                  <label>Matn</label>
                    <label>Email</label>
                    placeholder="Bog'lanish bo'limi matni"
                    value={homeContactForm.text}
                    onChange={(e) => setHomeContactForm({ ...homeContactForm, text: e.target.value })}
                      value={clinicForm.email}
                      onChange={(e) => setClinicForm({ ...clinicForm, email: e.target.value })}
                      required
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Telegram link</label>
                  <input
                    type="url"
                    placeholder="https://t.me/..."
                    value={homeContactForm.telegram_link}
                    onChange={(e) => setHomeContactForm({ ...homeContactForm, telegram_link: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label>Tel nomer</label>
                  <input
                    type="text"
                    placeholder="+998..."
                    value={homeContactForm.phone_number}
                    onChange={(e) => setHomeContactForm({ ...homeContactForm, phone_number: e.target.value })}
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Instagram link</label>
                  <input
                    type="url"
                    placeholder="https://instagram.com/..."
                    value={homeContactForm.instagram_link}
                    onChange={(e) => setHomeContactForm({ ...homeContactForm, instagram_link: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label>Email</label>
                  <input
                    type="text"
                    placeholder="support@yourdomain.uz"
                    value={homeContactForm.email_display}
                    onChange={(e) => setHomeContactForm({ ...homeContactForm, email_display: e.target.value })}
                    onBlur={(e) => setHomeContactForm({ ...homeContactForm, email_display: normalizeEmailWithDefaultDomain(e.target.value) })}
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Bog'lanish bo'limi rasmi</label>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={(e) => setHomeContactImageFile(e.target.files?.[0] || null)}
                  />
                  {homeContactImageUrl ? (
                    <img src={homeContactImageUrl} alt="Bog'lanish" className="admin-contact-image-preview" />
                  ) : null}
                </div>
              </div>

              <button className="btn-submit" type="submit" disabled={homeContactLoading}>
                {homeContactLoading ? 'Saqlanmoqda...' : 'Saqlash'}
              </button>
            </form>
          )}

          <div className="admin-contact-leads">
            <div className="admin-contact-leads-header">
              <h3>Xabarlar</h3>
              <div className="admin-contact-leads-meta">
                {contactLeadsLoading ? 'Yuklanyapti...' : `${unreadLeadsCount} ta o'qilmagan`}
              </div>
            </div>

            <div className="admin-contact-leads-list">
              {contactLeads.length === 0 ? (
                <div className="admin-contact-leads-empty">Hozircha xabarlar yo'q</div>
              ) : (
                contactLeads.map((lead) => {
                  const isUnread = lead?.is_read === false
                  const isSelected = selectedLeadId === lead.id
                  const title = (lead?.name || '').trim() || (lead?.phone_number || '').trim() || (lead?.email || '').trim() || 'Yangi xabar'
                  const snippet = (lead?.message || '').trim().slice(0, 140)

                  return (
                    <div
                      key={lead.id}
                      className={`admin-contact-lead ${isUnread ? 'unread' : 'read'} ${isSelected ? 'selected' : ''}`}
                    >
                      <button
                        type="button"
                        className="admin-contact-lead-row"
                        onClick={async () => {
                          setSelectedLeadId(isSelected ? null : lead.id)
                          if (isUnread) {
                            await handleMarkLeadRead(lead.id)
                          }
                        }}
                      >
                        <div className="admin-contact-lead-left">
                          <div className="admin-contact-lead-title">
                            {title}
                            {isUnread ? <span className="lead-pill unread">O'qilmagan</span> : <span className="lead-pill read">O'qilgan</span>}
                          </div>
                          <div className="admin-contact-lead-sub">
                            {lead?.phone_number ? `📞 ${lead.phone_number}` : ''}
                            {lead?.email ? (lead?.phone_number ? `  •  ✉️ ${lead.email}` : `✉️ ${lead.email}`) : ''}
                          </div>
                        </div>
                        <div className="admin-contact-lead-right">
                          <div className="admin-contact-lead-time">{formatLeadTime(lead?.created_at)}</div>
                          <div className="admin-contact-lead-snippet">{snippet}{(lead?.message || '').length > 140 ? '…' : ''}</div>
                        </div>
                      </button>

                      {isSelected ? (
                        <div className="admin-contact-lead-details">
                          <div className="admin-contact-lead-details-label">Xabar</div>
                          <div className="admin-contact-lead-details-text">{(lead?.message || '').trim() || '—'}</div>
                        </div>
                      ) : null}
                    </div>
                  )
                })
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'alerts' && (
        <div className="add-clinic-form">
          <div className="admin-system-alerts-header">
            <h3>Tizim xatoliklari va ogohlantirishlar</h3>
            <div className="admin-system-alerts-meta">
              {systemAlertsLoading ? 'Yuklanyapti...' : `${unresolvedAlertsCount} ta yechilmagan`}
            </div>
          </div>

          <div className="admin-system-alerts-list">
            {systemAlerts.length === 0 ? (
              <div className="admin-contact-leads-empty">Hozircha yechilmagan xatolik yo'q</div>
            ) : (
              systemAlerts.map((alertItem) => {
                const isExpanded = selectedAlertId === alertItem.id
                return (
                <div
                  key={alertItem.id}
                  className={`admin-system-alert ${alertItem.severity || 'error'} ${isExpanded ? 'expanded' : ''}`}
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelectedAlertId((prev) => (prev === alertItem.id ? null : alertItem.id))}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault()
                      setSelectedAlertId((prev) => (prev === alertItem.id ? null : alertItem.id))
                    }
                  }}
                >
                  <div className="admin-system-alert-row">
                    <div className="admin-system-alert-main">
                      <div className="admin-system-alert-title">
                        <span className={`alert-pill ${alertItem.severity || 'error'}`}>
                          {(alertItem.severity || 'error').toUpperCase()}
                        </span>
                        <strong>{alertItem.alert_type || 'system_alert'}</strong>
                      </div>
                      <div className="admin-system-alert-message">{alertItem.message || '—'}</div>
                      <div className="admin-system-alert-time">
                        {formatAlertTime(alertItem.created_at)} • {isExpanded ? 'Batafsil yopish' : 'Batafsil ochish'}
                      </div>
                    </div>
                    <button
                      type="button"
                      className="admin-system-alert-resolve"
                      onClick={(event) => {
                        event.stopPropagation()
                        handleResolveSystemAlert(alertItem.id)
                      }}
                      disabled={Boolean(alertItem.is_resolved)}
                    >
                      {alertItem.is_resolved ? 'Yechilgan' : 'Yechildi'}
                    </button>
                  </div>

                  {isExpanded ? (
                    <div className="admin-system-alert-details">
                      {(() => {
                        const details = getAlertDetails(alertItem)
                        return (
                          <>
                            <div className="admin-system-alert-grid">
                              <div className="admin-system-alert-detail-item">
                                <span className="admin-system-alert-detail-label">Nima uchun xato bo'ldi</span>
                                <span className="admin-system-alert-detail-value">{details.reason}</span>
                              </div>
                              <div className="admin-system-alert-detail-item">
                                <span className="admin-system-alert-detail-label">Xato turi</span>
                                <span className="admin-system-alert-detail-value">{details.type}</span>
                              </div>
                              <div className="admin-system-alert-detail-item">
                                <span className="admin-system-alert-detail-label">Qayerda xato</span>
                                <span className="admin-system-alert-detail-value">{details.endpoint || 'Noma\'lum'}</span>
                              </div>
                              <div className="admin-system-alert-detail-item">
                                <span className="admin-system-alert-detail-label">HTTP</span>
                                <span className="admin-system-alert-detail-value">
                                  {details.method || '—'} {details.status ? `• ${details.status}` : ''}
                                </span>
                              </div>
                              <div className="admin-system-alert-detail-item">
                                <span className="admin-system-alert-detail-label">Qaysi fayl</span>
                                <span className="admin-system-alert-detail-value">{details.file || 'Noma\'lum'}</span>
                              </div>
                              <div className="admin-system-alert-detail-item">
                                <span className="admin-system-alert-detail-label">Qator / Ustun</span>
                                <span className="admin-system-alert-detail-value">
                                  {details.line || '—'} {details.column ? `/ ${details.column}` : ''}
                                </span>
                              </div>
                              <div className="admin-system-alert-detail-item">
                                <span className="admin-system-alert-detail-label">Foydalanuvchi</span>
                                <span className="admin-system-alert-detail-value">{details.userId || 'Anonim'}</span>
                              </div>
                              <div className="admin-system-alert-detail-item">
                                <span className="admin-system-alert-detail-label">Qo'shimcha sabab</span>
                                <span className="admin-system-alert-detail-value">{details.extraReason || '—'}</span>
                              </div>
                            </div>

                            {details.firstTraceLine ? (
                              <div className="admin-system-alert-trace-head">
                                <span className="admin-system-alert-detail-label">Asosiy traceback qatori</span>
                                <span className="admin-system-alert-detail-value">{details.firstTraceLine}</span>
                              </div>
                            ) : null}

                            {details.trace ? (
                              <div className="admin-system-alert-code-block">
                                <div className="admin-system-alert-detail-label">To'liq traceback</div>
                                <pre>{details.trace}</pre>
                              </div>
                            ) : null}

                            <div className="admin-system-alert-code-block">
                              <div className="admin-system-alert-detail-label">To'liq context (JSON)</div>
                              <pre>{JSON.stringify(details.context || {}, null, 2)}</pre>
                            </div>
                          </>
                        )
                      })()}
                    </div>
                  ) : null}
                </div>
              )})
            )}
          </div>
        </div>
      )}

      {/* Add Clinic Form */}
      {showAddClinic && activeTab === 'clinics' && (
        <form className="add-clinic-form" onSubmit={handleAddClinic}>
          <h3>Yangi Klinika Qo'shish</h3>
          <div className="form-row">
            <div className="form-group">
              <label>Klinika nomi</label>
              <input
                type="text"
                placeholder="Klinika nomi"
                value={clinicForm.name}
                onChange={(e) => setClinicForm({ ...clinicForm, name: e.target.value })}
                required
              />
            </div>
            <div className="form-group">
              <label>Email</label>
              <input
                type="email"
                placeholder="clinic@example.uz"
                value={clinicForm.email}
                onChange={(e) => setClinicForm({ ...clinicForm, email: e.target.value })}
                onBlur={(e) => setClinicForm({ ...clinicForm, email: normalizeEmailWithDefaultDomain(e.target.value) })}
                required
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Egasi ismi</label>
              <input
                type="text"
                placeholder="Ism"
                value={clinicForm.ownerFirstName}
                onChange={(e) => setClinicForm({ ...clinicForm, ownerFirstName: e.target.value })}
                required
              />
            </div>
            <div className="form-group">
              <label>Egasi familiyasi</label>
              <input
                type="text"
                placeholder="Familiya"
                value={clinicForm.ownerLastName}
                onChange={(e) => setClinicForm({ ...clinicForm, ownerLastName: e.target.value })}
                required
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Egasi pasport ID</label>
              <input
                type="text"
                placeholder="AA1234567"
                value={clinicForm.ownerPassportId}
                onChange={(e) => setClinicForm({ ...clinicForm, ownerPassportId: e.target.value.replace(/\s+/g, '').toUpperCase() })}
                required
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Telefon</label>
              <input
                type="tel"
                placeholder="+998 90 123 45 67"
                value={clinicForm.phone}
                onChange={(e) => setClinicForm({ ...clinicForm, phone: e.target.value })}
                required
              />
            </div>
            <div className="form-group">
              <label>Manzil</label>
              <input
                type="text"
                placeholder="Klinika manzili"
                value={clinicForm.address}
                onChange={(e) => setClinicForm({ ...clinicForm, address: e.target.value })}
                required
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Klinika raqami</label>
              <input
                type="text"
                placeholder="CLN-..."
                value={clinicForm.registrationNumber}
                readOnly
                required
              />
              <small style={{ color: '#6b7280' }}>Avtomatik yaratiladi va takrorlanmaydi.</small>
            </div>
            <div className="form-group">
              <label>Egasi parol</label>
              <PasswordInput
                placeholder="Parol"
                value={clinicForm.password}
                onChange={(e) => setClinicForm({ ...clinicForm, password: e.target.value })}
                required
              />
            </div>
          </div>
          <button type="submit" className="btn-submit">Qo'shish</button>
        </form>
      )}

      {/* Add Pharmacy Form */}
      {showAddPharmacy && activeTab === 'pharmacies' && (
        <form className="add-clinic-form" onSubmit={handleAddPharmacy}>
          <h3>Yangi Dorixona Qo'shish</h3>
          <div className="form-row">
            <div className="form-group">
              <label>Dorixona nomi</label>
              <input
                type="text"
                placeholder="Dorixona nomi"
                value={pharmacyForm.name}
                onChange={(e) => setPharmacyForm({ ...pharmacyForm, name: e.target.value })}
                required
              />
            </div>
            <div className="form-group">
              <label>Dorixona email</label>
              <input
                type="email"
                placeholder="pharmacy@example.uz"
                value={pharmacyForm.pharmacyEmail}
                onChange={(e) => setPharmacyForm({ ...pharmacyForm, pharmacyEmail: e.target.value })}
                onBlur={(e) => setPharmacyForm({ ...pharmacyForm, pharmacyEmail: normalizeEmailWithDefaultDomain(e.target.value) })}
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Egasi ismi</label>
              <input
                type="text"
                placeholder="Ism"
                value={pharmacyForm.ownerFirstName}
                onChange={(e) => setPharmacyForm({ ...pharmacyForm, ownerFirstName: e.target.value })}
                required
              />
            </div>
            <div className="form-group">
              <label>Egasi familiyasi</label>
              <input
                type="text"
                placeholder="Familiya"
                value={pharmacyForm.ownerLastName}
                onChange={(e) => setPharmacyForm({ ...pharmacyForm, ownerLastName: e.target.value })}
                required
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Egasi email</label>
              <input
                type="email"
                placeholder="owner@example.uz"
                value={pharmacyForm.ownerEmail}
                onChange={(e) => setPharmacyForm({ ...pharmacyForm, ownerEmail: e.target.value })}
                onBlur={(e) => setPharmacyForm({ ...pharmacyForm, ownerEmail: normalizeEmailWithDefaultDomain(e.target.value) })}
                required
              />
            </div>
            <div className="form-group">
              <label>Egasi telefon</label>
              <input
                type="tel"
                placeholder="+998 90 123 45 67"
                value={pharmacyForm.ownerPhone}
                onChange={(e) => setPharmacyForm({ ...pharmacyForm, ownerPhone: e.target.value })}
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Telefon</label>
              <input
                type="tel"
                placeholder="+998 90 123 45 67"
                value={pharmacyForm.phone}
                onChange={(e) => setPharmacyForm({ ...pharmacyForm, phone: e.target.value })}
                required
              />
            </div>
            <div className="form-group">
              <label>Manzili</label>
              <input
                type="text"
                placeholder="Manzili"
                value={pharmacyForm.address}
                onChange={(e) => setPharmacyForm({ ...pharmacyForm, address: e.target.value })}
                required
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Ro'yxat raqami</label>
              <input
                type="text"
                placeholder="REG-001"
                value={pharmacyForm.registrationNumber}
                onChange={(e) => setPharmacyForm({ ...pharmacyForm, registrationNumber: e.target.value })}
                required
              />
            </div>
            <div className="form-group">
              <label>Egasi parol</label>
              <PasswordInput
                placeholder="Parol"
                value={pharmacyForm.password}
                onChange={(e) => setPharmacyForm({ ...pharmacyForm, password: e.target.value })}
                required
              />
            </div>
          </div>
          <button type="submit" className="btn-submit">Qo'shish</button>
        </form>
      )}

      {/* Clinics Table */}
      {activeTab === 'clinics' && (
        <div className="clinics-section">
          <div className="table-header">
            <h2>🏥 Klinikalarda ro'yxat ({filteredClinics.length})</h2>
          </div>

          <div className="table-container">
            <table className="clinics-table">
              <thead>
                <tr>
                  <th>Klinika</th>
                  <th>Klinika raqami</th>
                  <th>Email</th>
                  <th>Egasi</th>
                  <th>Telefon</th>
                  <th>Manzil</th>
                  <th>To'lov</th>
                  <th>Status</th>
                  <th>Harakatlar</th>
                </tr>
              </thead>
              <tbody>
                {filteredClinics.map(clinic => (
                  <tr key={clinic.id} className={`status-${clinic.status}`}>
                    <td className="clinic-name">
                      {clinic.name}
                    </td>
                    <td>
                      <code>{clinic.registration_number || '—'}</code>
                    </td>
                    <td className="email-cell">
                      <a href={`mailto:${clinic.clinicEmail}`} title={clinic.clinicEmail}>
                        {clinic.clinicEmail}
                      </a>
                    </td>
                    <td>{clinic.ownerName}</td>
                    <td>
                      <a href={`tel:${clinic.phone}`} className="phone-link">
                        {clinic.phone}
                      </a>
                    </td>
                    <td>{clinic.address || 'Manzil kiritilmagan'}</td>
                    <td>
                      <div className={`payment-badge ${clinic.paid ? 'paid' : 'unpaid'}`}>
                        {clinic.paid ? '✅ To\'landi' : '❌ To\'lanmadi'}
                      </div>
                      <small>{clinic.amount.toLocaleString()} so'm</small>
                    </td>
                    <td>
                      <span className={`status-badge status-${clinic.status}`}>
                        {clinic.status === 'active' ? '✅ Faol' : '🔴 Yopiq'}
                      </span>
                    </td>
                    <td>
                      <div className="action-buttons">
                        <button
                          className="btn-action password"
                          onClick={() => openClinicPasswordModal(clinic)}
                          title="Parolni O'zgartirish"
                        >
                          🔐
                        </button>

                        <button
                          className="btn-action amount"
                          onClick={() => openClinicAmountModal(clinic)}
                          title="To'lov Miqdori O'rnatish"
                        >
                          💵
                        </button>

                        <button
                          className="btn-action amount"
                          onClick={async () => {
                            try {
                              const result = await generateClinicPaymentLink(clinic.id, false)
                              window.prompt("To'lov linki:", result.payment_url)
                            } catch (error) {
                              alert(`Link yaratishda xatolik: ${error.message}`)
                            }
                          }}
                          title="Online to'lov linkini yaratish"
                        >
                          🔗
                        </button>

                        <button
                          className="btn-action amount"
                          onClick={async () => {
                            try {
                              await generateClinicPaymentLink(clinic.id, true)
                              alert('To\'lov linki emailga yuborildi! ✅')
                            } catch (error) {
                              alert(`Email yuborishda xatolik: ${error.message}`)
                            }
                          }}
                          title="Email orqali to'lov linkini yuborish"
                        >
                          📧
                        </button>

                        <button
                          className="btn-action approve"
                          onClick={async () => {
                            if (window.confirm(`${clinic.name} obunasini 30 kunga faollashtirasizmi?`)) {
                              try {
                                await approveClinicSubscription(clinic.id)
                                alert('Obuna 30 kunga faollashtirildi! ✅')
                              } catch (error) {
                                console.error('Obunani faollashtirish xatosi:', error)
                                alert(`Xatolik: ${error.message}`)
                              }
                            }
                          }}
                          title="Obunani 30 kunga faollashtirish (qo'lda tasdiqlash)"
                        >
                          ✅
                        </button>
                        
                        {!clinic.paid && (
                          <button
                            className="btn-action paid"
                            onClick={() => {
                              markClinicPaid(clinic.id)
                              alert(`${clinic.name} faol holga o'tkazildi! ✅`)
                            }}
                            title="To'lovni Tasdiqlash"
                          >
                            💰
                          </button>
                        )}
                        
                        <button
                          className={`btn-action ${clinic.status === 'active' ? 'suspend' : 'activate'}`}
                          onClick={async () => {
                            try {
                              await toggleClinicStatus(clinic.id)
                              alert(`${clinic.name} ${clinic.status === 'active' ? 'vaqtinchalik yopildi' : 'faol qilindi'}! ✅`)
                            } catch (error) {
                              console.error('Status o\'zgartirish xatosi:', error)
                              alert(`Status o'ngartirishda xatolik: ${error.response?.data?.detail || error.message}`)
                            }
                          }}
                          title={clinic.status === 'active' ? 'Yopish' : 'Ochish'}
                        >
                          {clinic.status === 'active' ? '🔒' : '🔓'}
                        </button>

                        <button
                          className="btn-action delete"
                          onClick={async () => {
                            if (window.confirm(`${clinic.name} o'chirilsinmi?`)) {
                              try {
                                await deleteClinic(clinic.id)
                                alert('Klinika o\'chirildi! ✅')
                              } catch (error) {
                                console.error('O\'chirish xatosi:', error)
                                alert(`O'chirishda xatolik: ${error.response?.data?.detail || error.message}`)
                              }
                            }
                          }}
                          title="O'chirish"
                        >
                          🗑️
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Pharmacies Table */}
      {activeTab === 'pharmacies' && (
        <div className="clinics-section">
          <div className="table-header">
            <h2>💊 Dorixonalarda ro'yxat ({filteredPharmacies.length})</h2>
          </div>

          <div className="table-container">
            <table className="clinics-table">
              <thead>
                <tr>
                  <th>Dorixona</th>
                  <th>Email</th>
                  <th>Egasi</th>
                  <th>Telefon</th>
                  <th>Manzil</th>
                  <th>To'lov</th>
                  <th>Status</th>
                  <th>Harakatlar</th>
                </tr>
              </thead>
              <tbody>
                {filteredPharmacies.map(pharmacy => (
                  <tr key={pharmacy.id} className={`status-${pharmacy.status}`}>
                    <td className="clinic-name">
                      {pharmacy.name}
                    </td>
                    <td className="email-cell">
                      <a href={`mailto:${pharmacy.pharmacyEmail}`} title={pharmacy.pharmacyEmail}>
                        {pharmacy.pharmacyEmail}
                      </a>
                    </td>
                    <td>{pharmacy.ownerName}</td>
                    <td>
                      <a href={`tel:${pharmacy.phone}`} className="phone-link">
                        {pharmacy.phone}
                      </a>
                    </td>
                    <td>{pharmacy.address || 'Manzil kiritilmagan'}</td>
                    <td>
                      <div className={`payment-badge ${pharmacy.paid ? 'paid' : 'unpaid'}`}>
                        {pharmacy.paid ? '✅ To\'landi' : '❌ To\'lanmadi'}
                      </div>
                      <small>{pharmacy.amount.toLocaleString()} so'm</small>
                    </td>
                    <td>
                      <span className={`status-badge status-${pharmacy.status}`}>
                        {pharmacy.status === 'active' ? '✅ Faol' : '🔴 Yopiq'}
                      </span>
                    </td>
                    <td>
                      <div className="action-buttons">
                        <button
                          className="btn-action password"
                          onClick={() => openPharmacyPasswordModal(pharmacy)}
                          title="Parolni O'zgartirish"
                        >
                          🔐
                        </button>

                        <button
                          className="btn-action amount"
                          onClick={() => openPharmacyAmountModal(pharmacy)}
                          title="To'lov Miqdori O'rnatish"
                        >
                          💵
                        </button>

                        <button
                          className="btn-action amount"
                          onClick={async () => {
                            try {
                              const result = await generatePharmacyPaymentLink(pharmacy.id, false)
                              window.prompt("To'lov linki:", result.payment_url)
                            } catch (error) {
                              alert(`Link yaratishda xatolik: ${error.message}`)
                            }
                          }}
                          title="Online to'lov linkini yaratish"
                        >
                          🔗
                        </button>

                        <button
                          className="btn-action amount"
                          onClick={async () => {
                            try {
                              await generatePharmacyPaymentLink(pharmacy.id, true)
                              alert('To\'lov linki emailga yuborildi! ✅')
                            } catch (error) {
                              alert(`Email yuborishda xatolik: ${error.message}`)
                            }
                          }}
                          title="Email orqali to'lov linkini yuborish"
                        >
                          📧
                        </button>

                        <button
                          className="btn-action approve"
                          onClick={async () => {
                            if (window.confirm(`${pharmacy.name} obunasini 30 kunga faollashtirasizmi?`)) {
                              try {
                                await approvePharmacySubscription(pharmacy.id)
                                alert('Obuna 30 kunga faollashtirildi! ✅')
                              } catch (error) {
                                console.error('Obunani faollashtirish xatosi:', error)
                                alert(`Xatolik: ${error.message}`)
                              }
                            }
                          }}
                          title="Obunani 30 kunga faollashtirish (qo'lda tasdiqlash)"
                        >
                          ✅
                        </button>
                        
                        {!pharmacy.paid && (
                          <button
                            className="btn-action paid"
                            onClick={() => {
                              markPharmacyPaid(pharmacy.id)
                              alert(`${pharmacy.name} faol holga o'tkazildi! ✅`)
                            }}
                            title="To'lovni Tasdiqlash"
                          >
                            💰
                          </button>
                        )}
                        
                        <button
                          className={`btn-action ${pharmacy.status === 'active' ? 'suspend' : 'activate'}`}
                          onClick={async () => {
                            try {
                              await togglePharmacyStatus(pharmacy.id)
                              alert(`${pharmacy.name} ${pharmacy.status === 'active' ? 'vaqtinchalik yopildi' : 'faol qilindi'}! ✅`)
                            } catch (error) {
                              console.error('Status o\'zgartirish xatosi:', error)
                              alert(`Status o'ngartirishda xatolik: ${error.response?.data?.detail || error.message}`)
                            }
                          }}
                          title={pharmacy.status === 'active' ? 'Yopish' : 'Ochish'}
                        >
                          {pharmacy.status === 'active' ? '🔒' : '🔓'}
                        </button>

                        <button
                          className="btn-action delete"
                          onClick={async () => {
                            if (window.confirm(`${pharmacy.name} o'chirilsinmi?`)) {
                              try {
                                await deletePharmacy(pharmacy.id)
                                alert('Dorixona o\'chirildi! ✅')
                              } catch (error) {
                                console.error('O\'chirish xatosi:', error)
                                alert(`O'chirishda xatolik: ${error.response?.data?.detail || error.message}`)
                              }
                            }
                          }}
                          title="O'chirish"
                        >
                          🗑️
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Change Password Modal */}
      <ChangePasswordModal
        isOpen={showChangePasswordModal}
        clinic={selectedClinic || selectedPharmacy}
        onClose={() => {
          setShowChangePasswordModal(false)
          setSelectedClinic(null)
          setSelectedPharmacy(null)
        }}
        onSubmit={selectedClinic ? handleChangeClinicPassword : handleChangePharmacyPassword}
        isLoading={isLoadingModal}
      />

      {/* Set Payment Amount Modal */}
      <SetPaymentAmountModal
        isOpen={showSetAmountModal}
        clinic={selectedClinic || selectedPharmacy}
        onClose={() => {
          setShowSetAmountModal(false)
          setSelectedClinic(null)
          setSelectedPharmacy(null)
        }}
        onSubmit={selectedClinic ? handleSetClinicAmount : handleSetPharmacyAmount}
        isLoading={isLoadingModal}
      />
    </div>
  )}

export default AdminDashboard