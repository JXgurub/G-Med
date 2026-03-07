import { createContext, useContext, useEffect, useState } from 'react'
import { authApi, pharmaciesApi, pharmacyInventoryApi, medicinesApi, resolveMediaUrl } from '../services/api'

const PharmacyContext = createContext()

const ACCESS_TOKEN_KEY = 'access_token'
const REFRESH_TOKEN_KEY = 'refresh_token'

const mapInventoryToMedicine = (inventoryItem) => {
  return {
    id: inventoryItem.id,
    medicineId: inventoryItem.medicine,
    name: inventoryItem.medicine_name || inventoryItem.medicine_name_fallback || 'Noma\'lum',
    price: Number(inventoryItem.unit_price || 0),
    category: inventoryItem.medicine_category || 'Boshqa',
    stock: Number(inventoryItem.quantity_in_stock || 0)
  }
}

const normalizeMedicineName = (value) => (value || '').trim().toLowerCase()

const normalizePharmacy = (pharmacy) => ({
  ...pharmacy,
  phone: pharmacy.phone_number || pharmacy.phone || '',
  workingHours: pharmacy.working_hours || pharmacy.workingHours || '09:00 - 18:00',
  city: pharmacy.city || pharmacy.address || '',
  medicines: pharmacy.medicines || [],
  logoUrl: resolveMediaUrl(pharmacy.logo),
})

export const PharmacyProvider = ({ children }) => {
  const [pharmacies, setPharmacies] = useState([])
  const [currentPharmacy, setCurrentPharmacy] = useState(null)
  const [medicines, setMedicines] = useState([])
  const [loading, setLoading] = useState(true)

  const loadPharmacyInventory = async (pharmacyId) => {
    try {
      const inventory = await pharmacyInventoryApi.getAll({ pharmacy: pharmacyId })
      const items = inventory?.results || inventory || []
      const mapped = items.map((item) => ({
        ...item,
        medicine_name: item.medicine_name || item.medicine_name_fallback,
        medicine_category: item.medicine_category
      }))
      setMedicines(mapped.map(mapInventoryToMedicine))
      return mapped
    } catch (error) {
      console.error('Error loading pharmacy inventory:', error)
      setMedicines([])
      return []
    }
  }

  const refreshCurrentPharmacyData = async () => {
    if (!currentPharmacy?.id) return null

    const pharmacy = await pharmaciesApi.getMy()
    const normalized = normalizePharmacy(pharmacy)
    const isSubscriptionExpired = pharmacy.subscription?.is_expired || false

    setCurrentPharmacy((prev) => ({
      ...prev,
      ...normalized,
      isSubscriptionExpired,
    }))

    setPharmacies((prev) => prev.map((item) => (
      item.id === normalized.id
        ? { ...item, ...normalized }
        : item
    )))

    await loadPharmacyInventory(pharmacy.id)
    return normalized
  }

  const loadSession = async () => {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY)
    const userRole = localStorage.getItem('user_role')
    
    if (!token) {
      console.log('[PharmacyContext] No token found, skipping session load')
      return
    }
    
    // Only load if user role is explicitly pharmacy
    if (userRole !== 'pharmacy') {
      console.log('[PharmacyContext] User role is not pharmacy, skipping')
      return
    }
    
    console.log('[PharmacyContext] Loading session...')
    try {
      const pharmacy = await pharmaciesApi.getMy()

      // Check if pharmacy is suspended or blocked (but don't clear tokens on refresh)
      if (pharmacy.status === 'suspended' || pharmacy.status === 'inactive' || pharmacy.is_blocked) {
        console.log('[PharmacyContext] Pharmacy is suspended/blocked')
        // Don't clear tokens here - let user see status message
      }

      // Check subscription expiry - if expired, set pharmacy data but with flag
      const isSubscriptionExpired = pharmacy.subscription?.is_expired || false

      console.log('[PharmacyContext] Pharmacy loaded successfully:', pharmacy.name)
      setCurrentPharmacy({
        ...normalizePharmacy(pharmacy),
        isSubscriptionExpired
      })
      // Try to load inventory but don't fail if it errors
      try {
        await loadPharmacyInventory(pharmacy.id)
      } catch (inventoryErr) {
        console.warn('[PharmacyContext] Could not load inventory:', inventoryErr)
        // Continue anyway
      }
    } catch (error) {
      // 404 means user is not a pharmacy owner - this is normal
      if (error?.response?.status === 404) {
        console.log('[PharmacyContext] User is not a pharmacy owner (404), skipping')
        return
      }
      console.error('[PharmacyContext] Session restore error:', error?.response?.status, error.message)
      // Only clear tokens for 401/403 errors, not network errors
      if (error?.response?.status === 401 || error?.response?.status === 403) {
        console.log('[PharmacyContext] 401/403 detected, clearing tokens')
        localStorage.removeItem(ACCESS_TOKEN_KEY)
        localStorage.removeItem(REFRESH_TOKEN_KEY)
        localStorage.removeItem('user_role')
        setCurrentPharmacy(null)
      }
    }
  }

  useEffect(() => {
    const init = async () => {
      try {
        const list = await pharmaciesApi.getAll()
        const results = list?.results || list || []
        const normalized = results.map(normalizePharmacy)
        setPharmacies(normalized)
      } catch (error) {
        console.warn('Warning: Could not load pharmacies list:', error)
        setPharmacies([])
      }
      
      // Load session - errors are handled inside loadSession
      await loadSession()
      setLoading(false)
    }
    init()
  }, [])

  const loginPharmacy = async (email, password) => {
    try {
      const data = await authApi.login({ email, password })
      if (!data?.access) {
        return { success: false, error: 'Kirishda xatolik yuz berdi' }
      }

      if (data.user?.role !== 'pharmacy') {
        return { success: false, error: 'Bu hisob dorixona egasi emas' }
      }

      localStorage.setItem(ACCESS_TOKEN_KEY, data.access)
      localStorage.setItem(REFRESH_TOKEN_KEY, data.refresh)
      localStorage.setItem('user_role', data.user.role)

      try {
        const pharmacy = await pharmaciesApi.getMy()

        // Check if pharmacy is suspended or blocked
        if (pharmacy.status === 'suspended' || pharmacy.status === 'inactive' || pharmacy.is_blocked) {
          localStorage.removeItem(ACCESS_TOKEN_KEY)
          localStorage.removeItem(REFRESH_TOKEN_KEY)
          return { success: false, error: 'Dorixona vaqtincha to\'xtatilgan yoki yopilgan. Admin bilan bog\'laning.' }
        }

        // Check subscription status - don't allow login if expired
        if (pharmacy.subscription?.is_expired) {
          localStorage.removeItem(ACCESS_TOKEN_KEY)
          localStorage.removeItem(REFRESH_TOKEN_KEY)
          return { 
            success: false, 
            error: 'Obunangiz muddati tugagan. Admin bilan bog\'laning.',
            isSubscriptionExpired: true
          }
        }

        setCurrentPharmacy(normalizePharmacy(pharmacy))
        // Load inventory but don't fail if it errors
        try {
          await loadPharmacyInventory(pharmacy.id)
        } catch (inventoryError) {
          console.warn('Warning: Could not load pharmacy inventory:', inventoryError)
          // Still return success, just without inventory
        }
      } catch (pharmacyError) {
        console.error('Pharmacy details loading error:', pharmacyError)
        return { success: false, error: pharmacyError.message || 'Dorixona ma\'lumotlarini yukladib bo\'lmadi' }
      }
      return { success: true }
    } catch (error) {
      console.error('Login error:', error)
      const errorMsg = error?.response?.data?.detail || error?.message || 'Dorixona topilmadi yoki parol noto\'g\'ri'
      return { success: false, error: errorMsg }
    }
  }

  const logoutPharmacy = () => {
    setCurrentPharmacy(null)
    setMedicines([])
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
    localStorage.removeItem('user_role')
  }

  const getPharmacyById = (pharmacyId) => {
    return pharmacies.find((ph) => ph.id === pharmacyId)
  }

  const searchMedicines = (pharmacyId, query) => {
    if (!currentPharmacy || currentPharmacy.id !== pharmacyId) return []
    const lowerQuery = query.toLowerCase().trim()
    return medicines.filter((medicine) =>
      medicine.name.toLowerCase().includes(lowerQuery)
    )
  }

  const getMedicineById = (pharmacyId, medicineId) => {
    if (!currentPharmacy || currentPharmacy.id !== pharmacyId) return null
    return medicines.find((m) => m.id === medicineId)
  }

  const addMedicine = async (pharmacyId, medicineData) => {
    const requestedName = (medicineData.name || '').trim()
    const existingMedicine = medicines.find(
      (med) => normalizeMedicineName(med.name) === normalizeMedicineName(requestedName)
    )

    if (existingMedicine) {
      await updateMedicine(pharmacyId, existingMedicine.id, {
        ...medicineData,
        name: requestedName,
        category: medicineData.category || existingMedicine.category,
      })
      return { mode: 'updated_existing', medicineId: existingMedicine.id }
    }

    const expiryDate = new Date()
    expiryDate.setFullYear(expiryDate.getFullYear() + 1)

    const medicine = await medicinesApi.create({
      name: medicineData.name,
      description: medicineData.category || '',
      is_active: true
    })

    const inventoryItem = await pharmacyInventoryApi.create({
      pharmacy: pharmacyId,
      medicine: medicine.id,
      batch_number: `AUTO-${Date.now()}`,
      expiry_date: expiryDate.toISOString().slice(0, 10),
      quantity_in_stock: medicineData.stock === 'out' ? 0 : parseInt(medicineData.stock, 10) || 1,
      unit_price: parseInt(medicineData.price, 10) || 0,
      is_available: true
    })

    await loadPharmacyInventory(pharmacyId)
    return { mode: 'created', medicineId: inventoryItem.id }
  }

  const updateMedicine = async (pharmacyId, medicineId, updates) => {
    const inventoryId = medicineId
    const targetMedicine = medicines.find((med) => med.id === medicineId)
    if (!targetMedicine) {
      throw new Error('Dori topilmadi')
    }

    await medicinesApi.update(targetMedicine.medicineId, {
      name: (updates.name || targetMedicine.name || '').trim(),
      description: updates.category || targetMedicine.category || ''
    })

    await pharmacyInventoryApi.update(inventoryId, {
      quantity_in_stock: updates.stock === 'out' ? 0 : parseInt(updates.stock, 10),
      unit_price: parseInt(updates.price, 10)
    })

    await loadPharmacyInventory(pharmacyId)
  }

  const deleteMedicine = async (pharmacyId, medicineId) => {
    await pharmacyInventoryApi.delete(medicineId)
    await loadPharmacyInventory(pharmacyId)
  }

  const uploadPharmacyLogo = async (file) => {
    if (!currentPharmacy?.id || !file) {
      throw new Error('Dorixona yoki rasm topilmadi')
    }

    const formData = new FormData()
    formData.append('logo', file)

    const updated = await pharmaciesApi.updateForm(currentPharmacy.id, formData)
    const normalizedUpdated = normalizePharmacy(updated)

    setCurrentPharmacy((prev) => ({
      ...prev,
      ...normalizedUpdated,
      isSubscriptionExpired: prev?.isSubscriptionExpired || false,
    }))
    setPharmacies((prev) => prev.map((item) => (
      item.id === normalizedUpdated.id
        ? { ...item, ...normalizedUpdated }
        : item
    )))

    return normalizedUpdated
  }

  const removePharmacyLogo = async () => {
    if (!currentPharmacy?.id) {
      throw new Error('Dorixona topilmadi')
    }

    const updated = await pharmaciesApi.update(currentPharmacy.id, { logo: null })
    const normalizedUpdated = normalizePharmacy(updated)

    setCurrentPharmacy((prev) => ({
      ...prev,
      ...normalizedUpdated,
      isSubscriptionExpired: prev?.isSubscriptionExpired || false,
    }))
    setPharmacies((prev) => prev.map((item) => (
      item.id === normalizedUpdated.id
        ? { ...item, ...normalizedUpdated }
        : item
    )))

    return normalizedUpdated
  }

  return (
    <PharmacyContext.Provider
      value={{
        pharmacies,
        currentPharmacy,
        medicines,
        loading,
        loginPharmacy,
        logoutPharmacy,
        getPharmacyById,
        searchMedicines,
        getMedicineById,
        addMedicine,
        updateMedicine,
        deleteMedicine,
        uploadPharmacyLogo,
        removePharmacyLogo,
        refreshCurrentPharmacyData
      }}
    >
      {children}
    </PharmacyContext.Provider>
  )
}

export const usePharmacy = () => {
  const context = useContext(PharmacyContext)
  if (!context) {
    throw new Error('usePharmacy must be used within PharmacyProvider')
  }
  return context
}
