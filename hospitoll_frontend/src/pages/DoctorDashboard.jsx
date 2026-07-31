import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDoctor } from '../context/DoctorContext'
import { clinicsApi, patientsApi } from '../services/api'
import PasswordInput from '../components/PasswordInput'
import MedicineAutocomplete from '../components/MedicineAutocomplete'
import { normalizeEmailWithDefaultDomain } from '../utils/helpers'
import { formatCurrencyInput, parseCurrencyInput } from '../utils/currency'
import './DoctorDashboard.css'

const FIRST_WORK_YEAR_MIN = 1950

const formatBirthDateLabel = (dateValue) => {
  if (!dateValue) {
    return 'Kiritilmagan'
  }

  const raw = String(dateValue).trim()
  const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (match) {
    return `${match[1]}-${match[2]}-${match[3]}`
  }

  return 'Kiritilmagan'
}

const sanitizeFirstWorkYearDraft = (value) => String(value || '').replace(/\D+/g, '').slice(0, 4)

const normalizeFirstWorkYear = (value, currentYear) => {
  const digitsOnly = sanitizeFirstWorkYearDraft(value)
  if (!digitsOnly) return ''

  const yearNumber = Number(digitsOnly)
  if (!Number.isFinite(yearNumber)) return ''
  if (yearNumber < FIRST_WORK_YEAR_MIN) return String(FIRST_WORK_YEAR_MIN)
  if (yearNumber > currentYear) return String(currentYear)
  return String(yearNumber)
}

const parseFirstWorkYear = (value, currentYear) => {
  const normalized = normalizeFirstWorkYear(value, currentYear)
  if (!normalized) return null
  return Number(normalized)
}

const calculateExperiencePreview = (firstWorkYear, firstWorkMonth, nowDate = new Date()) => {
  if (!Number.isFinite(firstWorkYear) || firstWorkYear < FIRST_WORK_YEAR_MIN) return null

  const currentYear = nowDate.getFullYear()
  const currentMonth = nowDate.getMonth() + 1
  let years = currentYear - firstWorkYear

  if (Number.isFinite(firstWorkMonth) && firstWorkMonth >= 1 && firstWorkMonth <= 12 && currentMonth < firstWorkMonth) {
    years -= 1
  }

  return Math.max(0, years)
}

const getApiErrorMessage = (error, fallback = 'Sozlamalarni saqlashda xatolik yuz berdi') => {
  const responseData = error?.response?.data
  if (typeof responseData === 'string' && responseData.trim()) {
    return responseData
  }
  if (responseData && typeof responseData === 'object') {
    if (responseData.detail) return String(responseData.detail)
    if (responseData.message) return String(responseData.message)

    const firstValue = Object.values(responseData).find((value) => {
      if (Array.isArray(value)) return value.length > 0
      return value !== null && value !== undefined && String(value).trim() !== ''
    })

    if (Array.isArray(firstValue) && firstValue.length > 0) {
      return String(firstValue[0])
    }
    if (firstValue !== undefined && firstValue !== null) {
      return String(firstValue)
    }
  }

  return error?.message || fallback
}

const createInitialNewVisitForm = () => ({
  complaint: '',
  diagnosis: '',
  medicines: ''
})

const createInitialQueueCancelConfirm = () => ({
  open: false,
  appointment: null,
})

const DEFAULT_PHONE_PREFIX = '+998'

const createInitialPatientForm = () => ({
  fullName: '',
  phone: DEFAULT_PHONE_PREFIX,
  complaint: '',
  diagnosis: '',
  medicines: '',
  fatherName: '',
  motherName: '',
  guardianName: '',
  email: '',
  password: ''
})

const DoctorDashboard = () => {
  const navigate = useNavigate()
  const {
    doctor,
    doctorStatus,
    specialtyPrices,
    onlineAppointments,
    appointmentsLoading,
    loading,
    cancelTodaysAppointments,
    addPatient,
    loadOnlineAppointments,
    acceptOnlineAppointment,
    getPatientsTodayAndYesterday,
    getPatientHistory,
    searchPatientByPassport,
    searchPatientInDatabase,
    addVisitToPatient,
    addExistingPatientVisit,
    getDoctorStats,
    loadDoctorDashboardStats,
    notifyOnlineAppointmentReady,
    applyQueueDecision,
    logoutDoctor,
    loadSpecialtyPrices,
    updateSpecialtyPrice,
    uploadDoctorProfileImage,
    removeDoctorProfileImage,
    updateDoctorProfileSettings
  } = useDoctor()
  const [showAddPatient, setShowAddPatient] = useState(false)
  const [selectedPatient, setSelectedPatient] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [databaseSearchResults, setDatabaseSearchResults] = useState([])
  const [showSearchResults, setShowSearchResults] = useState(false)
  const searchRequestSeqRef = useRef(0)
  const [existingPatientSelected, setExistingPatientSelected] = useState(null)
  const [showSpecialtyPrices, setShowSpecialtyPrices] = useState(false)
  const [editingPriceId, setEditingPriceId] = useState(null)
  const [priceInputs, setPriceInputs] = useState({})
  const [priceInputClearedOnFocus, setPriceInputClearedOnFocus] = useState({})
  const [newVisitForm, setNewVisitForm] = useState(createInitialNewVisitForm)
  const [showNewVisitForm, setShowNewVisitForm] = useState(false)
  const [queueDecisionLoading, setQueueDecisionLoading] = useState({})
  const [queueCancelConfirm, setQueueCancelConfirm] = useState(createInitialQueueCancelConfirm)
  const [cancelTodayConfirmOpen, setCancelTodayConfirmOpen] = useState(false)
  const [cancelTodayLoading, setCancelTodayLoading] = useState(false)
  const [selectedAvatarFile, setSelectedAvatarFile] = useState(null)
  const [avatarPreviewUrl, setAvatarPreviewUrl] = useState('')
  const [avatarSaving, setAvatarSaving] = useState(false)
  const [showAvatarMenu, setShowAvatarMenu] = useState(false)
  const [showSettingsPanel, setShowSettingsPanel] = useState(false)
  const [settingsSaving, setSettingsSaving] = useState(false)
  const [settingsCertificateFile, setSettingsCertificateFile] = useState(null)
  const [settingsForm, setSettingsForm] = useState({
    firstName: '',
    lastName: '',
    email: '',
    phone: DEFAULT_PHONE_PREFIX,
    bio: '',
    pinfl: '',
    passportId: '',
    licenseNumber: '',
    diplomaNumber: '',
    firstWorkYear: '',
    slotMinutes: 30,
  })
  const avatarFileInputRef = useRef(null)
  const avatarActionWrapRef = useRef(null)
  const noticeTimerRef = useRef(null)
  const [patientForm, setPatientForm] = useState(createInitialPatientForm)
  const [notice, setNotice] = useState({ open: false, type: 'info', text: '' })
  const currentYear = new Date().getFullYear()

  const showNotice = (text, type = 'info') => {
    if (noticeTimerRef.current) {
      window.clearTimeout(noticeTimerRef.current)
    }
    setNotice({ open: true, type, text: String(text || '') })
    noticeTimerRef.current = window.setTimeout(() => {
      setNotice((prev) => ({ ...prev, open: false }))
    }, 2800)
  }

  const [staffInbox, setStaffInbox] = useState([])
  const [staffInboxLoading, setStaffInboxLoading] = useState(false)
  const loadStaffInbox = async () => {
    setStaffInboxLoading(true)
    try {
      const items = await clinicsApi.getStaffInboxMessages({ unread: true, limit: 5 })
      setStaffInbox(Array.isArray(items) ? items : [])
    } catch (e) {
      // Silent fail to avoid blocking doctor work
      setStaffInbox([])
    } finally {
      setStaffInboxLoading(false)
    }
  }

  useEffect(() => {
    if (loading) {
      return
    }
    if (!doctor) {
      navigate('/doctor-login', { replace: true })
      return
    }
    loadOnlineAppointments(doctor.id)
    loadStaffInbox()
  }, [doctor, loading, navigate])

  useEffect(() => {
    if (!doctor) return
    const id = setInterval(() => {
      loadStaffInbox()
    }, 20000)
    return () => clearInterval(id)
  }, [doctor])

  useEffect(() => {
    if (!doctor) return

    loadDoctorDashboardStats()
    const id = setInterval(() => {
      if (typeof document !== 'undefined' && document.visibilityState !== 'visible') return
      loadDoctorDashboardStats()
    }, 15000)

    return () => clearInterval(id)
  }, [doctor])

  useEffect(() => {
    if (!doctor) return
    setSettingsForm({
      firstName: doctor.firstName || '',
      lastName: doctor.lastName || '',
      email: doctor.email || '',
      phone: doctor.phone || DEFAULT_PHONE_PREFIX,
      bio: doctor.bio || '',
      pinfl: doctor.pinfl || '',
      passportId: doctor.passportId || '',
      licenseNumber: doctor.licenseNumber || '',
      diplomaNumber: doctor.diplomaNumber || '',
      firstWorkYear: doctor.firstWorkYear || '',
      slotMinutes: Number(doctor.slotMinutes || 30),
    })
    setSettingsCertificateFile(null)
  }, [doctor])

  useEffect(() => {
    if (!selectedAvatarFile) {
      setAvatarPreviewUrl('')
      return
    }
    const objectUrl = URL.createObjectURL(selectedAvatarFile)
    setAvatarPreviewUrl(objectUrl)
    return () => URL.revokeObjectURL(objectUrl)
  }, [selectedAvatarFile])

  useEffect(() => {
    if (!showAvatarMenu) return

    const handleOutsideClick = (event) => {
      if (!avatarActionWrapRef.current) return
      if (avatarActionWrapRef.current.contains(event.target)) return
      setShowAvatarMenu(false)
    }

    document.addEventListener('mousedown', handleOutsideClick)
    document.addEventListener('touchstart', handleOutsideClick)

    return () => {
      document.removeEventListener('mousedown', handleOutsideClick)
      document.removeEventListener('touchstart', handleOutsideClick)
    }
  }, [showAvatarMenu])

  useEffect(() => {
    if (!queueCancelConfirm.open && !cancelTodayConfirmOpen) return

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setQueueCancelConfirm(createInitialQueueCancelConfirm())
        setCancelTodayConfirmOpen(false)
      }
    }

    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [queueCancelConfirm.open, cancelTodayConfirmOpen])

  useEffect(() => {
    return () => {
      if (noticeTimerRef.current) {
        window.clearTimeout(noticeTimerRef.current)
      }
    }
  }, [])

  if (loading) {
    return <div style={{ padding: '20px', textAlign: 'center' }}>Yuklanyapti...</div>
  }

  if (!doctor) {
    return null
  }

  const handleRequestCancelTodaysAppointments = () => {
    if (!canPractice) {
      showNotice('Siz klinikada faol emassiz. Bugungi qabulni bekor qila olmaysiz.', 'warning')
      return
    }
    setCancelTodayConfirmOpen(true)
  }

  const handleConfirmCancelTodaysAppointments = async () => {
    setCancelTodayLoading(true)
    try {
      const result = await cancelTodaysAppointments()
      const cancelledCount = Number(result?.cancelled_count || 0)
      if (cancelledCount > 0) {
        showNotice(`Bugungi ${cancelledCount} ta qabul bekor qilindi.`, 'success')
      } else {
        showNotice('Bugun bekor qilinadigan qabul topilmadi.', 'info')
      }
      setCancelTodayConfirmOpen(false)
    } catch (error) {
      showNotice(getApiErrorMessage(error, 'Bugungi qabullarni bekor qilishda xatolik yuz berdi'), 'error')
    } finally {
      setCancelTodayLoading(false)
    }
  }

  const formatPrice = (value) => {
    const amount = Number(value)
    if (!Number.isFinite(amount)) return '0 so‘m'
    return `${amount.toLocaleString('uz-UZ')} so‘m`
  }

  const handleStartEditSpecialtyPrice = (specialty) => {
    setEditingPriceId(specialty.id)
    setPriceInputs((prev) => ({
      ...prev,
      [specialty.id]: formatCurrencyInput(specialty.consultation_fee ?? ''),
    }))
    setPriceInputClearedOnFocus((prev) => ({
      ...prev,
      [specialty.id]: false,
    }))
  }

  const handleCancelEditSpecialtyPrice = () => {
    setEditingPriceId(null)
    setPriceInputs({})
    setPriceInputClearedOnFocus({})
  }

  const handleUpdateSpecialtyPrice = async (specialtyPriceId) => {
    const rawValue = String(priceInputs[specialtyPriceId] ?? '').trim()
    const newPrice = parseCurrencyInput(rawValue)
    if (!rawValue || !Number.isFinite(newPrice) || newPrice < 0) {
      showNotice('Iltimos, to\'g\'ri narx kiriting', 'warning')
      return
    }
    try {
      await updateSpecialtyPrice(specialtyPriceId, newPrice)
      setPriceInputs({})
      setPriceInputClearedOnFocus({})
      setEditingPriceId(null)
      showNotice('✓ Narx yangilandi!', 'success')
    } catch (error) {
      showNotice('Narxni yangilashda xatolik: ' + (error.message || ''), 'error')
    }
  }

  const handleSaveSettings = async (e) => {
    e.preventDefault()
    setSettingsSaving(true)
    try {
      const firstWorkYear = parseFirstWorkYear(settingsForm.firstWorkYear, currentYear)
      const payload = {
        first_name: settingsForm.firstName,
        last_name: settingsForm.lastName,
        email: normalizeEmailWithDefaultDomain(settingsForm.email),
        phone_number: settingsForm.phone,
        bio: settingsForm.bio,
        license_number: settingsForm.licenseNumber,
        diploma_number: settingsForm.diplomaNumber,
        first_work_year: firstWorkYear,
        slot_minutes: Number(settingsForm.slotMinutes || 30),
      }

      if (!String(settingsForm.licenseNumber || '').trim()) {
        delete payload.license_number
      }

      if (!doctor.pinfl && settingsForm.pinfl?.trim()) {
        payload.pinfl = settingsForm.pinfl.trim()
      }

      if (settingsCertificateFile) {
        const formData = new FormData()
        Object.entries(payload).forEach(([key, value]) => {
          if (value !== null && value !== undefined && value !== '') {
            formData.append(key, value)
          }
        })
        formData.append('certificate_document', settingsCertificateFile)
        await updateDoctorProfileSettings(formData)
      } else {
        await updateDoctorProfileSettings(payload)
      }

      showNotice('Sozlamalar saqlandi ✅', 'success')
      setShowSettingsPanel(false)
    } catch (error) {
      showNotice(getApiErrorMessage(error), 'error')
    } finally {
      setSettingsSaving(false)
    }
  }

  const handleAddPatient = async (e) => {
    e.preventDefault()
    
    // If we're adding an existing patient
    if (existingPatientSelected) {
      if (!existingPatientSelected.complaint) {
        showNotice('Bemor shikoyatini kiriting', 'warning')
        return
      }
      
      try {
        await addExistingPatientVisit(existingPatientSelected, {
          complaint: existingPatientSelected.complaint,
          diagnosis: existingPatientSelected.diagnosis || '',
          medicines: existingPatientSelected.medicines || ''
        })

        if (doctor?.id) {
          await loadOnlineAppointments(doctor.id)
        }
        
        setExistingPatientSelected(null)
        setShowAddPatient(false)
        setPatientForm(createInitialPatientForm())
        showNotice("Bemor qo'shildi! ✅", 'success')
      } catch (error) {
        showNotice('Bemor qo\'shishda xatolik yuz berdi: ' + (error.message || ''), 'error')
      }
      return
    }
    
    // New patient creation
    if (!patientForm.fullName || !patientForm.phone || !patientForm.complaint) {
      showNotice('Bemor ismi, telefon va shikoyatni to\'ldiring', 'warning')
      return
    }

    if (!patientForm.password) {
      showNotice('Bemor uchun parol kiriting', 'warning')
      return
    }

    try {
      const patientPayload = {
        ...patientForm,
        email: normalizeEmailWithDefaultDomain(patientForm.email),
      }
      await addPatient(patientPayload)
      setPatientForm(createInitialPatientForm())
      setShowAddPatient(false)
      showNotice(`${patientForm.fullName} qo'shildi! ✅`, 'success')
    } catch (error) {
      showNotice('Bemor qo\'shishda xatolik yuz berdi: ' + (error.message || 'Noma\'lum xatolik'), 'error')
    }
  }

  const todaysPatients = getPatientsTodayAndYesterday()
  const doctorStats = getDoctorStats
    ? getDoctorStats()
    : {
        todayPatients: 0,
        cancelledAppointments: 0,
        monthPatients: 0,
        monthRevenue: 0,
        monthBalance: 0,
        compensationType: 'salary',
        compensationValue: 0,
      }
  const canPractice = Boolean(doctor?.isActive && doctor?.isAssignedToClinic)
  const ratingDisplay = Number(doctor?.rating || 0).toFixed(1)
  const birthDateLabel = formatBirthDateLabel(doctor?.dateOfBirth)
  const firstWorkYearNumber = parseFirstWorkYear(settingsForm.firstWorkYear, currentYear)
  const firstWorkMonthNumber = Number(doctor?.firstWorkMonth)
  const computedExperiencePreview = calculateExperiencePreview(firstWorkYearNumber, firstWorkMonthNumber) ?? (doctor?.yearsOfExperience || 0)

  const handleSearch = async (e) => {
    const query = e.target.value
    setSearchQuery(query)

    const trimmedQuery = query.trim()
    const requestSeq = ++searchRequestSeqRef.current

    if (!trimmedQuery) {
      setSearchResults([])
      setDatabaseSearchResults([])
      setShowSearchResults(false)
      return
    }

    const localResults = searchPatientByPassport(trimmedQuery)
    setSearchResults(localResults)

    try {
      const dbResults = await searchPatientInDatabase(trimmedQuery)

      // If user cleared/changed query while request was in-flight, ignore stale results.
      if (requestSeq !== searchRequestSeqRef.current) return

      setDatabaseSearchResults(Array.isArray(dbResults) ? dbResults : [])
      setShowSearchResults(true)
    } catch (error) {
      if (requestSeq !== searchRequestSeqRef.current) return
      setDatabaseSearchResults([])
      setShowSearchResults(true)
    }
  }

  const handleSearchResultClick = (patient) => {
    if (patient.isExisting) {
      // For existing patients, show them in the form with a notice that they're already registered
      setExistingPatientSelected(patient)
    } else {
      // For local patients (already added by this doctor)
      setSelectedPatient(patient)
    }
    setShowSearchResults(false)
    setSearchQuery('')
  }

  const handleAddNewVisit = async (e) => {
    e.preventDefault()
    if (!canPractice) {
      showNotice('Siz klinikada faol emassiz. Faqat profilingizni tahrirlashingiz mumkin.', 'warning')
      return
    }

    if (selectedPatient && newVisitForm.complaint) {
      try {
        await Promise.resolve(addVisitToPatient(selectedPatient.id, newVisitForm))
        setSelectedPatient(getPatientHistory(selectedPatient.id))
        showNotice('Yangi tashrif qo\'shildi! ✅', 'success')
      } catch (error) {
        showNotice(error?.message || 'Yangi tashrif qo\'shishda xatolik', 'error')
        return
      }
    }

    setShowNewVisitForm(false)
    setNewVisitForm(createInitialNewVisitForm())
  }

  const handleAcceptAppointment = async (appointment) => {
    try {
      await applyQueueDecision(appointment.id, 'enter', {
        notify_current: false,
        notify_all_shifted: true,
      })
      await acceptOnlineAppointment(appointment.id)
      await notifyOnlineAppointmentReady(appointment.id)
      await loadOnlineAppointments(doctor.id)
    } catch (error) {
      showNotice(error.message || 'Qabul qilishda xatolik', 'error')
    }
  }

  const executeQueueDecision = async (appointment, decision) => {
    const loadingKey = `${appointment.id}:${decision}`
    if (queueDecisionLoading[loadingKey]) {
      return
    }

    setQueueDecisionLoading((prev) => ({ ...prev, [loadingKey]: true }))
    try {
      const result = await applyQueueDecision(appointment.id, decision)
      await loadOnlineAppointments(doctor.id)
    } catch (e) {
      const detail = e?.response?.data?.detail
      showNotice(detail || 'Navbat boshqarishda xatolik yuz berdi', 'error')
    } finally {
      setQueueDecisionLoading((prev) => ({ ...prev, [loadingKey]: false }))
    }
  }

  const handleQueueDecision = async (appointment, decision) => {
    const queueLeaderId = onlineAppointments?.[0]?.id
    if ((decision === 'enter' || decision === 'wait') && queueLeaderId && appointment?.id !== queueLeaderId) {
      showNotice('Avval navbatdagi 1-bemor bilan ishlang. Kerak bo\'lsa navbatni yangilang.', 'warning')
      return
    }

    if (decision === 'cancel') {
      setQueueCancelConfirm({ open: true, appointment })
      return
    }

    await executeQueueDecision(appointment, decision)
  }

  const handleConfirmCancelQueue = async () => {
    const appointment = queueCancelConfirm.appointment
    if (!appointment?.id) {
      setQueueCancelConfirm(createInitialQueueCancelConfirm())
      return
    }

    await executeQueueDecision(appointment, 'cancel')
    setQueueCancelConfirm(createInitialQueueCancelConfirm())
  }

  const closePatientHistory = () => {
    setSelectedPatient(null)
    setShowNewVisitForm(false)
    setNewVisitForm(createInitialNewVisitForm())
  }

  const normalizeMedicines = (medicines) => {
    if (!medicines) return []
    if (Array.isArray(medicines)) return medicines
    if (typeof medicines === 'string') return medicines.split(',')
    return []
  }

  const handleAvatarSave = async () => {
    if (!selectedAvatarFile) {
      showNotice('Rasm faylini tanlang', 'warning')
      return
    }

    setAvatarSaving(true)
    try {
      await uploadDoctorProfileImage(selectedAvatarFile)
      setSelectedAvatarFile(null)
      setShowAvatarMenu(false)
      showNotice('Profil rasmi saqlandi ✅', 'success')
    } catch (error) {
      showNotice(error?.message || 'Profil rasmini saqlashda xatolik', 'error')
    } finally {
      setAvatarSaving(false)
    }
  }

  const handleRemoveAvatar = async () => {
    if (selectedAvatarFile && !doctor?.avatarUrl) {
      setSelectedAvatarFile(null)
      setAvatarPreviewUrl('')
      setShowAvatarMenu(false)
      return
    }

    if (!doctor?.avatarUrl) return

    setAvatarSaving(true)
    try {
      await removeDoctorProfileImage()
      setSelectedAvatarFile(null)
      setAvatarPreviewUrl('')
      setShowAvatarMenu(false)
      showNotice("Profil rasmi o'chirildi ✅", 'success')
    } catch (error) {
      showNotice(error?.message || 'Profil rasmini o\'chirishda xatolik', 'error')
    } finally {
      setAvatarSaving(false)
    }
  }

  const handleAvatarInputChange = (event) => {
    const file = event.target.files?.[0] || null
    setSelectedAvatarFile(file)
    if (file) {
      setShowAvatarMenu(true)
    }
    event.target.value = ''
  }

  const openAvatarFilePicker = () => {
    avatarFileInputRef.current?.click()
  }

  const handleAvatarClick = () => {
    if (avatarSaving) return
    if (doctor?.avatarUrl || selectedAvatarFile) {
      setShowAvatarMenu((prev) => !prev)
      return
    }
    openAvatarFilePicker()
  }

  return (
    <div className="doctor-dashboard">
      {notice.open && (
        <div className={`doctor-notice doctor-notice-${notice.type}`} role="status" aria-live="polite">
          {notice.text}
        </div>
      )}

      {/* Header */}
      <div className="dash-header">
        <div className="header-left">
          <div className="avatar-action-wrap" ref={avatarActionWrapRef}>
            <button
              type="button"
              className="doctor-avatar doctor-avatar-button"
              onClick={handleAvatarClick}
              disabled={avatarSaving}
              title={doctor.avatarUrl ? 'Rasm boshqaruvi' : 'Rasm qo\'shish'}
            >
              {avatarPreviewUrl || doctor.avatarUrl ? (
                <img src={avatarPreviewUrl || doctor.avatarUrl} alt={doctor.fullName} className="doctor-avatar-image" />
              ) : (
                doctor.image
              )}
            </button>
            <input
              ref={avatarFileInputRef}
              type="file"
              accept="image/*"
              onChange={handleAvatarInputChange}
              hidden
            />
            {showAvatarMenu && (
              <div className="avatar-action-menu">
                <button
                  type="button"
                  className="avatar-action-btn avatar-action-change"
                  onClick={openAvatarFilePicker}
                  disabled={avatarSaving}
                >
                  Rasmni o‘zgartirish
                </button>
                {selectedAvatarFile && (
                  <button
                    type="button"
                    className="avatar-action-btn avatar-action-save"
                    onClick={handleAvatarSave}
                    disabled={avatarSaving}
                  >
                    {avatarSaving ? 'Saqlanmoqda...' : 'Rasmni saqlash'}
                  </button>
                )}
                {doctor.avatarUrl && (
                  <button
                    type="button"
                    className="avatar-action-btn avatar-action-remove"
                    onClick={handleRemoveAvatar}
                    disabled={avatarSaving}
                  >
                    Rasmni o‘chirish
                  </button>
                )}
                {selectedAvatarFile && <div className="avatar-action-filename">{selectedAvatarFile.name}</div>}
              </div>
            )}
          </div>
          <div>
            <h1>{doctor.fullName}</h1>
            <p className="header-subtitle">{doctor.specialization}</p>
            <p className="header-clinic">{doctor.clinicName}</p>
          </div>
        </div>
        <div className="header-right">
          <button
            className="btn-logout"
            onClick={() => {
              logoutDoctor()
              navigate('/doctor-login')
            }}
          >
            Chiqish →
          </button>
        </div>
      </div>

      {/* Clinic Staff Messages */}
      <div className="staff-inbox-bar">
        <div className="staff-inbox-title">📣 Klinika habarlari</div>
        {staffInboxLoading ? (
          <div className="staff-inbox-empty">Yuklanyapti...</div>
        ) : staffInbox.length === 0 ? (
          <div className="staff-inbox-empty">Yangi habar yo'q</div>
        ) : (
          <div className="staff-inbox-list">
            {staffInbox.map((m) => (
              <div key={m.id} className="staff-inbox-item">
                <div className="staff-inbox-body">{m.body}</div>
                <button
                  className="staff-inbox-read"
                  onClick={async () => {
                    try {
                      await clinicsApi.markStaffInboxMessageRead(m.id)
                    } finally {
                      loadStaffInbox()
                    }
                  }}
                  title="O'qildi"
                >
                  Ko'rdim
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Main Content */}
      <div className="dash-content">
        {/* Left Sidebar - Profile & Check-in */}
        <aside className="dash-sidebar">
          <section className="doctor-balance-banner" aria-label="Mening balansim">
            <div className="doctor-balance-icon" aria-hidden="true">💼</div>
            <div className="doctor-balance-content">
              <p className="doctor-balance-title">Mening balansim (shu oy)</p>
              <p className="doctor-balance-amount">{formatPrice(doctorStats.monthBalance || 0)}</p>
              <p className="doctor-balance-meta">
                {doctorStats.compensationType === 'percent'
                  ? `${doctorStats.compensationValue || 0}% × ${formatPrice(doctorStats.monthRevenue || 0)}`
                  : `Oylik maosh: ${formatPrice(doctorStats.compensationValue || 0)}`}
              </p>
            </div>
          </section>

          <div className="profile-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3>Shaxsiy Ma'lumot</h3>
              <button
                type="button"
                className="btn-toggle-prices"
                onClick={() => setShowSettingsPanel((prev) => !prev)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '16px' }}
                title="Sozlamalar"
              >
                ⚙️
              </button>
            </div>
            
            <div className="info-row">
              <span className="label">Tajriba:</span>
              <span className="value">{doctor.experience}</span>
            </div>
            
            <div className="info-row">
              <span className="label">Reyting:</span>
              <span className="value profile-rating-value">⭐ {ratingDisplay}/5</span>
            </div>
            
            <div className="info-row">
              <span className="label">Ish vaqti:</span>
              <span className="value">{doctor.availableSlots}</span>
            </div>

            <div className="info-row">
              <span className="label">Navbat oralig‘i:</span>
              <span className="value">{doctor.slotMinutes || 30} daqiqa</span>
            </div>
            
            <div className="info-row">
              <span className="label">Telefon:</span>
              <span className="value phone-link">{doctor.phone}</span>
            </div>

            <div className="info-row">
              <span className="label">Tug'ilgan sana:</span>
              <span className="value">{birthDateLabel}</span>
            </div>
            {!canPractice && (
              <div style={{ marginTop: '10px', padding: '10px', borderRadius: '8px', background: '#fff4e5', color: '#8a5700', fontSize: '13px' }}>
                Siz klinikada faol emassiz. Faqat profil ma'lumotlari va rasmingizni o'zgartira olasiz.
              </div>
            )}

            <div className={`check-status ${doctorStatus?.isCheckedIn ? 'active' : 'inactive'}`}>
              {doctorStatus?.isCheckedIn && <div className="status-badge">✅ Hozir ishda</div>}
              {doctorStatus?.isCheckedIn && doctorStatus?.checkedInTime && doctorStatus?.checkedInDate && (
                <p className="time-info">
                  {doctorStatus.checkedInTime} • {doctorStatus.checkedInDate}
                </p>
              )}
              <button
                className="btn-cancel-today"
                onClick={handleRequestCancelTodaysAppointments}
                disabled={!canPractice || cancelTodayLoading}
              >
                {cancelTodayLoading ? 'Bekor qilinmoqda...' : 'Bugungi navbatni yopish'}
              </button>
            </div>

            {showSettingsPanel && (
              <form onSubmit={handleSaveSettings} className="doctor-settings-form">
                <div className="doctor-settings-grid">
                  <div className="doctor-settings-field">
                    <label>Ism</label>
                    <input type="text" value={settingsForm.firstName} onChange={(e) => setSettingsForm((prev) => ({ ...prev, firstName: e.target.value }))} />
                  </div>
                  <div className="doctor-settings-field">
                    <label>Familiya</label>
                    <input type="text" value={settingsForm.lastName} onChange={(e) => setSettingsForm((prev) => ({ ...prev, lastName: e.target.value }))} />
                  </div>
                  <div className="doctor-settings-field">
                    <label>Email</label>
                    <input
                      type="email"
                      value={settingsForm.email}
                      onChange={(e) => setSettingsForm((prev) => ({ ...prev, email: e.target.value }))}
                      onBlur={(e) => setSettingsForm((prev) => ({ ...prev, email: normalizeEmailWithDefaultDomain(e.target.value) }))}
                    />
                  </div>
                  <div className="doctor-settings-field">
                    <label>Telefon</label>
                    <input type="tel" value={settingsForm.phone} onChange={(e) => setSettingsForm((prev) => ({ ...prev, phone: e.target.value }))} />
                  </div>
                  <div className="doctor-settings-field">
                    <label>PINFL</label>
                    <input
                      type="text"
                      inputMode="numeric"
                      pattern="[0-9]*"
                      value={settingsForm.pinfl}
                      onChange={(e) => setSettingsForm((prev) => ({ ...prev, pinfl: e.target.value.replace(/\D+/g, '') }))}
                      disabled={Boolean(doctor.pinfl)}
                      placeholder={doctor.pinfl ? 'PINFL saqlangan' : 'PINFL kiriting'}
                    />
                  </div>
                  <div className="doctor-settings-field">
                    <label>Pasport ID</label>
                    <input
                      type="text"
                      value={settingsForm.passportId}
                      readOnly
                      placeholder="Klinika egasi tomonidan kiritiladi"
                    />
                  </div>
                  <div className="doctor-settings-field">
                    <label>Litsenziya raqami</label>
                    <input type="text" value={settingsForm.licenseNumber} onChange={(e) => setSettingsForm((prev) => ({ ...prev, licenseNumber: e.target.value }))} />
                  </div>
                  <div className="doctor-settings-field">
                    <label>Diplom raqami</label>
                    <input type="text" value={settingsForm.diplomaNumber} onChange={(e) => setSettingsForm((prev) => ({ ...prev, diplomaNumber: e.target.value }))} />
                  </div>
                  <div className="doctor-settings-field">
                    <label>Birinchi ish boshlagan yil</label>
                    <input
                      type="text"
                      inputMode="numeric"
                      pattern="[0-9]*"
                      placeholder={`Masalan: ${currentYear - 5}`}
                      value={settingsForm.firstWorkYear}
                      onChange={(e) => setSettingsForm((prev) => ({ ...prev, firstWorkYear: sanitizeFirstWorkYearDraft(e.target.value) }))}
                      onBlur={() => setSettingsForm((prev) => ({ ...prev, firstWorkYear: normalizeFirstWorkYear(prev.firstWorkYear, currentYear) }))}
                    />
                  </div>
                  <div className="doctor-settings-field">
                    <label>Avtomatik tajriba (yil)</label>
                    <input type="text" value={computedExperiencePreview} readOnly />
                  </div>
                  <div className="doctor-settings-field doctor-settings-file-field">
                    <label>Sertifikat</label>
                    <input type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={(e) => setSettingsCertificateFile(e.target.files?.[0] || null)} />
                    {doctor.certificateDocumentUrl && (
                      <a href={doctor.certificateDocumentUrl} target="_blank" rel="noreferrer" className="doctor-settings-link">Mavjud sertifikatni ko'rish</a>
                    )}
                  </div>
                  <div className="doctor-settings-field doctor-settings-field-full">
                    <label>Bio</label>
                    <textarea rows={3} value={settingsForm.bio} onChange={(e) => setSettingsForm((prev) => ({ ...prev, bio: e.target.value }))} />
                  </div>

                  <div className="doctor-settings-field doctor-settings-field-full doctor-queue-interval-field">
                    <label>Navbat oralig‘i (real vaqt qayta hisoblash uchun)</label>
                    <div className="doctor-queue-interval-select-wrap">
                      <select
                        value={settingsForm.slotMinutes}
                        onChange={(e) => setSettingsForm((prev) => ({ ...prev, slotMinutes: Number(e.target.value) }))}
                      >
                        <option value={15}>15 daqiqa</option>
                        <option value={20}>20 daqiqa</option>
                        <option value={30}>30 daqiqa</option>
                      </select>
                      <span className="doctor-queue-interval-badge">Hozirgi: {settingsForm.slotMinutes} daqiqa</span>
                    </div>
                    <p className="doctor-queue-interval-help">
                      Bu qiymat `Kiring` va `Qabul qildim` tugmalaridan keyingi navbat vaqtlarini avtomatik qayta taqsimlashda ishlatiladi.
                    </p>
                  </div>
                </div>
                <div className="doctor-settings-note">Ish vaqti va ish kunlari klinika egasi tomonidan boshqariladi, lekin navbat oralig‘ini doktor o‘zi tanlaydi.</div>
                <button type="submit" className="btn-checkin" disabled={settingsSaving}>
                  {settingsSaving ? 'Saqlanmoqda...' : 'Sozlamalarni saqlash'}
                </button>
              </form>
            )}
          </div>

          {/* Specialty Prices Card */}
          <div className="specialty-prices-card">
            <div className="specialty-prices-header">
              <div>
                <h3>💰 Ixtisoslik narxlari</h3>
                <p className="specialty-prices-subtitle">Har bir yo‘nalish uchun qabul narxini shu yerda o‘zgartiring.</p>
              </div>
              <button
                className="btn-toggle-prices"
                onClick={() => setShowSpecialtyPrices(!showSpecialtyPrices)}
              >
                {showSpecialtyPrices ? '▼' : '▶'}
              </button>
            </div>

            {showSpecialtyPrices && (
              <div className="specialty-prices-list-wrap">
                {specialtyPrices && specialtyPrices.length > 0 ? (
                  <div className="specialty-prices-list">
                    {specialtyPrices.map((specialty) => (
                      <div key={specialty.id} className="specialty-price-row">
                        <div className="specialty-price-main">
                          <p className="specialty-price-name">{specialty.specialization.name}</p>
                          {editingPriceId === specialty.id ? (
                            <div className="specialty-price-edit-wrap">
                              <input
                                type="text"
                                inputMode="numeric"
                                placeholder="Masalan: 100000"
                                value={priceInputs[specialty.id] ?? ''}
                                onChange={(e) => setPriceInputs({ ...priceInputs, [specialty.id]: formatCurrencyInput(e.target.value) })}
                                onFocus={() => {
                                  if (priceInputClearedOnFocus[specialty.id] || !priceInputs[specialty.id]) {
                                    return
                                  }
                                  setPriceInputs((prev) => ({ ...prev, [specialty.id]: '' }))
                                  setPriceInputClearedOnFocus((prev) => ({ ...prev, [specialty.id]: true }))
                                }}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') {
                                    e.preventDefault()
                                    handleUpdateSpecialtyPrice(specialty.id)
                                  }
                                }}
                                className="specialty-price-input"
                              />
                              <span className="specialty-price-input-hint">so‘m</span>
                            </div>
                          ) : (
                            <span className="specialty-price-value">{formatPrice(specialty.consultation_fee)}</span>
                          )}
                        </div>
                        {editingPriceId === specialty.id ? (
                          <div className="specialty-price-actions">
                            <button
                              onClick={() => handleUpdateSpecialtyPrice(specialty.id)}
                              className="specialty-price-btn save"
                            >
                              Saqlash
                            </button>
                            <button
                              onClick={handleCancelEditSpecialtyPrice}
                              className="specialty-price-btn cancel"
                            >
                              Bekor
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => handleStartEditSpecialtyPrice(specialty)}
                            className="specialty-price-btn edit"
                          >
                            Narxni o‘zgartirish
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="specialty-prices-empty">
                    Hech qanday ixtisoslik yo'q
                  </p>
                )}
              </div>
            )}
          </div>
        </aside>

        {/* Right Content - Patients & Stats */}
        <main className="dash-main">
          {/* Stats */}
          <div className="stats-section">
            <div className="stat-card">
              <div className="stat-icon">👥</div>
              <div className="stat-content">
                <p className="stat-label">Bugungi bemorlar</p>
                <p className="stat-value">{doctorStats.todayPatients || 0}</p>
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-icon">✅</div>
              <div className="stat-content">
                <p className="stat-label">Bekor qilingan qabul soni</p>
                <p className="stat-value">{doctorStats.cancelledAppointments || 0}</p>
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-icon">⏳</div>
              <div className="stat-content">
                <p className="stat-label">Jami bemorlar soni (shu oy)</p>
                <p className="stat-value">{doctorStats.monthPatients || 0}</p>
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-icon">⭐</div>
              <div className="stat-content">
                <p className="stat-label">Mening bahom</p>
                <p className="stat-value">{ratingDisplay}/5</p>
                <p className="stat-detail" style={{fontSize: '0.75rem', color: '#6b7280'}}>
                  {doctor?.totalRatings || 0} ta baho
                </p>
              </div>
            </div>

          </div>

          <section className="queue-search-section">
            <div className="queue-search-header">
              <div>
                <h3>📋 Onlayn navbat va qidiruv</h3>
                <p className="queue-search-subtitle">Bemorlarni tez toping va navbatni boshqaring</p>
              </div>
              <button className="btn-refresh" onClick={() => loadOnlineAppointments(doctor.id)}>
                Yangilash
              </button>
            </div>

            <div className="queue-search-grid">
              <div className="queue-panel">
                <div className="queue-panel-header">
                  <h4>📋 Onlayn navbatlar</h4>
                  <span className="queue-count">
                    {appointmentsLoading ? '...' : `${onlineAppointments.length} ta`}
                  </span>
                </div>

                {appointmentsLoading && (
                  <div className="appointments-loading">Yuklanmoqda...</div>
                )}

                {!appointmentsLoading && onlineAppointments.length === 0 && (
                  <div className="appointments-empty">Hozircha onlayn navbatlar yo'q</div>
                )}

                {!appointmentsLoading && onlineAppointments.length > 0 && (
                  <div className="appointments-list">
                    {onlineAppointments.map((appointment, index) => {
                      const scheduled = new Date(appointment.scheduled_date)
                      const timeLabel = scheduled.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' })
                      const dateLabel = scheduled.toLocaleDateString('uz-UZ')
                      const isQueueLeader = index === 0
                      const queueLabel = index + 1
                      const queueLocked = !isQueueLeader
                      return (
                        <div key={appointment.id} className="appointment-card">
                          <div className="appointment-info">
                            <h4>{appointment.patient_info?.fullName || 'Bemor'}</h4>
                            <p>📌 Navbat raqami: #{queueLabel}</p>
                            {queueLocked && <p className="queue-lock-note">⚠️ Avval 1-navbatdagi bemor bilan ishlang</p>}
                            <p>📱 {appointment.patient_info?.phone || 'Telefon yo\'q'}</p>
                            <p>🗓 {dateLabel} • ⏰ {timeLabel}</p>
                            {appointment.reason && <p>📝 {appointment.reason}</p>}
                          </div>
                          <div className="appointment-actions">
                            <button
                              className="btn-accept"
                              onClick={() => handleAcceptAppointment(appointment)}
                              disabled={queueLocked}
                              title={queueLocked ? 'Faqat navbatdagi birinchi bemorni qabul qilish mumkin' : ''}
                            >
                              Qabul qildim
                            </button>
                            <button
                              className={`btn-enter ${queueDecisionLoading[`${appointment.id}:enter`] ? 'is-loading' : ''}`}
                              onClick={() => handleQueueDecision(appointment, 'enter')}
                              disabled={Boolean(queueLocked || queueDecisionLoading[`${appointment.id}:enter`] || queueDecisionLoading[`${appointment.id}:wait`] || queueDecisionLoading[`${appointment.id}:cancel`])}
                              title={queueLocked ? 'Faqat navbatdagi birinchi bemorni chaqirish mumkin' : ''}
                            >
                              {queueDecisionLoading[`${appointment.id}:enter`] ? 'Yuborilmoqda...' : 'Kiring'}
                            </button>
                            <button
                              className={`btn-wait ${queueDecisionLoading[`${appointment.id}:wait`] ? 'is-loading' : ''}`}
                              onClick={() => handleQueueDecision(appointment, 'wait')}
                              disabled={Boolean(queueLocked || queueDecisionLoading[`${appointment.id}:wait`] || queueDecisionLoading[`${appointment.id}:enter`] || queueDecisionLoading[`${appointment.id}:cancel`])}
                              title={queueLocked ? 'Faqat navbatdagi birinchi bemorga kutish beriladi' : ''}
                            >
                              {queueDecisionLoading[`${appointment.id}:wait`] ? 'Hisoblanmoqda...' : '15 daqiqa kuting'}
                            </button>
                            {isQueueLeader ? (
                              <button
                                className={`btn-cancel ${queueDecisionLoading[`${appointment.id}:cancel`] ? 'is-loading' : ''}`}
                                onClick={() => handleQueueDecision(appointment, 'cancel')}
                                disabled={Boolean(queueDecisionLoading[`${appointment.id}:cancel`] || queueDecisionLoading[`${appointment.id}:enter`] || queueDecisionLoading[`${appointment.id}:wait`])}
                              >
                                {queueDecisionLoading[`${appointment.id}:cancel`] ? 'Bekor qilinmoqda...' : 'Bekor qilish'}
                              </button>
                            ) : (
                              <div className="btn-action-placeholder" aria-hidden="true" />
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>

              <div className="queue-panel">
                <div className="queue-panel-header">
                  <h4>Bemor qidirish</h4>
                  <span className="queue-hint">
                    Ism yoki telefon <span className="queue-hint-icon">🔍</span>
                  </span>
                </div>

                <div className="search-container compact-search">
                  <div className="search-wrapper">
                    <input
                      type="text"
                      placeholder="Ism yoki telefon bo'yicha qidiring..."
                      value={searchQuery}
                      onChange={handleSearch}
                      className="search-input"
                      autoComplete="off"
                    />
                    <span className="search-icon">🔎</span>
                  </div>
                  {showSearchResults && searchQuery.trim() && (searchResults.length > 0 || databaseSearchResults.length > 0) && (
                    <div className="search-results">
                      {databaseSearchResults.length > 0 && (
                        <>
                          <div className="search-results-header">
                            <p className="results-count" style={{ color: '#059669' }}>
                              ✅ Bazada topilgan: {databaseSearchResults.length}
                            </p>
                          </div>
                          {databaseSearchResults.map((patient) => (
                            <div
                              key={`db-${patient.id}`}
                              className="search-result-item database-result"
                              onClick={() => handleSearchResultClick(patient)}
                              style={{ borderLeft: '4px solid #059669' }}
                            >
                              <div className="result-avatar" style={{ backgroundColor: '#d1fae5' }}>
                                {patient.fullName.charAt(0)}
                              </div>
                              <div className="result-info">
                                <p className="result-name">{patient.fullName}</p>
                                <p className="result-detail">
                                  📱 {patient.phone}
                                  {patient.age && ` • 👤 ${patient.age} y.`}
                                </p>
                                <p className="result-status" style={{ color: '#059669', fontSize: '0.85rem', marginTop: '4px' }}>
                                  ✓ Allaqachon ro'yxatda
                                </p>
                              </div>
                              <span className="result-arrow">→</span>
                            </div>
                          ))}
                        </>
                      )}
                      
                      {searchResults.length > 0 && (
                        <>
                          <div className="search-results-header">
                            <p className="results-count">Sizning bemorlar: {searchResults.length}</p>
                          </div>
                          {searchResults.map((patient) => (
                            <div
                              key={patient.id}
                              className="search-result-item"
                              onClick={() => handleSearchResultClick(patient)}
                            >
                              <div className="result-avatar">{patient.fullName.charAt(0)}</div>
                              <div className="result-info">
                                <p className="result-name">{patient.fullName}</p>
                                <p className="result-detail">
                                  📱 {patient.phone}
                                  {patient.age && ` • 👤 ${patient.age} y.`}
                                </p>
                              </div>
                              <span className="result-arrow">→</span>
                            </div>
                          ))}
                        </>
                      )}
                    </div>
                  )}
                  {showSearchResults && searchQuery.trim() && searchResults.length === 0 && (
                    <div className="search-no-results">
                      {databaseSearchResults.length > 0 ? (
                        <>
                          <p>ℹ️ Bu bemor bu klinikadan ro'yxatdan o'tmagan</p>
                          <p className="suggestion">Pastdagi bazadan chiqqan bemorni tanlab klinikaga bog'lang</p>
                        </>
                      ) : (
                        <>
                          <p>❌ Bemor topilmadi</p>
                          <p className="suggestion">Ism yoki telefonni tekshiring</p>
                        </>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </section>
          <section className="patients-section">
            <div className="section-header">
              <h2>Bemorlar</h2>
              <button 
                className="btn-add-patient"
                onClick={() => setShowAddPatient(!showAddPatient)}
                disabled={!canPractice}
              >
                {showAddPatient ? '✕ Bekor qilish' : '+ Bemor qo\'shish'}
              </button>
            </div>

            {showAddPatient && existingPatientSelected && (
              <form className="add-patient-form existing-patient-form" onSubmit={handleAddPatient}>
                <div className="existing-patient-notice">
                  <p className="notice-icon" style={{ color: '#059669' }}>✅</p>
                  <p className="notice-text">Bu bemor allaqachon ro'yxatdan o'tgan. Yangi tashrif qo'shmoqchisiz?</p>
                </div>
                
                <div className="patient-info-display">
                  <div className="info-row">
                    <span className="label">F.I.O:</span>
                    <span className="value">{existingPatientSelected.fullName}</span>
                  </div>
                  <div className="info-row">
                    <span className="label">Telefon:</span>
                    <span className="value">{existingPatientSelected.phone}</span>
                  </div>
                  {existingPatientSelected.age && (
                    <div className="info-row">
                      <span className="label">Yosh:</span>
                      <span className="value">{existingPatientSelected.age}</span>
                    </div>
                  )}
                </div>

                <div className="form-group">
                  <label>Shikoyat</label>
                  <input
                    type="text"
                    placeholder="Bemor shikoyatini kiriting"
                    value={existingPatientSelected.complaint || ''}
                    onChange={(e) => setExistingPatientSelected({ ...existingPatientSelected, complaint: e.target.value })}
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Tashxis (ixtiyoriy)</label>
                  <input
                    type="text"
                    placeholder="Tashxis"
                    value={existingPatientSelected.diagnosis || ''}
                    onChange={(e) => setExistingPatientSelected({ ...existingPatientSelected, diagnosis: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label>Dorilar (ixtiyoriy)</label>
                  <MedicineAutocomplete
                    value={existingPatientSelected.medicines || ''}
                    onChange={(e) => setExistingPatientSelected({ ...existingPatientSelected, medicines: e.target.value })}
                    placeholder="Dori nomini yozing va tavsiyalardan tanlang"
                  />
                </div>
                <div className="form-buttons">
                  <button type="submit" className="btn-submit">Tashrif qo'shish ✅</button>
                  <button 
                    type="button" 
                    className="btn-cancel"
                    onClick={() => {
                      setExistingPatientSelected(null)
                      setShowAddPatient(false)
                    }}
                  >
                    Bekor qilish
                  </button>
                </div>
              </form>
            )}

            {showAddPatient && !existingPatientSelected && (
              <form className="add-patient-form" onSubmit={handleAddPatient}>
                <div className="form-group">
                  <input
                    type="text"
                    placeholder="Bemor ismi"
                    value={patientForm.fullName}
                    onChange={(e) => setPatientForm({ ...patientForm, fullName: e.target.value })}
                    required
                  />
                </div>
                <div className="form-group">
                  <input
                    type="tel"
                    placeholder="Telefon raqami"
                    value={patientForm.phone}
                    onChange={(e) => setPatientForm({ ...patientForm, phone: e.target.value })}
                    required
                  />
                </div>

                <div className="form-group">
                  <p className="minor-label">🔐 Bemor hisob ma'lumotlari</p>
                </div>
                <div className="form-group">
                  <input
                    type="email"
                    placeholder="Email (ixtiyoriy)"
                    value={patientForm.email}
                    onChange={(e) => setPatientForm({ ...patientForm, email: e.target.value })}
                    onBlur={(e) => setPatientForm({ ...patientForm, email: normalizeEmailWithDefaultDomain(e.target.value) })}
                  />
                </div>
                <div className="form-group">
                  <PasswordInput
                    placeholder="Parol"
                    value={patientForm.password}
                    onChange={(e) => setPatientForm({ ...patientForm, password: e.target.value })}
                    required
                  />
                </div>

                <div className="form-group">
                  <input
                    type="text"
                    placeholder="Shikoyat"
                    value={patientForm.complaint}
                    onChange={(e) => setPatientForm({ ...patientForm, complaint: e.target.value })}
                    required
                  />
                </div>
                <div className="form-group">
                  <input
                    type="text"
                    placeholder="Tashxis"
                    value={patientForm.diagnosis}
                    onChange={(e) => setPatientForm({ ...patientForm, diagnosis: e.target.value })}
                  />
                </div>
                <div className="form-group medicine-form-group">
                  <MedicineAutocomplete
                    value={patientForm.medicines}
                    onChange={(e) => setPatientForm({ ...patientForm, medicines: e.target.value })}
                    placeholder="Dori nomini yozing va tavsiyalardan tanlang"
                  />
                </div>
                <button type="submit" className="btn-submit btn-submit-patient">Bemor qo'shish</button>
              </form>
            )}

            <div className="patients-list">
              {todaysPatients.length > 0 ? (
                todaysPatients.map((patient) => (
                  <div
                    key={patient.id}
                    className="patient-card clickable"
                    onClick={() => setSelectedPatient(patient)}
                  >
                    <div className="patient-header">
                      <div className="patient-avatar">{patient.fullName.charAt(0)}</div>
                      <div className="patient-info">
                        <h3>{patient.fullName}</h3>
                        <p className="complaint">{patient.complaint}</p>
                      </div>
                      <div className="patient-time">
                        <span className="time">{patient.addedTime}</span>
                        <span className="badge status-pending">👁️ Tarikhni ko'rish</span>
                      </div>
                    </div>
                    <div className="patient-contact">
                      <a href={`tel:${patient.phone}`} className="phone-link" onClick={(e) => e.stopPropagation()}>
                        📞 {patient.phone}
                      </a>
                    </div>
                  </div>
                ))
              ) : (
                <div className="no-patients">
                  <p>Oxirgi 24 soat ichida bemor qo'shilmagan</p>
                </div>
              )}
            </div>
          </section>
        </main>
      </div>

      {/* Patient History Modal */}
      {selectedPatient && (
        <div className="modal-overlay" onClick={closePatientHistory}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">
                <h2>{selectedPatient.fullName}</h2>
                <p className="patient-phone">📱 {selectedPatient.phone}</p>
              </div>
              <button className="btn-close" onClick={closePatientHistory}>✕</button>
            </div>

            <div className="modal-body">
              <div className="patient-basic-info">
                <div className="info-item">
                  <span className="label">Yosh:</span>
                  <span className="value">{selectedPatient.age ? `${selectedPatient.age} yoshda` : '—'}</span>
                </div>
                <div className="info-item">
                  <span className="label">Jinsi:</span>
                  <span className="value">
                    {selectedPatient.gender === 'male'
                      ? 'Erkak'
                      : selectedPatient.gender === 'female'
                        ? 'Ayol'
                        : selectedPatient.gender === 'other'
                          ? 'Boshqa'
                          : '—'}
                  </span>
                </div>
                <div className="info-item">
                  <span className="label">Birinchi marta qo'shilgan:</span>
                  <span className="value">{selectedPatient.addedDate} - {selectedPatient.addedTime}</span>
                </div>
                {selectedPatient.age && parseInt(selectedPatient.age) < 18 && (
                  <>
                    <div className="info-divider"></div>
                    <div className="info-item minor-info">
                      <span className="label">👨‍👩‍👧 Ota-Ona Ma'lumotlari:</span>
                    </div>
                    {selectedPatient.fatherName && (
                      <div className="info-item">
                        <span className="label">Otasining ismi:</span>
                        <span className="value">{selectedPatient.fatherName}</span>
                      </div>
                    )}
                    {selectedPatient.motherName && (
                      <div className="info-item">
                        <span className="label">Onasining ismi:</span>
                        <span className="value">{selectedPatient.motherName}</span>
                      </div>
                    )}
                    {selectedPatient.guardianName && (
                      <div className="info-item">
                        <span className="label">Vasil (Vakil):</span>
                        <span className="value">{selectedPatient.guardianName}</span>
                      </div>
                    )}
                  </>
                )}
              </div>

              <div className="visits-section">
                <h3>Tashrif tarixi</h3>
                {selectedPatient.visits && selectedPatient.visits.length > 0 ? (
                  <div className="visits-list">
                    {selectedPatient.visits.map((visit, idx) => (
                      <div key={visit.id} className="visit-card">
                        <div className="visit-header">
                          <div>
                            <p className="visit-doctor">👨‍⚕️ Dr. {visit.doctorName}</p>
                            <p className="visit-time">⏰ {visit.visitTime} • {visit.visitDate}</p>
                          </div>
                          <span className="visit-number">#{idx + 1}</span>
                        </div>

                        <div className="visit-details">
                          <div className="detail-item">
                            <span className="label">Shikoyat:</span>
                            <span className="value">{visit.complaint}</span>
                          </div>

                          <div className="detail-item">
                            <span className="label">Tashxis:</span>
                            <span className="value">
                              {visit.diagnosis || <em className="text-light">Belgilanmagan</em>}
                            </span>
                          </div>

                          <div className="detail-item">
                            <span className="label">Dorilar:</span>
                            <div className="medicines-list">
                                {normalizeMedicines(visit.medicines).length > 0 ? (
                                  normalizeMedicines(visit.medicines).map((med, i) => (
                                  <span key={i} className="medicine-badge">
                                    💊 {med.trim()}
                                  </span>
                                ))
                              ) : (
                                <em className="text-light">Belgilanmagan</em>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-light">Tashrif tarixi bo'sh</p>
                )}
              </div>

              {/* Add New Visit Form */}
              <div className="new-visit-section">
                <button 
                  className="btn-add-visit"
                  onClick={() => setShowNewVisitForm(!showNewVisitForm)}
                >
                  {showNewVisitForm ? '✕ Bekor qilish' : '+ Yangi tashrif qo\'shish'}
                </button>

                {showNewVisitForm && (
                  <form className="new-visit-form" onSubmit={handleAddNewVisit}>
                    <div className="form-group">
                      <input
                        type="text"
                        placeholder="Shikoyat"
                        value={newVisitForm.complaint}
                        onChange={(e) => setNewVisitForm({ ...newVisitForm, complaint: e.target.value })}
                        required
                      />
                    </div>
                    <div className="form-group">
                      <input
                        type="text"
                        placeholder="Tashxis"
                        value={newVisitForm.diagnosis}
                        onChange={(e) => setNewVisitForm({ ...newVisitForm, diagnosis: e.target.value })}
                      />
                    </div>
                    <div className="form-group">
                      <label style={{ display: 'block', marginBottom: '5px', fontSize: '0.9rem', color: '#666' }}>Dorilar</label>
                      <MedicineAutocomplete
                        value={newVisitForm.medicines}
                        onChange={(e) => setNewVisitForm({ ...newVisitForm, medicines: e.target.value })}
                        placeholder="Dori nomini yozing va tavsiyalardan tanlang"
                      />
                    </div>
                    <button type="submit" className="btn-submit-visit">Tashrif qo'shish</button>
                  </form>
                )}
              </div>
            </div>

            <div className="modal-footer">
              <button className="btn-close-modal" onClick={closePatientHistory}>Yopish</button>
            </div>
          </div>
        </div>
      )}

      {queueCancelConfirm.open && (
        <div className="modal-overlay" onClick={() => setQueueCancelConfirm(createInitialQueueCancelConfirm())}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">
                <h2>Qabulni bekor qilish</h2>
                <p className="patient-phone">
                  {queueCancelConfirm.appointment?.patient_info?.fullName || 'Bemor'}
                </p>
              </div>
              <button
                className="btn-close"
                onClick={() => setQueueCancelConfirm(createInitialQueueCancelConfirm())}
              >
                ✕
              </button>
            </div>
            <div className="modal-body">
              <p style={{ margin: 0, color: 'var(--text-dark)', fontWeight: 600 }}>
                Ushbu qabulni bekor qilmoqchimisiz?
              </p>
            </div>
            <div className="form-buttons">
              <button className="btn-submit" onClick={handleConfirmCancelQueue}>
                Ha, bekor qilish
              </button>
              <button className="btn-cancel" onClick={() => setQueueCancelConfirm(createInitialQueueCancelConfirm())}>
                Yo‘q
              </button>
            </div>
          </div>
        </div>
      )}

      {cancelTodayConfirmOpen && (
        <div
          className="modal-overlay"
          onClick={() => {
            if (!cancelTodayLoading) setCancelTodayConfirmOpen(false)
          }}
        >
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">
                <h2>Bugungi navbatni yopish</h2>
                <p className="patient-phone">Bugunga belgilangan navbatlar bekor qilinadi</p>
              </div>
              <button
                className="btn-close"
                onClick={() => {
                  if (!cancelTodayLoading) setCancelTodayConfirmOpen(false)
                }}
                disabled={cancelTodayLoading}
              >
                ✕
              </button>
            </div>
            <div className="modal-body">
              <p style={{ margin: 0, color: 'var(--text-dark)', fontWeight: 600 }}>
                Bugungi navbatlarni bekor qilib, yangi navbatni yopamizmi?
              </p>
            </div>
            <div className="form-buttons">
              <button className="btn-submit" onClick={handleConfirmCancelTodaysAppointments} disabled={cancelTodayLoading}>
                {cancelTodayLoading ? 'Bajarilmoqda...' : 'Ha, yopish'}
              </button>
              <button className="btn-cancel" onClick={() => setCancelTodayConfirmOpen(false)} disabled={cancelTodayLoading}>
                Yo‘q, qoldirish
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default DoctorDashboard
