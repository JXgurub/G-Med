import { createContext, useContext, useEffect, useState } from 'react'
import api, { authApi, clinicsApi, pharmaciesApi } from '../services/api'

const adminContextUnavailable = async () => ({
  success: false,
  error: 'Admin konteksti mavjud emas',
})

const defaultAdminContextValue = {
  admin: null,
  clinics: [],
  pharmacies: [],
  loading: false,
  loginAdmin: adminContextUnavailable,
  toggleClinicStatus: async () => {},
  markClinicPaid: async () => {},
  deleteClinic: async () => {},
  addClinic: adminContextUnavailable,
  togglePharmacyStatus: async () => {},
  markPharmacyPaid: async () => {},
  deletePharmacy: async () => {},
  addPharmacy: adminContextUnavailable,
  changeClinicPassword: async () => {},
  setClinicPaymentAmount: async () => {},
  changePharmacyPassword: async () => {},
  setPharmacyPaymentAmount: async () => {},
  generateClinicPaymentLink: adminContextUnavailable,
  generatePharmacyPaymentLink: adminContextUnavailable,
  approveClinicSubscription: adminContextUnavailable,
  approvePharmacySubscription: adminContextUnavailable,
  refreshAdminData: async () => {},
  logoutAdmin: () => {},
}

const AdminContext = createContext(defaultAdminContextValue)

const ACCESS_TOKEN_KEY = 'access_token'
const REFRESH_TOKEN_KEY = 'refresh_token'

export const AdminProvider = ({ children }) => {
  const [admin, setAdmin] = useState(null)
  const [clinics, setClinics] = useState([])
  const [pharmacies, setPharmacies] = useState([])
  const [loading, setLoading] = useState(true)

  const parseItems = (payload) => payload?.results || payload || []

  const loadLists = async () => {
    const [clinicsResult, pharmaciesResult] = await Promise.allSettled([
      clinicsApi.getAll(),
      pharmaciesApi.getAll()
    ])

    if (clinicsResult.status === 'fulfilled') {
      setClinics(parseItems(clinicsResult.value))
    } else {
      console.error('[AdminContext] Clinics list fetch failed:', clinicsResult.reason)
    }

    if (pharmaciesResult.status === 'fulfilled') {
      setPharmacies(parseItems(pharmaciesResult.value))
    } else {
      console.error('[AdminContext] Pharmacies list fetch failed:', pharmaciesResult.reason)
    }

    return {
      clinicsOk: clinicsResult.status === 'fulfilled',
      pharmaciesOk: pharmaciesResult.status === 'fulfilled',
    }
  }

  const refreshAdminData = async () => {
    if (!admin) return
    try {
      await loadLists()
    } catch (error) {
      console.error('[AdminContext] refreshAdminData failed:', error)
    }
  }

  const loadSession = async () => {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY)
    const userRole = localStorage.getItem('user_role')
    
    if (!token) {
      console.log('[AdminContext] No token found, skipping session load')
      setLoading(false)
      return
    }
    
    // Only load if user role is explicitly admin
    if (userRole !== 'admin') {
      console.log('[AdminContext] User role is not admin, skipping')
      setLoading(false)
      return
    }
    
    console.log('[AdminContext] Loading session...')
    try {
      const profile = await authApi.getProfile()

      if (profile?.role !== 'admin' && !profile?.is_superuser) {
        console.warn('[AdminContext] Session role is not admin, clearing tokens')
        localStorage.removeItem(ACCESS_TOKEN_KEY)
        localStorage.removeItem(REFRESH_TOKEN_KEY)
        localStorage.removeItem('user_role')
        setAdmin(null)
        setClinics([])
        setPharmacies([])
        return
      }

      console.log('[AdminContext] Session loaded successfully for admin:', profile.email)
      setAdmin(profile)
      await loadLists()
    } catch (error) {
      console.error('[AdminContext] Session load error:', error?.response?.status, error.message)
      if (error?.response?.status === 401 || error?.response?.status === 403) {
        console.log('[AdminContext] 401/403 detected, clearing tokens')
        localStorage.removeItem(ACCESS_TOKEN_KEY)
        localStorage.removeItem(REFRESH_TOKEN_KEY)
        localStorage.removeItem('user_role')
        setAdmin(null)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSession()
  }, [])

  const loginAdmin = async (email, password) => {
    try {
      const data = await authApi.login({ email, password })
      if (!data?.access) {
        return { success: false, error: 'Kirishda xatolik yuz berdi' }
      }

      if (data.user?.role !== 'admin' && !data.user?.is_superuser) {
        return { success: false, error: 'Bu hisob admin emas' }
      }

      localStorage.setItem(ACCESS_TOKEN_KEY, data.access)
      localStorage.setItem(REFRESH_TOKEN_KEY, data.refresh)
      localStorage.setItem('user_role', 'admin')
      setAdmin(data.user)
      await loadLists()
      return { success: true, admin: data.user }
    } catch (error) {
      return { success: false, error: 'Email yoki parol noto\'g\'ri' }
    }
  }

  const toggleClinicStatus = async (clinicId) => {
    const clinic = clinics.find((item) => item.id === clinicId)
    if (!clinic) {
      throw new Error('Klinika topilmadi')
    }
    console.log(`[Admin] Toggling clinic ${clinicId} status from ${clinic.status}...`)
    const nextStatus = clinic.status === 'active' ? 'suspended' : 'active'
    const result = await clinicsApi.update(clinicId, { status: nextStatus })
    console.log(`[Admin] Clinic status updated:`, result)
    await loadLists()
  }

  const markClinicPaid = async (clinicId) => {
    console.log(`[Admin] Marking clinic ${clinicId} as paid...`)
    await clinicsApi.update(clinicId, { status: 'active' })
    await loadLists()
  }

  const deleteClinic = async (clinicId) => {
    console.log(`[Admin] Deleting clinic ${clinicId}...`)
    const result = await clinicsApi.delete(clinicId)
    console.log(`[Admin] Clinic deleted:`, result)
    await loadLists()
  }

  const addClinic = async (clinicData) => {
    const created = await clinicsApi.create(clinicData)
    await loadLists()
    return created
  }

  const togglePharmacyStatus = async (pharmacyId) => {
    const pharmacy = pharmacies.find((item) => item.id === pharmacyId)
    if (!pharmacy) {
      throw new Error('Dorixona topilmadi')
    }
    console.log(`[Admin] Toggling pharmacy ${pharmacyId} status from ${pharmacy.status}...`)
    const nextStatus = pharmacy.status === 'active' ? 'suspended' : 'active'
    const result = await pharmaciesApi.update(pharmacyId, { status: nextStatus })
    console.log(`[Admin] Pharmacy status updated:`, result)
    await loadLists()
  }

  const markPharmacyPaid = async (pharmacyId) => {
    console.log(`[Admin] Marking pharmacy ${pharmacyId} as paid...`)
    await pharmaciesApi.update(pharmacyId, { status: 'active' })
    await loadLists()
  }

  const deletePharmacy = async (pharmacyId) => {
    console.log(`[Admin] Deleting pharmacy ${pharmacyId}...`)
    const result = await pharmaciesApi.delete(pharmacyId)
    console.log(`[Admin] Pharmacy deleted:`, result)
    await loadLists()
  }

  const addPharmacy = async (pharmacyData) => {
    const created = await pharmaciesApi.create(pharmacyData)
    await loadLists()
    return created
  }

  const changeClinicPassword = async (clinicId, newPassword) => {
    await clinicsApi.update(clinicId, { owner_password: newPassword })
    await loadLists()
  }

  const setClinicPaymentAmount = async (clinicId, amount, description = '') => {
    const now = new Date().toISOString()
    await clinicsApi.update(clinicId, { 
      amount, 
      payment_description: description,
      payment_date: now 
    })
    await loadLists()
  }

  const changePharmacyPassword = async (pharmacyId, newPassword) => {
    await pharmaciesApi.update(pharmacyId, { owner_password: newPassword })
    await loadLists()
  }

  const setPharmacyPaymentAmount = async (pharmacyId, amount, description = '') => {
    const now = new Date().toISOString()
    await pharmaciesApi.update(pharmacyId, { 
      amount, 
      payment_description: description,
      payment_date: now 
    })
    await loadLists()
  }

  const generateClinicPaymentLink = async (clinicId, sendEmail = false) => {
    const response = await api.request('/payments/payments/admin_create_subscription_payment/', {
      method: 'POST',
      body: JSON.stringify({ clinic_id: clinicId, send_email: sendEmail })
    })
    if (!response.success) {
      throw new Error(response.error || 'Link yaratishda xatolik')
    }
    return response
  }

  const generatePharmacyPaymentLink = async (pharmacyId, sendEmail = false) => {
    const response = await api.request('/payments/payments/admin_create_subscription_payment/', {
      method: 'POST',
      body: JSON.stringify({ pharmacy_id: pharmacyId, send_email: sendEmail })
    })
    if (!response.success) {
      throw new Error(response.error || 'Link yaratishda xatolik')
    }
    return response
  }

  const approveClinicSubscription = async (clinicId) => {
    console.log(`[Admin] Approving clinic ${clinicId} subscription...`)
    const response = await api.request('/payments/payments/admin_approve_subscription/', {
      method: 'POST',
      body: JSON.stringify({ clinic_id: clinicId })
    })
    if (!response.success) {
      throw new Error(response.error || 'Obunani faollashtirishda xatolik')
    }
    await loadLists()
    return response
  }

  const approvePharmacySubscription = async (pharmacyId) => {
    console.log(`[Admin] Approving pharmacy ${pharmacyId} subscription...`)
    const response = await api.request('/payments/payments/admin_approve_subscription/', {
      method: 'POST',
      body: JSON.stringify({ pharmacy_id: pharmacyId })
    })
    if (!response.success) {
      throw new Error(response.error || 'Obunani faollashtirishda xatolik')
    }
    await loadLists()
    return response
  }

  const logoutAdmin = () => {
    setAdmin(null)
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
    localStorage.removeItem('user_role')
  }

  return (
    <AdminContext.Provider value={{
      admin,
      clinics,
      pharmacies,
      loading,
      loginAdmin,
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
    }}>
      {children}
    </AdminContext.Provider>
  )
}

export const useAdmin = () => {
  const context = useContext(AdminContext)
  if (!context) return defaultAdminContextValue
  return context
}
