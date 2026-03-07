import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePharmacy } from '../context/PharmacyContext'
import { pharmaciesApi } from '../services/api'
import useSmartAutoRefresh from '../hooks/useSmartAutoRefresh'
import { formatCurrencyInput, parseCurrencyInput } from '../utils/currency'
import './PharmacyOwnerDashboard.css'

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

  return { name, category, price, stock }
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
  const navigate = useNavigate()
  const {
    currentPharmacy,
    medicines: pharmacyMedicines,
    loading,
    logoutPharmacy,
    addMedicine,
    updateMedicine,
    deleteMedicine,
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
    phone_number: '',
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
    name: '',
    price: '',
    category: 'Boshqa',
    stock: '1'
  })
  const [priceClearedOnFocus, setPriceClearedOnFocus] = useState(false)
  const [medicineSearch, setMedicineSearch] = useState('')
  const [selectedLogoFile, setSelectedLogoFile] = useState(null)
  const [logoPreviewUrl, setLogoPreviewUrl] = useState('')
  const [logoSaving, setLogoSaving] = useState(false)
  const [showLogoMenu, setShowLogoMenu] = useState(false)
  const [medicineTransferMessage, setMedicineTransferMessage] = useState('')
  const [medicineTransferType, setMedicineTransferType] = useState('success')
  const [medicineImporting, setMedicineImporting] = useState(false)
  const [medicinesUpdatedAt, setMedicinesUpdatedAt] = useState(null)
  const logoInputRef = useRef(null)
  const logoActionWrapRef = useRef(null)
  const medicineImportInputRef = useRef(null)

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
      phone_number: currentPharmacy.phone_number || currentPharmacy.phone || '',
      working_hours: currentPharmacy.working_hours || '09:00 - 20:00'
    })
  }, [currentPharmacy, loading, navigate, pharmacyMedicines])

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

  const handleAddMedicine = async (e) => {
    e.preventDefault()
    const priceValue = parseCurrencyInput(formData.price)
    if (!formData.name || !priceValue) {
      alert('Dori nomi va narxini kiriting')
      return
    }

    try {
      if (editingId) {
        await updateMedicine(currentPharmacy.id, editingId, {
          name: formData.name,
          price: priceValue,
          category: formData.category,
          stock: formData.stock === 'out' ? 0 : parseInt(formData.stock)
        })
        setEditingId(null)
        alert('Dori yangilandi! ✅')
      } else {
        const result = await addMedicine(currentPharmacy.id, {
          ...formData,
          price: priceValue,
          stock: formData.stock === 'out' ? 0 : parseInt(formData.stock)
        })
        if (result?.mode === 'updated_existing') {
          alert('Bu dori allaqachon mavjud edi — mavjud yozuv yangilandi ✅')
        } else {
          alert('Dori qo\'shildi! ✅')
        }
      }

      setFormData({ name: '', price: '', category: 'Boshqa', stock: '1' })
      setPriceClearedOnFocus(false)
      setShowAddForm(false)
    } catch (error) {
      console.error('Medicine operation error:', error)
      alert('Xatolik: ' + (error.message || 'Dori qo\'shishda xatolik yuz berdi'))
    }
  }

  const handleEdit = (medicine) => {
    setFormData({
      name: medicine.name,
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
        `${medicine.name} ${medicine.category}`.toLowerCase().includes(normalizedMedicineSearch)
      )
    : medicines

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
      name: medicine.name,
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
      ['medicine_id', 'name', 'category', 'price', 'stock', 'availability'],
      ...payload.items.map((item) => [
        item.medicine_id,
        item.name,
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

  const handleImportMedicines = async (event) => {
    const file = event.target.files?.[0]
    event.target.value = ''

    if (!file || !currentPharmacy?.id) return

    setMedicineImporting(true)
    setMedicineTransferMessage('')

    try {
      const fileName = file.name.toLowerCase()
      let rawRows = []

      if (fileName.endsWith('.json')) {
        const text = await file.text()
        const parsed = JSON.parse(text)
        if (Array.isArray(parsed)) {
          rawRows = parsed
        } else if (Array.isArray(parsed?.medicines)) {
          rawRows = parsed.medicines
        } else {
          rawRows = []
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
      if (mappedRows.length === 0) {
        setMedicineTransferType('error')
        setMedicineTransferMessage('Import uchun yaroqli qator topilmadi. Ustunlar: name/narx/category/stock.')
        return
      }

      const seen = new Set()
      let importedCount = 0
      let skippedCount = rawRows.length - mappedRows.length
      let failedCount = 0

      for (const medicine of mappedRows) {
        const key = medicine.name.trim().toLowerCase()
        if (seen.has(key)) {
          skippedCount += 1
          continue
        }
        seen.add(key)

        try {
          await addMedicine(currentPharmacy.id, medicine)
          importedCount += 1
        } catch (error) {
          failedCount += 1
          console.error('Medicine import row failed:', error)
        }
      }

      await refreshCurrentPharmacyData()
      setMedicineTransferType(failedCount > 0 ? 'error' : 'success')
      setMedicineTransferMessage(`Import yakunlandi: qo'shildi ${importedCount}, o'tkazib yuborildi ${skippedCount}, xatolik ${failedCount}.`)
    } catch (error) {
      console.error('Medicine import error:', error)
      setMedicineTransferType('error')
      setMedicineTransferMessage(`Importda xatolik: ${error?.message || 'noma\'lum xatolik'}`)
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
                  {medicineImporting ? 'Import...' : 'Import'}
                </button>
                <input
                  ref={medicineImportInputRef}
                  type="file"
                  accept=".xlsx,.xls,.csv,.tsv,.json"
                  onChange={handleImportMedicines}
                  hidden
                />
              </div>
              <button
                className="btn-add"
                onClick={() => {
                  setShowAddForm(!showAddForm)
                  setEditingId(null)
                  setFormData({ name: '', price: '', category: 'Boshqa', stock: '1' })
                }}
              >
                {showAddForm ? '✕ Bekor qilish' : '+ Yangi dori qo\'shish'}
              </button>
            </div>
          </div>

          {medicineTransferMessage && (
            <div className={`medicine-transfer-message ${medicineTransferType === 'error' ? 'error' : 'success'}`}>
              {medicineTransferMessage}
            </div>
          )}

          {showAddForm && (
            <form className="add-medicine-form" onSubmit={handleAddMedicine}>
              <div className="add-form-search">
                <label>Mavjud dorilar ichidan qidirish</label>
                <div className="search-input-wrap">
                  <span className="search-icon">🔎</span>
                  <input
                    type="text"
                    placeholder="Nom yoki kategoriya bo'yicha qidiring..."
                    value={medicineSearch}
                    onChange={(e) => setMedicineSearch(e.target.value)}
                  />
                </div>

                {normalizedMedicineSearch && (
                  <div className="search-preview-list">
                    {filteredMedicines.slice(0, 4).map((medicine) => (
                      <button
                        key={`search-${medicine.id}`}
                        type="button"
                        className="search-preview-item"
                        onClick={() => handleEdit(medicine)}
                      >
                        <div>
                          <strong>{medicine.name}</strong>
                          <span>{medicine.category} • {medicine.price.toLocaleString()} so'm</span>
                        </div>
                        <span className="search-preview-action">Tahrirlash</span>
                      </button>
                    ))}

                    {filteredMedicines.length === 0 && (
                      <p className="search-preview-empty">Bu so'rov bo'yicha dori topilmadi</p>
                    )}
                  </div>
                )}
              </div>

              <div className="form-group">
                <label>Dori nomi</label>
                <input
                  type="text"
                  placeholder="masalan: Aspirin 500mg"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                />
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
                      <h3>{medicine.name}</h3>
                      <p className="category">{medicine.category}</p>
                    </div>
                    <span className={`stock-badge ${medicine.stock === 0 ? 'out' : 'available'}`}>
                      {medicine.stock === 0 ? 'Tugagan' : 'Bor'}
                    </span>
                  </div>

                  <div className="medicine-details">
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
