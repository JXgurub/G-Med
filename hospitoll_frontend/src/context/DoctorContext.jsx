import { createContext, useEffect, useState, useContext } from 'react'
import { authApi, doctorsApi, clinicsApi, patientsApi, medicalApi, medicalRecordsApi, resolveMediaUrl } from '../services/api'

const DoctorContext = createContext()

const normalizePassportId = (value) => {
  if (value === null || value === undefined) return ''
  return String(value).replace(/\s+/g, '').trim().toUpperCase()
}

const normalizePhone = (value) => {
  if (value === null || value === undefined) return ''
  return String(value).replace(/\s+/g, '')
}

const calcAgeFromDob = (dateOfBirth) => {
  if (!dateOfBirth) return ''
  const dob = new Date(dateOfBirth)
  if (Number.isNaN(dob.getTime())) return ''
  const today = new Date()
  let age = today.getFullYear() - dob.getFullYear()
  const monthDiff = today.getMonth() - dob.getMonth()
  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
    age -= 1
  }
  if (!Number.isFinite(age) || age < 0 || age > 130) return ''
  return String(age)
}

const normalizeAge = (value) => {
  if (value === null || value === undefined) return ''
  const trimmed = String(value).trim()
  if (!trimmed) return ''
  const num = Number(trimmed)
  if (!Number.isFinite(num)) return ''
  const intAge = Math.floor(num)
  if (intAge < 0 || intAge > 130) return ''
  return String(intAge)
}

// Using sessionStorage instead of localStorage to support multiple doctors in different tabs
const ACCESS_TOKEN_KEY = 'doctor_access_token'
const REFRESH_TOKEN_KEY = 'doctor_refresh_token'
const DOCTOR_CACHE_KEY = 'doctor_profile'

const mapDoctorProfile = async (doctorData) => {
  const fullName = doctorData.user
    ? `${doctorData.user.first_name || ''} ${doctorData.user.last_name || ''}`.trim()
    : 'Doktor'
  let clinicName = ''
  try {
    const clinic = await clinicsApi.getById(doctorData.clinic)
    clinicName = clinic.name || ''
  } catch (error) {
    clinicName = ''
  }

  return {
    id: doctorData.id,
    clinicId: doctorData.clinic,
    isActive: Boolean(doctorData.is_active),
    isAssignedToClinic: Boolean(doctorData.clinic),
    firstName: doctorData.user?.first_name || '',
    lastName: doctorData.user?.last_name || '',
    email: doctorData.user?.email || '',
    bio: doctorData.bio || '',
    pinfl: doctorData.pinfl || '',
    passportId: normalizePassportId(doctorData.passport_id || ''),
    licenseNumber: doctorData.license_number || '',
    diplomaNumber: doctorData.diploma_number || '',
    firstWorkYear: doctorData.first_work_year || '',
    firstWorkMonth: doctorData.first_work_month || '',
    dateOfBirth: doctorData.date_of_birth || '',
    certificateDocumentUrl: resolveMediaUrl(doctorData.certificate_document),
    yearsOfExperience: doctorData.years_of_experience || 0,
    consultationFee: doctorData.consultation_fee || 0,
    availableFrom: doctorData.available_from || '09:00',
    availableUntil: doctorData.available_until || '17:00',
    slotMinutes: doctorData.slot_minutes || 30,
    workingDays: doctorData.working_days || 'Mon,Tue,Wed,Thu,Fri',
    fullName: fullName || 'Doktor',
    specialization: doctorData.specializations?.map((s) => s.name).join(', ') || 'N/A',
    experience: doctorData.years_of_experience || 0,
    rating: doctorData.rating || 0,
    todayAppointments: doctorData.today_appointments || 0,
    todayPatients: doctorData.today_patients || 0,
    monthlyPatients: doctorData.monthly_patients || 0,
    monthlyCancelledAppointments: doctorData.monthly_cancelled_appointments || 0,
    availableSlots: `${doctorData.available_from || '09:00'} - ${doctorData.available_until || '17:00'}`,
    phone: doctorData.user?.phone_number || '',
    clinicName,
    avatarUrl: resolveMediaUrl(doctorData.profile_image),
    image: fullName ? fullName.charAt(0) : 'D'
  }
}

const buildPatientHistory = (records, patients, doctor) => {
  const patientMap = {}

  records.forEach((record) => {
    const patient = patients.find((p) => p.id === record.patient)
    if (!patient) return

    const fullName = patient.user
      ? `${patient.user.first_name || ''} ${patient.user.last_name || ''}`.trim()
      : 'Bemor'

    if (!patientMap[patient.id]) {
      const storedAge = normalizeAge(patient.age)
      patientMap[patient.id] = {
        id: patient.id,
        fullName: fullName || 'Bemor',
        phone: patient.phone_number || patient.user?.phone_number || '',
        gender: patient.gender || '',
        dateOfBirth: patient.date_of_birth || null,
        age: storedAge || calcAgeFromDob(patient.date_of_birth),
        complaint: record.chief_complaint || '',
        diagnosis: record.assessment || '',
        medicines: record.plan || '',
        addedAt: new Date(record.created_at).getTime(),
        addedTime: new Date(record.created_at).toLocaleTimeString('uz-UZ'),
        addedDate: new Date(record.created_at).toLocaleDateString('uz-UZ'),
        doctorId: doctor.id,
        doctorName: doctor.fullName,
        clinicId: doctor.clinicId,
        visits: []
      }
    }

    patientMap[patient.id].visits.push({
      id: record.id,
      doctorId: doctor.id,
      doctorName: doctor.fullName,
      visitTime: new Date(record.created_at).toLocaleTimeString('uz-UZ'),
      visitDate: new Date(record.created_at).toLocaleDateString('uz-UZ'),
      diagnosis: record.assessment || '',
      medicines: record.plan || '',
      complaint: record.chief_complaint || ''
    })
  })

  return patientMap
}

export const DoctorProvider = ({ children }) => {
  const [doctor, setDoctor] = useState(null)
  const [doctorStatus, setDoctorStatus] = useState(null)
  const [patientHistory, setPatientHistory] = useState({})
  const [records, setRecords] = useState([])
  const [patients, setPatients] = useState([])
  const [specialtyPrices, setSpecialtyPrices] = useState([])
  const [onlineAppointments, setOnlineAppointments] = useState([])
  const [dashboardStats, setDashboardStats] = useState({
    todayPatients: 0,
    cancelledAppointments: 0,
    monthPatients: 0,
    monthRevenue: 0,
    monthBalance: 0,
    compensationType: 'salary',
    compensationValue: 0,
  })
  const [appointmentsLoading, setAppointmentsLoading] = useState(false)
  const [loading, setLoading] = useState(true)

  const getDoctorStats = () => {
    return dashboardStats
  }

  const loadDoctorDashboardStats = async () => {
    try {
      const stats = await medicalApi.getDoctorDashboardStats()

      setDashboardStats({
        todayPatients: Number(stats?.today_24h_patients || 0),
        cancelledAppointments: Number(stats?.monthly_cancelled_appointments || 0),
        monthPatients: Number(stats?.monthly_arrived_patients || 0),
        monthRevenue: Number(stats?.monthly_effective_revenue || 0),
        monthBalance: Number(stats?.monthly_estimated_balance || 0),
        compensationType: String(stats?.compensation_type || 'salary'),
        compensationValue: Number(stats?.compensation_value || 0),
      })
    } catch (error) {
      console.error('[DoctorContext] Error loading dashboard stats:', error)
      setDashboardStats({
        todayPatients: 0,
        cancelledAppointments: 0,
        monthPatients: 0,
        monthRevenue: 0,
        monthBalance: 0,
        compensationType: 'salary',
        compensationValue: 0,
      })
    }
  }

  const loadDoctorData = async () => {
    try {
      const doctorData = await doctorsApi.getMy()
      
      // Check if doctor is suspended/inactive (but don't clear tokens on refresh)
      if (doctorData.is_active === false) {
        console.log('[DoctorContext] Doctor is suspended')
        // Don't clear tokens here - let them see a message instead
        // This prevents logout on every page refresh
      }
      
      const mappedDoctor = await mapDoctorProfile(doctorData)
      setDoctor(mappedDoctor)
      sessionStorage.setItem(DOCTOR_CACHE_KEY, JSON.stringify(mappedDoctor))

      // Set doctor status based on check-in state
      if (doctorData.is_checked_in) {
        const checkedInTime = new Date(doctorData.checked_in_at)
        setDoctorStatus({
          doctorId: mappedDoctor.id,
          checkedInTime: checkedInTime.toLocaleTimeString('uz-UZ'),
          checkedInDate: checkedInTime.toLocaleDateString('uz-UZ'),
          isCheckedIn: true,
          todaysPatients: doctorData.today_appointments || 0,
          seenPatients: 0
        })
      } else {
        setDoctorStatus({
          doctorId: mappedDoctor.id,
          checkedInTime: null,
          checkedInDate: null,
          isCheckedIn: false,
          todaysPatients: doctorData.today_appointments || 0,
          seenPatients: 0
        })
      }

      const [patientList, recordList] = await Promise.all([
        patientsApi.getAll(),
        medicalRecordsApi.getAll({ doctor: doctorData.id })
      ])

      const patientResults = patientList?.results || patientList || []
      const recordResults = recordList?.results || recordList || []

      setPatients(patientResults)
      setRecords(recordResults)
      setPatientHistory(buildPatientHistory(recordResults, patientResults, mappedDoctor))
      
      // Load specialty prices
      await loadSpecialtyPrices()
      await loadOnlineAppointments(doctorData.id)
    } catch (error) {
      console.error('[DoctorContext] Error loading doctor data:', error)
      throw error
    }
  }

  const loadOnlineAppointments = async (doctorId) => {
    if (!doctorId) return []
    setAppointmentsLoading(true)
    try {
      // Backend provides a dedicated endpoint for today's queue
      const items = await medicalApi.getTodaysAppointments()
      const excludedStatuses = new Set(['pending_telegram_confirmation', 'cancelled', 'completed', 'no_show', 'in_progress'])
      const todays = (items || []).filter((item) => !excludedStatuses.has(item.status))
      const patientIds = [...new Set(todays.map((item) => item.patient))]
      const patientMap = {}
      await Promise.all(patientIds.map(async (id) => {
        try {
          const patient = await patientsApi.getById(id)
          const fullName = patient.user
            ? `${patient.user.first_name || ''} ${patient.user.last_name || ''}`.trim()
            : 'Bemor'
          patientMap[id] = {
            fullName: fullName || 'Bemor',
            phone: patient.user?.phone_number || patient.phone_number || ''
          }
        } catch (error) {
          patientMap[id] = { fullName: 'Bemor', phone: '' }
        }
      }))

      const mapped = todays
        .sort((a, b) => {
          const timeDiff = new Date(a.scheduled_date) - new Date(b.scheduled_date)
          if (timeDiff !== 0) return timeDiff

          const createdDiff = new Date(a.created_at) - new Date(b.created_at)
          if (createdDiff !== 0) return createdDiff

          const aPos = Number(a?.queue_position)
          const bPos = Number(b?.queue_position)
          const safeAPos = Number.isFinite(aPos) && aPos > 0 ? aPos : Number.MAX_SAFE_INTEGER
          const safeBPos = Number.isFinite(bPos) && bPos > 0 ? bPos : Number.MAX_SAFE_INTEGER
          if (safeAPos !== safeBPos) return safeAPos - safeBPos

          return 0
        })
        .map((item) => ({
        ...item,
        patient_info: patientMap[item.patient] || item.patient_info || { fullName: 'Bemor', phone: '' }
      }))
      setOnlineAppointments(mapped)
      await loadDoctorDashboardStats()
      return mapped
    } catch (error) {
      console.error('Error loading online appointments:', error)
      setOnlineAppointments([])
      await loadDoctorDashboardStats()
      return []
    } finally {
      setAppointmentsLoading(false)
    }
  }

  const loadSession = async () => {
    const token = sessionStorage.getItem(ACCESS_TOKEN_KEY)
    const userRole = sessionStorage.getItem('user_role')
    
    if (!token) {
      console.log('[DoctorContext] No token found, skipping session load')
      setLoading(false)
      return
    }
    
    // Only load if user role is explicitly doctor
    if (userRole !== 'doctor') {
      console.log('[DoctorContext] User role is not doctor, skipping')
      setLoading(false)
      return
    }
    
    console.log('[DoctorContext] Loading session...')
    try {
      await loadDoctorData()
      console.log('[DoctorContext] Session loaded successfully')
    } catch (error) {
      console.error('[DoctorContext] Session load error:', error?.response?.status, error.message)
      if (error?.response?.status === 401) {
        console.log('[DoctorContext] 401/403 detected, clearing tokens')
        sessionStorage.removeItem(ACCESS_TOKEN_KEY)
        sessionStorage.removeItem(REFRESH_TOKEN_KEY)
        sessionStorage.removeItem(DOCTOR_CACHE_KEY)
        sessionStorage.removeItem('user_role')
        setDoctor(null)
      } else {
        const cachedDoctor = sessionStorage.getItem(DOCTOR_CACHE_KEY)
        if (cachedDoctor) {
          try {
            setDoctor(JSON.parse(cachedDoctor))
          } catch (parseError) {
            setDoctor(null)
          }
        }
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSession()
  }, [])

  const loginDoctor = async (email, password) => {
    try {
      const data = await authApi.login({ email, password })
      if (!data?.access) {
        return { success: false, error: 'Kirishda xatolik yuz berdi' }
      }

      if (data.user?.role !== 'doctor') {
        return { success: false, error: 'Bu hisob doktor emas' }
      }

      // Store tokens and user role in sessionStorage (per-tab)
      sessionStorage.setItem(ACCESS_TOKEN_KEY, data.access)
      sessionStorage.setItem(REFRESH_TOKEN_KEY, data.refresh)
      sessionStorage.setItem('user_role', data.user.role)

      await loadDoctorData()
      return { success: true }
    } catch (error) {
      const errorMessage = error.message || 'Email yoki parol noto\'g\'ri'
      // Check if doctor is suspended
      if (errorMessage.includes('vaqtincha')) {
        return { success: false, error: 'Sizning ish foliyatingiz vaqtincha to\'xtatib qo\'yilgan. Klinika egasi bilan bog\'laning.' }
      }
      return { success: false, error: 'Email yoki parol noto\'g\'ri' }
    }
  }

  const logoutDoctor = () => {
    setDoctor(null)
    setDoctorStatus(null)
    setPatientHistory({})
    setPatients([])
    setRecords([])
    setSpecialtyPrices([])
    setDashboardStats({
      todayPatients: 0,
      cancelledAppointments: 0,
      monthPatients: 0,
      monthRevenue: 0,
      monthBalance: 0,
      compensationType: 'salary',
      compensationValue: 0,
    })
    sessionStorage.removeItem(ACCESS_TOKEN_KEY)
    sessionStorage.removeItem(REFRESH_TOKEN_KEY)
    sessionStorage.removeItem(DOCTOR_CACHE_KEY)
    sessionStorage.removeItem('user_role')
  }

  const loadSpecialtyPrices = async () => {
    try {
      const prices = await doctorsApi.getMySpecializations()
      const priceList = prices?.results || prices || []
      setSpecialtyPrices(priceList)
      return priceList
    } catch (error) {
      console.error('Error loading specialty prices:', error)
      setSpecialtyPrices([])
      return []
    }
  }

  const updateSpecialtyPrice = async (specialtyPriceId, newPrice) => {
    try {
      const updated = await doctorsApi.updateSpecialtyPrice(specialtyPriceId, { consultation_fee: newPrice })
      await loadSpecialtyPrices()
      return updated
    } catch (error) {
      console.error('Error updating specialty price:', error)
      throw error
    }
  }

  const uploadDoctorProfileImage = async (file) => {
    if (!doctor?.id || !file) return null
    const formData = new FormData()
    formData.append('profile_image', file)
    await doctorsApi.updateForm(doctor.id, formData)
    await loadDoctorData()
    return true
  }

  const removeDoctorProfileImage = async () => {
    if (!doctor?.id) return null
    await doctorsApi.update(doctor.id, { profile_image: null })
    await loadDoctorData()
    return true
  }

  const updateDoctorProfileSettings = async (payload) => {
    if (typeof FormData !== 'undefined' && payload instanceof FormData) {
      await doctorsApi.updateMyProfileForm(payload)
    } else {
      await doctorsApi.updateMyProfile(payload)
    }
    await loadDoctorData()
    return true
  }

  const checkInDoctor = async () => {
    if (!doctor) return null
    try {
      const response = await doctorsApi.checkIn()
      const now = new Date()
      const status = {
        doctorId: doctor.id,
        checkedInTime: now.toLocaleTimeString('uz-UZ'),
        checkedInDate: now.toLocaleDateString('uz-UZ'),
        isCheckedIn: true,
        todaysPatients: Object.values(patientHistory).length,
        seenPatients: 0
      }
      setDoctorStatus(status)
      // Reload doctor data to reflect the check-in status
      await loadDoctorData()
      return status
    } catch (error) {
      console.error('Check-in error:', error)
      return null
    }
  }

  const checkOutDoctor = async () => {
    if (!doctor) return null
    try {
      const response = await doctorsApi.checkOut()
      const now = new Date()
      if (doctorStatus) {
        const updatedStatus = {
          ...doctorStatus,
          isCheckedIn: false,
          checkedOutTime: now.toLocaleTimeString('uz-UZ')
        }
        setDoctorStatus(updatedStatus)
      }
      // Reload doctor data to reflect the check-out status
      await loadDoctorData()
      return doctorStatus
    } catch (error) {
      console.error('Check-out error:', error)
      return null
    }
  }

  const addPatient = async (patientInfo) => {
    if (!doctor) return null

    const [firstName, ...rest] = patientInfo.fullName.split(' ')
    const lastName = rest.join(' ')
    const normalizedLastName = lastName.trim() || 'Bemor'

    try {
      const normalizedAge = normalizeAge(patientInfo.age)
      const patientPayload = {
        email: patientInfo.email || '',
        password: patientInfo.password,
        first_name: firstName || 'Bemor',
        last_name: normalizedLastName,
        phone_number: patientInfo.phone,
        city: patientInfo.city || '',
        address: patientInfo.address || ''
      }

      if (patientInfo.gender) {
        patientPayload.gender = patientInfo.gender
      }

      if (normalizedAge) {
        patientPayload.age = Number(normalizedAge)
      }

      const createdPatient = await patientsApi.create(patientPayload)

      const record = await medicalRecordsApi.create({
        patient: createdPatient.id,
        doctor: doctor.id,
        clinic: doctor.clinicId,
        chief_complaint: patientInfo.complaint,
        assessment: patientInfo.diagnosis || '',
        plan: patientInfo.medicines || ''
      })

      const updatedRecords = [record, ...records]
      const updatedPatients = [createdPatient, ...patients]

      setRecords(updatedRecords)
      setPatients(updatedPatients)
      setPatientHistory(buildPatientHistory(updatedRecords, updatedPatients, doctor))
      return record
    } catch (error) {
      if (error?.response?.status === 400) {
        const errorData = error.response.data
        if (errorData?.email) {
          throw new Error(`Bu email allaqachon ishlatilib bo'lgan.`)
        }
        throw new Error(JSON.stringify(errorData) || `Bemor qo'shishda xatolik yuz berdi.`)
      }
      throw error
    }
  }

  const getPatientsTodayAndYesterday = () => {
    const now = Date.now()
    const oneDayAgo = now - 24 * 60 * 60 * 1000
    return Object.values(patientHistory)
      .filter((p) => p.addedAt >= oneDayAgo)
      .sort((a, b) => b.addedAt - a.addedAt)
  }

  const getPatientHistory = (patientId) => {
    return patientHistory[patientId] || null
  }

  const updatePatientVisit = async (patientId, visitIndex, diagnosis, medicines) => {
    const patient = patientHistory[patientId]
    if (!patient || !patient.visits[visitIndex]) return

    const visit = patient.visits[visitIndex]
    await medicalRecordsApi.update(visit.id, {
      assessment: diagnosis,
      plan: medicines
    })

    await loadDoctorData()
  }

  const searchPatientByPassport = (passportId) => {
    if (!passportId || passportId.trim() === '') return []
    const searchTerm = String(passportId).toLowerCase().trim()
    const phoneSearch = normalizePhone(passportId)

    return Object.values(patientHistory)
      .filter((p) => {
        const nameMatch = p.fullName && p.fullName.toLowerCase().includes(searchTerm)
        const phoneMatch = p.phone && normalizePhone(p.phone).includes(phoneSearch)
        return nameMatch || phoneMatch
      })
      .sort((a, b) => b.addedAt - a.addedAt)
  }

  const searchPatientInDatabase = async (passportId) => {
    if (!passportId || passportId.trim() === '') return []
    try {
      const allPatients = await patientsApi.getAll({ q: passportId.trim() })
      const results = allPatients?.results || allPatients || []
      
      // Map the API response to match our patient format
      return results.map((p) => {
        const fullName = p.user
          ? `${p.user.first_name || ''} ${p.user.last_name || ''}`.trim()
          : 'Bemor'
        
        return {
          id: p.id,
          fullName: fullName || 'Bemor',
          phone: p.user?.phone_number || p.phone_number || '',
          age: normalizeAge(p.age) || calcAgeFromDob(p.date_of_birth),
          gender: p.gender || '',
          email: p.user?.email || '',
          isExisting: true // Mark as existing in database
        }
      })
    } catch (error) {
      console.error('Bemor qidirishda xatolik:', error)
      return []
    }
  }

  const addVisitToPatient = async (patientId, visitData) => {
    if (!doctor) return null

    const record = await medicalRecordsApi.create({
      patient: patientId,
      doctor: doctor.id,
      clinic: doctor.clinicId,
      chief_complaint: visitData.complaint,
      assessment: visitData.diagnosis || '',
      plan: visitData.medicines || ''
    })

    const updatedRecords = [record, ...records]
    setRecords(updatedRecords)
    setPatientHistory(buildPatientHistory(updatedRecords, patients, doctor))
    return record
  }

  const addExistingPatientVisit = async (existingPatient, visitData) => {
    if (!doctor) return null

    // Add this patient to the local patient list if not already there
    if (!patients.find((p) => p.id === existingPatient.id)) {
      const updatedPatients = [existingPatient, ...patients]
      setPatients(updatedPatients)
    }

    // Create a medical record linking the patient to this doctor
    const record = await medicalRecordsApi.create({
      patient: existingPatient.id,
      doctor: doctor.id,
      clinic: doctor.clinicId,
      appointment: existingPatient.appointmentId || null,
      chief_complaint: visitData.complaint,
      assessment: visitData.diagnosis || '',
      plan: visitData.medicines || ''
    })

    if (existingPatient.appointmentId) {
      await medicalApi.updateAppointment(existingPatient.appointmentId, { status: 'completed' })
    }

    const updatedRecords = [record, ...records]
    setRecords(updatedRecords)
    setPatientHistory(buildPatientHistory(updatedRecords, patients, doctor))
    return record
  }

  const notifyOnlineAppointmentReady = async (appointmentId, payload = {}) => {
    await medicalApi.notifyAppointmentReady(appointmentId, payload)
  }

  const applyQueueDecision = async (appointmentId, decision, options = {}) => {
    return medicalApi.queueDecision(appointmentId, { decision, ...options })
  }

  const acceptOnlineAppointment = async (appointmentId) => {
    await medicalApi.updateAppointment(appointmentId, { status: 'in_progress' })
    if (doctor?.id) {
      await loadDoctorData()
    }
  }

  return (
    <DoctorContext.Provider value={{
      doctor,
      doctorStatus,
      specialtyPrices,
      onlineAppointments,
      appointmentsLoading,
      loading,
      loginDoctor,
      logoutDoctor,
      checkInDoctor,
      checkOutDoctor,
      addPatient,
      loadOnlineAppointments,
      acceptOnlineAppointment,
      notifyOnlineAppointmentReady,
      applyQueueDecision,
      getPatientsTodayAndYesterday,
      getPatientHistory,
      updatePatientVisit,
      searchPatientByPassport,
      searchPatientInDatabase,
      addVisitToPatient,
      addExistingPatientVisit,
      getDoctorStats,
      loadDoctorDashboardStats,
      loadSpecialtyPrices,
      updateSpecialtyPrice,
      uploadDoctorProfileImage,
      removeDoctorProfileImage,
      updateDoctorProfileSettings
    }}>
      {children}
    </DoctorContext.Provider>
  )
}

export const useDoctor = () => {
  const context = useContext(DoctorContext)
  if (!context) {
    throw new Error('useDoctor must be used within DoctorProvider')
  }
  return context
}
