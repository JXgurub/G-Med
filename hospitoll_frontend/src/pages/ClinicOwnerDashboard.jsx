import { useCallback, useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useClinic } from '../context/ClinicContext'
import { clinicsApi, doctorsApi, medicalApi } from '../services/api'
import useSmartAutoRefresh from '../hooks/useSmartAutoRefresh'
import DashboardSidebar from '../components/DashboardSidebar'
import PasswordInput from '../components/PasswordInput'
import { normalizeEmailWithDefaultDomain } from '../utils/helpers'
import { formatCurrencyInput, parseCurrencyInput } from '../utils/currency'
import './ClinicOwnerDashboard.css'

const formatMonthKey = (year, month) => `${year}-${String(month).padStart(2, '0')}`

const formatMonthLabel = (year, month, monthKey) => {
  let resolvedYear = Number(year)
  let resolvedMonth = Number(month)

  if ((!resolvedYear || !resolvedMonth) && monthKey) {
    const match = String(monthKey).match(/^(\d{4})-(\d{1,2})$/)
    if (match) {
      resolvedYear = Number(match[1])
      resolvedMonth = Number(match[2])
    }
  }

  if (!resolvedYear || !resolvedMonth || resolvedMonth < 1 || resolvedMonth > 12) {
    return monthKey || '—'
  }

  const date = new Date(resolvedYear, resolvedMonth - 1, 1)
  const monthName = new Intl.DateTimeFormat('uz-UZ', { month: 'long' }).format(date)
  const monthPretty = monthName.charAt(0).toUpperCase() + monthName.slice(1)
  return `${monthPretty} ${resolvedYear}`
}

const formatMonthCode = (year, month, monthKey) => {
  const directYear = Number(year)
  const directMonth = Number(month)
  if (directYear && directMonth >= 1 && directMonth <= 12) {
    return formatMonthKey(directYear, directMonth)
  }
  if (monthKey) return String(monthKey)
  return '—'
}

const getHistoryMonthSortValue = (item) => {
  const year = Number(item?.year)
  const month = Number(item?.month)
  if (year && month >= 1 && month <= 12) {
    return (year * 100) + month
  }
  const match = String(item?.month_key || '').match(/^(\d{4})-(\d{1,2})$/)
  if (match) {
    return (Number(match[1]) * 100) + Number(match[2])
  }
  return 0
}

const DEFAULT_WORKING_HOURS = {
  from: '09:00',
  to: '18:00'
}

const DEFAULT_PHONE_PREFIX = '+998'

const normalizeTime = (value, fallback) => {
  const source = String(value || '').trim()
  const parts = source.split(':')
  if (parts.length !== 2) return fallback
  const hour = Number(parts[0])
  const minute = Number(parts[1])
  if (Number.isNaN(hour) || Number.isNaN(minute)) return fallback
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return fallback
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
}

const parseWorkingHoursRange = (value) => {
  const source = String(value || '').trim()
  const match = source.match(/(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})/)
  if (!match) {
    return { ...DEFAULT_WORKING_HOURS }
  }
  return {
    from: normalizeTime(match[1], DEFAULT_WORKING_HOURS.from),
    to: normalizeTime(match[2], DEFAULT_WORKING_HOURS.to)
  }
}

const timeToMinutes = (value) => {
  const normalized = normalizeTime(value, '00:00')
  const [hour, minute] = normalized.split(':').map(Number)
  return (hour * 60) + minute
}

const formatSom = (value) => {
  const num = Number(value || 0)
  return `${Math.round(num).toLocaleString()} so'm`
}

const toCsv = (rows) => {
  const escapeCell = (cell) => {
    const str = String(cell ?? '')
    if (/[",\n]/.test(str)) return `"${str.replace(/"/g, '""')}"`
    return str
  }
  return rows.map((r) => r.map(escapeCell).join(',')).join('\n')
}

const downloadBlob = (content, filename, mimeType) => {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

const ClinicOwnerDashboard = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { 
    clinicOwner,
    clinicServices,
    clinicDepartments,
    specializations,
    loading,
    updateClinicBanner,
    updateClinicProfile,
    addDoctor, 
    getDoctorsByClinic, 
    deleteDoctor, 
    toggleDoctorStatus,
    updateDoctorSchedule,
    updateDoctorCompensation,
    addService,
    updateService,
    deleteService,
    addDepartment,
    updateDepartment,
    deleteDepartment,
    fetchSpecializations,
    refreshClinicData
  } = useClinic()
  const [showAddDoctor, setShowAddDoctor] = useState(false)
  const [showAddService, setShowAddService] = useState(false)
  const [showAddDepartment, setShowAddDepartment] = useState(false)
  const [editingServiceId, setEditingServiceId] = useState(null)
  const [editingDepartmentId, setEditingDepartmentId] = useState(null)
  const [doctorForm, setDoctorForm] = useState({
    pinfl: '',
    passportId: '',
    dateOfBirth: '',
    firstName: '',
    lastName: '',
    email: '',
    phone: DEFAULT_PHONE_PREFIX,
    password: '',
    compensationType: 'salary',
    compensationValue: '',
    consultationFee: '',
    specializationInput: '',
    specialization_ids: [],
    specialty_prices: [],
    availableFrom: '09:00',
    availableUntil: '17:00',
    lunchBreakStart: '',
    lunchBreakEnd: '',
    workingDays: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
  })
  const [doctorFormErrors, setDoctorFormErrors] = useState({})
  const [compensationClearedOnFocus, setCompensationClearedOnFocus] = useState(false)
  const [serviceForm, setServiceForm] = useState({
    name: '',
    description: '',
    price: '',
    department: ''
  })
  const [servicePriceClearedOnFocus, setServicePriceClearedOnFocus] = useState(false)
  const [departmentForm, setDepartmentForm] = useState({
    name: '',
    description: ''
  })
  const [activeView, setActiveView] = useState('overview')
  const [scheduleForms, setScheduleForms] = useState({})
  const [compensationForms, setCompensationForms] = useState({})
  const [doctorCardTabs, setDoctorCardTabs] = useState({})
  const [compensationSavingDoctorId, setCompensationSavingDoctorId] = useState(null)
  const [identityCheckState, setIdentityCheckState] = useState({
    status: 'idle',
    message: '',
    loading: false,
    canSubmit: true,
    fieldErrors: {}
  })
  const [bannerFile, setBannerFile] = useState(null)
  const [bannerPreviewUrl, setBannerPreviewUrl] = useState('')
  const [bannerSaving, setBannerSaving] = useState(false)

  const [settingsSaving, setSettingsSaving] = useState(false)
  const [settingsMessage, setSettingsMessage] = useState('')
  const [settingsWorkingHoursError, setSettingsWorkingHoursError] = useState('')
  const [settingsWorkingHoursRange, setSettingsWorkingHoursRange] = useState({ ...DEFAULT_WORKING_HOURS })
  const [settingsForm, setSettingsForm] = useState({
    name: '',
    description: '',
    address: '',
    phone_number: DEFAULT_PHONE_PREFIX,
    email: '',
    website: '',
    working_hours: '09:00 - 18:00',
    owner_password: ''
  })

  const [staffMessageBody, setStaffMessageBody] = useState('')
  const [staffMessageSending, setStaffMessageSending] = useState(false)
  const [staffMessageStatus, setStaffMessageStatus] = useState('')
  const [showStaffMessageModal, setShowStaffMessageModal] = useState(false)
  const [specializationCreateLoading, setSpecializationCreateLoading] = useState(false)
  const [specializationCreateMessage, setSpecializationCreateMessage] = useState('')
  const [showSpecializationSuggestions, setShowSpecializationSuggestions] = useState(false)

  const dayOptions = [
    { key: 'Mon', label: 'Du' },
    { key: 'Tue', label: 'Se' },
    { key: 'Wed', label: 'Ch' },
    { key: 'Thu', label: 'Pa' },
    { key: 'Fri', label: 'Ju' },
    { key: 'Sat', label: 'Sh' },
    { key: 'Sun', label: 'Ya' }
  ]

  useEffect(() => {
    if (loading) {
      return
    }
    if (!clinicOwner) {
      navigate('/clinic-owner-login', { replace: true })
      return
    }
    // Check if subscription is expired and redirect to blocked page
    if (clinicOwner.subscription?.is_expired || clinicOwner.isSubscriptionExpired) {
      navigate('/subscription-blocked', { replace: true })
      return
    }
  }, [clinicOwner, loading, navigate])

  const clinicId = clinicOwner?.id
  const clinicDoctorsList = clinicId ? getDoctorsByClinic(clinicId) : []
  const activeClinicDoctorsList = clinicDoctorsList.filter(
    (doctor) => !(doctor.isFormerForClinic || doctor.clinicAssociationStatus === 'former')
  )
  const formerClinicDoctorsList = clinicDoctorsList.filter(
    (doctor) => doctor.isFormerForClinic || doctor.clinicAssociationStatus === 'former'
  )
  const doctorsListForView = activeView === 'former-doctors' ? formerClinicDoctorsList : activeClinicDoctorsList
  const selectedSpecializationObjects = (specializations || []).filter((spec) =>
    doctorForm.specialization_ids.includes(spec.id)
  )
  const specializationSuggestions = (specializations || [])
    .filter((spec) => !doctorForm.specialization_ids.includes(spec.id))
    .filter((spec) => {
      const q = (doctorForm.specializationInput || '').trim().toLowerCase()
      if (!q) return true
      return spec.name.toLowerCase().includes(q)
    })

  const findMatchingSpecialization = (queryText) => {
    const query = String(queryText || '').trim().toLowerCase()
    if (!query) return null
    return (specializations || []).find(
      (spec) => spec.name.toLowerCase() === query
    ) || (specializations || []).find(
      (spec) => spec.name.toLowerCase().includes(query)
    )
  }

  const buildSpecializationCode = (name) => {
    const base = String(name || '')
      .toUpperCase()
      .replace(/[^A-Z0-9]+/g, '')
      .slice(0, 8)
    const suffix = Date.now().toString().slice(-4)
    return `${base || 'SPEC'}${suffix}`
  }

  const addSpecializationFromInput = (inputValue) => {
    const matched = findMatchingSpecialization(inputValue)

    if (!matched) return false
    if (doctorForm.specialization_ids.includes(matched.id)) {
      setDoctorForm((prev) => ({ ...prev, specializationInput: '' }))
      return true
    }

    setDoctorForm((prev) => ({
      ...prev,
      specialization_ids: [...prev.specialization_ids, matched.id],
      specializationInput: ''
    }))
    return true
  }

  const createSpecializationFromInput = async (inputValue) => {
    const rawName = String(inputValue || '').trim()
    if (!rawName) return

    const existingMatch = findMatchingSpecialization(rawName)
    if (existingMatch) {
      addSpecializationFromInput(rawName)
      return
    }

    const normalizedName = rawName.replace(/\s+/g, ' ')
    setSpecializationCreateLoading(true)
    setSpecializationCreateMessage('')

    try {
      const created = await doctorsApi.createSpecialization({
        name: normalizedName,
        code: buildSpecializationCode(normalizedName)
      })

      const refreshed = await fetchSpecializations()
      const refreshedList = refreshed?.results || refreshed || []
      const createdSpec = created?.id
        ? created
        : refreshedList.find((item) => String(item?.name || '').toLowerCase() === normalizedName.toLowerCase())

      if (!createdSpec?.id) {
        throw new Error('Ixtisoslik yaratildi, lekin ro\'yxatdan topilmadi.')
      }

      setDoctorForm((prev) => {
        const alreadySelected = prev.specialization_ids.includes(createdSpec.id)
        return {
          ...prev,
          specialization_ids: alreadySelected
            ? prev.specialization_ids
            : [...prev.specialization_ids, createdSpec.id],
          specializationInput: ''
        }
      })
      setSpecializationCreateMessage(`"${normalizedName}" qo'shildi.`)
    } catch (error) {
      const detail = error?.response?.data?.detail
      setSpecializationCreateMessage(detail || 'Ixtisoslikni yaratib bo\'lmadi.')
    } finally {
      setSpecializationCreateLoading(false)
    }
  }

  const removeSpecialization = (specId) => {
    setDoctorForm((prev) => ({
      ...prev,
      specialization_ids: prev.specialization_ids.filter((id) => id !== specId)
    }))
  }

  const [appointmentsLoading, setAppointmentsLoading] = useState(false)
  const [appointmentsError, setAppointmentsError] = useState('')
  const [appointmentsStats, setAppointmentsStats] = useState(null)
  const [appointmentsStatsUpdatedAt, setAppointmentsStatsUpdatedAt] = useState(null)
  const [clinicStatsLoading, setClinicStatsLoading] = useState(false)
  const [clinicStatsError, setClinicStatsError] = useState('')
  const [clinicDashboardStats, setClinicDashboardStats] = useState(null)
  const [clinicStatsUpdatedAt, setClinicStatsUpdatedAt] = useState(null)

  useEffect(() => {
    if (!showAddDoctor) return
    // Always refresh specializations when opening the doctor form.
    fetchSpecializations()
  }, [showAddDoctor])

  useEffect(() => {
    if (showAddDoctor) return
    setShowSpecializationSuggestions(false)
  }, [showAddDoctor])

  useEffect(() => {
    // Allow sidebar route to open appointments stats without adding extra top tabs
    const path = location.pathname || ''
    if (path.includes('/clinic-dashboard/appointments')) {
      setActiveView('appointments')
    }
    if (path.includes('/clinic-dashboard/services') || path.includes('/clinic-dashboard/directions')) {
      setActiveView('services')
    }
    if (path.includes('/clinic-dashboard/former-doctors')) {
      setActiveView('former-doctors')
    }
    if (path.includes('/clinic-dashboard/settings')) {
      setActiveView('settings')
    }
  }, [location.pathname])

  useEffect(() => {
    if (!clinicOwner) return
    setSettingsForm((prev) => ({
      ...prev,
      name: clinicOwner.name || clinicOwner.clinicName || '',
      description: clinicOwner.description || '',
      address: clinicOwner.address || clinicOwner.location || '',
      phone_number: clinicOwner.phone_number || clinicOwner.clinicPhone || DEFAULT_PHONE_PREFIX,
      email: clinicOwner.email || '',
      website: clinicOwner.website || '',
      working_hours: clinicOwner.working_hours || '09:00 - 18:00',
      owner_password: ''
    }))
    setSettingsWorkingHoursRange(parseWorkingHoursRange(clinicOwner.working_hours || '09:00 - 18:00'))
    setSettingsWorkingHoursError('')
  }, [clinicOwner])

  const handleSaveSettings = async (e) => {
    e.preventDefault()
    setSettingsMessage('')
    setSettingsWorkingHoursError('')

    if (timeToMinutes(settingsWorkingHoursRange.to) <= timeToMinutes(settingsWorkingHoursRange.from)) {
      setSettingsWorkingHoursError('Tugash vaqti boshlanish vaqtidan katta bo‘lishi kerak.')
      return
    }

    setSettingsSaving(true)
    try {
      const workingHoursValue = `${settingsWorkingHoursRange.from} - ${settingsWorkingHoursRange.to}`
      const payload = {
        name: settingsForm.name,
        description: settingsForm.description,
        address: settingsForm.address,
        phone_number: settingsForm.phone_number,
        email: normalizeEmailWithDefaultDomain(settingsForm.email),
        website: settingsForm.website,
        working_hours: workingHoursValue,
        ...(settingsForm.owner_password ? { owner_password: settingsForm.owner_password } : {})
      }
      const updatedClinic = await updateClinicProfile(payload)
      const savedWorkingHours = updatedClinic?.working_hours || workingHoursValue
      setSettingsForm((prev) => ({
        ...prev,
        owner_password: '',
        working_hours: savedWorkingHours
      }))
      setSettingsWorkingHoursRange(parseWorkingHoursRange(savedWorkingHours))
      setSettingsMessage('✅ Ma\'lumotlar saqlandi')
    } catch (error) {
      setSettingsMessage(`❌ ${error?.message || 'Xatolik yuz berdi'}`)
    } finally {
      setSettingsSaving(false)
    }
  }

  useEffect(() => {
    if (!clinicDoctorsList.length) return
    setScheduleForms((prev) => {
      const next = { ...prev }
      clinicDoctorsList.forEach((doctor) => {
        if (!next[doctor.id]) {
          next[doctor.id] = {
            availableFrom: doctor.availableFrom || '09:00',
            availableUntil: doctor.availableUntil || '17:00',
            lunchBreakStart: doctor.lunchBreakStart || '',
            lunchBreakEnd: doctor.lunchBreakEnd || '',
            workingDays: (doctor.workingDays || 'Mon,Tue,Wed,Thu,Fri')
              .split(',')
              .map((d) => d.trim())
              .filter(Boolean)
          }
        }
      })
      return next
    })
  }, [clinicDoctorsList])

  useEffect(() => {
    if (!clinicDoctorsList.length) return
    setCompensationForms((prev) => {
      const next = { ...prev }
      clinicDoctorsList.forEach((doctor) => {
        if (!next[doctor.id]) {
          const type = doctor.compensationType || 'salary'
          const rawValue = doctor.compensationValue || ''
          next[doctor.id] = {
            compensationType: type,
            compensationValue: type === 'percent' ? String(rawValue || '') : formatCurrencyInput(rawValue)
          }
        }
      })
      return next
    })
  }, [clinicDoctorsList])

  useEffect(() => {
    if (!showAddDoctor) {
      setIdentityCheckState({
        status: 'idle',
        message: '',
        loading: false,
        canSubmit: true,
        fieldErrors: {}
      })
      return
    }

    const pinfl = String(doctorForm.pinfl || '').trim()
    const passport = String(doctorForm.passportId || '').trim()
    if (!pinfl && !passport) {
      setIdentityCheckState({
        status: 'idle',
        message: '',
        loading: false,
        canSubmit: true,
        fieldErrors: {}
      })
      return
    }

    if (pinfl && pinfl.length < 14) {
      setIdentityCheckState({
        status: 'typing',
        message: 'JSHSHIR 14 ta bo\'lgach tekshiruv avtomatik ishlaydi.',
        loading: false,
        canSubmit: false,
        fieldErrors: {}
      })
      return
    }

    let isCancelled = false
    const timeoutId = setTimeout(async () => {
      setIdentityCheckState((prev) => ({ ...prev, loading: true }))
      try {
        const response = await doctorsApi.identityCheck({
          pinfl,
          passport_id: passport,
          first_name: doctorForm.firstName,
          last_name: doctorForm.lastName,
          email: normalizeEmailWithDefaultDomain(doctorForm.email),
          date_of_birth: doctorForm.dateOfBirth,
          clinic: clinicOwner?.id
        })
        if (isCancelled) return

        const rawFieldErrors = response?.field_errors || {}
        setIdentityCheckState({
          status: response?.status || 'idle',
          message: response?.message || '',
          loading: false,
          canSubmit: response?.can_submit !== false,
          fieldErrors: rawFieldErrors,
        })

        if (Object.keys(rawFieldErrors).length > 0) {
          setDoctorFormErrors((prev) => ({
            ...prev,
            ...(rawFieldErrors.pinfl ? { pinfl: rawFieldErrors.pinfl } : {}),
            ...(rawFieldErrors.passport_id ? { passportId: rawFieldErrors.passport_id } : {}),
            ...(rawFieldErrors.first_name ? { firstName: rawFieldErrors.first_name } : {}),
            ...(rawFieldErrors.last_name ? { lastName: rawFieldErrors.last_name } : {}),
            ...(rawFieldErrors.email ? { email: rawFieldErrors.email } : {}),
            ...(rawFieldErrors.date_of_birth ? { dateOfBirth: rawFieldErrors.date_of_birth } : {}),
          }))
        }
      } catch (error) {
        if (isCancelled) return
        setIdentityCheckState({
          status: 'error',
          message: error?.message || 'Real-time tekshiruvda xatolik yuz berdi.',
          loading: false,
          canSubmit: true,
          fieldErrors: {},
        })
      }
    }, 450)

    return () => {
      isCancelled = true
      clearTimeout(timeoutId)
    }
  }, [
    showAddDoctor,
    doctorForm.pinfl,
    doctorForm.passportId,
    doctorForm.firstName,
    doctorForm.lastName,
    doctorForm.email,
    doctorForm.dateOfBirth,
    clinicOwner?.id,
  ])

  const fetchMonthlyAppointmentsStats = useCallback(async ({ silent = false } = {}) => {
    if (!clinicOwner?.id) return

    if (!silent) setAppointmentsLoading(true)
    setAppointmentsError('')
    try {
      const stats = await medicalApi.getAppointmentsMonthlyStats({ clinic: clinicOwner.id })
      setAppointmentsStats(stats)
      setAppointmentsStatsUpdatedAt(new Date())
    } catch (e) {
      setAppointmentsStats(null)
      setAppointmentsError(e?.message || 'Statistika yuklashda xatolik')
    } finally {
      if (!silent) setAppointmentsLoading(false)
    }
  }, [clinicOwner?.id])

  const fetchClinicDashboardStats = useCallback(async ({ silent = false } = {}) => {
    if (!clinicOwner?.id) return

    if (!silent) setClinicStatsLoading(true)
    setClinicStatsError('')
    try {
      const stats = await medicalApi.getClinicDashboardStats()
      setClinicDashboardStats(stats)
      setClinicStatsUpdatedAt(new Date())
    } catch (e) {
      setClinicDashboardStats(null)
      setClinicStatsError(e?.message || 'Klinika statistikasi yuklashda xatolik')
    } finally {
      if (!silent) setClinicStatsLoading(false)
    }
  }, [clinicOwner?.id])

  useEffect(() => {
    void fetchMonthlyAppointmentsStats()
  }, [fetchMonthlyAppointmentsStats])

  useEffect(() => {
    void fetchClinicDashboardStats()
  }, [fetchClinicDashboardStats])

  const refreshClinicOwnerDashboard = useCallback(async () => {
    if (!clinicOwner?.id) return

    const isDoctorsOrStatsView = ['overview', 'appointments', 'doctors', 'former-doctors', 'settings'].includes(activeView)
    const isServicesView = activeView === 'services'

    const tasks = [
      refreshClinicData({
        owner: true,
        doctors: isDoctorsOrStatsView,
        services: isServicesView,
      }),
    ]

    if (isDoctorsOrStatsView) {
      tasks.push(fetchMonthlyAppointmentsStats({ silent: true }))
      tasks.push(fetchClinicDashboardStats({ silent: true }))
    }

    await Promise.all(tasks)
  }, [clinicOwner?.id, activeView, refreshClinicData, fetchMonthlyAppointmentsStats, fetchClinicDashboardStats])

  useSmartAutoRefresh({
    enabled: Boolean(clinicOwner?.id),
    callback: refreshClinicOwnerDashboard,
    minIntervalMs: 45000,
    maxIntervalMs: 60000,
    immediate: false,
  })

  useEffect(() => {
    if (!bannerFile) {
      setBannerPreviewUrl('')
      return
    }
    const url = URL.createObjectURL(bannerFile)
    setBannerPreviewUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [bannerFile])

  if (loading) {
    return <div style={{ padding: '20px', textAlign: 'center' }}>Yuklanyapti...</div>
  }

  if (!clinicOwner) {
    return null
  }

  const getFirstErrorMessage = (value) => {
    if (Array.isArray(value)) {
      return String(value[0] || '').trim()
    }
    return String(value || '').trim()
  }

  const mapDoctorCreateErrors = (responseData) => {
    if (!responseData || typeof responseData !== 'object') {
      return {}
    }

    const nextErrors = {}

    const pinflError = getFirstErrorMessage(responseData.pinfl)
    if (pinflError) {
      nextErrors.pinfl = pinflError
    }

    const passportError = getFirstErrorMessage(responseData.passport_id)
    if (passportError) {
      nextErrors.passportId = passportError
    }

    const emailError = getFirstErrorMessage(responseData.email)
    if (emailError) {
      nextErrors.email = emailError
    }

    const firstNameError = getFirstErrorMessage(responseData.first_name)
    if (firstNameError) {
      nextErrors.firstName = firstNameError
    }

    const lastNameError = getFirstErrorMessage(responseData.last_name)
    if (lastNameError) {
      nextErrors.lastName = lastNameError
    }

    const dateOfBirthError = getFirstErrorMessage(responseData.date_of_birth)
    if (dateOfBirthError) {
      nextErrors.dateOfBirth = dateOfBirthError
    }

    const phoneError = getFirstErrorMessage(responseData.phone_number)
    if (phoneError) {
      nextErrors.phone = phoneError
    }

    const consultationFeeError = getFirstErrorMessage(responseData.consultation_fee)
    if (consultationFeeError) {
      nextErrors.consultationFee = consultationFeeError
    }

    const specializationError = getFirstErrorMessage(responseData.specialization_ids)
    if (specializationError) {
      nextErrors.specialization_ids = specializationError
    }

    const passwordError = getFirstErrorMessage(responseData.password)
    if (passwordError) {
      nextErrors.password = passwordError
    }

    const generalError = getFirstErrorMessage(responseData.detail || responseData.non_field_errors)
    if (generalError) {
      nextErrors.general = generalError
    }

    return nextErrors
  }

  const handleAddDoctor = async (e) => {
    e.preventDefault()
    setDoctorFormErrors({})
    const normalizedDoctorEmail = normalizeEmailWithDefaultDomain(doctorForm.email)
    const pinfl = String(doctorForm.pinfl || '').replace(/\D+/g, '')
    if (!pinfl) {
      setDoctorFormErrors({ pinfl: "JSHSHIR kiritish majburiy." })
      return
    }
    if (pinfl.length !== String(doctorForm.pinfl || '').trim().length) {
      setDoctorFormErrors({ pinfl: "JSHSHIR faqat raqamlardan iborat bo'lishi kerak." })
      return
    }
    if (pinfl.length !== 14) {
      setDoctorFormErrors({ pinfl: "JSHSHIR 14 ta raqamdan iborat bo'lishi kerak." })
      return
    }

    if (identityCheckState.loading) {
      setDoctorFormErrors({ general: 'Iltimos, identity tekshiruvi tugashini kuting.' })
      return
    }

    if (identityCheckState.canSubmit === false) {
      setDoctorFormErrors({
        general: identityCheckState.message || 'Kiritilgan JSHSHIR/Pasport ma\'lumotlari bilan doktorni ishga olish mumkin emas.'
      })
      return
    }

    const localErrors = {}
    if (!doctorForm.passportId) localErrors.passportId = "Pasport/ID majburiy."
    if (!doctorForm.dateOfBirth) localErrors.dateOfBirth = "Tug'ilgan sana majburiy."
    if (!doctorForm.firstName) localErrors.firstName = "Ism majburiy."
    if (!doctorForm.lastName) localErrors.lastName = "Familiya majburiy."
    if (!normalizedDoctorEmail) localErrors.email = "Email majburiy."
    if (!doctorForm.phone || doctorForm.phone === DEFAULT_PHONE_PREFIX) localErrors.phone = "Telefon majburiy."
    if (!doctorForm.consultationFee) localErrors.consultationFee = "Konsultatsiya narxi majburiy."
    if (doctorForm.specialization_ids.length === 0) localErrors.specialization_ids = "Kamida bitta ixtisoslik tanlang."
    if (identityCheckState.status === 'new_doctor_allowed' && !doctorForm.password) {
      localErrors.password = 'Yangi doktor uchun parol majburiy.'
    }

    if (Object.keys(localErrors).length > 0) {
      setDoctorFormErrors(localErrors)
      return
    }

    const parsedConsultationFee = parseCurrencyInput(doctorForm.consultationFee)
    if (parsedConsultationFee <= 0) {
      setDoctorFormErrors({ consultationFee: "Konsultatsiya narxi 0 dan katta bo'lishi kerak." })
      return
    }

    const generatedSpecialtyPrices = doctorForm.specialization_ids.map((specializationId) => ({
      specialization_id: String(specializationId),
      consultation_fee: String(parsedConsultationFee)
    }))

    try {
      const payload = {
        pinfl,
        first_name: doctorForm.firstName,
        last_name: doctorForm.lastName,
        email: normalizedDoctorEmail,
        phone_number: doctorForm.phone,
        ...(doctorForm.password ? { password: doctorForm.password } : {}),
        date_of_birth: doctorForm.dateOfBirth || null,
        passport_id: doctorForm.passportId || null,
        compensation_type: doctorForm.compensationType,
        compensation_value: doctorForm.compensationValue ? parseCurrencyInput(doctorForm.compensationValue) : null,
        consultation_fee: parsedConsultationFee,
        specialization_ids: doctorForm.specialization_ids,
        specialty_prices: generatedSpecialtyPrices,
        available_from: doctorForm.availableFrom,
        available_until: doctorForm.availableUntil,
        lunch_break_start: doctorForm.lunchBreakStart || null,
        lunch_break_end: doctorForm.lunchBreakEnd || null,
        working_days: doctorForm.workingDays.join(',')
      }

      await addDoctor(clinicOwner.id, payload)

      setDoctorForm({
        pinfl: '',
        passportId: '',
        dateOfBirth: '',
        firstName: '',
        lastName: '',
        email: '',
        phone: DEFAULT_PHONE_PREFIX,
        password: '',
        compensationType: 'salary',
        compensationValue: '',
        consultationFee: '',
        specializationInput: '',
        specialization_ids: [],
        specialty_prices: [],
        availableFrom: '09:00',
        availableUntil: '17:00',
        lunchBreakStart: '',
        lunchBreakEnd: '',
        workingDays: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
      })
      setCompensationClearedOnFocus(false)
      setDoctorFormErrors({})
      setShowAddDoctor(false)
      alert("Doktor muvaffaqiyatli qo'shildi yoki qayta ishga olindi!")
    } catch (error) {
      const mappedErrors = mapDoctorCreateErrors(error?.response?.data)
      if (Object.keys(mappedErrors).length > 0) {
        setDoctorFormErrors(mappedErrors)
      }

      const detail = mappedErrors.general || error?.response?.data?.detail
      const msg = detail || error?.message || "Doktor qo'shishda xatolik yuz berdi"
      if (Object.keys(mappedErrors).length === 0) {
        alert(msg)
      }
    }
  }

  const handleBannerFileChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setBannerFile(file)
  }

  const handleSaveBanner = async () => {
    if (!bannerFile) return
    setBannerSaving(true)
    try {
      await updateClinicBanner(bannerFile)
      setBannerFile(null)
      alert('Fon rasm yangilandi!')
    } catch (error) {
      alert(error?.message || 'Fon rasmni saqlashda xatolik yuz berdi')
    } finally {
      setBannerSaving(false)
    }
  }

  const activeDoctors = Number(clinicDashboardStats?.active_doctors || 0)
  const totalDoctors = Number(clinicDashboardStats?.total_doctors || 0)
  const monthlyTotalPatients = Number(clinicDashboardStats?.monthly_arrived_patients || 0)
  const totalWorkHours = Number(clinicDashboardStats?.monthly_total_hours || 0)
  const monthlyRevenueByDoctor = Array.isArray(clinicDashboardStats?.monthly_estimated_revenue_by_doctor)
    ? clinicDashboardStats.monthly_estimated_revenue_by_doctor
    : []
  const activeDoctorIds = new Set(activeClinicDoctorsList.map((doctor) => String(doctor.id)))
  const activeMonthlyRevenueByDoctor = monthlyRevenueByDoctor.filter((item) =>
    activeDoctorIds.has(String(item.doctor_id))
  )
  const monthlyEstimatedRevenue = activeMonthlyRevenueByDoctor.reduce(
    (sum, item) => sum + Number(item.estimated_revenue || 0),
    0
  )
  const formerDoctorsCount = formerClinicDoctorsList.length
  const formerMonthlyRevenueTotal = formerClinicDoctorsList.reduce(
    (sum, doctor) => sum + Number(doctor.monthlyEffectiveRevenue || 0),
    0
  )
  const formerMonthlySalaryTotal = formerClinicDoctorsList.reduce(
    (sum, doctor) => sum + Number(doctor.monthlyEstimatedSalary || 0),
    0
  )

  const getDoctorRevenueShare = (doctorRevenue) => {
    const total = Number(monthlyEstimatedRevenue || 0)
    const value = Number(doctorRevenue || 0)
    if (!total || total <= 0 || value <= 0) return 0
    return (value / total) * 100
  }

  const handleToggleStatus = async (doctor) => {
    try {
      console.log('[ClinicOwnerDashboard] handleToggleStatus called for:', doctor.fullName)
      const result = await toggleDoctorStatus(clinicOwner.id, doctor.id)
      console.log('[ClinicOwnerDashboard] toggleDoctorStatus result:', result)
      if (result && result.success) {
        if (result.newStatus === false) {
          // Doctor is now suspended
          console.log('[ClinicOwnerDashboard] Doctor suspended successfully')
          alert(`✓ ${doctor.fullName} ning ish foliyati vaqtincha to'xtatib qo'yildi`)
        } else {
          // Doctor is now active
          console.log('[ClinicOwnerDashboard] Doctor activated successfully')
          alert(`✓ ${doctor.fullName} ning ish foliyati faollashtirildi`)
        }
      } else {
        console.error('[ClinicOwnerDashboard] Toggle result was not successful:', result)
        alert('Doktor statusini o\'zgartira olmadi. Iltimos qayta urining.')
      }
    } catch (error) {
      console.error('[ClinicOwnerDashboard] Error toggling doctor status:', error)
      alert(`Xatolik yuz berdi: ${error.message || 'Iltimos qayta urining'}`)
    }
  }

  const handleAddService = (e) => {
    e.preventDefault()
    const servicePrice = parseCurrencyInput(serviceForm.price)
    if (serviceForm.name && servicePrice > 0) {
      const payload = {
        name: serviceForm.name,
        description: serviceForm.description,
        price: servicePrice,
        is_active: true
      }
      
      if (editingServiceId) {
        updateService(clinicOwner.id, editingServiceId, payload).then(() => {
          setServiceForm({ name: '', description: '', price: '', department: '' })
          setServicePriceClearedOnFocus(false)
          setShowAddService(false)
          setEditingServiceId(null)
          alert('Xizmat yangilandi!')
        })
      } else {
        addService(clinicOwner.id, payload).then(() => {
          setServiceForm({ name: '', description: '', price: '', department: '' })
          setServicePriceClearedOnFocus(false)
          setShowAddService(false)
          alert('Xizmat qo\'shildi!')
        })
      }
    }
  }

  const handleEditService = (service) => {
    setServiceForm({
      name: service.name,
      description: service.description,
      price: formatCurrencyInput(service.price),
      department: ''
    })
    setServicePriceClearedOnFocus(false)
    setEditingServiceId(service.id)
    setShowAddService(true)
  }

  const handleDeleteService = (serviceId) => {
    if (window.confirm('Xizmatni o\'chirishni istaysizmi?')) {
      deleteService(clinicOwner.id, serviceId).then(() => {
        alert('Xizmat o\'chirildi!')
      })
    }
  }

  const handleAddDepartment = (e) => {
    e.preventDefault()
    if (departmentForm.name) {
      const payload = {
        name: departmentForm.name,
        description: departmentForm.description,
        is_active: true
      }
      
      if (editingDepartmentId) {
        updateDepartment(clinicOwner.id, editingDepartmentId, payload).then(() => {
          setDepartmentForm({ name: '', description: '' })
          setShowAddDepartment(false)
          setEditingDepartmentId(null)
          alert('yo\'nalish yangilandi!')
        })
      } else {
        addDepartment(clinicOwner.id, payload).then(() => {
          setDepartmentForm({ name: '', description: '' })
          setShowAddDepartment(false)
          alert('yo\'nalish qo\'shildi!')
        })
      }
    }
  }

  const handleEditDepartment = (department) => {
    setDepartmentForm({
      name: department.name,
      description: department.description
    })
    setEditingDepartmentId(department.id)
    setShowAddDepartment(true)
  }

  const handleDeleteDepartment = (departmentId) => {
    if (window.confirm('yo\'nalishni o\'chirishni istaysizmi?')) {
      deleteDepartment(clinicOwner.id, departmentId).then(() => {
        alert('yo\'nalish o\'chirildi!')
      })
    }
  }

  const handleScheduleChange = (doctorId, field, value) => {
    setScheduleForms((prev) => ({
      ...prev,
      [doctorId]: {
        ...prev[doctorId],
        [field]: value
      }
    }))
  }

  const handleScheduleDayToggle = (doctorId, dayKey, checked) => {
    setScheduleForms((prev) => {
      const current = prev[doctorId] || { availableFrom: '09:00', availableUntil: '17:00', workingDays: [] }
      const nextDays = checked
        ? [...current.workingDays, dayKey]
        : current.workingDays.filter((d) => d !== dayKey)
      return {
        ...prev,
        [doctorId]: {
          ...current,
          workingDays: nextDays
        }
      }
    })
  }

  const handleSaveSchedule = async (doctorId) => {
    const schedule = scheduleForms[doctorId]
    if (!schedule) return
    await updateDoctorSchedule(clinicOwner.id, doctorId, {
      availableFrom: schedule.availableFrom,
      availableUntil: schedule.availableUntil,
      lunchBreakStart: schedule.lunchBreakStart,
      lunchBreakEnd: schedule.lunchBreakEnd,
      workingDays: schedule.workingDays.join(',')
    })
    alert('Doktor ish vaqti yangilandi!')
  }

  const handleCompensationChange = (doctorId, field, value) => {
    setCompensationForms((prev) => {
      const current = prev[doctorId] || { compensationType: 'salary', compensationValue: '' }
      const next = { ...current, [field]: value }
      return {
        ...prev,
        [doctorId]: next
      }
    })
  }

  const handleSaveCompensation = async (doctorId) => {
    const compensation = compensationForms[doctorId]
    if (!compensation) return

    let parsedValue = null
    if (String(compensation.compensationValue || '').trim()) {
      if (compensation.compensationType === 'percent') {
        parsedValue = Number(compensation.compensationValue)
        if (!Number.isFinite(parsedValue) || parsedValue < 0 || parsedValue > 100) {
          alert('Foiz 0 dan 100 gacha bo\'lishi kerak.')
          return
        }
      } else {
        parsedValue = parseCurrencyInput(compensation.compensationValue)
        if (parsedValue < 0) {
          alert('Ish haqi manfiy bo\'lishi mumkin emas.')
          return
        }
      }
    }

    try {
      setCompensationSavingDoctorId(doctorId)
      await updateDoctorCompensation(clinicOwner.id, doctorId, {
        compensationType: compensation.compensationType,
        compensationValue: parsedValue,
      })
      alert('Doktor oylik ish haqi/foizi yangilandi!')
    } catch (error) {
      alert(error?.message || 'Ish haqi/foizni saqlashda xatolik yuz berdi')
    } finally {
      setCompensationSavingDoctorId(null)
    }
  }

  const handleSendStaffMessage = async (e) => {
    e.preventDefault()
    setStaffMessageStatus('')
    const body = String(staffMessageBody || '').trim()
    if (!body) {
      setStaffMessageStatus('❌ Habar matnini kiriting')
      return
    }
    setStaffMessageSending(true)
    try {
      const res = await clinicsApi.sendStaffMessage({ body })
      const sent = res?.sent
      setStaffMessageBody('')
      setStaffMessageStatus(`✅ Yuborildi${typeof sent === 'number' ? ` (${sent} xodim)` : ''}`)
    } catch (err) {
      setStaffMessageStatus(`❌ ${err?.message || 'Yuborishda xatolik'}`)
    } finally {
      setStaffMessageSending(false)
    }
  }

  const formatReportUpdatedAt = (value) => {
    if (!value) return '—'
    const d = value instanceof Date ? value : new Date(value)
    if (Number.isNaN(d.getTime())) return '—'
    return d.toLocaleString('uz-UZ', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const buildClinicAccountingExportData = () => {
    if (!appointmentsStats?.current) return null

    const cur = appointmentsStats.current
    const prev = appointmentsStats.previous || {}
    const comp = appointmentsStats.comparison || {}
    const history = Array.isArray(appointmentsStats.history) ? appointmentsStats.history : []
    const sortedHistory = [...history].sort((a, b) => getHistoryMonthSortValue(b) - getHistoryMonthSortValue(a))
    const monthKey = formatMonthKey(cur.year, cur.month)
    const generatedAt = new Date()
    const generatedAtIso = generatedAt.toISOString()

    const curRevenueTotal = Number(cur.revenue_total ?? cur.revenue_paid ?? 0)
    const prevRevenueTotal = Number(prev.revenue_total ?? prev.revenue_paid ?? 0)
    const curRevenuePaid = Number(cur.revenue_paid ?? 0)
    const prevRevenuePaid = Number(prev.revenue_paid ?? 0)
    const forecastRevenueTotal = Number(cur.forecast_revenue_total ?? cur.forecast_revenue_paid ?? 0)
    const forecastRevenuePaid = Number(cur.forecast_revenue_paid ?? 0)

    const summaryRows = [
      {
        "Ko'rsatkich": 'Qabullar soni',
        "Joriy oy": Number(cur.appointments ?? 0),
        "O'tgan oy": Number(prev.appointments ?? 0),
        Farq: Number(comp.appointments_diff ?? 0),
        Foiz: comp.appointments_pct ?? '',
      },
      {
        "Ko'rsatkich": 'Daromad (jami)',
        "Joriy oy": curRevenueTotal,
        "O'tgan oy": prevRevenueTotal,
        Farq: Number(comp.revenue_total_diff ?? 0),
        Foiz: comp.revenue_total_pct ?? '',
      },
      {
        "Ko'rsatkich": 'Daromad (to\'langan)',
        "Joriy oy": curRevenuePaid,
        "O'tgan oy": prevRevenuePaid,
        Farq: Number(comp.revenue_paid_diff ?? 0),
        Foiz: comp.revenue_paid_pct ?? '',
      },
      {
        "Ko'rsatkich": 'Pragnoz qabullar',
        "Joriy oy": Number(cur.forecast_appointments ?? 0),
        "O'tgan oy": '',
        Farq: '',
        Foiz: '',
      },
      {
        "Ko'rsatkich": 'Pragnoz daromad (jami)',
        "Joriy oy": forecastRevenueTotal,
        "O'tgan oy": '',
        Farq: '',
        Foiz: '',
      },
      {
        "Ko'rsatkich": 'Pragnoz daromad (to\'langan)',
        "Joriy oy": forecastRevenuePaid,
        "O'tgan oy": '',
        Farq: '',
        Foiz: '',
      },
      {
        "Ko'rsatkich": 'Eng ko\'p ixtisoslik',
        "Joriy oy": cur.top_specialization || '—',
        "O'tgan oy": prev.top_specialization || '—',
        Farq: '',
        Foiz: '',
      },
    ]

    const monthlyRows = sortedHistory.map((item) => ({
      Oy: formatMonthLabel(item.year, item.month, item.month_key),
      "Oy kodi": formatMonthCode(item.year, item.month, item.month_key),
      Qabullar: Number(item.appointments ?? 0),
      'Daromad (jami)': Number(item.revenue_total ?? item.revenue_paid ?? 0),
      "Daromad (to'langan)": Number(item.revenue_paid ?? 0),
      'Jami qabullar': Number(item.cumulative_appointments ?? 0),
      'Jami daromad': Number(item.cumulative_revenue_total ?? item.cumulative_revenue_paid ?? 0),
    }))

    return {
      monthKey,
      generatedAtIso,
      summaryRows,
      monthlyRows,
      reportInfo: {
        "Klinika": clinicOwner?.clinicName || clinicOwner?.name || '',
        "Davr": formatMonthLabel(cur.year, cur.month),
        "Yuklab olingan vaqt": generatedAt.toLocaleString('uz-UZ'),
      },
    }
  }

  const handleDownloadAppointmentsExcel = async () => {
    const exportData = buildClinicAccountingExportData()
    if (!exportData) return

    const XLSX = await import('xlsx')
    const wb = XLSX.utils.book_new()
    const infoSheet = XLSX.utils.json_to_sheet([exportData.reportInfo])
    const summarySheet = XLSX.utils.json_to_sheet(exportData.summaryRows)
    const monthlySheet = XLSX.utils.json_to_sheet(exportData.monthlyRows)
    XLSX.utils.book_append_sheet(wb, infoSheet, 'Hisobot')
    XLSX.utils.book_append_sheet(wb, summarySheet, 'Qisqa_jamlanma')
    XLSX.utils.book_append_sheet(wb, monthlySheet, 'Oylar_jamlama')
    XLSX.writeFile(wb, `clinic-accounting-report-${exportData.monthKey}.xlsx`)
  }

  const handleDownloadAppointmentsCsv = () => {
    const exportData = buildClinicAccountingExportData()
    if (!exportData) return

    const infoHeader = Object.keys(exportData.reportInfo || {})
    const summaryHeader = Object.keys(exportData.summaryRows[0] || {})
    const monthlyHeader = Object.keys(exportData.monthlyRows[0] || {
      Oy: '',
      Qabullar: 0,
      'Daromad (jami)': 0,
      "Daromad (to'langan)": 0,
      'Jami qabullar': 0,
      'Jami daromad': 0,
    })

    const rows = [
      ["Hisobot turi", "Klinika qabullar hisoboti"],
      ...infoHeader.map((key) => [key, exportData.reportInfo?.[key] ?? '']),
      [],
      ["Qisqa jamlanma"],
      summaryHeader,
      ...exportData.summaryRows.map((row) => summaryHeader.map((key) => row[key] ?? '')),
      [],
      ["Oylar bo'yicha jamlanma"],
      monthlyHeader,
      ...exportData.monthlyRows.map((row) => monthlyHeader.map((key) => row[key] ?? '')),
    ]

    downloadBlob(toCsv(rows), `clinic-accounting-report-${exportData.monthKey}.csv`, 'text/csv;charset=utf-8')
  }


  return (
    <div className="clinic-owner-dashboard">
      <DashboardSidebar />
      
      <main className="dashboard-main-content">
        <div className="dashboard-header">
          <div className="header-content">
            <h1>Salom, {clinicOwner.ownerName}!</h1>
            <p className="header-subtitle">{clinicOwner.clinicName}</p>
          </div>
          <div className="header-actions">
            <button
              className="btn-icon"
              title="Obuna to'lovi"
              onClick={() => navigate('/subscription-payment')}
            >
              💳
            </button>
            <button
              className="btn-icon"
              title="Xodimlarga habar"
              onClick={() => {
                setStaffMessageStatus('')
                setShowStaffMessageModal(true)
              }}
            >
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M15.5 1.5H4.5C3.12 1.5 2 2.62 2 4v9c0 1.38 1.12 2.5 2.5 2.5h2l0 3.5 3.5-3.5h7.5c1.38 0 2.5-1.12 2.5-2.5v-9c0-1.38-1.12-2.5-2.5-2.5z" stroke="currentColor" strokeWidth="1.5" fill="none"/>
              </svg>
            </button>
            <button
              className="btn-icon"
              title="Sozlamalar"
              onClick={() => setActiveView('settings')}
            >
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <circle cx="10" cy="10" r="2" stroke="currentColor" strokeWidth="1.5"/>
                <path d="M10 1v2M10 17v2M6.5 3.5l-1.4-1.4M15.5 12.5l1.4 1.4M3.5 6.5l-1.4 1.4M12.5 15.5l1.4 1.4M1 10h2M17 10h2M3.5 13.5l-1.4 1.4M12.5 4.5l1.4-1.4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </button>
          </div>
        </div>

        {showStaffMessageModal && (
          <div className="staff-message-modal-backdrop" onClick={() => setShowStaffMessageModal(false)}>
            <div className="staff-message-modal" onClick={(e) => e.stopPropagation()}>
              <div className="section-header-with-action">
                <h2>Xodimlarga habar</h2>
                <button
                  type="button"
                  className="btn-icon"
                  title="Yopish"
                  onClick={() => setShowStaffMessageModal(false)}
                >
                  ✕
                </button>
              </div>

              <form className="staff-message-form" onSubmit={handleSendStaffMessage}>
                <textarea
                  className="staff-message-textarea"
                  value={staffMessageBody}
                  onChange={(e) => setStaffMessageBody(e.target.value)}
                  placeholder="Klinikadagi barcha xodimlarga yuboriladigan habar..."
                  rows={4}
                  maxLength={2000}
                  disabled={staffMessageSending}
                />
                <div className="staff-message-actions">
                  <div className="staff-message-status">{staffMessageStatus}</div>
                  <button className="btn-send-staff-message" type="submit" disabled={staffMessageSending}>
                    {staffMessageSending ? 'Yuborilyapti...' : 'Yuborish'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Tab Navigation */}
        <div className="dashboard-tabs">
          <button 
            className={`tab-button ${activeView === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveView('overview')}
          >
            📊 Umumiy ko'rinish
          </button>
          <button 
            className={`tab-button ${activeView === 'doctors' ? 'active' : ''}`}
            onClick={() => setActiveView('doctors')}
          >
            👨‍⚕️ Doktorlar boshqaruvi
          </button>
        </div>

        <div className="dashboard-content">
          
          {/* Overview Tab */}
          {activeView === 'overview' && (
            <>
              {/* Statistics Cards */}
              <section className="dashboard-section">
                <h2>Klinika statistikasi</h2>
                <div className="report-updated-at">Oxirgi yangilanish: {formatReportUpdatedAt(clinicStatsUpdatedAt)}</div>
                {clinicStatsError && (
                  <div className="appointments-loading">{clinicStatsError}</div>
                )}
                <div className="clinic-statistics-grid">
                  <div className="stat-card doctors">
                    <div className="stat-icon">👨‍⚕️</div>
                    <div className="stat-content">
                      <h3>Faol doktorlar</h3>
                      <p className="stat-value">{clinicStatsLoading ? '...' : `${activeDoctors} ta`}</p>
                      <span className="stat-detail">Jami: {clinicStatsLoading ? '...' : `${totalDoctors} ta`}</span>
                    </div>
                  </div>
                  <div className="stat-card hours">
                    <div className="stat-icon">⏰</div>
                    <div className="stat-content">
                      <h3>Oylik jami soat</h3>
                      <p className="stat-value">{clinicStatsLoading ? '...' : `${totalWorkHours.toFixed(1)} soat`}</p>
                      <span className="stat-detail">Barcha doktorlar bo'yicha</span>
                    </div>
                  </div>
                  <div className="stat-card patients">
                    <div className="stat-icon">🏥</div>
                    <div className="stat-content">
                      <h3>Oylik jami bemorlar</h3>
                      <p className="stat-value">{clinicStatsLoading ? '...' : `${monthlyTotalPatients} ta`}</p>
                      <span className="stat-detail">Oy boshidan jamlanadi, oy almashganda 0 dan boshlanadi</span>
                    </div>
                  </div>
                  <div className="stat-card revenue">
                    <div className="stat-icon">💰</div>
                    <div className="stat-content">
                      <h3>Jami doktorlar oylik Daromadi</h3>
                      <p className="stat-value">{clinicStatsLoading ? '...' : formatSom(monthlyEstimatedRevenue)}</p>
                      <span className="stat-detail">Har doktor narxi × shu oy ko'rilgan bemorlar soni</span>
                    </div>
                  </div>
                </div>

                <div className="doctor-revenue-breakdown">
                  <h3>Doktorlar kesimida oylik daromad</h3>
                  {clinicStatsLoading ? (
                    <p className="doctor-revenue-empty">Yuklanyapti...</p>
                  ) : activeMonthlyRevenueByDoctor.length === 0 ? (
                    <p className="doctor-revenue-empty">Hozircha bu oy uchun ma'lumot yo'q</p>
                  ) : (
                    <div className="doctor-revenue-list">
                      {activeMonthlyRevenueByDoctor.map((item) => (
                        <div className="doctor-revenue-row" key={item.doctor_id}>
                          <div className="doctor-revenue-name">{item.doctor_name}</div>
                          <div className="doctor-revenue-meta">
                            {item.seen_patients} ta bemor × {formatSom(item.consultation_fee)}
                            <span className="doctor-revenue-share"> • Ulushi: {getDoctorRevenueShare(item.estimated_revenue).toFixed(1)}%</span>
                          </div>
                          <div className="doctor-revenue-value">{formatSom(item.estimated_revenue)}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </section>

            </>
          )}

          {activeView === 'appointments' && (
            <>
              <section className="dashboard-section">
                <div className="section-header-with-action">
                  <div>
                    <h2>Qabullar statistikasi (shu oy)</h2>
                    <div className="report-updated-at">Oxirgi yangilanish: {formatReportUpdatedAt(appointmentsStatsUpdatedAt)}</div>
                  </div>
                  <div className="appointments-actions">
                    <button
                      type="button"
                      className="btn-appointments-download"
                      disabled={!appointmentsStats || appointmentsLoading}
                      onClick={handleDownloadAppointmentsExcel}
                    >
                      Excel
                    </button>
                    <button
                      type="button"
                      className="btn-appointments-download"
                      disabled={!appointmentsStats || appointmentsLoading}
                      onClick={handleDownloadAppointmentsCsv}
                    >
                      CSV
                    </button>
                  </div>
                </div>

                {appointmentsLoading ? (
                  <div className="appointments-loading">Yuklanyapti...</div>
                ) : appointmentsError ? (
                  <div className="appointments-loading">{appointmentsError}</div>
                ) : !appointmentsStats?.current ? (
                  <div className="appointments-loading">Ma'lumot topilmadi</div>
                ) : (
                  <div className="appointments-stats-grid">
                    <div className="appointments-stat-card">
                      <div className="appointments-stat-label">Qabullar (shu oy)</div>
                      <div className="appointments-stat-value">{appointmentsStats.current.appointments}</div>
                      <div className="appointments-stat-sub">
                        O'tgan oy: {appointmentsStats.previous?.appointments ?? 0} • Farq:{' '}
                        {(appointmentsStats.comparison?.appointments_diff ?? 0) >= 0 ? '+' : ''}
                        {appointmentsStats.comparison?.appointments_diff ?? 0}
                        {typeof appointmentsStats.comparison?.appointments_pct === 'number'
                          ? ` (${appointmentsStats.comparison.appointments_pct.toFixed(1)}%)`
                          : ''}
                      </div>
                    </div>
                    <div className="appointments-stat-card">
                      <div className="appointments-stat-label">Daromad (jami, shu oy)</div>
                      <div className="appointments-stat-value">{formatSom(appointmentsStats.current.revenue_total ?? appointmentsStats.current.revenue_paid)}</div>
                      <div className="appointments-stat-sub">
                        To'langan: {formatSom(appointmentsStats.current.revenue_paid ?? 0)} • O'tgan oy: {formatSom(appointmentsStats.previous?.revenue_total ?? appointmentsStats.previous?.revenue_paid ?? 0)} • Farq:{' '}
                        {(appointmentsStats.comparison?.revenue_total_diff ?? 0) >= 0 ? '+' : ''}
                        {Math.round(appointmentsStats.comparison?.revenue_total_diff ?? 0).toLocaleString()} so'm
                        {typeof appointmentsStats.comparison?.revenue_total_pct === 'number'
                          ? ` (${appointmentsStats.comparison.revenue_total_pct.toFixed(1)}%)`
                          : ''}
                      </div>
                    </div>
                    <div className="appointments-stat-card">
                      <div className="appointments-stat-label">Pragnoz (oy oxiri) qabullar</div>
                      <div className="appointments-stat-value">{appointmentsStats.current.forecast_appointments}</div>
                      <div className="appointments-stat-sub">
                        {appointmentsStats.current.days_elapsed}/{appointmentsStats.current.days_in_month} kun bo'yicha
                      </div>
                    </div>
                    <div className="appointments-stat-card">
                      <div className="appointments-stat-label">Pragnoz (oy oxiri) daromad</div>
                      <div className="appointments-stat-value">{formatSom(appointmentsStats.current.forecast_revenue_total ?? appointmentsStats.current.forecast_revenue_paid)}</div>
                      <div className="appointments-stat-sub">To'langan: {formatSom(appointmentsStats.current.forecast_revenue_paid ?? 0)}</div>
                    </div>
                    <div className="appointments-stat-card">
                      <div className="appointments-stat-label">Eng ko'p ixtisoslik</div>
                      <div className="appointments-stat-value">{appointmentsStats.current.top_specialization || '—'}</div>
                    </div>
                  </div>
                )}

                {!appointmentsLoading && !appointmentsError && appointmentsStats?.current && (
                  <div className="appointments-history-wrap">
                    <h3>Oylar bo'yicha jamlama</h3>
                    {Array.isArray(appointmentsStats.history) && appointmentsStats.history.length > 0 ? (
                      <div className="appointments-history-table-wrap">
                        <table className="appointments-history-table">
                          <thead>
                            <tr>
                              <th>Oy</th>
                              <th>Qabullar</th>
                              <th>Daromad (jami)</th>
                              <th>Daromad (to'langan)</th>
                              <th>Jami qabullar</th>
                              <th>Jami daromad</th>
                            </tr>
                          </thead>
                          <tbody>
                            {[...appointmentsStats.history]
                              .sort((a, b) => getHistoryMonthSortValue(b) - getHistoryMonthSortValue(a))
                              .map((item) => (
                              <tr key={item.month_key || formatMonthKey(item.year, item.month)}>
                                <td className="appointments-month-cell">
                                  <span className="appointments-month-main">{formatMonthLabel(item.year, item.month, item.month_key)}</span>
                                  <span className="appointments-month-sub">{formatMonthCode(item.year, item.month, item.month_key)}</span>
                                </td>
                                <td>{item.appointments ?? 0}</td>
                                <td>{formatSom(item.revenue_total ?? item.revenue_paid ?? 0)}</td>
                                <td>{formatSom(item.revenue_paid ?? 0)}</td>
                                <td>{item.cumulative_appointments ?? 0}</td>
                                <td>{formatSom(item.cumulative_revenue_total ?? item.cumulative_revenue_paid ?? 0)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="appointments-loading">Tarixiy oylar uchun ma'lumot topilmadi</div>
                    )}
                  </div>
                )}
              </section>
            </>
          )}

          {activeView === 'settings' && (
            <>
              <section className="dashboard-section">
                <div className="section-header-with-action">
                  <h2>Sozlamalar</h2>
                </div>

                <form className="clinic-settings-form" onSubmit={handleSaveSettings}>
                  <div className="settings-grid">
                    <div className="form-group">
                      <label>Klinika nomi</label>
                      <input
                        type="text"
                        value={settingsForm.name}
                        onChange={(e) => setSettingsForm({ ...settingsForm, name: e.target.value })}
                        required
                        disabled={settingsSaving}
                      />
                    </div>

                    <div className="form-group">
                      <label>Email</label>
                      <input
                        type="email"
                        value={settingsForm.email}
                        onChange={(e) => setSettingsForm({ ...settingsForm, email: e.target.value })}
                        onBlur={(e) => setSettingsForm({ ...settingsForm, email: normalizeEmailWithDefaultDomain(e.target.value) })}
                        required
                        disabled={settingsSaving}
                      />
                    </div>

                    <div className="form-group">
                      <label>Telefon</label>
                      <input
                        type="tel"
                        value={settingsForm.phone_number}
                        onChange={(e) => setSettingsForm({ ...settingsForm, phone_number: e.target.value })}
                        required
                        disabled={settingsSaving}
                      />
                    </div>

                    <div className="form-group">
                      <label>Website (ixtiyoriy)</label>
                      <input
                        type="url"
                        value={settingsForm.website}
                        onChange={(e) => setSettingsForm({ ...settingsForm, website: e.target.value })}
                        placeholder="https://"
                        disabled={settingsSaving}
                      />
                    </div>

                    <div className="form-group full-width">
                      <label>Ish vaqti</label>
                      <div className="working-hours-row">
                        <div className="working-hours-field">
                          <span>Boshlanish</span>
                          <input
                            type="time"
                            value={settingsWorkingHoursRange.from}
                            onChange={(e) => {
                              setSettingsWorkingHoursRange((prev) => ({ ...prev, from: e.target.value || prev.from }))
                              if (settingsWorkingHoursError) setSettingsWorkingHoursError('')
                            }}
                            required
                            disabled={settingsSaving}
                          />
                        </div>
                        <div className="working-hours-separator">—</div>
                        <div className="working-hours-field">
                          <span>Tugash</span>
                          <input
                            type="time"
                            value={settingsWorkingHoursRange.to}
                            onChange={(e) => {
                              setSettingsWorkingHoursRange((prev) => ({ ...prev, to: e.target.value || prev.to }))
                              if (settingsWorkingHoursError) setSettingsWorkingHoursError('')
                            }}
                            required
                            disabled={settingsSaving}
                          />
                        </div>
                      </div>
                      <div className="working-hours-preview">
                        Ko‘rinishi: {settingsWorkingHoursRange.from} - {settingsWorkingHoursRange.to}
                      </div>
                      {settingsWorkingHoursError && (
                        <div className="settings-inline-error">{settingsWorkingHoursError}</div>
                      )}
                    </div>

                    <div className="form-group full-width">
                      <label>Manzil</label>
                      <input
                        type="text"
                        value={settingsForm.address}
                        onChange={(e) => setSettingsForm({ ...settingsForm, address: e.target.value })}
                        required
                        disabled={settingsSaving}
                      />
                    </div>

                    <div className="form-group full-width">
                      <label>Tavsif (ixtiyoriy)</label>
                      <textarea
                        rows="4"
                        value={settingsForm.description}
                        onChange={(e) => setSettingsForm({ ...settingsForm, description: e.target.value })}
                        disabled={settingsSaving}
                      />
                    </div>

                    <div className="form-group full-width">
                      <label>Yangi parol (ixtiyoriy)</label>
                      <PasswordInput
                        value={settingsForm.owner_password}
                        onChange={(e) => setSettingsForm({ ...settingsForm, owner_password: e.target.value })}
                        placeholder="Yangi parol"
                        disabled={settingsSaving}
                      />
                    </div>
                  </div>

                  {settingsMessage && (
                    <div className="settings-message">{settingsMessage}</div>
                  )}

                  <button
                    type="submit"
                    className="btn-save-settings"
                    disabled={settingsSaving}
                  >
                    {settingsSaving ? 'Saqlanmoqda...' : 'Saqlash'}
                  </button>
                </form>
              </section>

              <section className="dashboard-section clinic-banner-section">
                <div className="section-header-with-action">
                  <h2>Klinika fon rasmi</h2>
                </div>
                <div className="clinic-banner-grid">
                  <div className="banner-preview-container">
                    {bannerPreviewUrl || clinicOwner.banner_image ? (
                      <img
                        className="banner-preview"
                        src={bannerPreviewUrl || clinicOwner.banner_image}
                        alt="Klinika fon rasmi"
                      />
                    ) : (
                      <div className="banner-placeholder">
                        Fon rasm yo'q
                      </div>
                    )}
                  </div>

                  <div className="banner-upload-controls">
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleBannerFileChange}
                      disabled={bannerSaving}
                    />
                    <button
                      type="button"
                      className="btn-upload-banner"
                      onClick={handleSaveBanner}
                      disabled={!bannerFile || bannerSaving}
                    >
                      {bannerSaving ? 'Saqlanmoqda...' : 'Saqlash'}
                    </button>
                  </div>
                </div>
              </section>
            </>
          )}

          {/* Doctors Management Tab */}
          {(activeView === 'doctors' || activeView === 'former-doctors') && (
            <>
              <section className="dashboard-section">
                <div className="section-header-with-action">
                  <h2>{activeView === 'former-doctors' ? 'Ishdan olinganlar' : 'Doktorlar boshqaruvi'}</h2>
                  {activeView === 'doctors' && (
                    <button
                      className="btn-add-doctor"
                      onClick={() => setShowAddDoctor(!showAddDoctor)}
                    >
                      {showAddDoctor ? '✕ Bekor' : '+ Doktor Qo\'shish'}
                    </button>
                  )}
                </div>

                {activeView === 'former-doctors' && (
                  <div className="appointments-stats-grid" style={{ marginBottom: '1rem' }}>
                    <div className="appointments-stat-card">
                      <div className="appointments-stat-label">Ishdan olingan doktorlar</div>
                      <div className="appointments-stat-value">{formerDoctorsCount}</div>
                      <div className="appointments-stat-sub">Tarixiy ro'yxat (joriy klinika)</div>
                    </div>
                    <div className="appointments-stat-card">
                      <div className="appointments-stat-label">Tarixiy oylik daromad</div>
                      <div className="appointments-stat-value">{formatSom(formerMonthlyRevenueTotal)}</div>
                      <div className="appointments-stat-sub">Jami (ishdan olinganlar kartalari bo'yicha)</div>
                    </div>
                    <div className="appointments-stat-card">
                      <div className="appointments-stat-label">Tarixiy oylik ish haqi</div>
                      <div className="appointments-stat-value">{formatSom(formerMonthlySalaryTotal)}</div>
                      <div className="appointments-stat-sub">Jami (ishdan olinganlar kartalari bo'yicha)</div>
                    </div>
                  </div>
                )}

                {activeView === 'doctors' && showAddDoctor && (
                  <form className="add-doctor-form" onSubmit={handleAddDoctor}>
                    <div className="form-grid">
                      <div className="form-group">
                        <label>JSHSHIR</label>
                        <input
                          type="text"
                          inputMode="numeric"
                          pattern="[0-9]*"
                          maxLength={14}
                          placeholder="12345678901234"
                          value={doctorForm.pinfl}
                          className={doctorFormErrors.pinfl ? 'input-error' : ''}
                          onChange={(e) => {
                            setDoctorForm({ ...doctorForm, pinfl: e.target.value.replace(/\D+/g, '') })
                            if (doctorFormErrors.pinfl || doctorFormErrors.general) {
                              setDoctorFormErrors((prev) => ({ ...prev, pinfl: '', general: '' }))
                            }
                          }}
                          required
                        />
                        {doctorFormErrors.pinfl && (
                          <p className="form-field-error">{doctorFormErrors.pinfl}</p>
                        )}
                      </div>
                      <div className="form-group">
                        <label>Pasport/ID</label>
                        <input
                          type="text"
                          placeholder="AA1234567"
                          value={doctorForm.passportId}
                          className={doctorFormErrors.passportId ? 'input-error' : ''}
                          onChange={(e) => {
                            setDoctorForm({ ...doctorForm, passportId: e.target.value.replace(/\s+/g, '').toUpperCase() })
                            if (doctorFormErrors.passportId || doctorFormErrors.general) {
                              setDoctorFormErrors((prev) => ({ ...prev, passportId: '', general: '' }))
                            }
                          }}
                        />
                        {doctorFormErrors.passportId && (
                          <p className="form-field-error">{doctorFormErrors.passportId}</p>
                        )}
                      </div>
                      <div className="form-group full-width">
                        <div className={`identity-check-hint ${identityCheckState.status || 'idle'}`}>
                          {identityCheckState.loading
                            ? 'JSHSHIR/Pasport real-time tekshirilmoqda...'
                            : (identityCheckState.message || 'JSHSHIR va Pasport kiritilganda real-time tekshiruv ishlaydi.')}
                        </div>
                      </div>
                      <div className="form-group">
                        <label>Tug'ilgan sana</label>
                        <input
                          type="date"
                          value={doctorForm.dateOfBirth}
                          className={doctorFormErrors.dateOfBirth ? 'input-error' : ''}
                          onChange={(e) => {
                            setDoctorForm({ ...doctorForm, dateOfBirth: e.target.value })
                            if (doctorFormErrors.dateOfBirth) {
                              setDoctorFormErrors((prev) => ({ ...prev, dateOfBirth: '' }))
                            }
                          }}
                        />
                        {doctorFormErrors.dateOfBirth && (
                          <p className="form-field-error">{doctorFormErrors.dateOfBirth}</p>
                        )}
                      </div>
                      <div className="form-group">
                        <label>Ism</label>
                        <input
                          type="text"
                          placeholder="Ali"
                          value={doctorForm.firstName}
                          className={doctorFormErrors.firstName ? 'input-error' : ''}
                          onChange={(e) => {
                            setDoctorForm({ ...doctorForm, firstName: e.target.value })
                            if (doctorFormErrors.firstName) {
                              setDoctorFormErrors((prev) => ({ ...prev, firstName: '' }))
                            }
                          }}
                        />
                        {doctorFormErrors.firstName && (
                          <p className="form-field-error">{doctorFormErrors.firstName}</p>
                        )}
                      </div>
                      <div className="form-group">
                        <label>Familiya</label>
                        <input
                          type="text"
                          placeholder="Karimov"
                          value={doctorForm.lastName}
                          className={doctorFormErrors.lastName ? 'input-error' : ''}
                          onChange={(e) => {
                            setDoctorForm({ ...doctorForm, lastName: e.target.value })
                            if (doctorFormErrors.lastName) {
                              setDoctorFormErrors((prev) => ({ ...prev, lastName: '' }))
                            }
                          }}
                        />
                        {doctorFormErrors.lastName && (
                          <p className="form-field-error">{doctorFormErrors.lastName}</p>
                        )}
                      </div>
                      <div className="form-group">
                        <label>Email</label>
                        <input
                          type="email"
                          placeholder="doctor@example.uz"
                          value={doctorForm.email}
                          className={doctorFormErrors.email ? 'input-error' : ''}
                          onChange={(e) => {
                            const value = e.target.value
                            setDoctorForm({ ...doctorForm, email: value })
                            if (doctorFormErrors.email || doctorFormErrors.general) {
                              setDoctorFormErrors((prev) => ({ ...prev, email: '', general: '' }))
                            }
                          }}
                          onBlur={(e) => setDoctorForm({ ...doctorForm, email: normalizeEmailWithDefaultDomain(e.target.value) })}
                        />
                        {doctorFormErrors.email && (
                          <p className="form-field-error">{doctorFormErrors.email}</p>
                        )}
                      </div>
                      <div className="form-group">
                        <label>Telefon</label>
                        <input
                          type="tel"
                          placeholder="+998 90 123 45 67"
                          value={doctorForm.phone}
                          className={doctorFormErrors.phone ? 'input-error' : ''}
                          onChange={(e) => {
                            setDoctorForm({ ...doctorForm, phone: e.target.value })
                            if (doctorFormErrors.phone) {
                              setDoctorFormErrors((prev) => ({ ...prev, phone: '' }))
                            }
                          }}
                        />
                        {doctorFormErrors.phone && (
                          <p className="form-field-error">{doctorFormErrors.phone}</p>
                        )}
                      </div>
                      <div className="form-group">
                        <label>Ish haqi turi</label>
                        <select
                          value={doctorForm.compensationType}
                          onChange={(e) => {
                            setDoctorForm({ ...doctorForm, compensationType: e.target.value })
                            setCompensationClearedOnFocus(false)
                          }}
                        >
                          <option value="salary">Ish haqi</option>
                          <option value="percent">Foiz</option>
                        </select>
                      </div>
                      <div className="form-group">
                        <label>{doctorForm.compensationType === 'percent' ? 'Foiz (%)' : 'Ish haqi (so\'m)'}</label>
                        <input
                          type="text"
                          inputMode="numeric"
                          placeholder={doctorForm.compensationType === 'percent' ? '20' : '5000000'}
                          value={doctorForm.compensationValue}
                          onFocus={() => {
                            if (compensationClearedOnFocus || !doctorForm.compensationValue) {
                              return
                            }
                            setDoctorForm((prev) => ({ ...prev, compensationValue: '' }))
                            setCompensationClearedOnFocus(true)
                          }}
                          onChange={(e) => {
                            const rawValue = e.target.value
                            const nextValue = doctorForm.compensationType === 'percent'
                              ? (() => {
                                  const percent = parseCurrencyInput(rawValue)
                                  if (!percent && rawValue.trim() === '') return ''
                                  return String(Math.min(percent, 100))
                                })()
                              : formatCurrencyInput(rawValue)
                            setDoctorForm({ ...doctorForm, compensationValue: nextValue })
                          }}
                        />
                      </div>
                      <div className="form-group">
                        <label>Konsultatsiya narxi (so'm) *</label>
                        <input
                          type="text"
                          inputMode="numeric"
                          placeholder="50 000"
                          value={doctorForm.consultationFee}
                          className={doctorFormErrors.consultationFee ? 'input-error' : ''}
                          onChange={(e) => setDoctorForm({
                            ...doctorForm,
                            consultationFee: formatCurrencyInput(e.target.value)
                          })}
                          required
                        />
                        {doctorFormErrors.consultationFee && (
                          <p className="form-field-error">{doctorFormErrors.consultationFee}</p>
                        )}
                      </div>
                      <div className="form-group full-width">
                        <div className="specialization-header">
                          <span>Ixtisoslik(lar) *</span>
                          <button
                            type="button"
                            className="btn-refresh-specs"
                            onClick={() => fetchSpecializations()}
                          >
                            Yangilash
                          </button>
                        </div>
                        <div className="specialization-manual-wrap">
                          <input
                            type="text"
                            placeholder="Ixtisoslik nomini yozing (masalan: kard...)"
                            value={doctorForm.specializationInput}
                            onFocus={() => {
                              setShowSpecializationSuggestions(true)
                              if (!(specializations || []).length) {
                                fetchSpecializations()
                              }
                            }}
                            onChange={(e) => {
                              setDoctorForm({ ...doctorForm, specializationInput: e.target.value })
                              if (specializationCreateMessage) {
                                setSpecializationCreateMessage('')
                              }
                            }}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' || e.key === ',') {
                                e.preventDefault()
                                addSpecializationFromInput(doctorForm.specializationInput)
                              }
                            }}
                            onBlur={() => {
                              addSpecializationFromInput(doctorForm.specializationInput)
                              setTimeout(() => setShowSpecializationSuggestions(false), 120)
                            }}
                          />
                          {showSpecializationSuggestions && specializationSuggestions.length > 0 && (
                            <div className="specialization-suggestions">
                              {specializationSuggestions.map((spec) => (
                                <button
                                  key={spec.id}
                                  type="button"
                                  className="specialization-suggestion-item"
                                  onMouseDown={(e) => {
                                    e.preventDefault()
                                    setDoctorForm((prev) => ({
                                      ...prev,
                                      specialization_ids: [...prev.specialization_ids, spec.id],
                                      specializationInput: ''
                                    }))
                                  }}
                                >
                                  {spec.name}
                                </button>
                              ))}
                            </div>
                          )}
                          {doctorForm.specializationInput.trim() && specializationSuggestions.length === 0 && (
                            <div className="spec-required-hint" style={{ marginTop: '8px' }}>
                              Ro'yxatda topilmadi.
                              {' '}
                              <button
                                type="button"
                                className="btn-refresh-specs"
                                onMouseDown={(e) => e.preventDefault()}
                                onClick={() => createSpecializationFromInput(doctorForm.specializationInput)}
                                disabled={specializationCreateLoading}
                              >
                                {specializationCreateLoading ? 'Yaratilmoqda...' : 'Yangi ixtisoslik qo\'shish'}
                              </button>
                            </div>
                          )}
                          {specializationCreateMessage && (
                            <p className="spec-required-hint">{specializationCreateMessage}</p>
                          )}
                        </div>

                        <div className="selected-specializations">
                          {selectedSpecializationObjects.map((spec) => (
                            <span key={spec.id} className="selected-spec-chip">
                              {spec.name}
                              <button type="button" onClick={() => removeSpecialization(spec.id)}>×</button>
                            </span>
                          ))}
                        </div>
                        {doctorForm.specialization_ids.length === 0 && (
                          <p className="spec-required-hint">{doctorFormErrors.specialization_ids || 'Kamida bitta ixtisoslik tanlang'}</p>
                        )}
                      </div>
                      <div className="form-group">
                        <label>Ish boshlanishi</label>
                        <input
                          type="time"
                          value={doctorForm.availableFrom}
                          onChange={(e) => setDoctorForm({ ...doctorForm, availableFrom: e.target.value })}
                          required
                        />
                      </div>
                      <div className="form-group">
                        <label>Ish tugashi</label>
                        <input
                          type="time"
                          value={doctorForm.availableUntil}
                          onChange={(e) => setDoctorForm({ ...doctorForm, availableUntil: e.target.value })}
                          required
                        />
                      </div>
                      <div className="form-group">
                        <label>Abet boshlanishi</label>
                        <input
                          type="time"
                          value={doctorForm.lunchBreakStart}
                          onChange={(e) => setDoctorForm({ ...doctorForm, lunchBreakStart: e.target.value })}
                        />
                      </div>
                      <div className="form-group">
                        <label>Abet tugashi</label>
                        <input
                          type="time"
                          value={doctorForm.lunchBreakEnd}
                          onChange={(e) => setDoctorForm({ ...doctorForm, lunchBreakEnd: e.target.value })}
                        />
                      </div>
                      <div className="form-group full-width">
                        <label>Ish kunlari</label>
                        <div className="workdays-grid">
                          {dayOptions.map((day) => (
                            <label key={day.key} className="workday-item">
                              <input
                                type="checkbox"
                                checked={doctorForm.workingDays.includes(day.key)}
                                onChange={(e) => {
                                  const nextDays = e.target.checked
                                    ? [...doctorForm.workingDays, day.key]
                                    : doctorForm.workingDays.filter((d) => d !== day.key)
                                  setDoctorForm({ ...doctorForm, workingDays: nextDays })
                                }}
                              />
                              <span>{day.label}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                      <div className="form-group">
                        <label>Parol (doktor uchun)</label>
                        <PasswordInput
                          placeholder="Parol"
                          value={doctorForm.password}
                          onChange={(e) => {
                            setDoctorForm({ ...doctorForm, password: e.target.value })
                            if (doctorFormErrors.password) {
                              setDoctorFormErrors((prev) => ({ ...prev, password: '' }))
                            }
                          }}
                        />
                        {doctorFormErrors.password && (
                          <p className="form-field-error">{doctorFormErrors.password}</p>
                        )}
                      </div>
                    </div>
                    {doctorFormErrors.general && (
                      <p className="form-field-error">{doctorFormErrors.general}</p>
                    )}
                    <button
                      type="submit"
                      className="btn-submit-doctor"
                      disabled={!doctorForm.pinfl || identityCheckState.loading || identityCheckState.canSubmit === false}
                    >
                      Qo'shish
                    </button>
                  </form>
                )}

                <div className="doctors-list">
                  {doctorsListForView.length > 0 ? (
                    doctorsListForView.map((doctor) => {
                      const schedule = scheduleForms[doctor.id] || {
                        availableFrom: doctor.availableFrom || '09:00',
                        availableUntil: doctor.availableUntil || '17:00',
                        lunchBreakStart: doctor.lunchBreakStart || '',
                        lunchBreakEnd: doctor.lunchBreakEnd || '',
                        workingDays: (doctor.workingDays || 'Mon,Tue,Wed,Thu,Fri')
                          .split(',')
                          .map((d) => d.trim())
                          .filter(Boolean)
                      }
                      const compensation = compensationForms[doctor.id] || {
                        compensationType: doctor.compensationType || 'salary',
                        compensationValue: doctor.compensationType === 'percent'
                          ? String(doctor.compensationValue || '')
                          : formatCurrencyInput(doctor.compensationValue || '')
                      }
                      const isFormerDoctor = doctor.isFormerForClinic || doctor.clinicAssociationStatus === 'former'
                      const doctorRating = Number(doctor.raw?.rating || 0)
                      const doctorRatingCount = Number(doctor.raw?.total_ratings || 0)
                      const ratingPercent = Math.max(0, Math.min(100, (doctorRating / 5) * 100))
                      const doctorCardTab = doctorCardTabs[doctor.id] || 'salary'

                      if (isFormerDoctor) {
                        return (
                          <div key={doctor.id} className="doctor-work-card former-doctor-card former-doctor-card-modern">
                            <div className="former-doctor-top">
                              <div className="former-doctor-identity">
                                <div className="doctor-avatar-placeholder former-avatar">{doctor.fullName.charAt(0)}</div>
                                <div className="former-doctor-text">
                                  <h3>{doctor.fullName}</h3>
                                  <p>{doctor.specialization} • {doctor.experience} tajriba</p>
                                </div>
                              </div>
                              <div className="former-doctor-actions">
                                <span className="status-badge former">Bo'shatilgan</span>
                                <button
                                  type="button"
                                  className="btn-former-history"
                                  onClick={() => setActiveView('appointments')}
                                >
                                  Tarixiy hisobot
                                </button>
                              </div>
                            </div>

                            <div className="former-doctor-dismissed-date">
                              <span className="former-doctor-date-icon">📅</span>
                              <span>Bo'shatilgan sana: {doctor.scopedEmploymentEndedAt ? new Date(doctor.scopedEmploymentEndedAt).toLocaleDateString('uz-UZ') : '—'}</span>
                            </div>

                            <div className="former-doctor-stats-panel">
                              <div className="former-doctor-stats-title">📊 Statistikasi</div>
                              <div className="former-doctor-stats-grid">
                                <div className="former-stat-item">
                                  <span className="former-stat-label">Ish soati</span>
                                  <span className="former-stat-value">{doctor.monthlyHours ? `${doctor.monthlyHours.toFixed(1)} soat` : '0 soat'}</span>
                                </div>
                                <div className="former-stat-item">
                                  <span className="former-stat-label">Daromad</span>
                                  <span className="former-stat-value">{formatSom(doctor.monthlyEffectiveRevenue || 0)}</span>
                                </div>
                                <div className="former-stat-item">
                                  <span className="former-stat-label">Ish haqi</span>
                                  <span className="former-stat-value">{formatSom(doctor.monthlyEstimatedSalary || 0)}</span>
                                </div>
                                <div className="former-stat-item">
                                  <span className="former-stat-label">Rating</span>
                                  <span className="former-stat-value former-rating-value">
                                    {doctor.raw?.rating ? `${doctor.raw.rating}` : '0.0'}
                                    <span className="former-rating-scale">/5</span>
                                  </span>
                                  <span className="former-stat-detail">{doctor.raw?.total_ratings || 0} baho</span>
                                </div>
                              </div>
                            </div>

                            <div className="work-note former-work-note">
                              ⚠ Bu doktor klinikadan bo'shatilgan. Faqat tarixiy ma'lumotlar saqlangan.
                            </div>
                          </div>
                        )
                      }

                      return (
                        <div key={doctor.id} className="doctor-work-card doctor-active-card">
                          <div className="doctor-active-header">
                            <div className="doctor-left">
                              <div className="doctor-avatar-placeholder">
                                {doctor.fullName.charAt(0)}
                                {doctor.isCheckedIn && (
                                  <span className="online-indicator" title="Ishda"></span>
                                )}
                              </div>
                              <div className="doctor-info">
                                <div className="doctor-name-status">
                                  <h3>{doctor.fullName}</h3>
                                  <span className={`status-badge ${doctor.status === 'active' ? 'active' : 'suspended'}`}>
                                    {doctor.status === 'active' ? '✓ Faol' : '⏸ To\'xtatilgan'}
                                  </span>
                                  {doctor.isCheckedIn && (
                                    <span className="check-in-badge" title="Doktor ishda">🟢 Ishda</span>
                                  )}
                                </div>
                                <p className="doctor-active-subtitle">
                                  {doctor.specialization} • {doctor.isCheckedIn ? 'Ishlayapti' : doctor.status === 'active' ? 'Tayyor' : 'To\'xtatilgan'}
                                </p>
                              </div>
                            </div>

                            <div className="doctor-actions doctor-active-actions">
                              <a href={`tel:${doctor.phone}`} className="btn-icon btn-icon-call" title="Qo'ng'iroq qilish">
                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="17" height="17"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.11 13 19.79 19.79 0 0 1 1.06 4.38 2 2 0 0 1 3.03 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 21 17z"/></svg>
                              </a>
                              <button
                                className={`btn-toggle-status ${doctor.status === 'active' ? 'active' : 'suspended'}`}
                                onClick={() => handleToggleStatus(doctor)}
                                title={doctor.status === 'active' ? 'To\'xtatish' : 'Faollashtirish'}
                              >
                                {doctor.status === 'active' ? (
                                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" width="17" height="17"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
                                ) : (
                                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="17" height="17"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                                )}
                              </button>
                              <button
                                className="btn-icon btn-delete"
                                onClick={async () => {
                                  if (window.confirm(`${doctor.fullName}ni klinikadan bo'shatish kerakmi?`)) {
                                    try {
                                      await deleteDoctor(clinicOwner.id, doctor.id)
                                      alert('Doktor klinikadan bo\'shatildi. Profil saqlandi!')
                                    } catch (error) {
                                      alert(error?.message || 'Doktorni bo\'shatishda xatolik yuz berdi')
                                    }
                                  }
                                }}
                                title="Klinikadan bo'shatish"
                              >
                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="17" height="17"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><line x1="18" y1="8" x2="23" y2="13"/><line x1="23" y1="8" x2="18" y2="13"/></svg>
                              </button>
                            </div>
                          </div>

                          <div className="doctor-active-metrics-grid">
                            <div className="doctor-active-metric">
                              <span className="doctor-active-metric-label">🕒 Bugun kelgan</span>
                              <span className="doctor-active-metric-value">{doctor.todayCheckedIn || '--:--'}</span>
                            </div>
                            <div className="doctor-active-metric">
                              <span className="doctor-active-metric-label">⏱ Ishdan ketgan</span>
                              <span className="doctor-active-metric-value">{doctor.todayCheckedOut || '--:--'}</span>
                            </div>
                            <div className="doctor-active-metric">
                              <span className="doctor-active-metric-label">💸 Oylik daromad</span>
                              <span className="doctor-active-metric-value">{formatSom(doctor.monthlyEffectiveRevenue || 0)}</span>
                            </div>
                            <div className="doctor-active-metric">
                              <span className="doctor-active-metric-label">💼 Oylik ish haqi</span>
                              <span className="doctor-active-metric-value">{formatSom(doctor.monthlyEstimatedSalary || 0)}</span>
                            </div>
                            <div className="doctor-active-metric doctor-active-metric-wide">
                              <span className="doctor-active-metric-label">👥 Bugungi bemorlar</span>
                              <span className="doctor-active-metric-value">{doctor.todayPatients || 0}</span>
                            </div>
                            <div className="doctor-active-metric doctor-active-metric-rating">
                              <div className="doctor-active-rating-row">
                                <span className="doctor-active-metric-label">⭐ Rating</span>
                                <span className="doctor-active-metric-value">{doctorRating.toFixed(1)} / 5</span>
                              </div>
                              <div className="doctor-rating-progress">
                                <span style={{ width: `${ratingPercent}%` }}></span>
                              </div>
                              <span className="doctor-active-metric-detail">{doctorRatingCount} baho</span>
                            </div>
                          </div>

                          <div className="work-note doctor-active-note">
                            Iltimos klinika bo'yicha doktorning oylik/minimal foiz stavkasini belgilang.
                          </div>

                          <div className="doctor-active-tabs">
                            <button
                              type="button"
                              className={`doctor-active-tab ${doctorCardTab === 'salary' ? 'active' : ''}`}
                              onClick={() => setDoctorCardTabs((prev) => ({ ...prev, [doctor.id]: 'salary' }))}
                            >
                              Moash
                            </button>
                            <button
                              type="button"
                              className={`doctor-active-tab ${doctorCardTab === 'time' ? 'active' : ''}`}
                              onClick={() => setDoctorCardTabs((prev) => ({ ...prev, [doctor.id]: 'time' }))}
                            >
                              Vaqtni sozlash
                            </button>
                          </div>

                          {doctorCardTab === 'salary' ? (
                            <div className="doctor-active-settings-grid">
                              <div className="doctor-compensation">
                                <h4>Moash</h4>
                                <div className="doctor-monthly-hours-chip">
                                  Oylik jami ish soati: <strong>{doctor.monthlyHours ? `${doctor.monthlyHours.toFixed(1)} soat` : '0 soat'}</strong>
                                </div>
                                <div className="schedule-row">
                                  <div className="schedule-field">
                                    <label>Turi</label>
                                    <select
                                      value={compensation.compensationType}
                                      onChange={(e) => {
                                        const nextType = e.target.value
                                        const currentValue = compensation.compensationValue
                                        handleCompensationChange(doctor.id, 'compensationType', nextType)
                                        if (!String(currentValue || '').trim()) return
                                        if (nextType === 'percent') {
                                          handleCompensationChange(doctor.id, 'compensationValue', String(parseCurrencyInput(currentValue)))
                                        } else {
                                          handleCompensationChange(doctor.id, 'compensationValue', formatCurrencyInput(currentValue))
                                        }
                                      }}
                                    >
                                      <option value="salary">Moash</option>
                                      <option value="percent">Foiz</option>
                                    </select>
                                  </div>
                                  <div className="schedule-field">
                                    <label>{compensation.compensationType === 'percent' ? 'Foiz (%)' : 'Moash (UZS)'}</label>
                                    <input
                                      type="text"
                                      inputMode="numeric"
                                      value={compensation.compensationValue}
                                      onChange={(e) => {
                                        const raw = e.target.value
                                        if (compensation.compensationType === 'percent') {
                                          const nextPercent = Math.min(parseCurrencyInput(raw), 100)
                                          handleCompensationChange(
                                            doctor.id,
                                            'compensationValue',
                                            raw.trim() ? String(nextPercent) : ''
                                          )
                                          return
                                        }
                                        handleCompensationChange(doctor.id, 'compensationValue', formatCurrencyInput(raw))
                                      }}
                                      placeholder={compensation.compensationType === 'percent' ? '20' : '50 000'}
                                    />
                                  </div>
                                </div>
                                <button
                                  className="btn-save-schedule"
                                  onClick={() => handleSaveCompensation(doctor.id)}
                                  disabled={compensationSavingDoctorId === doctor.id}
                                >
                                  {compensationSavingDoctorId === doctor.id ? 'Saqlanmoqda...' : 'Moashni saqlash'}
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div className="doctor-active-settings-grid doctor-active-time-grid">
                              <div className="doctor-schedule doctor-schedule-full">
                                <h4>Ish vaqti va abet</h4>
                                <div className="schedule-row">
                                  <div className="schedule-field">
                                    <label>Ish boshlanishi</label>
                                    <input
                                      type="time"
                                      value={schedule.availableFrom}
                                      onChange={(e) => handleScheduleChange(doctor.id, 'availableFrom', e.target.value)}
                                    />
                                  </div>
                                  <div className="schedule-field">
                                    <label>Ish tugashi</label>
                                    <input
                                      type="time"
                                      value={schedule.availableUntil}
                                      onChange={(e) => handleScheduleChange(doctor.id, 'availableUntil', e.target.value)}
                                    />
                                  </div>
                                  <div className="schedule-field">
                                    <label>Abet boshlanishi</label>
                                    <input
                                      type="time"
                                      value={schedule.lunchBreakStart || ''}
                                      onChange={(e) => handleScheduleChange(doctor.id, 'lunchBreakStart', e.target.value)}
                                    />
                                  </div>
                                  <div className="schedule-field">
                                    <label>Abet tugashi</label>
                                    <input
                                      type="time"
                                      value={schedule.lunchBreakEnd || ''}
                                      onChange={(e) => handleScheduleChange(doctor.id, 'lunchBreakEnd', e.target.value)}
                                    />
                                  </div>
                                </div>

                                <div className="schedule-days">
                                  <label>Ish kunlari</label>
                                  <div className="workdays-grid compact">
                                    {dayOptions.map((day) => (
                                      <label key={day.key} className="workday-item">
                                        <input
                                          type="checkbox"
                                          checked={schedule.workingDays.includes(day.key)}
                                          onChange={(e) => handleScheduleDayToggle(doctor.id, day.key, e.target.checked)}
                                        />
                                        <span>{day.label}</span>
                                      </label>
                                    ))}
                                  </div>
                                </div>
                                <button className="btn-save-schedule" onClick={() => handleSaveSchedule(doctor.id)}>
                                  Ish vaqtini saqlash
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                    )})
                  ) : (
                    <div className="no-doctors">
                      <p>
                        {activeView === 'former-doctors'
                          ? 'Hozircha ishdan olingan doktorlar yo\'q'
                          : 'Hozircha doktorlar qo\'shilmagan'}
                      </p>
                      {activeView === 'doctors' && (
                        <button
                          className="btn-add-first"
                          onClick={() => setShowAddDoctor(true)}
                        >
                          Birinchi doktorni qo'shish
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </section>
            </>
          )}

          {/* Services Management Tab */}
          {activeView === 'services' && (
            <>
              {/* Departments Section */}
              <section className="dashboard-section">
                <div className="section-header-with-action">
                  <h2>🏥 Klinika yo'nalishlari</h2>
                  <button 
                    className="btn-add-service"
                    onClick={() => {
                      setDepartmentForm({ name: '', description: '' })
                      setEditingDepartmentId(null)
                      setShowAddDepartment(!showAddDepartment)
                    }}
                  >
                    {showAddDepartment ? '✕ Bekor' : '+ Yo\'nalish Qo\'shish'}
                  </button>
                </div>

                {showAddDepartment && (
                  <form className="add-service-form" onSubmit={handleAddDepartment}>
                    <div className="form-grid">
                      <div className="form-group full-width">
                        <label>Yo'nalish nomi * (Stomatologiya, Ginekologiya va h.k.)</label>
                        <input
                          type="text"
                          placeholder="Stomatologiya"
                          value={departmentForm.name}
                          onChange={(e) => setDepartmentForm({ ...departmentForm, name: e.target.value })}
                          required
                        />
                      </div>
                      <div className="form-group full-width">
                        <label>Tavsif</label>
                        <textarea
                          placeholder="Yo'nalish haqida maluot..."
                          value={departmentForm.description}
                          onChange={(e) => setDepartmentForm({ ...departmentForm, description: e.target.value })}
                          rows="3"
                        />
                      </div>
                    </div>
                    <button type="submit" className="btn-submit-service">
                      {editingDepartmentId ? 'Yangilash' : 'Qo\'shish'}
                    </button>
                  </form>
                )}

                <div className="departments-list">
                  {clinicDepartments && clinicDepartments.length > 0 ? (
                    <div className="departments-container">
                      {clinicDepartments.map((department) => (
                        <div key={department.id} className="department-card">
                          <div className="department-header">
                            <div className="department-info">
                              <h3>{department.name}</h3>
                              <p>{department.description || 'Tavsif yo\'q'}</p>
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
                          <div className="department-services">
                            {clinicServices && clinicServices.filter(s => s.department === department.id).length > 0 ? (
                              <div className="services-mini-list">
                                {clinicServices.filter(s => s.department === department.id).map((service) => (
                                  <div key={service.id} className="service-mini-item">
                                    <span className="service-name">{service.name}</span>
                                    <span className="service-price">{service.price.toLocaleString()} so'm</span>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className="no-services-notice">Bu yo'nalish bo'yicha xizmatlar qo'shilmagan</p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="no-services">
                      <p>Hozircha yo'nalishlar qo'shilmagan</p>
                      <button 
                        className="btn-add-first"
                        onClick={() => setShowAddDepartment(true)}
                      >
                        Birinchi yo'nalishni qo'shish
                      </button>
                    </div>
                  )}
                </div>
              </section>

              {/* Services Section */}
              <section className="dashboard-section">
                <div className="section-header-with-action">
                  <h2>Xizmatlar boshqaruvi</h2>
                  <button 
                    className="btn-add-service"
                    onClick={() => {
                      setServiceForm({ name: '', description: '', price: '', department: '' })
                      setServicePriceClearedOnFocus(false)
                      setEditingServiceId(null)
                      setShowAddService(!showAddService)
                    }}
                  >
                    {showAddService ? '✕ Bekor' : '+ Xizmat Qo\'shish'}
                  </button>
                </div>

                {showAddService && (
                  <form className="add-service-form" onSubmit={handleAddService}>
                    <div className="form-grid">
                      <div className="form-group full-width">
                        <label>Xizmat nomi *</label>
                        <input
                          type="text"
                          placeholder="Umumiy konsultatsiya"
                          value={serviceForm.name}
                          onChange={(e) => setServiceForm({ ...serviceForm, name: e.target.value })}
                          required
                        />
                      </div>
                      <div className="form-group full-width">
                        <label>Tavsif</label>
                        <textarea
                          placeholder="Xizmat haqida maluot..."
                          value={serviceForm.description}
                          onChange={(e) => setServiceForm({ ...serviceForm, description: e.target.value })}
                          rows="3"
                        />
                      </div>
                      <div className="form-group">
                        <label>Narx (So'm) *</label>
                        <input
                          type="text"
                          inputMode="numeric"
                          placeholder="500000"
                          value={serviceForm.price}
                          onFocus={() => {
                            if (servicePriceClearedOnFocus || !serviceForm.price) {
                              return
                            }
                            setServiceForm((prev) => ({ ...prev, price: '' }))
                            setServicePriceClearedOnFocus(true)
                          }}
                          onChange={(e) => setServiceForm({ ...serviceForm, price: formatCurrencyInput(e.target.value) })}
                          required
                        />
                      </div>
                      <div className="form-group">
                        <label>Yo'nalish</label>
                        <select
                          value={serviceForm.department}
                          onChange={(e) => setServiceForm({ ...serviceForm, department: e.target.value })}
                        >
                          <option value="">-- Tanlang --</option>
                          {clinicDepartments && clinicDepartments.map((dept) => (
                            <option key={dept.id} value={dept.id}>
                              {dept.name}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <button type="submit" className="btn-submit-service">
                      {editingServiceId ? 'Yangilash' : 'Qo\'shish'}
                    </button>
                  </form>
                )}

                <div className="services-list">
                  {clinicServices && clinicServices.length > 0 ? (
                    <div className="services-table">
                      <div className="table-header">
                        <div className="col-name">Xizmat nomi</div>
                        <div className="col-description">Tavsif</div>
                        <div className="col-price">Narx</div>
                        <div className="col-actions">Amallar</div>
                      </div>
                      {clinicServices.map((service) => (
                        <div key={service.id} className="table-row">
                          <div className="col-name">
                            <strong>{service.name}</strong>
                          </div>
                          <div className="col-description">
                            {service.description || 'Tavsif yo\'q'}
                          </div>
                          <div className="col-price">
                            {service.price.toLocaleString()} so'm
                          </div>
                          <div className="col-actions">
                            <button
                              className="btn-icon btn-edit"
                              onClick={() => handleEditService(service)}
                              title="Tahrirlash"
                            >
                              ✏️
                            </button>
                            <button
                              className="btn-icon btn-delete"
                              onClick={() => handleDeleteService(service.id)}
                              title="O'chirish"
                            >
                              🗑️
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="no-services">
                      <p>Hozircha xizmatlar qo'shilmagan</p>
                      <button 
                        className="btn-add-first"
                        onClick={() => {
                          setServiceForm({ name: '', description: '', price: '', department: '' })
                          setServicePriceClearedOnFocus(false)
                          setShowAddService(true)
                        }}
                      >
                        Birinchi xizmatni qo'shish
                      </button>
                    </div>
                  )}
                </div>
              </section>
            </>
          )}
        </div>
      </main>
    </div>
  )
}

export default ClinicOwnerDashboard
