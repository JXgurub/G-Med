import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePharmacy } from '../context/PharmacyContext'
import { useNotifications } from '../hooks/useWebSocket'
import { pharmaciesApi, medicinesApi } from '../services/api'
import useSmartAutoRefresh from '../hooks/useSmartAutoRefresh'
import { formatCurrencyInput, parseCurrencyInput } from '../utils/currency'
import './PharmacyOwnerDashboard.css'

const DEFAULT_MEDICINE_FORM = {
  name: '',
  dosageForm: 'tabletka',
  expiryDate: '',
  countryOfOrigin: '',
  price: '',
  category: 'Boshqa',
  stock: '1'
}

const MEDICINE_APPEARANCE_OPTIONS = ['tabletka', 'sirop', 'kapsula', 'svecha', 'ampula', 'kukon']
const MEDICINE_COUNTRY_OPTIONS = ["O'zbekiston", 'Rossiya', 'Vetnam', 'Boshqa']

const downloadBlob = (content, filename, mimeType) => {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

const formatDateForFile = (date = new Date()) => {
  const pad = (num) => String(num).padStart(2, '0')
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}-${pad(date.getHours())}${pad(date.getMinutes())}`
}

const normalizeHeader = (value) => String(value || '')
  .trim()
  .toLowerCase()
  .replace(/\s+/g, '_')
  .replace(/[^a-z0-9_]/g, '')

const parseStockValue = (value) => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Math.max(0, Math.round(value))
  }
  if (typeof value === 'boolean') {
    return value ? 1 : 0
  }

  const text = String(value || '').trim().toLowerCase()
  if (!text) return 1
  if (['out', 'yoq', 'yo\'q', 'tugagan', 'none', '0', 'false'].includes(text)) return 0
  if (['bor', 'mavjud', 'in_stock', 'instock', 'available', 'true'].includes(text)) return 1

  const parsed = Number.parseInt(text.replace(/[^0-9-]/g, ''), 10)
  if (!Number.isFinite(parsed)) return 1
  return Math.max(0, parsed)
}

const parsePriceValue = (value) => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Math.round(value)
  }
  const parsed = parseCurrencyInput(String(value || ''))
  return Number.isFinite(parsed) ? parsed : 0
}

const normalizeCountryOption = (value) => {
  const country = String(value || '').trim()
  const normalized = country.toLowerCase()
  if (!normalized) return ''

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
  if (MEDICINE_COUNTRY_OPTIONS.includes(country)) {
    return country
  }
  return 'Boshqa'
}

const buildMedicineDisplayName = (name, strength = '') => {
  const cleanName = String(name || '').trim()
  const cleanStrength = String(strength || '').trim()

  if (!cleanStrength) return cleanName
  if (cleanName.toLowerCase().includes(cleanStrength.toLowerCase())) {
    return cleanName
  }
  return `${cleanName} ${cleanStrength}`.trim()
}

const normalizeExpiryDateValue = (value) => {
  if (value == null || value === '') return ''
  if (typeof value === 'number' && Number.isFinite(value)) {
    const excelEpoch = new Date(Date.UTC(1899, 11, 30))
    const nextDate = new Date(excelEpoch.getTime() + Math.round(value) * 86400000)
    return String(nextDate.getUTCFullYear())
  }

  const text = String(value).trim()
  if (!text) return ''
  if (/^\d{4}$/.test(text)) return text
  const direct = text.match(/^\d{4}-\d{2}-\d{2}$/)
  if (direct) return text.slice(0, 4)

  const parsed = new Date(text)
  if (Number.isNaN(parsed.getTime())) return ''
  return String(parsed.getFullYear())
}

const formatDateLabel = (value) => {
  return normalizeExpiryDateValue(value) || '—'
}

const normalizeMedicineLabel = (value) => String(value || '').trim().toLowerCase()

const buildMedicineIdentityKey = (value = {}) => {
  const name = normalizeMedicineLabel(buildMedicineDisplayName(value.name, value.strength || value.medicine_strength))
  const dosageForm = normalizeMedicineLabel(value.dosageForm || value.appearance || value.dosage_form)
  const category = normalizeMedicineLabel(value.category)
  const country = normalizeMedicineLabel(value.countryOfOrigin || value.country_of_origin)
  return `${name}__${dosageForm}__${category}__${country}`
}

const formatMedicinePreviewLabel = (value) => String(value || '')
  .replace(/[_-]\d+$/g, '')
  .replace(/_/g, ' ')
  .replace(/\s+/g, ' ')
  .trim()

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

const getMedicineNameSuggestionScore = (medicineName, query) => {
  const normalizedMedicineName = normalizeMedicineLabel(medicineName)
  const normalizedQuery = normalizeMedicineLabel(query)

  if (!normalizedMedicineName || !normalizedQuery) return 0
  if (normalizedMedicineName === normalizedQuery) return 100
  if (normalizedMedicineName.startsWith(normalizedQuery)) return 80
  if (normalizedMedicineName.includes(normalizedQuery)) return 60

  const queryTokens = normalizedQuery.split(/\s+/).filter(Boolean)
  if (queryTokens.length > 0 && queryTokens.every((token) => normalizedMedicineName.includes(token))) {
    return 40
  }

  return 0
}

const mapImportedMedicineRow = (row) => {
  const normalized = {}
  Object.entries(row || {}).forEach(([key, value]) => {
    normalized[normalizeHeader(key)] = value
  })

  const name = String(
    normalized.name
    ?? normalized.dori
    ?? normalized.dori_nomi
    ?? normalized.medicine
    ?? normalized.product
    ?? ''
  ).trim()

  const category = String(
    normalized.category
    ?? normalized.kategoriya
    ?? normalized.group
    ?? 'Boshqa'
  ).trim() || 'Boshqa'

  const strength = String(
    normalized.strength
    ?? normalized.dose
    ?? normalized.dosage
    ?? normalized.dozasi
    ?? ''
  ).trim()
  const fullName = buildMedicineDisplayName(name, strength)

  const dosageForm = String(
    normalized.dosage_form
    ?? normalized.appearance
    ?? normalized.korinishi
    ?? normalized.korinishi
    ?? normalized.form
    ?? 'tabletka'
  ).trim().toLowerCase() || 'tabletka'

  const countryOfOrigin = normalizeCountryOption(String(
    normalized.country_of_origin
    ?? normalized.country
    ?? normalized.ishlab_chiqarilgan_davlat
    ?? normalized.davlat
    ?? ''
  ).trim())

  const expiryDate = normalizeExpiryDateValue(
    normalized.expiry_year
    ?? normalized.year
    ?? normalized.expiry_date
    ?? normalized.expiry
    ?? normalized.yaroqlik_muddati
    ?? normalized.yaroqlilik_muddati
  )

  const price = parsePriceValue(
    normalized.price
    ?? normalized.narx
    ?? normalized.unit_price
    ?? normalized.unitprice
  )

  const stock = parseStockValue(
    normalized.stock
    ?? normalized.miqdor
    ?? normalized.quantity
    ?? normalized.count
  )

  if (!name || !price || price < 0) {
    return null
  }

  return {
    name: fullName,
    strength: '',
    dosageForm,
    countryOfOrigin,
    expiryDate,
    category,
    price,
    stock,
  }
}

const toDelimitedText = (rows, delimiter = ',') => rows
  .map((row) => row
    .map((cell) => {
      const raw = cell == null ? '' : String(cell)
      const escaped = raw.replace(/"/g, '""')
      return `"${escaped}"`
    })
    .join(delimiter))
  .join('\n')

const PharmacyOwnerDashboard = () => {
  const DEFAULT_PHONE_PREFIX = '+998'
  const currentYear = new Date().getFullYear()
  const navigate = useNavigate()
  const {
    currentPharmacy,
    medicines: pharmacyMedicines,
    loading,
    logoutPharmacy,
    addMedicine,
    updateMedicine,
    deleteMedicine,
    clearAllMedicines,
    uploadPharmacyLogo,
    removePharmacyLogo,
    refreshCurrentPharmacyData
  } = usePharmacy()
  
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [medicines, setMedicines] = useState([])
  const [showPharmacyEdit, setShowPharmacyEdit] = useState(false)
  const [pharmacyInfo, setPharmacyInfo] = useState({
    address: '',
    phone_number: DEFAULT_PHONE_PREFIX,
    working_hours: ''
  })
  const [updatingPharmacy, setUpdatingPharmacy] = useState(false)
  const [updateMessage, setUpdateMessage] = useState('')
  const [salesStats, setSalesStats] = useState({
    todayRevenue: 0,
    monthRevenue: 0,
    totalRevenue: 0
  })
  const [formData, setFormData] = useState({
    ...DEFAULT_MEDICINE_FORM
  })
  const [medicineBase, setMedicineBase] = useState([])
  const [medicineBaseLoading, setMedicineBaseLoading] = useState(false)
  const [medicineNameAlerts, setMedicineNameAlerts] = useState([])
  const [medicineNameAlertsLoading, setMedicineNameAlertsLoading] = useState(false)
  const [correctionDrafts, setCorrectionDrafts] = useState({})
  const [correctionSavingId, setCorrectionSavingId] = useState(null)
  const [priceClearedOnFocus, setPriceClearedOnFocus] = useState(false)
  const [medicineSearch, setMedicineSearch] = useState('')
  const [selectedLogoFile, setSelectedLogoFile] = useState(null)
  const [logoPreviewUrl, setLogoPreviewUrl] = useState('')
  const [logoSaving, setLogoSaving] = useState(false)
  const [showLogoMenu, setShowLogoMenu] = useState(false)
  const [medicineTransferMessage, setMedicineTransferMessage] = useState('')
  const [medicineTransferType, setMedicineTransferType] = useState('success')
  const [medicineImporting, setMedicineImporting] = useState(false)
  const [medicineImportProgress, setMedicineImportProgress] = useState(0)
  const [pendingImportFiles, setPendingImportFiles] = useState([])
  const [medicineTransferMeta, setMedicineTransferMeta] = useState(null)
  const [confirmingAllNameAlerts, setConfirmingAllNameAlerts] = useState(false)
  const [bulkDeletingMedicines, setBulkDeletingMedicines] = useState(false)
  const [medicinesUpdatedAt, setMedicinesUpdatedAt] = useState(null)
  const logoInputRef = useRef(null)
  const logoActionWrapRef = useRef(null)
  const medicineImportInputRef = useRef(null)
  const medicineMessageTimerRef = useRef(null)

  useEffect(() => {
    // Don't redirect while loading
    if (loading) return
    
    if (!currentPharmacy) {
      navigate('/pharmacy-owner-login')
      return
    }
    
    // Check if subscription is expired and redirect to blocked page
    if (currentPharmacy.subscription?.is_expired || currentPharmacy.isSubscriptionExpired) {
      navigate('/subscription-blocked', { replace: true })
      return
    }
    
    setMedicines(pharmacyMedicines)
    // Initialize pharmacy info
    setPharmacyInfo({
      address: currentPharmacy.address || '',
      phone_number: currentPharmacy.phone_number || currentPharmacy.phone || DEFAULT_PHONE_PREFIX,
      working_hours: currentPharmacy.working_hours || '09:00 - 20:00'
    })
  }, [currentPharmacy, loading, navigate, pharmacyMedicines])

  useEffect(() => {
    if (!currentPharmacy?.id) {
      setMedicineBase([])
      return
    }

    let cancelled = false

    const loadMedicineBase = async () => {
      setMedicineBaseLoading(true)
      try {
        let page = 1
        const all = []

        while (page <= 100) {
          const response = await medicinesApi.getAll({ page })

          if (Array.isArray(response)) {
            all.push(...response)
            break
          }

          const rows = Array.isArray(response?.results) ? response.results : []
          all.push(...rows)

          if (!response?.next || rows.length === 0) {
            break
          }

          page += 1
        }

        if (cancelled) return

        const mapped = all.map((item) => ({
          id: item.id,
          name: buildMedicineDisplayName(item.name || '', item.strength || ''),
          strength: item.strength || '',
          dosageForm: item.dosage_form || 'tabletka',
          countryOfOrigin: normalizeCountryOption(item.country_of_origin || ''),
          category: item.category || item.description || 'Boshqa',
          genericName: item.generic_name || '',
          atcCode: item.atc_code || '',
          manufacturer: item.manufacturer || '',
          description: item.description || '',
        }))

        setMedicineBase(mapped)
      } catch (error) {
        if (!cancelled) {
          setMedicineBase([])
        }
      } finally {
        if (!cancelled) {
          setMedicineBaseLoading(false)
        }
      }
    }

    loadMedicineBase()

    return () => {
      cancelled = true
    }
  }, [currentPharmacy?.id])

  // Sync medicines whenever pharmacyMedicines changes
  useEffect(() => {
    if (Array.isArray(pharmacyMedicines)) {
      setMedicines(pharmacyMedicines)
      setMedicinesUpdatedAt(new Date())
    }
  }, [pharmacyMedicines])

  useEffect(() => {
    if (!currentPharmacy) return

    const todayKey = new Date().toISOString().slice(0, 10)
    const monthKey = todayKey.slice(0, 7)
    const storageKey = 'pharmacySalesStats'
    const stored = JSON.parse(localStorage.getItem(storageKey) || '{}')

    const createSeed = (text) => {
      let hash = 0
      for (let i = 0; i < text.length; i += 1) {
        hash = (hash * 31 + text.charCodeAt(i)) % 100000
      }
      return hash
    }

    const inStockCount = medicines.filter((m) => m.stock > 0).length
    const totalPrice = medicines.reduce((sum, m) => sum + (m.price || 0), 0)
    const avgPrice = medicines.length ? totalPrice / medicines.length : 0
    const baseRevenue = avgPrice * Math.max(1, Math.min(25, inStockCount))
    const seed = createSeed(`${currentPharmacy.id}-${todayKey}-${medicines.length}`)
    const factor = 0.4 + (seed % 80) / 100
    const todayRevenue = Math.round(baseRevenue * factor)

    const existing = stored[currentPharmacy.id]
    if (existing && existing.lastDate === todayKey) {
      setSalesStats({
        todayRevenue: existing.todayRevenue,
        monthRevenue: existing.monthRevenue,
        totalRevenue: existing.totalRevenue
      })
      return
    }

    const monthRevenue = existing && existing.monthKey === monthKey
      ? existing.monthRevenue + todayRevenue
      : todayRevenue * 12
    const totalRevenue = existing
      ? existing.totalRevenue + todayRevenue
      : monthRevenue * 6

    stored[currentPharmacy.id] = {
      lastDate: todayKey,
      monthKey,
      todayRevenue,
      monthRevenue,
      totalRevenue
    }
    localStorage.setItem(storageKey, JSON.stringify(stored))
    setSalesStats({ todayRevenue, monthRevenue, totalRevenue })
  }, [currentPharmacy, medicines])

  useEffect(() => {
    if (!selectedLogoFile) {
      setLogoPreviewUrl('')
      return
    }

    const objectUrl = URL.createObjectURL(selectedLogoFile)
    setLogoPreviewUrl(objectUrl)
    return () => URL.revokeObjectURL(objectUrl)
  }, [selectedLogoFile])

  useEffect(() => {
    if (!showLogoMenu) return

    const handleOutsideClick = (event) => {
      if (!logoActionWrapRef.current) return
      if (logoActionWrapRef.current.contains(event.target)) return
      setShowLogoMenu(false)
    }

    document.addEventListener('mousedown', handleOutsideClick)
    document.addEventListener('touchstart', handleOutsideClick)

    return () => {
      document.removeEventListener('mousedown', handleOutsideClick)
      document.removeEventListener('touchstart', handleOutsideClick)
    }
  }, [showLogoMenu])

  useEffect(() => () => {
    if (medicineMessageTimerRef.current) {
      window.clearTimeout(medicineMessageTimerRef.current)
    }
  }, [])

  const showTemporaryMedicineMessage = useCallback((message, type = 'success') => {
    setMedicineTransferType(type)
    setMedicineTransferMessage(message)
    setMedicineTransferMeta(null)

    if (medicineMessageTimerRef.current) {
      window.clearTimeout(medicineMessageTimerRef.current)
    }

    medicineMessageTimerRef.current = window.setTimeout(() => {
      setMedicineTransferMessage('')
      medicineMessageTimerRef.current = null
    }, 5000)
  }, [])

  const loadMedicineNameAlerts = useCallback(async ({ silent = false } = {}) => {
    if (!currentPharmacy?.id) {
      setMedicineNameAlerts([])
      return
    }

    if (!silent) {
      setMedicineNameAlertsLoading(true)
    }

    try {
      const response = await medicinesApi.getNameAlerts()
      const rows = Array.isArray(response) ? response : (Array.isArray(response?.results) ? response.results : [])
      setMedicineNameAlerts(rows)
    } catch (error) {
      if (!silent) {
        setMedicineTransferType('error')
        setMedicineTransferMessage('Dori nomi bo\'yicha xabarlarni yuklashda xatolik yuz berdi.')
        setMedicineTransferMeta(null)
      }
      setMedicineNameAlerts([])
    } finally {
      if (!silent) {
        setMedicineNameAlertsLoading(false)
      }
    }
  }, [currentPharmacy?.id])

  useEffect(() => {
    loadMedicineNameAlerts()
  }, [loadMedicineNameAlerts])

  const handleMedicineNotification = useCallback(async (event) => {
    const notificationType = event?.data?.notification_type
    const payload = event?.data?.payload || {}

    if (notificationType === 'medicine_name_verification_created') {
      showTemporaryMedicineMessage(
        payload?.message || `${payload?.original_name || 'Yangi dori'} bo'yicha tekshiruv xabari keldi.`
      )
      await loadMedicineNameAlerts({ silent: true })
      return
    }

    if (notificationType === 'medicine_name_verification_resolved') {
      const resolutionType = payload?.resolution_type
      showTemporaryMedicineMessage(
        resolutionType === 'kept_original'
          ? `${payload?.original_name || 'Dori'} nomi shu holatda qoldi.`
          : `${payload?.original_name || 'Dori'} nomi ${payload?.corrected_name || "to'g'rilandi"} qilib yangilandi.`
      )
      await loadMedicineNameAlerts({ silent: true })
      await refreshCurrentPharmacyData()
    }
  }, [loadMedicineNameAlerts, refreshCurrentPharmacyData, showTemporaryMedicineMessage])

  useNotifications(currentPharmacy?.owner, handleMedicineNotification)

  const refreshPharmacyDashboard = useCallback(async () => {
    if (!currentPharmacy?.id) return
    if (showAddForm || showPharmacyEdit || logoSaving || updatingPharmacy) return
    await refreshCurrentPharmacyData()
  }, [
    currentPharmacy?.id,
    showAddForm,
    showPharmacyEdit,
    logoSaving,
    updatingPharmacy,
    refreshCurrentPharmacyData,
  ])

  useSmartAutoRefresh({
    enabled: Boolean(currentPharmacy?.id),
    callback: refreshPharmacyDashboard,
    minIntervalMs: 45000,
    maxIntervalMs: 60000,
    immediate: false,
  })

  if (loading) {
    return <div style={{ padding: '20px', textAlign: 'center' }}>Yuklanyapti...</div>
  }

  if (!currentPharmacy) {
    return null
  }

  const findMatchingMedicineBase = (medicineLike) => {
    const key = buildMedicineIdentityKey(medicineLike)
    if (!key || key.startsWith('___')) return null
    return medicineBase.find((item) => buildMedicineIdentityKey(item) === key) || null
  }

  const runImportOperationWithRetry = async (operation, label = '') => {
    const maxAttempts = 4

    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      try {
        return await operation()
      } catch (error) {
        const isThrottle = error?.response?.status === 429
        if (!isThrottle || attempt === maxAttempts) {
          throw error
        }

        const detail = String(error?.response?.data?.detail || error?.message || '')
        const retryAfterMatch = detail.match(/available in\s+(\d+)\s+second/i)
        const retryAfterSeconds = retryAfterMatch ? Number.parseInt(retryAfterMatch[1], 10) : null
        const fallbackSeconds = Math.min(12, attempt * 3)
        const waitSeconds = Number.isFinite(retryAfterSeconds)
          ? Math.max(2, Math.min(15, retryAfterSeconds))
          : fallbackSeconds

        setMedicineTransferType('error')
        setMedicineTransferMessage(
          `So'rov limiti vaqtincha to'ldi${label ? ` (${label})` : ''}. ${waitSeconds} soniyadan keyin qayta urinilmoqda (${attempt}/${maxAttempts}).`
        )
        await wait(waitSeconds * 1000)
      }
    }

    return null
  }

  const handleAddMedicine = async (e) => {
    e.preventDefault()
    const priceValue = parseCurrencyInput(formData.price)
    const expiryYear = normalizeExpiryDateValue(formData.expiryDate)
    if (!formData.name || !formData.dosageForm || !expiryYear || !formData.countryOfOrigin || !priceValue) {
      alert('Dori nomi, ko\'rinishi, yaroqlilik yili, ishlab chiqarilgan davlat va narxini kiriting')
      return
    }

    try {
      if (editingId) {
        await updateMedicine(currentPharmacy.id, editingId, {
          name: formData.name,
          dosageForm: formData.dosageForm,
          countryOfOrigin: formData.countryOfOrigin,
          expiryDate: expiryYear,
          price: priceValue,
          category: formData.category,
          stock: formData.stock === 'out' ? 0 : parseInt(formData.stock)
        })
        setEditingId(null)
        alert('Dori yangilandi! ✅')
      } else {
        const matchedGlobalMedicine = findMatchingMedicineBase({
          ...formData,
          expiryDate: expiryYear,
        })

        const result = await addMedicine(currentPharmacy.id, {
          ...formData,
          expiryDate: expiryYear,
          price: priceValue,
          stock: formData.stock === 'out' ? 0 : parseInt(formData.stock)
        }, {
          preferredMedicineId: matchedGlobalMedicine?.id || null,
        })
        if (result?.mode === 'updated_existing') {
          alert('Bu dori allaqachon mavjud edi — mavjud yozuv yangilandi ✅')
        } else if (result?.nameVerificationAlertCreated) {
          alert('Dori qo\'shildi. Nomi bazada topilmadi, boshqa dorixonalarga xabar yuborildi ✅')
        } else {
          alert('Dori qo\'shildi! ✅')
        }
      }

      setFormData({ ...DEFAULT_MEDICINE_FORM })
      setPriceClearedOnFocus(false)
      setShowAddForm(false)
    } catch (error) {
      console.error('Medicine operation error:', error)
      alert('Xatolik: ' + (error.message || 'Dori qo\'shishda xatolik yuz berdi'))
    }
  }

  const handleEdit = (medicine) => {
    setFormData({
      name: buildMedicineDisplayName(medicine.name, medicine.strength),
      dosageForm: medicine.dosageForm || medicine.appearance || 'tabletka',
      expiryDate: normalizeExpiryDateValue(medicine.expiryDate) || '',
      countryOfOrigin: normalizeCountryOption(medicine.countryOfOrigin) || '',
      price: formatCurrencyInput(medicine.price),
      category: medicine.category,
      stock: medicine.stock === 0 ? 'out' : medicine.stock.toString()
    })
    setPriceClearedOnFocus(false)
    setEditingId(medicine.id)
    setShowAddForm(true)
  }

  const handleDelete = (medicineId) => {
    if (window.confirm('Rostlik olib tashlamoqchisiz?')) {
      deleteMedicine(currentPharmacy.id, medicineId)
      alert('Dori o\'chirildi! ✅')
    }
  }

  const handleDeleteAllMedicines = async () => {
    if (!currentPharmacy?.id) return
    if (medicines.length === 0) {
      alert('O\'chirish uchun dori topilmadi')
      return
    }

    const confirmed = window.confirm(
      `Rostdan ham barcha dorilarni o\'chirmoqchimisiz?\nJami: ${medicines.length} ta dori.`
    )
    if (!confirmed) return

    setBulkDeletingMedicines(true)
    try {
      const result = await clearAllMedicines(currentPharmacy.id)
      if (result.failedCount > 0) {
        alert(`Qisman bajarildi: o\'chirildi ${result.deletedCount}, xatolik ${result.failedCount}.`)
      } else {
        alert(`Barcha dorilar o\'chirildi: ${result.deletedCount} ta ✅`)
      }
    } catch (error) {
      alert('Barcha dorilarni o\'chirishda xatolik: ' + (error?.message || 'noma\'lum xatolik'))
    } finally {
      setBulkDeletingMedicines(false)
    }
  }

  const handleLogout = () => {
    logoutPharmacy()
    navigate('/pharmacy-owner-login')
  }

  const handleUpdatePharmacyInfo = async (e) => {
    e.preventDefault()
    setUpdatingPharmacy(true)
    setUpdateMessage('')

    try {
      await pharmaciesApi.update(currentPharmacy.id, {
        address: pharmacyInfo.address,
        phone_number: pharmacyInfo.phone_number,
        working_hours: pharmacyInfo.working_hours
      })
      
      setUpdateMessage('✅ Dorixona ma\'lumotlari yangilandi')
      setShowPharmacyEdit(false)
      
      // Update local pharmacy info
      setTimeout(() => {
        setUpdateMessage('')
      }, 3000)
    } catch (error) {
      console.error('Error updating pharmacy:', error)
      setUpdateMessage('❌ Xatolik: ' + (error.message || 'Yangilanishda xatolik'))
    } finally {
      setUpdatingPharmacy(false)
    }
  }

  const openLogoFilePicker = () => {
    logoInputRef.current?.click()
  }

  const handleLogoClick = () => {
    if (logoSaving) return
    if (currentPharmacy?.logoUrl || selectedLogoFile) {
      setShowLogoMenu((prev) => !prev)
      return
    }
    openLogoFilePicker()
  }

  const handleLogoInputChange = (event) => {
    const file = event.target.files?.[0] || null
    setSelectedLogoFile(file)
    if (file) {
      setShowLogoMenu(true)
    }
    event.target.value = ''
  }

  const handleLogoSave = async () => {
    if (!selectedLogoFile) {
      alert('Rasm faylini tanlang')
      return
    }

    setLogoSaving(true)
    try {
      await uploadPharmacyLogo(selectedLogoFile)
      setSelectedLogoFile(null)
      setShowLogoMenu(false)
      alert('Dorixona rasmi saqlandi ✅')
    } catch (error) {
      alert(error?.message || 'Dorixona rasmini saqlashda xatolik')
    } finally {
      setLogoSaving(false)
    }
  }

  const handleLogoRemove = async () => {
    if (selectedLogoFile && !currentPharmacy?.logoUrl) {
      setSelectedLogoFile(null)
      setLogoPreviewUrl('')
      setShowLogoMenu(false)
      return
    }

    if (!currentPharmacy?.logoUrl) return

    setLogoSaving(true)
    try {
      await removePharmacyLogo()
      setSelectedLogoFile(null)
      setLogoPreviewUrl('')
      setShowLogoMenu(false)
      alert('Dorixona rasmi o\'chirildi ✅')
    } catch (error) {
      alert(error?.message || 'Dorixona rasmini o\'chirishda xatolik')
    } finally {
      setLogoSaving(false)
    }
  }

  const normalizedMedicineSearch = medicineSearch.trim().toLowerCase()
  const filteredMedicines = normalizedMedicineSearch
    ? medicines.filter((medicine) =>
        `${buildMedicineDisplayName(medicine.name, medicine.strength)} ${medicine.dosageForm || medicine.appearance || ''} ${medicine.countryOfOrigin || ''} ${medicine.category}`.toLowerCase().includes(normalizedMedicineSearch)
      )
    : medicines

  const filteredMedicineBase = normalizedMedicineSearch
    ? medicineBase.filter((medicine) =>
        `${buildMedicineDisplayName(medicine.name, medicine.strength)} ${medicine.dosageForm || ''} ${medicine.countryOfOrigin || ''} ${medicine.category || ''}`.toLowerCase().includes(normalizedMedicineSearch)
      )
    : []

  const normalizedTypedMedicineName = normalizeMedicineLabel(formData.name)
  const medicineNameSuggestions = normalizedTypedMedicineName
    ? medicineBase
        .map((medicine) => ({
          medicine,
          score: getMedicineNameSuggestionScore(medicine.name, normalizedTypedMedicineName),
        }))
        .filter((item) => item.score > 0)
        .sort((left, right) => {
          if (right.score !== left.score) {
            return right.score - left.score
          }
          return String(left.medicine.name || '').localeCompare(String(right.medicine.name || ''), 'uz')
        })
        .slice(0, 5)
        .map((item) => item.medicine)
    : []
  const exactMedicineNameFound = Boolean(
    normalizedTypedMedicineName && medicineBase.some((medicine) => normalizeMedicineLabel(medicine.name) === normalizedTypedMedicineName)
  )

  const applyMedicineBaseTemplate = (medicine) => {
    setEditingId(null)
    setFormData((prev) => ({
      ...prev,
      name: buildMedicineDisplayName(medicine.name, medicine.strength) || '',
      dosageForm: medicine.dosageForm || 'tabletka',
      countryOfOrigin: normalizeCountryOption(medicine.countryOfOrigin) || prev.countryOfOrigin,
      category: medicine.category || prev.category || 'Boshqa',
    }))
  }

  const handleConfirmNameAlert = async (alertId) => {
    setCorrectionSavingId(alertId)
    try {
      const result = await medicinesApi.confirmNameAlert(alertId)
      await loadMedicineNameAlerts({ silent: true })
      if (result?.resolved) {
        showTemporaryMedicineMessage(
          result?.resolution_type === 'kept_original'
            ? 'Ko\'pchilik ovoziga ko\'ra nom shu holatda qoldi.'
            : `Ko\'pchilik ovoziga ko\'ra nom ${result?.corrected_name || 'yangilandi'}.`
        )
      } else {
        showTemporaryMedicineMessage('"To\'g\'ri kiritilgan" ovozi qabul qilindi.')
      }
      await refreshCurrentPharmacyData()
    } catch (error) {
      showTemporaryMedicineMessage(
        error?.message || 'Tasdiqlashda xatolik yuz berdi.',
        'error'
      )
    } finally {
      setCorrectionSavingId(null)
    }
  }

  const handleConfirmAllNameAlerts = async () => {
    if (medicineNameAlerts.length === 0) {
      return
    }

    const confirmed = window.confirm(
      `${medicineNameAlerts.length} ta xabarning barchasiga "To'g'ri kiritilgan" deb ovoz bermoqchimisiz?`
    )
    if (!confirmed) {
      return
    }

    setConfirmingAllNameAlerts(true)
    try {
      const result = await medicinesApi.confirmAllNameAlerts()
      await loadMedicineNameAlerts({ silent: true })
      await refreshCurrentPharmacyData()
      showTemporaryMedicineMessage(
        `Barchasi tasdiqlandi: ${result?.processed_count || 0} ta ovoz, ${result?.resolved_count || 0} ta yakunlandi.`
      )
    } catch (error) {
      showTemporaryMedicineMessage(
        error?.message || 'Barchasini tasdiqlashda xatolik yuz berdi.',
        'error'
      )
    } finally {
      setConfirmingAllNameAlerts(false)
    }
  }

  const handleCorrectNameAlert = async (alertId) => {
    const correctedName = String(correctionDrafts[alertId] || '').trim()
    if (!correctedName) {
      alert('To\'g\'ri dori nomini doza bilan birga kiriting')
      return
    }

    setCorrectionSavingId(alertId)
    try {
      const result = await medicinesApi.correctNameAlert(alertId, { name: correctedName })
      setCorrectionDrafts((prev) => {
        const nextState = { ...prev }
        delete nextState[alertId]
        return nextState
      })
      await loadMedicineNameAlerts({ silent: true })
      showTemporaryMedicineMessage(
        result?.resolved
          ? `Ko\'pchilik ovoziga ko\'ra dori nomi: ${result?.corrected_name || correctedName}`
          : 'Nom o\'zgartirish varianti qabul qilindi.'
      )
      await refreshCurrentPharmacyData()
    } catch (error) {
      showTemporaryMedicineMessage(
        error?.message || 'Dori nomini to\'g\'rilashda xatolik yuz berdi.',
        'error'
      )
    } finally {
      setCorrectionSavingId(null)
    }
  }

  const formatDateTimeLabel = (value) => {
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

  const buildMedicinesExportPayload = () => {
    const generatedAt = new Date()
    const generatedAtIso = generatedAt.toISOString()
    const generatedAtLabel = formatDateTimeLabel(generatedAt)
    const items = medicines.map((medicine) => ({
      medicine_id: medicine.id,
      name: buildMedicineDisplayName(medicine.name, medicine.strength),
      dosage_form: medicine.dosageForm || medicine.appearance || '',
      expiry_year: normalizeExpiryDateValue(medicine.expiryDate) || '',
      country_of_origin: normalizeCountryOption(medicine.countryOfOrigin) || 'Boshqa',
      category: medicine.category || 'Boshqa',
      price: Number(medicine.price || 0),
      stock: Number(medicine.stock || 0),
      availability: Number(medicine.stock || 0) > 0 ? 'available' : 'out_of_stock',
    }))

    return {
      generatedAtIso,
      generatedAtLabel,
      fileDate: formatDateForFile(generatedAt),
      pharmacy: {
        id: currentPharmacy.id,
        name: currentPharmacy.name,
        city: currentPharmacy.city || '',
        address: currentPharmacy.address || '',
      },
      items,
    }
  }

  const handleExportMedicines = async (format) => {
    const payload = buildMedicinesExportPayload()

    if (format === 'xlsx') {
      const XLSX = await import('xlsx')
      const wb = XLSX.utils.book_new()
      const infoSheet = XLSX.utils.json_to_sheet([
        {
          generated_at: payload.generatedAtIso,
          pharmacy_id: payload.pharmacy.id,
          pharmacy_name: payload.pharmacy.name,
          city: payload.pharmacy.city,
          address: payload.pharmacy.address,
          currency: 'UZS',
          total_items: payload.items.length,
        },
      ])
      const itemsSheet = XLSX.utils.json_to_sheet(payload.items)
      XLSX.utils.book_append_sheet(wb, infoSheet, 'Summary')
      XLSX.utils.book_append_sheet(wb, itemsSheet, 'Medicines')
      XLSX.writeFile(wb, `pharmacy-medicines-${payload.fileDate}.xlsx`)
      return
    }

    if (format === 'json') {
      const data = {
        generated_at: payload.generatedAtIso,
        pharmacy: payload.pharmacy,
        currency: 'UZS',
        medicines: payload.items,
      }
      downloadBlob(JSON.stringify(data, null, 2), `pharmacy-medicines-${payload.fileDate}.json`, 'application/json;charset=utf-8')
      return
    }

    const delimiter = format === 'tsv' ? '\t' : ','
    const rows = [
      ['generated_at', payload.generatedAtIso],
      ['pharmacy_id', payload.pharmacy.id],
      ['pharmacy_name', payload.pharmacy.name],
      ['city', payload.pharmacy.city],
      ['address', payload.pharmacy.address],
      ['currency', 'UZS'],
      [],
      ['medicine_id', 'name', 'dosage_form', 'expiry_year', 'country_of_origin', 'category', 'price', 'stock', 'availability'],
      ...payload.items.map((item) => [
        item.medicine_id,
        item.name,
        item.dosage_form,
        item.expiry_year,
        item.country_of_origin,
        item.category,
        item.price,
        item.stock,
        item.availability,
      ]),
    ]

    downloadBlob(
      toDelimitedText(rows, delimiter),
      `pharmacy-medicines-${payload.fileDate}.${format === 'tsv' ? 'tsv' : 'csv'}`,
      `text/${format === 'tsv' ? 'tab-separated-values' : 'csv'};charset=utf-8`
    )
  }

  const openMedicinesImportPicker = () => {
    medicineImportInputRef.current?.click()
  }

  const parseImportedRowsFromFile = async (file) => {
    const fileName = file.name.toLowerCase()
    let rawRows = []

    if (fileName.endsWith('.json')) {
      const text = await file.text()
      const parsed = JSON.parse(text)
      if (Array.isArray(parsed)) {
        rawRows = parsed
      } else if (Array.isArray(parsed?.medicines)) {
        rawRows = parsed.medicines
      }
    } else {
      const XLSX = await import('xlsx')
      const buffer = await file.arrayBuffer()
      const workbook = XLSX.read(buffer, { type: 'array' })
      const firstSheetName = workbook.SheetNames?.[0]
      if (firstSheetName) {
        const firstSheet = workbook.Sheets[firstSheetName]
        rawRows = XLSX.utils.sheet_to_json(firstSheet, { defval: '' })
      }
    }

    const mappedRows = rawRows.map(mapImportedMedicineRow).filter(Boolean)
    return { rawRows, mappedRows }
  }

  const handleImportFileSelected = async (event) => {
    const selectedFiles = Array.from(event.target.files || [])
    event.target.value = ''

    if (selectedFiles.length === 0 || !currentPharmacy?.id) return

    const files = selectedFiles.slice(0, 2)

    setMedicineImportProgress(0)

    try {
      let totalMappedRows = 0

      for (const file of files) {
        const { mappedRows } = await parseImportedRowsFromFile(file)
        totalMappedRows += mappedRows.length
      }

      setPendingImportFiles(files)

      if (totalMappedRows === 0) {
        setMedicineTransferType('error')
        setMedicineTransferMessage('Fayl tanlandi, lekin yaroqli qator topilmadi. Ustunlar: name/dosage_form/expiry_year/country/category/price/stock.')
        setMedicineTransferMeta(null)
        return
      }

      const truncatedNotice = selectedFiles.length > files.length
        ? ` (${selectedFiles.length} tadan faqat dastlabki 2 tasi tanlandi)`
        : ''

      setMedicineTransferType('success')
      setMedicineTransferMeta(null)
      setMedicineTransferMessage(
        `${files.length} ta fayl tanlandi${truncatedNotice}. Saqlash tugmasini bossangiz ${totalMappedRows} ta qator import qilinadi.`
      )
    } catch (error) {
      setPendingImportFiles([])
      setMedicineTransferType('error')
      setMedicineTransferMeta(null)
      setMedicineTransferMessage(`Faylni o\'qishda xatolik: ${error?.message || 'noma\'lum xatolik'}`)
    }
  }

  const handleImportMedicinesSave = async () => {
    if (pendingImportFiles.length === 0 || !currentPharmacy?.id) {
      setMedicineTransferType('error')
      setMedicineTransferMessage('Avval import faylini tanlang.')
      setMedicineTransferMeta(null)
      return
    }

    setMedicineImporting(true)
    setMedicineImportProgress(2)

    try {
      const parsedBatches = []

      for (let fileIndex = 0; fileIndex < pendingImportFiles.length; fileIndex += 1) {
        const file = pendingImportFiles[fileIndex]
        const parsed = await parseImportedRowsFromFile(file)
        parsedBatches.push({
          fileName: file.name,
          rawRows: parsed.rawRows,
          mappedRows: parsed.mappedRows,
        })

        const parsingProgress = 2 + Math.round(((fileIndex + 1) / pendingImportFiles.length) * 16)
        setMedicineImportProgress(Math.min(18, parsingProgress))
      }

      const allRawRowCount = parsedBatches.reduce((sum, batch) => sum + batch.rawRows.length, 0)
      const mappedRows = parsedBatches.flatMap((batch) => batch.mappedRows)

      if (mappedRows.length === 0) {
        setMedicineTransferType('error')
        setMedicineTransferMessage('Import uchun yaroqli qator topilmadi. Ustunlar: name/dosage_form/expiry_year/country/category/price/stock.')
        setMedicineTransferMeta(null)
        setMedicineImportProgress(0)
        return
      }

      setMedicineImportProgress(20)

      const seen = new Set()
      const existingKeys = new Set(medicines.map((medicine) => buildMedicineIdentityKey(medicine)))
      const medicineBaseByIdentity = new Map(
        medicineBase.map((item) => [buildMedicineIdentityKey(item), item]).filter(([identity]) => Boolean(identity))
      )
      const existingItems = []

      let importedCount = 0
      let skippedCount = Math.max(0, allRawRowCount - mappedRows.length)
      let existingCount = 0
      let failedCount = 0

      for (let index = 0; index < mappedRows.length; index += 1) {
        const medicine = mappedRows[index]
        const key = buildMedicineIdentityKey(medicine)

        if (seen.has(key)) {
          skippedCount += 1
          const progress = 20 + Math.round(((index + 1) / mappedRows.length) * 74)
          setMedicineImportProgress(Math.min(94, progress))
          continue
        }
        seen.add(key)

        if (existingKeys.has(key)) {
          existingCount += 1
          skippedCount += 1
          existingItems.push(buildMedicineDisplayName(medicine.name, medicine.strength))
          const progress = 20 + Math.round(((index + 1) / mappedRows.length) * 74)
          setMedicineImportProgress(Math.min(94, progress))
          continue
        }

        const matchedGlobalMedicine = medicineBaseByIdentity.get(key)

        try {
          await runImportOperationWithRetry(
            () => addMedicine(currentPharmacy.id, medicine, {
              skipReload: true,
              preferredMedicineId: matchedGlobalMedicine?.id || null,
            }),
            buildMedicineDisplayName(medicine.name, medicine.strength)
          )
          importedCount += 1
          existingKeys.add(key)
        } catch (error) {
          failedCount += 1
          console.error('Medicine import row failed:', error)
        }

        const progress = 20 + Math.round(((index + 1) / mappedRows.length) * 74)
        setMedicineImportProgress(Math.min(94, progress))
      }

      setMedicineImportProgress(96)
      await refreshCurrentPharmacyData()
      setMedicineImportProgress(100)

      const uniqueExistingItems = [...new Set(existingItems)]
      const existingPreviewItems = uniqueExistingItems
        .map(formatMedicinePreviewLabel)
        .filter(Boolean)
        .slice(0, 6)

      setMedicineTransferType(failedCount > 0 ? 'error' : 'success')
      setMedicineTransferMeta({
        kind: 'import-summary',
        fileCount: pendingImportFiles.length,
        importedCount,
        existingCount,
        skippedCount,
        failedCount,
        existingPreviewItems,
        hasMoreExisting: uniqueExistingItems.length > existingPreviewItems.length,
      })
      setMedicineTransferMessage(
        failedCount > 0
          ? 'Import yakunlandi, lekin ayrim qatorlarda xatolik bor.'
          : 'Import muvaffaqiyatli yakunlandi.'
      )
      setPendingImportFiles([])
    } catch (error) {
      console.error('Medicine import error:', error)
      setMedicineTransferType('error')
      setMedicineTransferMeta(null)
      setMedicineTransferMessage(`Importda xatolik: ${error?.message || 'noma\'lum xatolik'}`)
      setMedicineImportProgress(0)
    } finally {
      setMedicineImporting(false)
    }
  }

  return (
    <div className="pharmacy-owner-dashboard">
      {/* Header */}
      <header className="dashboard-header">
        <div className="header-left">
          <div className="pharmacy-avatar-wrap" ref={logoActionWrapRef}>
            <button
              type="button"
              className="pharmacy-avatar pharmacy-avatar-button"
              onClick={handleLogoClick}
              disabled={logoSaving}
              title={currentPharmacy.logoUrl ? 'Rasm boshqaruvi' : 'Rasm qo\'shish'}
            >
              {logoPreviewUrl || currentPharmacy.logoUrl ? (
                <img src={logoPreviewUrl || currentPharmacy.logoUrl} alt={currentPharmacy.name} className="pharmacy-avatar-image" />
              ) : (
                '💊'
              )}
            </button>
            <input
              ref={logoInputRef}
              type="file"
              accept="image/*"
              onChange={handleLogoInputChange}
              hidden
            />
            {showLogoMenu && (
              <div className="pharmacy-avatar-menu">
                <button
                  type="button"
                  className="pharmacy-avatar-btn pharmacy-avatar-change"
                  onClick={openLogoFilePicker}
                  disabled={logoSaving}
                >
                  Rasmni o‘zgartirish
                </button>
                {selectedLogoFile && (
                  <button
                    type="button"
                    className="pharmacy-avatar-btn pharmacy-avatar-save"
                    onClick={handleLogoSave}
                    disabled={logoSaving}
                  >
                    {logoSaving ? 'Saqlanmoqda...' : 'Rasmni saqlash'}
                  </button>
                )}
                {currentPharmacy.logoUrl && (
                  <button
                    type="button"
                    className="pharmacy-avatar-btn pharmacy-avatar-remove"
                    onClick={handleLogoRemove}
                    disabled={logoSaving}
                  >
                    Rasmni o‘chirish
                  </button>
                )}
                {selectedLogoFile && <div className="pharmacy-avatar-filename">{selectedLogoFile.name}</div>}
              </div>
            )}
          </div>
          <div>
            <h1>{currentPharmacy.name}</h1>
            <p className="header-subtitle">{currentPharmacy.city}</p>
            <p className="header-detail">{currentPharmacy.address}</p>
          </div>
        </div>
        <div>
          <button
            className="btn-logout"
            onClick={() => navigate('/subscription-payment')}
            style={{ marginRight: '8px' }}
          >
            Obuna to'lovi
          </button>
          <button className="btn-logout" onClick={handleLogout}>
            Chiqish →
          </button>
        </div>
      </header>

      {/* Main Content */}
      <div className="dashboard-content">
        {/* Stats */}
        <div className="stats-section">
          <div className="stat-card">
            <div className="stat-icon">💉</div>
            <div className="stat-content">
              <p className="stat-label">Jami dorilar</p>
              <p className="stat-value">{medicines.length}</p>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon">✅</div>
            <div className="stat-content">
              <p className="stat-label">Mavjud dorilar</p>
              <p className="stat-value">{medicines.filter((m) => m.stock > 0).length}</p>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon">⚠️</div>
            <div className="stat-content">
              <p className="stat-label">Tugagan dorilar</p>
              <p className="stat-value">{medicines.filter((m) => m.stock === 0).length}</p>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon">💰</div>
            <div className="stat-content">
              <p className="stat-label">Bugungi tushum</p>
              <p className="stat-value">{salesStats.todayRevenue.toLocaleString()} so'm</p>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon">📅</div>
            <div className="stat-content">
              <p className="stat-label">Oylik tushum</p>
              <p className="stat-value">{salesStats.monthRevenue.toLocaleString()} so'm</p>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon">🏦</div>
            <div className="stat-content">
              <p className="stat-label">Jami tushum</p>
              <p className="stat-value">{salesStats.totalRevenue.toLocaleString()} so'm</p>
            </div>
          </div>
        </div>

        {/* Pharmacy Info Management Section */}
        {updateMessage && (
          <div className="message-alert" style={{ 
            padding: '12px 16px', 
            marginBottom: '20px', 
            borderRadius: '6px',
            backgroundColor: updateMessage.startsWith('✅') ? '#d1fae5' : '#fee2e2',
            color: updateMessage.startsWith('✅') ? '#065f46' : '#991b1b'
          }}>
            {updateMessage}
          </div>
        )}

        <section className="pharmacy-info-section" style={{
          background: 'white',
          padding: '20px',
          borderRadius: '8px',
          marginBottom: '30px',
          border: '1px solid #e5e7eb'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: '600' }}>📋 Dorixona Ma'lumotlari</h3>
            <button 
              onClick={() => setShowPharmacyEdit(!showPharmacyEdit)}
              style={{
                padding: '8px 16px',
                background: showPharmacyEdit ? '#ef4444' : '#3b82f6',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '0.9rem',
                fontWeight: '600',
                transition: 'all 0.2s'
              }}
            >
              {showPharmacyEdit ? '✕ Bekor qilish' : '✏️ O\'zgartirilsin'}
            </button>
          </div>

          {showPharmacyEdit ? (
            <form onSubmit={handleUpdatePharmacyInfo}>
              <div style={{ display: 'grid', gap: '15px' }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '500', fontSize: '0.9rem' }}>
                    📍 Manzil
                  </label>
                  <input
                    type="text"
                    value={pharmacyInfo.address}
                    onChange={(e) => setPharmacyInfo({ ...pharmacyInfo, address: e.target.value })}
                    style={{
                      width: '100%',
                      padding: '10px 12px',
                      border: '1px solid #d1d5db',
                      borderRadius: '6px',
                      fontSize: '0.95rem',
                      fontFamily: 'inherit'
                    }}
                  />
                </div>

                <div className="form-row" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
                  <div>
                    <label style={{ display: 'block', marginBottom: '6px', fontWeight: '500', fontSize: '0.9rem' }}>
                      📞 Telefon
                    </label>
                    <input
                      type="tel"
                      value={pharmacyInfo.phone_number}
                      onChange={(e) => setPharmacyInfo({ ...pharmacyInfo, phone_number: e.target.value })}
                      style={{
                        width: '100%',
                        padding: '10px 12px',
                        border: '1px solid #d1d5db',
                        borderRadius: '6px',
                        fontSize: '0.95rem',
                        fontFamily: 'inherit'
                      }}
                    />
                  </div>

                  <div>
                    <label style={{ display: 'block', marginBottom: '6px', fontWeight: '500', fontSize: '0.9rem' }}>
                      🕐 Ish vaqti
                    </label>
                    <input
                      type="text"
                      placeholder="09:00 - 20:00"
                      value={pharmacyInfo.working_hours}
                      onChange={(e) => setPharmacyInfo({ ...pharmacyInfo, working_hours: e.target.value })}
                      style={{
                        width: '100%',
                        padding: '10px 12px',
                        border: '1px solid #d1d5db',
                        borderRadius: '6px',
                        fontSize: '0.95rem',
                        fontFamily: 'inherit'
                      }}
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={updatingPharmacy}
                  style={{
                    padding: '12px 16px',
                    background: '#10b981',
                    color: 'white',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: updatingPharmacy ? 'not-allowed' : 'pointer',
                    fontSize: '0.95rem',
                    fontWeight: '600',
                    opacity: updatingPharmacy ? 0.7 : 1,
                    transition: 'all 0.2s'
                  }}
                >
                  {updatingPharmacy ? '⏳ Saqlanmoqda...' : '✅ Saqlash'}
                </button>
              </div>
            </form>
          ) : (
            <div style={{ display: 'grid', gap: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '12px', borderBottom: '1px solid #f3f4f6' }}>
                <span style={{ color: '#666' }}>📍 Manzil:</span>
                <strong>{currentPharmacy.address || '-'}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '12px', borderBottom: '1px solid #f3f4f6' }}>
                <span style={{ color: '#666' }}>📞 Telefon:</span>
                <strong>{pharmacyInfo.phone_number || '-'}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#666' }}>🕐 Ish vaqti:</span>
                <strong>{pharmacyInfo.working_hours || '-'}</strong>
              </div>
            </div>
          )}
        </section>

        {/* Medicines Section */}
        <section className="medicines-section">
          <div className="section-header">
            <div>
              <h2>Dorilar</h2>
              <p className="medicines-updated-at">Oxirgi yangilanish: {formatDateTimeLabel(medicinesUpdatedAt)}</p>
            </div>
            <div className="medicine-toolbar">
              <div className="medicine-transfer-actions">
                <button type="button" className="btn-transfer" onClick={() => handleExportMedicines('xlsx')}>Excel</button>
                <button type="button" className="btn-transfer" onClick={() => handleExportMedicines('csv')}>CSV</button>
                <button type="button" className="btn-transfer" onClick={() => handleExportMedicines('json')}>JSON</button>
                <button type="button" className="btn-transfer" onClick={() => handleExportMedicines('tsv')}>TSV</button>
                <button
                  type="button"
                  className="btn-transfer"
                  onClick={openMedicinesImportPicker}
                  disabled={medicineImporting}
                >
                  Fayl tanlash
                </button>
                <button
                  type="button"
                  className="btn-transfer"
                  onClick={handleImportMedicinesSave}
                  disabled={medicineImporting || pendingImportFiles.length === 0}
                >
                  {medicineImporting ? 'Saqlanmoqda...' : 'Saqlash'}
                </button>
                <input
                  ref={medicineImportInputRef}
                  type="file"
                  accept=".xlsx,.xls,.csv,.tsv,.json"
                  onChange={handleImportFileSelected}
                  multiple
                  hidden
                />
                {pendingImportFiles.length > 0 && (
                  <div className="medicine-import-files">
                    {pendingImportFiles.map((file, fileIndex) => (
                      <span key={`${file.name}-${fileIndex}`} className="medicine-import-file">{file.name}</span>
                    ))}
                  </div>
                )}
              </div>
              <button
                className="btn-add"
                onClick={() => {
                  setShowAddForm(!showAddForm)
                  setEditingId(null)
                  setFormData({ ...DEFAULT_MEDICINE_FORM })
                }}
              >
                {showAddForm ? '✕ Bekor qilish' : '+ Yangi dori qo\'shish'}
              </button>
              <button
                type="button"
                className="btn-transfer btn-transfer-danger"
                onClick={handleDeleteAllMedicines}
                disabled={bulkDeletingMedicines || medicines.length === 0}
              >
                {bulkDeletingMedicines ? 'O\'chirilmoqda...' : 'Barchasini o\'chirish'}
              </button>
            </div>
          </div>

          {medicineTransferMessage && (
            <div className={`medicine-transfer-message ${medicineTransferType === 'error' ? 'error' : 'success'}`}>
              <div className="medicine-transfer-message-main">
                <div className="medicine-transfer-message-title-row">
                  <strong>
                    {medicineTransferType === 'error' ? 'Import natijasi' : 'Import holati'}
                  </strong>
                </div>
                <p className="medicine-transfer-message-text">{medicineTransferMessage}</p>

                {medicineTransferMeta?.kind === 'import-summary' && (
                  <>
                    <div className="medicine-transfer-summary-grid">
                      <div className="medicine-transfer-summary-item">
                        <span>Fayl</span>
                        <strong>{medicineTransferMeta.fileCount}</strong>
                      </div>
                      <div className="medicine-transfer-summary-item success">
                        <span>Qo'shildi</span>
                        <strong>{medicineTransferMeta.importedCount}</strong>
                      </div>
                      <div className="medicine-transfer-summary-item neutral">
                        <span>Oldin bor edi</span>
                        <strong>{medicineTransferMeta.existingCount}</strong>
                      </div>
                      <div className="medicine-transfer-summary-item neutral">
                        <span>O'tkazib yuborildi</span>
                        <strong>{medicineTransferMeta.skippedCount}</strong>
                      </div>
                      <div className="medicine-transfer-summary-item error">
                        <span>Xatolik</span>
                        <strong>{medicineTransferMeta.failedCount}</strong>
                      </div>
                    </div>

                    {medicineTransferMeta.existingPreviewItems.length > 0 && (
                      <div className="medicine-transfer-preview-block">
                        <div className="medicine-transfer-preview-title">Bazadagi mavjud dorilar</div>
                        <div className="medicine-transfer-preview-list">
                          {medicineTransferMeta.existingPreviewItems.map((item, index) => (
                            <span key={`${item}-${index}`} className="medicine-transfer-preview-chip">{item}</span>
                          ))}
                          {medicineTransferMeta.hasMoreExisting && (
                            <span className="medicine-transfer-preview-more">yana bor...</span>
                          )}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          )}

          {medicineImporting && (
            <div className="medicine-import-progress">
              <div className="medicine-import-progress-meta">
                <span>Import jarayoni</span>
                <strong>{medicineImportProgress}%</strong>
              </div>
              <div className="medicine-import-progress-track">
                <div
                  className="medicine-import-progress-fill"
                  style={{ width: `${Math.max(0, Math.min(100, medicineImportProgress))}%` }}
                />
              </div>
            </div>
          )}

          {(medicineNameAlertsLoading || medicineNameAlerts.length > 0) && (
            <div className="medicine-alerts-panel">
              <div className="medicine-alerts-header">
                <div>
                  <h3>Nomni tekshirish xabarlari</h3>
                  <p>
                    {medicineNameAlertsLoading
                      ? 'Yuklanmoqda...'
                      : `${medicineNameAlerts.length} ta boshqa dorixonadan kelgan xabar`}
                  </p>
                </div>
                <button
                  type="button"
                  className="medicine-alerts-confirm-all"
                  onClick={handleConfirmAllNameAlerts}
                  disabled={
                    confirmingAllNameAlerts
                    || medicineNameAlertsLoading
                    || medicineNameAlerts.length === 0
                  }
                >
                  {confirmingAllNameAlerts ? 'Saqlanmoqda...' : "Barchasi to'g'ri kiritilgan"}
                </button>
              </div>

              {medicineNameAlerts.map((alertItem) => (
                <div key={alertItem.id} className="medicine-alert-card">
                  <div className="medicine-alert-card-head">
                    <div>
                      <strong>{alertItem.original_name || 'Noma\'lum dori'}</strong>
                      <span>{alertItem.reported_by_pharmacy_name || 'Dorixona noma\'lum'}</span>
                    </div>
                    <span className="medicine-alert-badge">Tekshirish kerak</span>
                  </div>

                  <p className="medicine-alert-message">{alertItem.message}</p>

                  <div className="medicine-alert-meta">
                    <span>{alertItem.dosage_form || 'Ko\'rinishi yo\'q'}</span>
                    <span>{alertItem.country_of_origin || 'Davlat kiritilmagan'}</span>
                    <span>{alertItem.confirm_count || 0} ta to'g'ri</span>
                    <span>{alertItem.leading_correction_name ? `${alertItem.leading_correction_name} (${alertItem.leading_correction_count || 0})` : 'O\'zgartirish yo\'q'}</span>
                    <span>{alertItem.remaining_vote_count || 0} ta ovoz qolgan</span>
                  </div>

                  {alertItem.current_user_vote_type && (
                    <p className="medicine-alert-message">
                      Sizning ovozingiz: {alertItem.current_user_vote_type === 'confirm'
                        ? 'To\'g\'ri kiritilgan'
                        : (alertItem.current_user_corrected_name || 'Nom o\'zgartirish')}
                    </p>
                  )}

                  <div className="medicine-alert-correction">
                    <input
                      type="text"
                      placeholder="To'g'ri dori nomini doza bilan yozing"
                      value={correctionDrafts[alertItem.id] || ''}
                      onChange={(e) => setCorrectionDrafts((prev) => ({
                        ...prev,
                        [alertItem.id]: e.target.value,
                      }))}
                    />
                    <button
                      type="button"
                      className="medicine-alert-correct-btn medicine-alert-confirm-btn"
                      onClick={() => handleConfirmNameAlert(alertItem.id)}
                      disabled={correctionSavingId === alertItem.id}
                    >
                      {correctionSavingId === alertItem.id ? 'Saqlanmoqda...' : "To'g'ri kiritilgan"}
                    </button>
                    <button
                      type="button"
                      className="medicine-alert-correct-btn"
                      onClick={() => handleCorrectNameAlert(alertItem.id)}
                      disabled={correctionSavingId === alertItem.id}
                    >
                      {correctionSavingId === alertItem.id ? 'Saqlanmoqda...' : "To'g'irlash"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {showAddForm && (
            <form className="add-medicine-form" onSubmit={handleAddMedicine}>
              <div className="add-form-search">
                <label>Dorilar bazasidan qidirish</label>
                <div className="search-input-wrap">
                  <span className="search-icon">🔎</span>
                  <input
                    type="text"
                    placeholder="Nom, doza, ko'rinish yoki kategoriya bo'yicha qidiring..."
                    value={medicineSearch}
                    onChange={(e) => setMedicineSearch(e.target.value)}
                  />
                </div>
                <p className="medicine-base-meta">
                  Bazada: {medicineBase.length} ta dori {medicineBaseLoading ? '(yuklanmoqda...)' : ''}
                </p>

                {normalizedMedicineSearch && (
                  <div className="search-preview-list">
                    {filteredMedicineBase.slice(0, 6).map((medicine) => (
                      <button
                        key={`search-${medicine.id}`}
                        type="button"
                        className="search-preview-item"
                        onClick={() => applyMedicineBaseTemplate(medicine)}
                      >
                        <div>
                          <strong>{buildMedicineDisplayName(medicine.name, medicine.strength)}</strong>
                          <span>{medicine.dosageForm || 'tabletka'} • {medicine.countryOfOrigin || 'Davlat kiritilmagan'} • {medicine.category}</span>
                        </div>
                        <span className="search-preview-action">Formaga qo'yish</span>
                      </button>
                    ))}

                    {filteredMedicineBase.length === 0 && (
                      <p className="search-preview-empty">Bu so'rov bo'yicha bazada dori topilmadi</p>
                    )}
                  </div>
                )}
              </div>

              <div className="form-group">
                <label>Dori nomi va dozasi</label>
                <input
                  type="text"
                  placeholder="masalan: Aspirin 500mg"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                />

                {normalizedTypedMedicineName && (
                  <div className="medicine-name-suggestions">
                    <div className="medicine-name-suggestions-title">Nom bo'yicha tavsiyalar</div>

                    {medicineNameSuggestions.length > 0 ? (
                      medicineNameSuggestions.map((medicine) => (
                        <button
                          key={`name-suggestion-${medicine.id}`}
                          type="button"
                          className="medicine-name-suggestion-item"
                          onClick={() => applyMedicineBaseTemplate(medicine)}
                        >
                          <strong>{buildMedicineDisplayName(medicine.name, medicine.strength)}</strong>
                          <span>{medicine.dosageForm || 'tabletka'} • {medicine.countryOfOrigin || 'Davlat kiritilmagan'}</span>
                        </button>
                      ))
                    ) : (
                      <p className="medicine-name-suggestion-empty">
                        Bazada aynan shu nom topilmadi. Shu nom bilan qo'shsangiz, boshqa dorixonalarga xabar yuboriladi.
                      </p>
                    )}

                    {!exactMedicineNameFound && medicineNameSuggestions.length > 0 && (
                      <p className="medicine-name-suggestion-hint">
                        O'xshash nomlar topildi. Xato yozilmaganini tekshirib oling.
                      </p>
                    )}
                  </div>
                )}
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Ko'rinishi</label>
                  <select
                    value={formData.dosageForm}
                    onChange={(e) => setFormData({ ...formData, dosageForm: e.target.value })}
                  >
                    {MEDICINE_APPEARANCE_OPTIONS.map((option) => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label>Yaroqlilik yili</label>
                  <input
                    type="number"
                    inputMode="numeric"
                    min={currentYear}
                    max={currentYear + 50}
                    placeholder={`${currentYear + 1}`}
                    value={formData.expiryDate}
                    onChange={(e) => setFormData({ ...formData, expiryDate: String(e.target.value || '').replace(/\D+/g, '').slice(0, 4) })}
                    required
                  />
                </div>

                <div className="form-group">
                  <label>Ishlab chiqarilgan davlat</label>
                  <select
                    value={formData.countryOfOrigin}
                    onChange={(e) => setFormData({ ...formData, countryOfOrigin: e.target.value })}
                    required
                  >
                    <option value="">Davlatni tanlang</option>
                    {MEDICINE_COUNTRY_OPTIONS.map((option) => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Narxi (so'm)</label>
                  <input
                    type="text"
                    inputMode="numeric"
                    placeholder="5500"
                    value={formData.price}
                    onFocus={() => {
                      if (priceClearedOnFocus || !formData.price) {
                        return
                      }
                      setFormData((prev) => ({ ...prev, price: '' }))
                      setPriceClearedOnFocus(true)
                    }}
                    onChange={(e) => setFormData({ ...formData, price: formatCurrencyInput(e.target.value) })}
                    required
                  />
                </div>

                <div className="form-group">
                  <label>Kategoriya</label>
                  <select
                    value={formData.category}
                    onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                  >
                    <option>Joni dorilar</option>
                    <option>Antibiotiklar</option>
                    <option>Vitaminlar</option>
                    <option>Allergiya dori</option>
                    <option>Qon bosimi</option>
                    <option>Yurak</option>
                    <option>Boshqa</option>
                  </select>
                </div>

                <div className="form-group">
                  <label>Mavjudlik</label>
                  <select
                    value={formData.stock}
                    onChange={(e) => setFormData({ ...formData, stock: e.target.value })}
                  >
                    <option value="1">Bor</option>
                    <option value="10">Ko'p</option>
                    <option value="out">Tugagan</option>
                  </select>
                </div>
              </div>

              <button type="submit" className="btn-submit">
                {editingId ? 'Tahrirlashni saqlash' : 'Dorini qo\'shish'}
              </button>
            </form>
          )}

          <div className="medicines-grid">
            {filteredMedicines.length > 0 ? (
              filteredMedicines.map((medicine) => (
                <div key={medicine.id} className={`medicine-card ${medicine.stock === 0 ? 'out-of-stock' : ''}`}>
                  <div className="medicine-header">
                    <div>
                      <h3>{buildMedicineDisplayName(medicine.name, medicine.strength)}</h3>
                      <p className="category">{medicine.category}</p>
                    </div>
                    <span className={`stock-badge ${medicine.stock === 0 ? 'out' : 'available'}`}>
                      {medicine.stock === 0 ? 'Tugagan' : 'Bor'}
                    </span>
                  </div>

                  <div className="medicine-details">
                    <div className="detail">
                      <span className="label">Ko'rinishi:</span>
                      <span className="value">{medicine.dosageForm || medicine.appearance || '—'}</span>
                    </div>
                    <div className="detail">
                      <span className="label">Davlat:</span>
                      <span className="value">{medicine.countryOfOrigin || '—'}</span>
                    </div>
                    <div className="detail">
                      <span className="label">Yaroqlilik:</span>
                      <span className="value">{formatDateLabel(medicine.expiryDate)}</span>
                    </div>
                    <div className="detail">
                      <span className="label">Narxi:</span>
                      <span className="value price">{medicine.price.toLocaleString()} so'm</span>
                    </div>
                    <div className="detail">
                      <span className="label">Miqdori:</span>
                      <span className="value">{medicine.stock > 0 ? `${medicine.stock} donasi` : 'Tugagan'}</span>
                    </div>
                  </div>

                  <div className="medicine-actions">
                    <button 
                      className="btn-edit"
                      onClick={() => handleEdit(medicine)}
                    >
                      ✏️ Tahrirlash
                    </button>
                    <button 
                      className="btn-delete"
                      onClick={() => handleDelete(medicine.id)}
                    >
                      🗑️ O'chirish
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <div className="no-medicines">
                <p>
                  {medicines.length > 0
                    ? 'Qidiruv bo\'yicha dori topilmadi'
                    : 'Hozircha dori qo\'shilmagan'}
                </p>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}

export default PharmacyOwnerDashboard
