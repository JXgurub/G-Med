import { createContext, useContext, useEffect, useState } from 'react'
import { authApi, clinicsApi, doctorsApi, clinicServicesApi, clinicDepartmentsApi } from '../services/api'

const ClinicContext = createContext()

const ACCESS_TOKEN_KEY = 'access_token'
const REFRESH_TOKEN_KEY = 'refresh_token'

export const ClinicProvider = ({ children }) => {
  const [clinicOwner, setClinicOwner] = useState(null)
  const [clinicDoctors, setClinicDoctors] = useState([])
  const [clinicServices, setClinicServices] = useState([])
  const [clinicDepartments, setClinicDepartments] = useState([])
  const [specializations, setSpecializations] = useState([])
  const [loading, setLoading] = useState(true)

  const formatTimeValue = (value) => {
    if (!value) return null
    if (value instanceof Date) {
      return value.toLocaleTimeString('uz-UZ')
    }
    if (typeof value === 'string') {
      if (value.includes('T')) {
        return new Date(value).toLocaleTimeString('uz-UZ')
      }
      if (value.includes(':')) {
        return value.slice(0, 5)
      }
    }
    return null
  }

  const mapDoctor = (doctor) => {
    const fullName = doctor.user
      ? `${doctor.user.first_name || ''} ${doctor.user.last_name || ''}`.trim()
      : 'Doktor'
    
    let checkInTime = null
    let checkOutTime = null
    
    if (doctor.is_checked_in && doctor.checked_in_at) {
      checkInTime = formatTimeValue(doctor.checked_in_at)
    }
    
    if (doctor.checked_out_at) {
      checkOutTime = formatTimeValue(doctor.checked_out_at)
    }
    
    // Parse today's work record
    let todayCheckedIn = null
    let todayCheckedOut = null
    let todayHours = 0
    
    if (doctor.today_work_record) {
      todayCheckedIn = formatTimeValue(doctor.today_work_record.checked_in_at)
      todayCheckedOut = formatTimeValue(doctor.today_work_record.checked_out_at)
      todayHours = doctor.today_work_record.duration || 0
    }
    
    return {
      id: doctor.id,
      clinicId: doctor.clinic,
      scopeClinicId: doctor.scoped_clinic_id || doctor.clinic,
      fullName: fullName || 'Doktor',
      specialization: doctor.specializations?.map((s) => s.name).join(', ') || 'N/A',
      experience: doctor.years_of_experience || 0,
      phone: doctor.user?.phone_number || '',
      availableFrom: doctor.available_from || '09:00',
      availableUntil: doctor.available_until || '17:00',
      lunchBreakStart: doctor.lunch_break_start || '',
      lunchBreakEnd: doctor.lunch_break_end || '',
      workingDays: doctor.working_days || 'Mon,Tue,Wed,Thu,Fri',
      password: '********',
      status: doctor.is_active ? 'active' : 'suspended',
      isCheckedIn: doctor.is_checked_in || false,
      checkInTime: checkInTime,
      checkOutTime: checkOutTime,
      todayHours: todayHours,
      monthlyHours: doctor.monthly_hours || 0,
      monthlyPatients: doctor.monthly_patients || 0,
      todayCheckedIn: todayCheckedIn,
      todayCheckedOut: todayCheckedOut,
      compensationType: doctor.compensation_type || 'salary',
      compensationValue: doctor.compensation_value != null ? String(doctor.compensation_value) : '',
      workHours: 0,
      todayPatients: doctor.today_patients ?? doctor.today_appointments ?? 0,
      totalRevenue: Number(doctor.monthly_effective_revenue || 0),
      monthlyEffectiveRevenue: Number(doctor.monthly_effective_revenue || 0),
      monthlyEstimatedSalary: Number(doctor.monthly_estimated_salary || 0),
      version: doctor.updated_at || doctor.version,
      clinicAssociationStatus: doctor.clinic_association_status || 'current',
      isFormerForClinic: Boolean(doctor.is_former_for_scope_clinic),
      scopedEmploymentStartedAt: doctor.scoped_employment_started_at || null,
      scopedEmploymentEndedAt: doctor.scoped_employment_ended_at || null,
      raw: doctor
    }
  }

  const fetchClinicDoctors = async (clinicId) => {
    const firstPage = await doctorsApi.getAll({ clinic: clinicId, include_former: 1, page: 1 })

    let allResults = []
    if (Array.isArray(firstPage)) {
      allResults = firstPage
    } else {
      const firstResults = Array.isArray(firstPage?.results) ? firstPage.results : []
      allResults = [...firstResults]

      const totalCount = Number(firstPage?.count || firstResults.length)
      const pageSize = firstResults.length > 0 ? firstResults.length : (totalCount || 1)
      const totalPages = Math.max(1, Math.ceil(totalCount / pageSize))

      for (let page = 2; page <= totalPages; page += 1) {
        const nextPage = await doctorsApi.getAll({ clinic: clinicId, include_former: 1, page })
        const nextResults = Array.isArray(nextPage?.results) ? nextPage.results : []
        allResults.push(...nextResults)
      }
    }

    const mapped = allResults.map(mapDoctor)
    setClinicDoctors(mapped)
    return mapped
  }

  const fetchClinicServices = async (clinicId) => {
    try {
      const data = await clinicServicesApi.getAll({ clinic: clinicId })
      const results = data?.results || data || []
      setClinicServices(results)
      return results
    } catch (error) {
      console.error('Error fetching clinic services:', error)
      setClinicServices([])
      return []
    }
  }

  const fetchClinicDepartments = async (clinicId) => {
    try {
      const data = await clinicDepartmentsApi.getAll({ clinic: clinicId })
      const results = data?.results || data || []
      setClinicDepartments(results)
      return results
    } catch (error) {
      // Silently fail - departments are optional
      setClinicDepartments([])
      return []
    }
  }

  const fetchSpecializations = async () => {
    try {
      const data = await doctorsApi.getSpecializations()
      const results = data?.results || data || []
      setSpecializations(results)
      return results
    } catch (error) {
      console.error('Error fetching specializations:', error)
      setSpecializations([])
      return []
    }
  }

  const refreshClinicData = async (options = {}) => {
    const clinicId = clinicOwner?.id
    if (!clinicId) return null

    const {
      owner = true,
      doctors = true,
      services = false,
      departments = false,
      specializations: refreshSpecializations = false,
    } = options

    const tasks = []

    if (owner) {
      tasks.push(
        clinicsApi.getMy({ _ts: Date.now() }).then((updatedClinic) => {
          setClinicOwner((prev) => {
            if (!prev) return prev
            const ownerName = prev.ownerName || ''
            return {
              ...prev,
              ...updatedClinic,
              clinicName: updatedClinic.name || prev.clinicName,
              clinicPhone: updatedClinic.phone_number || prev.clinicPhone,
              location: updatedClinic.address || prev.location,
              ownerName,
              isSubscriptionExpired: updatedClinic.subscription?.is_expired || false,
            }
          })
          return updatedClinic
        })
      )
    }

    if (doctors) tasks.push(fetchClinicDoctors(clinicId))
    if (services) tasks.push(fetchClinicServices(clinicId))
    if (departments) tasks.push(fetchClinicDepartments(clinicId))
    if (refreshSpecializations) tasks.push(fetchSpecializations())

    await Promise.all(tasks)
    return true
  }

  const loadSession = async () => {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY)
    const userRole = localStorage.getItem('user_role')
    
    if (!token) {
      console.log('[ClinicContext] No token found, skipping session load')
      setLoading(false)
      return
    }
    
    // Only load if user role is explicitly clinic
    if (userRole !== 'clinic') {
      console.log('[ClinicContext] User role is not clinic, skipping')
      setLoading(false)
      return
    }
    
    console.log('[ClinicContext] Loading session...')
    try {
      const [profile, clinic] = await Promise.all([
        authApi.getProfile(),
        clinicsApi.getMy({ _ts: Date.now() })
      ])

      // Check if clinic is suspended or blocked (but don't clear tokens on refresh)
      if (clinic.status === 'suspended' || clinic.status === 'inactive' || clinic.is_blocked) {
        console.log('[ClinicContext] Clinic is suspended/blocked')
        // Don't clear tokens here - let user see status message
      }

      // Check subscription expiry - if expired, set owner data but with flag
      const isSubscriptionExpired = clinic.subscription?.is_expired || false

      console.log('[ClinicContext] Session loaded successfully for clinic:', clinic.name)
      const ownerName = `${profile.first_name || ''} ${profile.last_name || ''}`.trim()
      const ownerData = {
        ...clinic,
        owner: profile,
        clinicName: clinic.name || '',
        clinicPhone: clinic.phone_number || '',
        location: clinic.address || '',
        ownerName: ownerName || profile.email || 'Klinika egasi',
        revenue: 0,
        isSubscriptionExpired
      }
      setClinicOwner(ownerData)
      if (clinic?.id) {
        await Promise.all([
          fetchClinicDoctors(clinic.id),
          fetchClinicServices(clinic.id),
          fetchClinicDepartments(clinic.id),
          fetchSpecializations()
        ])
      }
    } catch (error) {
      console.error('[ClinicContext] Session load error:', error?.response?.status, error.message)
      if (error?.response?.status === 401 || error?.response?.status === 403) {
        console.log('[ClinicContext] 401/403 detected, clearing tokens')
        localStorage.removeItem(ACCESS_TOKEN_KEY)
        localStorage.removeItem(REFRESH_TOKEN_KEY)
        localStorage.removeItem('user_role')
        setClinicOwner(null)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSession()
  }, [])

  useEffect(() => {
    if (!clinicOwner?.id) return
    const intervalId = setInterval(() => {
      fetchClinicDoctors(clinicOwner.id)
    }, 5 * 60 * 1000)

    return () => clearInterval(intervalId)
  }, [clinicOwner?.id])

  const loginClinicOwner = async (email, password) => {
    try {
      const data = await authApi.login({ email, password })
      if (!data?.access) {
        return { success: false, error: 'Kirishda xatolik yuz berdi' }
      }

      if (data.user?.role !== 'clinic') {
        return { success: false, error: 'Bu hisob klinika egasi emas' }
      }

      localStorage.setItem(ACCESS_TOKEN_KEY, data.access)
      localStorage.setItem(REFRESH_TOKEN_KEY, data.refresh)
      localStorage.setItem('user_role', data.user.role)

      const clinic = await clinicsApi.getMy({ _ts: Date.now() })

      // Check if clinic is suspended or blocked
      if (clinic.status === 'suspended' || clinic.status === 'inactive' || clinic.is_blocked) {
        localStorage.removeItem(ACCESS_TOKEN_KEY)
        localStorage.removeItem(REFRESH_TOKEN_KEY)
        return { success: false, error: 'Klinika vaqtincha to\'xtatilgan yoki yopilgan. Admin bilan bog\'laning.' }
      }

      // Check subscription status - don't allow login if expired
      if (clinic.subscription?.is_expired) {
        localStorage.removeItem(ACCESS_TOKEN_KEY)
        localStorage.removeItem(REFRESH_TOKEN_KEY)
        return { 
          success: false, 
          error: 'Obunangiz muddati tugagan. Admin bilan bog\'laning.',
          isSubscriptionExpired: true
        }
      }

      const ownerName = `${data.user.first_name || ''} ${data.user.last_name || ''}`.trim()
      const ownerData = {
        ...clinic,
        owner: data.user,
        clinicName: clinic.name || '',
        clinicPhone: clinic.phone_number || '',
        location: clinic.address || '',
        ownerName: ownerName || data.user.email || 'Klinika egasi',
        revenue: 0
      }
      setClinicOwner(ownerData)
      if (clinic?.id) {
        await Promise.all([
          fetchClinicDoctors(clinic.id),
          fetchClinicServices(clinic.id),
          fetchClinicDepartments(clinic.id),
          fetchSpecializations()
        ])
      }
      return { success: true, owner: ownerData }
    } catch (error) {
      return { success: false, error: 'Klinika topilmadi yoki parol noto\'g\'ri' }
    }
  }

  const logoutClinicOwner = () => {
    setClinicOwner(null)
    setClinicDoctors([])
    setClinicServices([])
    setClinicDepartments([])
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
    localStorage.removeItem('user_role')
  }

  const updateClinicBanner = async (file) => {
    if (!clinicOwner?.id) {
      throw new Error('Klinika topilmadi')
    }
    if (!file) {
      throw new Error('Rasm tanlanmadi')
    }

    const formData = new FormData()
    formData.append('banner_image', file)

    const updatedClinic = await clinicsApi.updateMyBanner(formData)
    setClinicOwner((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        ...updatedClinic,
        clinicName: updatedClinic.name || prev.clinicName,
        clinicPhone: updatedClinic.phone_number || prev.clinicPhone,
        location: updatedClinic.address || prev.location,
      }
    })
    return updatedClinic
  }

  const updateClinicProfile = async (data) => {
    if (!clinicOwner?.id) {
      throw new Error('Klinika topilmadi')
    }
    await clinicsApi.updateMy(data)
    const updatedClinic = await clinicsApi.getMy({ _ts: Date.now() })
    setClinicOwner((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        ...updatedClinic,
        clinicName: updatedClinic.name || prev.clinicName,
        clinicPhone: updatedClinic.phone_number || prev.clinicPhone,
        location: updatedClinic.address || prev.location,
      }
    })
    return updatedClinic
  }

  const addDoctor = async (clinicId, doctorData) => {
    const payload = {
      ...doctorData,
      clinic: clinicId
    }
    const created = await doctorsApi.create(payload)
    await fetchClinicDoctors(clinicId)
    return created
  }

  const getDoctorsByClinic = (clinicId) => {
    if (!clinicId) return []
    return clinicDoctors.filter(
      (doctor) =>
        String(doctor.clinicId) === String(clinicId)
        || String(doctor.scopeClinicId) === String(clinicId)
    )
  }

  const deleteDoctor = async (clinicId, doctorId) => {
    setClinicDoctors((prev) => prev.filter((doctor) => doctor.id !== doctorId))
    await doctorsApi.terminate(doctorId)
    await fetchClinicDoctors(clinicId)
  }

  const toggleDoctorStatus = async (clinicId, doctorId) => {
    try {
      console.log('[ClinicContext] toggleDoctorStatus called for doctor:', doctorId)
      const doctor = clinicDoctors.find((d) => d.id === doctorId)
      if (!doctor) {
        console.error('[ClinicContext] Doctor not found in clinicDoctors array')
        return
      }
      // Note: doctor object is mapped, so we check status field (not is_active)
      // status: 'active' means is_active: true, status: 'suspended' means is_active: false
      const currentIsActive = doctor.status === 'active'
      console.log('[ClinicContext] Current doctor status:', doctor.status, '| is_active:', currentIsActive)
      const nextIsActive = !currentIsActive
      console.log('[ClinicContext] Sending PATCH request with is_active:', nextIsActive)
      
      // Include version for optimistic locking
      const updateData = { 
        is_active: nextIsActive,
        version: doctor.version
      }
      
      try {
        const updateResponse = await doctorsApi.update(doctorId, updateData)
        console.log('[ClinicContext] Update response:', updateResponse)
        console.log('[ClinicContext] Refreshing clinic doctors list...')
        const refreshedDoctors = await fetchClinicDoctors(clinicId)
        console.log('[ClinicContext] Refreshed doctors:', refreshedDoctors)
        return { success: true, newStatus: nextIsActive }
      } catch (error) {
        // Handle version conflict (409)
        if (error.response?.status === 409) {
          console.log('[ClinicContext] Version conflict detected, refreshing doctors...')
          await fetchClinicDoctors(clinicId)
          throw new Error('Ma\'lumot boshqa foydalanuvchi tomonidan o\'zgartirilgan. Iltimos, qaytadan urinib ko\'ring.')
        }
        throw error
      }
    } catch (error) {
      console.error('[ClinicContext] Error toggling doctor status:', error)
      console.error('[ClinicContext] Error message:', error.message)
      console.error('[ClinicContext] Error response:', error.response)
      throw error
    }
  }

  const updateDoctorSchedule = async (clinicId, doctorId, scheduleData) => {
    try {
      const doctor = clinicDoctors.find((d) => d.id === doctorId)
      
      const payload = {
        available_from: scheduleData.availableFrom,
        available_until: scheduleData.availableUntil,
        lunch_break_start: scheduleData.lunchBreakStart || null,
        lunch_break_end: scheduleData.lunchBreakEnd || null,
        working_days: scheduleData.workingDays,
        version: doctor?.version
      }
      
      try {
        const updated = await doctorsApi.update(doctorId, payload)
        await fetchClinicDoctors(clinicId)
        return updated
      } catch (error) {
        // Handle version conflict (409)
        if (error.response?.status === 409) {
          console.log('[ClinicContext] Version conflict detected, refreshing doctors...')
          await fetchClinicDoctors(clinicId)
          throw new Error('Ma\'lumot boshqa foydalanuvchi tomonidan o\'zgartirilgan. Iltimos, sahifani yangilang va qaytadan urinib ko\'ring.')
        }
        throw error
      }
    } catch (error) {
      console.error('[ClinicContext] Error updating doctor schedule:', error)
      throw error
    }
  }

  const updateDoctorCompensation = async (clinicId, doctorId, compensationData) => {
    try {
      const doctor = clinicDoctors.find((d) => d.id === doctorId)
      const payload = {
        compensation_type: compensationData.compensationType,
        compensation_value: compensationData.compensationValue,
        version: doctor?.version
      }

      try {
        const updated = await doctorsApi.update(doctorId, payload)
        await fetchClinicDoctors(clinicId)
        return updated
      } catch (error) {
        if (error.response?.status === 409) {
          await fetchClinicDoctors(clinicId)
          throw new Error('Ma\'lumot boshqa foydalanuvchi tomonidan o\'zgartirilgan. Iltimos, sahifani yangilang.')
        }
        throw error
      }
    } catch (error) {
      console.error('[ClinicContext] Error updating doctor compensation:', error)
      throw error
    }
  }

  const addService = async (clinicId, serviceData) => {
    const payload = {
      ...serviceData,
      clinic: clinicId,
      price: parseFloat(serviceData.price) || 0
    }
    const created = await clinicServicesApi.create(payload)
    await fetchClinicServices(clinicId)
    return created
  }

  const updateService = async (clinicId, serviceId, serviceData) => {
    const payload = {
      ...serviceData,
      price: parseFloat(serviceData.price) || 0
    }
    const updated = await clinicServicesApi.update(serviceId, payload)
    await fetchClinicServices(clinicId)
    return updated
  }

  const deleteService = async (clinicId, serviceId) => {
    await clinicServicesApi.delete(serviceId)
    await fetchClinicServices(clinicId)
  }

  const addDepartment = async (clinicId, departmentData) => {
    const payload = {
      ...departmentData,
      clinic: clinicId
    }
    const created = await clinicDepartmentsApi.create(payload)
    await fetchClinicDepartments(clinicId)
    return created
  }

  const updateDepartment = async (clinicId, departmentId, departmentData) => {
    const updated = await clinicDepartmentsApi.update(departmentId, departmentData)
    await fetchClinicDepartments(clinicId)
    return updated
  }

  const deleteDepartment = async (clinicId, departmentId) => {
    await clinicDepartmentsApi.delete(departmentId)
    await fetchClinicDepartments(clinicId)
  }

  return (
    <ClinicContext.Provider value={{
      clinicOwner,
      clinicDoctors,
      clinicServices,
      clinicDepartments,
      specializations,
      loading,
      loginClinicOwner,
      logoutClinicOwner,
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
    }}>
      {children}
    </ClinicContext.Provider>
  )
}

export const useClinic = () => {
  const context = useContext(ClinicContext)
  if (!context) {
    throw new Error('useClinic must be used within ClinicProvider')
  }
  return context
}
