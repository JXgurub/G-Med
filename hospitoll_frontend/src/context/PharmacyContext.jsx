import { createContext, useContext, useEffect, useState } from 'react'
import { authApi, pharmaciesApi, pharmacyInventoryApi, medicinesApi, resolveMediaUrl } from '../services/api'

const PharmacyContext = createContext()

const ACCESS_TOKEN_KEY = 'access_token'
const REFRESH_TOKEN_KEY = 'refresh_token'

const normalizeCountryOption = (value) => {
  const country = String(value || '').trim()
  const normalized = country.toLowerCase()
  if (!normalized) return 'Boshqa'

  const aliases = {
    "o'zbekiston": "O'zbekiston",
    'ozbekiston': "O'zbekiston",
    'uzbekistan': "O'zbekiston",
    'rossiya': 'Rossiya',
    'rassiya': 'Rossiya',
    'russia': 'Rossiya',
    'vetnam': 'Vetnam',
    'vietnam': 'Vetnam',
    'boshqa': 'Boshqa',
    'other': 'Boshqa',
  }

  if (aliases[normalized]) {
    return aliases[normalized]
  }
  if (["O'zbekiston", 'Rossiya', 'Vetnam', 'Boshqa'].includes(country)) {
    return country
  }
  return 'Boshqa'
}

const buildMedicineDisplayName = (name, strength = '') => {
  const cleanName = String(name || '').trim()
  const cleanStrength = String(strength || '').trim()

  if (!cleanStrength) return cleanName || 'Noma\'lum'
  if (cleanName.toLowerCase().includes(cleanStrength.toLowerCase())) {
    return cleanName
  }
  return `${cleanName} ${cleanStrength}`.trim()
}

const mapInventoryToMedicine = (inventoryItem) => {
  return {
    id: inventoryItem.id,
    medicineId: inventoryItem.medicine,
    name: buildMedicineDisplayName(
      inventoryItem.medicine_name || inventoryItem.medicine_name_fallback || 'Noma\'lum',
      inventoryItem.medicine_strength || ''
    ),
    price: Number(inventoryItem.unit_price || 0),
    category: inventoryItem.medicine_category || 'Boshqa',
    stock: Number(inventoryItem.quantity_in_stock || 0),
    strength: inventoryItem.medicine_strength || '',
    dosageForm: inventoryItem.medicine_dosage_form || '',
    appearance: inventoryItem.medicine_dosage_form || '',
    countryOfOrigin: normalizeCountryOption(inventoryItem.medicine_country_of_origin || ''),
    expiryDate: inventoryItem.expiry_date || ''
  }
}

const normalizeMedicineName = (value) => (value || '').trim().toLowerCase()
const buildMedicineIdentityKey = (value = {}) => {
  const name = normalizeMedicineName(buildMedicineDisplayName(value.name, value.strength))
  const dosageForm = normalizeMedicineName(value.dosageForm || value.appearance || value.dosage_form)
  const category = normalizeMedicineName(value.category)
  const countryOfOrigin = normalizeMedicineName(value.countryOfOrigin || value.country_of_origin)
  return `${name}__${dosageForm}__${category}__${countryOfOrigin}`
}

const toIsoDate = (value) => {
  if (!value) return ''
  const cleanValue = String(value).trim()
  if (/^\d{4}$/.test(cleanValue)) {
    return `${cleanValue}-12-31`
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toISOString().slice(0, 10)
}

const normalizePharmacy = (pharmacy) => ({
  ...pharmacy,
  phone: pharmacy.phone_number || pharmacy.phone || '',
  workingHours: pharmacy.working_hours || pharmacy.workingHours || '09:00 - 18:00',
  city: pharmacy.city || pharmacy.address || '',
  medicines: pharmacy.medicines || [],
  logoUrl: resolveMediaUrl(pharmacy.logo),
})

const MAX_INVENTORY_PAGE_FETCH = 500

const fetchAllInventoryRows = async (pharmacyId) => {
  let page = 1
  let allRows = []

  while (page <= MAX_INVENTORY_PAGE_FETCH) {
    const response = await pharmacyInventoryApi.getAll({ pharmacy: pharmacyId, page })

    if (Array.isArray(response)) {
      allRows = response
      break
    }

    const pageRows = Array.isArray(response?.results) ? response.results : []
    allRows = allRows.concat(pageRows)

    const totalCount = Number(response?.count || 0)
    const hasNext = Boolean(response?.next)
    if (!hasNext || pageRows.length === 0 || (totalCount > 0 && allRows.length >= totalCount)) {
      break
    }

    page += 1
  }

  if (page > MAX_INVENTORY_PAGE_FETCH) {
    console.warn(`[PharmacyContext] Inventory fetch reached page limit (${MAX_INVENTORY_PAGE_FETCH})`)
  }

  return allRows
}

export const PharmacyProvider = ({ children }) => {
  const [pharmacies, setPharmacies] = useState([])
  const [currentPharmacy, setCurrentPharmacy] = useState(null)
  const [medicines, setMedicines] = useState([])
  const [loading, setLoading] = useState(true)

  const loadPharmacyInventory = async (pharmacyId) => {
    try {
      const items = await fetchAllInventoryRows(pharmacyId)
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

  const addMedicine = async (pharmacyId, medicineData, options = {}) => {
    const { skipReload = false, preferredMedicineId = null } = options
    const requestedName = buildMedicineDisplayName(medicineData.name, medicineData.strength).trim()
    const requestedStrength = ''
    const requestedDosageForm = (medicineData.dosageForm || medicineData.appearance || '').trim()
    const requestedCategory = (medicineData.category || '').trim() || 'Boshqa'
    const requestedCountry = normalizeCountryOption(medicineData.countryOfOrigin)
    const requestedExpiryDate = toIsoDate(medicineData.expiryDate)
    const requestedIdentityKey = buildMedicineIdentityKey({
      name: requestedName,
      strength: requestedStrength,
      dosageForm: requestedDosageForm,
      category: requestedCategory,
      countryOfOrigin: requestedCountry,
    })

    const existingMedicine = medicines.find((med) => buildMedicineIdentityKey(med) === requestedIdentityKey)

    if (existingMedicine) {
      await updateMedicine(pharmacyId, existingMedicine.id, {
        ...medicineData,
        name: requestedName,
        category: requestedCategory || existingMedicine.category,
        strength: requestedStrength,
        dosageForm: requestedDosageForm || existingMedicine.dosageForm,
        appearance: requestedDosageForm || existingMedicine.appearance,
        countryOfOrigin: requestedCountry || existingMedicine.countryOfOrigin,
        expiryDate: requestedExpiryDate || existingMedicine.expiryDate,
      }, { skipReload })
      return { mode: 'updated_existing', medicineId: existingMedicine.id }
    }

    const expiryDate = new Date()
    expiryDate.setFullYear(expiryDate.getFullYear() + 1)

    let medicine = null
    if (preferredMedicineId) {
      medicine = {
        id: preferredMedicineId,
        name_verification_alert_created: false,
        name_verification_alert_id: null,
      }
    }

    if (!medicine) {
      medicine = await medicinesApi.create({
        name: requestedName,
        category: requestedCategory,
        description: requestedCategory,
        strength: requestedStrength,
        dosage_form: requestedDosageForm,
        country_of_origin: requestedCountry,
        is_active: true
      })
    }

    const stockValue = medicineData.stock === 'out' ? 0 : parseInt(medicineData.stock, 10) || 1
    const unitPrice = parseInt(medicineData.price, 10) || 0
    const expiryDateValue = requestedExpiryDate || expiryDate.toISOString().slice(0, 10)

    try {
      const inventoryItem = await pharmacyInventoryApi.create({
        pharmacy: pharmacyId,
        medicine: medicine.id,
        batch_number: `AUTO-${Date.now()}`,
        expiry_date: expiryDateValue,
        quantity_in_stock: stockValue,
        unit_price: unitPrice,
        is_available: true
      })

      if (!skipReload) {
        await loadPharmacyInventory(pharmacyId)
      }
      return {
        mode: 'created',
        medicineId: inventoryItem.id,
        nameVerificationAlertCreated: Boolean(medicine?.name_verification_alert_created),
        nameVerificationAlertId: medicine?.name_verification_alert_id || null,
      }
    } catch (error) {
      const duplicateMessage = String(error?.response?.data?.medicine || '').toLowerCase()
      if (duplicateMessage.includes('allaqachon mavjud')) {
        const refreshedRows = await loadPharmacyInventory(pharmacyId)
        const reloadedExisting = refreshedRows
          .map(mapInventoryToMedicine)
          .find((med) => buildMedicineIdentityKey(med) === requestedIdentityKey)

        if (reloadedExisting) {
          await updateMedicine(pharmacyId, reloadedExisting.id, {
            ...medicineData,
            name: requestedName,
            category: requestedCategory || reloadedExisting.category,
            strength: requestedStrength,
            dosageForm: requestedDosageForm || reloadedExisting.dosageForm,
            appearance: requestedDosageForm || reloadedExisting.appearance,
            countryOfOrigin: requestedCountry || reloadedExisting.countryOfOrigin,
            expiryDate: requestedExpiryDate || reloadedExisting.expiryDate,
          }, { skipReload })
          return { mode: 'updated_existing', medicineId: reloadedExisting.id }
        }
      }
      throw error
    }
  }

  const updateMedicine = async (pharmacyId, medicineId, updates, options = {}) => {
    const { skipReload = false } = options
    const inventoryId = medicineId
    const targetMedicine = medicines.find((med) => med.id === medicineId)
    if (!targetMedicine) {
      throw new Error('Dori topilmadi')
    }

    await medicinesApi.update(targetMedicine.medicineId, {
      name: buildMedicineDisplayName(updates.name || targetMedicine.name || '', updates.strength).trim(),
      category: (updates.category || targetMedicine.category || 'Boshqa').trim(),
      description: (updates.category || targetMedicine.category || 'Boshqa').trim(),
      strength: '',
      dosage_form: (updates.dosageForm || updates.appearance || targetMedicine.dosageForm || targetMedicine.appearance || '').trim(),
      country_of_origin: normalizeCountryOption(updates.countryOfOrigin || targetMedicine.countryOfOrigin || ''),
    })

    await pharmacyInventoryApi.update(inventoryId, {
      quantity_in_stock: updates.stock === 'out' ? 0 : parseInt(updates.stock, 10),
      unit_price: parseInt(updates.price, 10),
      expiry_date: toIsoDate(updates.expiryDate) || toIsoDate(targetMedicine.expiryDate),
    })

    if (!skipReload) {
      await loadPharmacyInventory(pharmacyId)
    }
  }

  const deleteMedicine = async (pharmacyId, medicineId) => {
    await pharmacyInventoryApi.delete(medicineId)
    await loadPharmacyInventory(pharmacyId)
  }

  const clearAllMedicines = async (pharmacyId) => {
    const result = await pharmacyInventoryApi.clearAll()
    const deletedCount = Number(result?.deleted_count || 0)
    const failedCount = 0

    await loadPharmacyInventory(pharmacyId)
    return { deletedCount, failedCount }
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
        clearAllMedicines,
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
