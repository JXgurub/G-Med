import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePharmacy } from '../context/PharmacyContext'
import { pharmacyPosApi } from '../services/api'
import {
  getActivatedPosDevice,
  getOrCreatePosClientId,
  getPendingOfflineSales,
  getPosSnapshot,
  markOfflineSaleSynced,
  rotatePosClientId,
  saveActivatedPosDevice,
  saveOfflineSale,
  savePosSnapshot,
} from '../services/pharmacyPosStore'
import './PharmacyPos.css'

const formatMoney = (value) => `${Number(value || 0).toLocaleString('uz-UZ')} so‘m`

const normalizeProduct = (item) => ({
  ...item,
  name: item.medicine_name || item.name || 'Noma’lum dori',
  strength: item.medicine_strength || item.strength || '',
  dosageForm: item.medicine_dosage_form || item.dosage_form || '',
  category: item.medicine_category || item.category || '',
  country: item.medicine_country_of_origin || item.country_of_origin || '',
  quantity: Number(item.quantity_in_stock ?? item.stock ?? 0),
  price: Number(item.unit_price ?? item.price ?? 0),
})

const PharmacyPos = ({
  embedded = false,
  onExit,
  showSales = true,
  showDeviceManagement = true,
  showHeader = true,
  onStatusChange,
  pharmacyInfo,
  showPharmacyEdit,
  setShowPharmacyEdit,
  updatingPharmacy,
  updateMessage,
  onPharmacyInfoChange,
  onUpdatePharmacyInfo,
}) => {
  const navigate = useNavigate()
  const { currentPharmacy, loading } = usePharmacy()
  const [online, setOnline] = useState(() => typeof navigator === 'undefined' || navigator.onLine)
  const [products, setProducts] = useState([])
  const [snapshotAt, setSnapshotAt] = useState('')
  const [device, setDevice] = useState(null)
  const [printerDevice, setPrinterDevice] = useState(null)
  const [printerInstallHelpOpen, setPrinterInstallHelpOpen] = useState(false)
  const [clientId, setClientId] = useState('')
  const [devices, setDevices] = useState([])
  const [basket, setBasket] = useState({})
  const [search, setSearch] = useState('')
  const [activationCode, setActivationCode] = useState('')
  const [computerName, setComputerName] = useState('')
  const [newDeviceName, setNewDeviceName] = useState('')
  const [generatedCode, setGeneratedCode] = useState('')
  const [generatedCodeExpiresAt, setGeneratedCodeExpiresAt] = useState('')
  const [generatedDeviceName, setGeneratedDeviceName] = useState('')
  const [pendingCount, setPendingCount] = useState(0)
  const [lastSale, setLastSale] = useState(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [messageType, setMessageType] = useState('info')
  const syncingRef = useRef(false)

  const showMessage = (text, type = 'info') => {
    setMessage(text)
    setMessageType(type)
  }

  useEffect(() => {
    onStatusChange?.({
      deviceName: device?.name || 'Boshqaruv kompyuteri',
      printerReady: Boolean(printerDevice?.printer_ready),
      printerName: printerDevice?.printer_name || printerDevice?.device_name || '',
    })
  }, [device?.name, onStatusChange, printerDevice])

  const loadDeviceList = useCallback(async () => {
    if (!online) return
    try {
      setDevices(await pharmacyPosApi.getDevices())
    } catch (error) {
      console.error('[Pharmacy POS] Kassir kompyuterlarini yuklab bo‘lmadi:', error)
    }
  }, [online])

  const loadPrinterStatus = useCallback(async () => {
    if (!online || !clientId) {
      setPrinterDevice(null)
      return null
    }
    try {
      const result = await pharmacyPosApi.getPrinter(clientId)
      const printer = result?.device || null
      setPrinterDevice(printer)
      return printer
    } catch (error) {
      console.error('[Pharmacy POS] Printer holatini tekshirib bo‘lmadi:', error)
      setPrinterDevice(null)
      return null
    }
  }, [clientId, online])

  const refreshLocalData = useCallback(async (forceRefresh = false) => {
    if (!currentPharmacy?.id) return
    const cached = await getPosSnapshot(currentPharmacy.id)
    if (cached) {
      setProducts((cached.inventory || []).filter((item) => item.is_available !== false).map(normalizeProduct))
      setSnapshotAt(cached.snapshot_at || '')
    }
    if (!online) return
    const cacheIsRecent = cached?.snapshot_at
      && Date.now() - new Date(cached.snapshot_at).getTime() < 10 * 60 * 1000
    if (cacheIsRecent && !forceRefresh) return

    try {
      const snapshot = await pharmacyPosApi.getSnapshot()
      await savePosSnapshot(snapshot)
      setProducts(snapshot.inventory.filter((item) => item.is_available !== false).map(normalizeProduct))
      setSnapshotAt(snapshot.snapshot_at || '')
    } catch (error) {
      console.error('[Pharmacy POS] Server nusxasini yangilab bo‘lmadi:', error)
      if (!cached) {
        showMessage('Internet yo‘q va ushbu kompyuterda saqlangan dori bazasi topilmadi.', 'error')
      }
    }
  }, [currentPharmacy?.id, online])

  const syncPendingSales = useCallback(async () => {
    if (!online || !currentPharmacy?.id || !device?.is_active || syncingRef.current) return
    syncingRef.current = true
    try {
      const pending = await getPendingOfflineSales(currentPharmacy.id)
      setPendingCount(pending.length)
      let discrepancyCount = 0

      for (const sale of pending) {
        const result = await pharmacyPosApi.syncSale(sale)
        await markOfflineSaleSynced(sale.id, result.has_stock_discrepancy)
        if (result.has_stock_discrepancy) discrepancyCount += 1
      }

      const remaining = await getPendingOfflineSales(currentPharmacy.id)
      setPendingCount(remaining.length)
      if (pending.length > 0 && remaining.length === 0) {
        showMessage(
          discrepancyCount > 0
            ? `${pending.length} ta sotuv sinxronlandi. ${discrepancyCount} tasida qoldiq tafovuti bor — egasi bilan tekshiring.`
            : `${pending.length} ta offline sotuv serverga sinxronlandi.`,
          discrepancyCount > 0 ? 'warning' : 'success',
        )
        if (discrepancyCount > 0) {
          await refreshLocalData(true)
        }
      }
    } catch (error) {
      console.error('[Pharmacy POS] Sotuvlarni sinxronlab bo‘lmadi:', error)
      showMessage(`Sotuv serverga yuborilmadi, lokal navbatda saqlandi: ${error.message}`, 'warning')
    } finally {
      syncingRef.current = false
    }
  }, [currentPharmacy?.id, device?.is_active, online, refreshLocalData])

  useEffect(() => {
    const setNetworkStatus = () => setOnline(navigator.onLine)
    window.addEventListener('online', setNetworkStatus)
    window.addEventListener('offline', setNetworkStatus)
    return () => {
      window.removeEventListener('online', setNetworkStatus)
      window.removeEventListener('offline', setNetworkStatus)
    }
  }, [])

  useEffect(() => {
    if (!currentPharmacy?.id) return
    let cancelled = false
    const load = async () => {
      try {
        const [cachedDevice, pending] = await Promise.all([
          getActivatedPosDevice(currentPharmacy.id),
          getPendingOfflineSales(currentPharmacy.id),
        ])
        if (cancelled) return
        setDevice(cachedDevice)
        setPendingCount(pending.length)
        setClientId(getOrCreatePosClientId(currentPharmacy.id))
        await refreshLocalData()
        if (cancelled) return
        await loadDeviceList()
      } catch (error) {
        console.error('[Pharmacy POS] Lokal kassani ochib bo‘lmadi:', error)
        if (!cancelled) showMessage(error.message, 'error')
      }
    }
    load()
    return () => { cancelled = true }
  }, [currentPharmacy?.id, refreshLocalData, loadDeviceList])

  useEffect(() => {
    if (currentPharmacy?.subscription?.is_expired || currentPharmacy?.isSubscriptionExpired) {
      navigate('/subscription-blocked', { replace: true })
    }
  }, [currentPharmacy, navigate])

  useEffect(() => {
    if (online) syncPendingSales()
  }, [online, syncPendingSales])

  useEffect(() => {
    loadPrinterStatus()
    const printerInterval = window.setInterval(loadPrinterStatus, 30000)
    return () => window.clearInterval(printerInterval)
  }, [loadPrinterStatus])

  const filteredProducts = useMemo(() => {
    const query = search.trim().toLocaleLowerCase()
    if (!query) return products
    return products.filter((product) => (
      `${product.name} ${product.strength} ${product.dosageForm} ${product.category} ${product.country}`
        .toLocaleLowerCase()
        .includes(query)
    ))
  }, [products, search])

  const basketLines = useMemo(() => Object.values(basket), [basket])
  const total = basketLines.reduce((sum, line) => sum + line.quantity * line.product.price, 0)

  const addToBasket = (product) => {
    setBasket((current) => {
      const line = current[product.id]
      return {
        ...current,
        [product.id]: {
          product,
          quantity: (line?.quantity || 0) + 1,
        },
      }
    })
  }

  const changeQuantity = (productId, adjustment) => {
    setBasket((current) => {
      const line = current[productId]
      if (!line) return current
      const quantity = line.quantity + adjustment
      if (quantity <= 0) {
        const next = { ...current }
        delete next[productId]
        return next
      }
      return { ...current, [productId]: { ...line, quantity } }
    })
  }

  const dispatchReceipt = async (sale) => {
    if (!online) {
      showMessage('Sotuv lokal navbatda saqlandi. Internet qaytgach sinxronlang; chek brauzer oynasi faqat qo‘lda chop etilganda ochiladi.', 'warning')
      return
    }

    try {
      const syncResult = await pharmacyPosApi.syncSale(sale)
      await markOfflineSaleSynced(sale.id, syncResult.has_stock_discrepancy)
      const pending = await getPendingOfflineSales(currentPharmacy.id)
      setPendingCount(pending.length)
    } catch (error) {
      console.error('[Pharmacy POS] Sotuv serverga sinxronlanmadi:', error)
      showMessage(`Sotuv lokal navbatda saqlandi, printerga yuborilmadi: ${error.message}`, 'warning')
      return
    }

    const currentPrinter = await loadPrinterStatus()
    if (!currentPrinter?.printer_ready || !clientId) {
      showMessage('Sotuv serverga saqlandi, lekin Xprinter tayyor emas. Printer xizmati va termal printer ulanishini tekshiring.', 'warning')
      return
    }

    try {
      const printResult = await pharmacyPosApi.printSale(sale.id, clientId)
      if (printResult.status === 'failed') {
        throw new Error('Printer xizmati chekni chop eta olmadi.')
      }
      showMessage('Sotuv saqlandi. Chek Xprinter navbatiga avtomatik yuborildi.', 'success')
    } catch (error) {
      console.error('[Pharmacy POS] Xprinter navbatiga chek yuborilmadi:', error)
      showMessage(`Sotuv serverga saqlandi, ammo Xprinterga chek yuborilmadi: ${error.message}`, 'warning')
    }
  }

  const handleReprintReceipt = () => {
    if (lastSale) window.print()
  }

  const completeSale = async () => {
    if (!basketLines.length || !currentPharmacy?.id) return
    if (!device?.is_active || !clientId) {
      showMessage('Sotuvdan oldin ushbu kompyuterni kassir sifatida ulang.', 'error')
      return
    }
    if (!globalThis.crypto?.randomUUID) {
      showMessage('Sotuv ID yaratish uchun zamonaviy brauzer kerak.', 'error')
      return
    }

    setBusy(true)
    try {
      const sale = {
        id: globalThis.crypto.randomUUID(),
        pharmacy_id: String(currentPharmacy.id),
        client_id: clientId,
        sold_at: new Date().toISOString(),
        total: Number(total.toFixed(2)),
        lines: basketLines.map(({ product, quantity }) => ({
          inventory_id: String(product.id),
          medicine_id: product.medicine ? String(product.medicine) : '',
          medicine_name: `${product.name} ${product.strength}`.trim(),
          quantity,
          cached_stock_before_sale: product.quantity,
          unit_price: Number(product.price.toFixed(2)),
          line_total: Number((product.price * quantity).toFixed(2)),
        })),
      }

      await saveOfflineSale(sale)
      setLastSale(sale)
      setBasket({})
      const pending = await getPendingOfflineSales(currentPharmacy.id)
      setPendingCount(pending.length)
      const cached = await getPosSnapshot(currentPharmacy.id)
      if (cached) setProducts(cached.inventory.filter((item) => item.is_available !== false).map(normalizeProduct))
      showMessage(
        online
          ? 'Sotuv saqlandi. Chekni chop eting; server bilan sinxronlash boshlanadi.'
          : 'Sotuv ushbu kompyuterda xavfsiz saqlandi. Internet qaytgach serverga yuboriladi.',
        online ? 'success' : 'warning',
      )
      await dispatchReceipt(sale)
    } catch (error) {
      console.error('[Pharmacy POS] Sotuvni lokal saqlab bo‘lmadi:', error)
      showMessage(`Sotuv saqlanmadi: ${error.message}`, 'error')
    } finally {
      setBusy(false)
    }
  }

  const activateThisComputer = async (event) => {
    event.preventDefault()
    if (!online) {
      showMessage('Kompyuterni ro‘yxatdan o‘tkazish uchun internetga ulaning.', 'error')
      return
    }
    setBusy(true)
    try {
      const id = clientId || getOrCreatePosClientId(currentPharmacy.id)
      const activated = await pharmacyPosApi.activateDevice({
        activation_code: activationCode.trim(),
        client_id: id,
        name: computerName.trim() || 'Kassir kompyuteri',
      })
      await saveActivatedPosDevice(currentPharmacy.id, activated)
      setClientId(id)
      setDevice(activated)
      setActivationCode('')
      showMessage('Kompyuter kassir sifatida ulandi.', 'success')
      await loadDeviceList()
    } catch (error) {
      console.error('[Pharmacy POS] Kompyuterni faollashtirib bo‘lmadi:', error)
      showMessage(error.message || 'Kompyuterni ulashda xatolik.', 'error')
    } finally {
      setBusy(false)
    }
  }

  const addCashierComputer = async (event) => {
    event.preventDefault()
    if (!online || !newDeviceName.trim()) return
    setBusy(true)
    try {
      const result = await pharmacyPosApi.createDevice(newDeviceName.trim())
      setGeneratedCode(result.activation_code)
      setGeneratedCodeExpiresAt(result.expires_at || '')
      setGeneratedDeviceName(result.name || newDeviceName.trim())
      setNewDeviceName('')
      await loadDeviceList()
      showMessage('Yangi kompyuter uchun ulash kodi yaratildi. Kod bir marta ko‘rsatiladi.', 'success')
    } catch (error) {
      console.error('[Pharmacy POS] Yangi kassir yaratilmadi:', error)
      showMessage(error.message || 'Yangi kassir kompyuterini yaratib bo‘lmadi.', 'error')
    } finally {
      setBusy(false)
    }
  }

  const setupPrinter = async () => {
    setPrinterInstallHelpOpen((isOpen) => !isOpen)
  }

  const deactivateComputer = async (id) => {
    if (!online) return
    const targetDevice = devices.find((item) => item.id === id)
    if (targetDevice?.client_id === clientId && pendingCount > 0) {
      showMessage('Avval ushbu kompyuterdagi sotuvlarni sinxronlang, keyin uni o‘chiring.', 'warning')
      return
    }
    if (!window.confirm('Kompyuter o‘chirilgach, undagi sinxronlanmagan sotuvlar serverga yuborilmaydi. Davom etilsinmi?')) {
      return
    }
    setBusy(true)
    try {
      await pharmacyPosApi.deactivateDevice(id)
      if (targetDevice?.client_id === clientId) {
        setDevice(null)
        await saveActivatedPosDevice(currentPharmacy.id, null)
        setClientId(rotatePosClientId(currentPharmacy.id))
      }
      await loadDeviceList()
      showMessage('Kassir kompyuteri o‘chirildi.', 'success')
    } catch (error) {
      console.error('[Pharmacy POS] Kassirni o‘chirib bo‘lmadi:', error)
      showMessage(error.message || 'Kassirni o‘chirib bo‘lmadi.', 'error')
    } finally {
      setBusy(false)
    }
  }

  const copyGeneratedCode = async () => {
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error('Brauzer clipboard nusxalashni qo‘llamaydi.')
      }
      await navigator.clipboard.writeText(generatedCode)
      showMessage('Ulash kodi nusxalandi.', 'success')
    } catch (error) {
      console.error('[Pharmacy POS] Ulash kodi clipboardga ko‘chirilmadi:', error)
      showMessage('Ulash kodini qo‘lda belgilang va nusxalang.', 'warning')
    }
  }

  if (loading) {
    return <div className="pharmacy-pos-loading">Dorixona ma’lumotlari yuklanmoqda...</div>
  }
  if (!currentPharmacy) {
    return (
      <div className="pharmacy-pos-loading">
        <p>Dorixona akkaunti topilmadi.</p>
        <button type="button" onClick={() => navigate('/pharmacy-owner-login')}>Kirish</button>
      </div>
    )
  }

  return (
    <main className={`pharmacy-pos-page${embedded ? ' pharmacy-pos-page-embedded' : ''}`}>
      <div className="pharmacy-pos-screen">
        {showHeader && <header className="pharmacy-pos-header" id="pharmacy-settings">
          {embedded ? (
            <div className="pharmacy-pos-dashboard-status">
              <strong>Kassa: {device?.name || 'Boshqaruv kompyuteri'}</strong>
              <span className={printerDevice?.printer_ready ? 'pharmacy-pos-printer-ready' : 'pharmacy-pos-printer-offline'}>
                Printer: {printerDevice?.printer_ready ? 'Tayyor' : 'Ulanmagan'}
                {printerDevice?.printer_ready && printerDevice.printer_name
                  ? ` · ${printerDevice.printer_name}`
                  : ''}
              </span>
            </div>
          ) : (
            <>
              <div>
                <p className="pharmacy-pos-kicker">G-MED · DORIXONA SOZLAMALARI</p>
                <h1>{currentPharmacy.name}</h1>
                <p>{device?.name || 'Boshqaruv kompyuteri'}</p>
              </div>
              <div className="pharmacy-pos-header-actions">
                <span className={`pharmacy-pos-network ${online ? 'is-online' : 'is-offline'}`}>
                  {online ? 'Internet bor' : 'Offline rejim'}
                </span>
                <a
                  className="pharmacy-pos-inventory-link"
                  href="#pharmacy-medicine-inventory"
                  onClick={(event) => {
                    event.preventDefault()
                    document.getElementById('pharmacy-medicine-inventory')?.scrollIntoView({
                      block: 'start',
                    })
                  }}
                >
                  Dori ombori
                </a>
                <button type="button" onClick={onExit || (() => navigate('/pharmacy-owner-dashboard/pos'))}>
                  Bosh sahifaga qaytish
                </button>
              </div>
            </>
          )}
        </header>}

        {message && <div className={`pharmacy-pos-message ${messageType}`}>{message}</div>}

        <section className="pharmacy-pos-sync-strip">
          <span>{pendingCount ? `${pendingCount} ta sotuv sinxronlash navbatida` : 'Sotuv navbati bo‘sh'}</span>
          <span>{snapshotAt ? `Ma’lumot yangilangan: ${new Date(snapshotAt).toLocaleString()}` : 'Dori bazasi yuklanmoqda...'}</span>
          {online && <button type="button" onClick={() => refreshLocalData(true)} disabled={busy}>Dorilar va qoldiqni yangilash</button>}
          {lastSale && <button type="button" onClick={handleReprintReceipt} disabled={busy}>Chekni brauzerda qo‘lda chop etish</button>}
          {online && device?.is_active && pendingCount > 0 && (
            <button type="button" onClick={syncPendingSales} disabled={busy}>Hozir sinxronlash</button>
          )}
        </section>

        {pharmacyInfo && (
          <>
            {updateMessage && (
              <div
                className={`pharmacy-pos-message ${updateMessage.startsWith('✅') ? 'success' : 'error'}`}
                role="status"
              >
                {updateMessage}
              </div>
            )}
            <section className="pharmacy-pos-panel pharmacy-pos-pharmacy-info">
              <div className="pharmacy-pos-panel-title">
                <h2>Dorixona Ma'lumotlari</h2>
                <button type="button" onClick={() => setShowPharmacyEdit(!showPharmacyEdit)}>
                  {showPharmacyEdit ? 'Bekor qilish' : 'O‘zgartirilsin'}
                </button>
              </div>
              {showPharmacyEdit ? (
                <form onSubmit={onUpdatePharmacyInfo}>
                  <div className="pharmacy-pos-pharmacy-info-form">
                    <label>
                      Manzil
                      <input
                        type="text"
                        value={pharmacyInfo.address}
                        onChange={(event) => onPharmacyInfoChange('address', event.target.value)}
                      />
                    </label>
                    <label>
                      Telefon
                      <input
                        type="tel"
                        value={pharmacyInfo.phone_number}
                        onChange={(event) => onPharmacyInfoChange('phone_number', event.target.value)}
                      />
                    </label>
                    <label>
                      Ish vaqti
                      <input
                        type="text"
                        placeholder="09:00 - 20:00"
                        value={pharmacyInfo.working_hours}
                        onChange={(event) => onPharmacyInfoChange('working_hours', event.target.value)}
                      />
                    </label>
                    <label>
                      Sayt
                      <input
                        type="url"
                        placeholder="https://"
                        value={pharmacyInfo.website}
                        onChange={(event) => onPharmacyInfoChange('website', event.target.value)}
                      />
                    </label>
                  </div>
                  <fieldset className="pharmacy-pos-receipt-settings">
                    <legend>Chek qog‘ozi sozlamalari</legend>
                    <p>Tanlangan ma’lumotlar termal printer va brauzer chekida ko‘rsatiladi.</p>
                    <label>
                      <input
                        type="checkbox"
                        checked={pharmacyInfo.receipt_show_address}
                        onChange={(event) => onPharmacyInfoChange('receipt_show_address', event.target.checked)}
                      />
                      Manzilni chiqarish
                    </label>
                    <label>
                      <input
                        type="checkbox"
                        checked={pharmacyInfo.receipt_show_phone}
                        onChange={(event) => onPharmacyInfoChange('receipt_show_phone', event.target.checked)}
                      />
                      Telefonni chiqarish
                    </label>
                    <label>
                      <input
                        type="checkbox"
                        checked={pharmacyInfo.receipt_show_website}
                        onChange={(event) => onPharmacyInfoChange('receipt_show_website', event.target.checked)}
                      />
                      Sayt havolasini chiqarish
                    </label>
                    <label>
                      <input
                        type="checkbox"
                        checked={pharmacyInfo.receipt_show_instagram}
                        onChange={(event) => onPharmacyInfoChange('receipt_show_instagram', event.target.checked)}
                      />
                      Instagramni chiqarish
                    </label>
                    <label className="pharmacy-pos-receipt-settings-url">
                      Instagram manzili yoki nomi
                      <input
                        type="text"
                        placeholder="@dorixona yoki https://instagram.com/..."
                        value={pharmacyInfo.receipt_instagram_url}
                        onChange={(event) => onPharmacyInfoChange('receipt_instagram_url', event.target.value)}
                      />
                    </label>
                  </fieldset>
                  <button type="submit" disabled={updatingPharmacy}>
                    {updatingPharmacy ? 'Saqlanmoqda...' : 'Saqlash'}
                  </button>
                </form>
              ) : (
                <div className="pharmacy-pos-pharmacy-info-details">
                  <div><span>Manzil:</span><strong>{pharmacyInfo.address || '-'}</strong></div>
                  <div><span>Telefon:</span><strong>{pharmacyInfo.phone_number || '-'}</strong></div>
                  <div><span>Ish vaqti:</span><strong>{pharmacyInfo.working_hours || '-'}</strong></div>
                </div>
              )}
            </section>
          </>
        )}

        {showDeviceManagement && (
        <>
        <section className="pharmacy-pos-panel pharmacy-pos-device-panel">
          <div className="pharmacy-pos-panel-title">
            <div>
              <h2>Yangi kassir kompyuterini ulash</h2>
              <p>
                Bu sahifani boshqaruv kompyuterida oching, yangi kompyuterga nom bering va ulash kodini yarating.
                Boshqa dorixona emas — aynan shu dorixona akkaunti bilan kiring. Bu kompyuterning o‘zida ham sotuv qilmoqchi bo‘lsangiz, yaratilgan kodni pastdagi formaga qo‘llang.
              </p>
            </div>
            <span>{devices.filter((item) => item.is_active).length} ta faol kassa</span>
          </div>
          <ol className="pharmacy-pos-setup-steps">
            <li>Boshqaruv kompyuterida nom kiriting va <strong>Ulash kodini yaratish</strong>-ni bosing.</li>
            <li>Yangi kassir kompyuterida shu dorixona login-paroli bilan tizimga kiring.</li>
            <li>Ulash kodini yangi kompyuterdagi kassaga kiriting. Kod bir marta ishlaydi va 30 daqiqada tugaydi.</li>
          </ol>
          <form className="pharmacy-pos-inline-form" onSubmit={addCashierComputer}>
            <input
              aria-label="Ulanadigan kompyuter nomi"
              placeholder="Masalan: Kassa 2"
              value={newDeviceName}
              onChange={(event) => setNewDeviceName(event.target.value)}
              maxLength={120}
              required
            />
            <button type="submit" disabled={busy || !online}>Ulash kodini yaratish</button>
          </form>
          {generatedCode && (
            <div className="pharmacy-pos-generated-code">
              <strong>{generatedDeviceName} uchun bir martalik ulash kodi:</strong>
              <code>{generatedCode}</code>
              <span>
                {generatedCodeExpiresAt
                  ? `Amal qilish muddati: ${new Date(generatedCodeExpiresAt).toLocaleString()}`
                  : 'Kod 30 daqiqa amal qiladi.'}
              </span>
              <button type="button" onClick={copyGeneratedCode}>Kodni nusxalash</button>
              {!device?.is_active && (
                <button
                  type="button"
                  onClick={() => {
                    setActivationCode(generatedCode)
                    setComputerName(generatedDeviceName)
                  }}
                >
                  Shu kompyuterga qo‘llash
                </button>
              )}
              <p>Kodni faqat ushbu dorixona kassasiga yuboring. Kod ishlatilgach bekor bo‘ladi.</p>
            </div>
          )}
          <ul className="pharmacy-pos-device-list">
            {devices.map((item) => (
              <li key={item.id}>
                <span>
                  <strong>{item.name}</strong>
                  <small>
                    {item.is_pending ? 'Ulanish kutilmoqda' : item.is_active ? 'Faol' : 'O‘chirilgan'}
                    {item.stock_discrepancy_count > 0
                      ? ` · ${item.stock_discrepancy_count} ta sotuvda qoldiq tafovuti bor`
                      : ''}
                  </small>
                </span>
                {item.is_active && (
                  <button type="button" disabled={!online || busy} onClick={() => deactivateComputer(item.id)}>
                    Kassani o‘chirish
                  </button>
                )}
              </li>
            ))}
          </ul>
          <p className="pharmacy-pos-separate-pharmacy-note">
            Ikki alohida dorixona akkaunti bir-biriga avtomatik ulanmaydi: ularning ombori va kassalari alohida.
            Bir dorixonaning bir nechta kassasi uchun esa har kompyuterda shu dorixona akkauntidan foydalaning.
          </p>
        </section>

        {!device?.is_active && (
          <section className="pharmacy-pos-panel pharmacy-pos-activation-panel">
            <h2>Ulash kodi bor — ushbu kompyuterni kassaga ulang</h2>
            <p>
              Yuqorida boshqaruv kompyuterida yaratilgan kodni kiriting. Hozir bu kompyuterda dorixona akkauntiga kirilgan
              bo‘lishi kerak; har bir kompyuter alohida ulanadi.
            </p>
            <form className="pharmacy-pos-inline-form" onSubmit={activateThisComputer}>
              <input
                aria-label="Kompyuter nomi"
                placeholder="Kompyuter nomi, masalan: Kassa 2"
                value={computerName}
                onChange={(event) => setComputerName(event.target.value)}
                maxLength={120}
                required
              />
              <input
                aria-label="Bir martalik ulash kodi"
                placeholder="Masalan: A1B2C3D4E5F6"
                value={activationCode}
                onChange={(event) => setActivationCode(event.target.value)}
                required
              />
              <button type="submit" disabled={busy || !online}>Kompyuterni ulash</button>
            </form>
          </section>
        )}

        <section className="pharmacy-pos-panel pharmacy-pos-printer-panel">
            <div className="pharmacy-pos-panel-title">
              <div>
                <h2>Chek printeri</h2>
                <p>
                  {printerDevice?.printer_ready
                    ? `Avtomatik printer tayyor: ${printerDevice.printer_name || printerDevice.device_name}`
                    : 'Avtomatik ulash uchun Windows printer dasturini o‘rnating. Dasturda shu dorixona egasining login-parolini kiriting; chek brauzer chop etish oynasidan ham chiqarilishi mumkin.'}
                </p>
              </div>
              <span className={printerDevice?.printer_ready ? 'pharmacy-pos-printer-ready' : 'pharmacy-pos-printer-offline'}>
                {printerDevice?.printer_ready ? 'Tayyor' : 'Ulanmagan'}
              </span>
            </div>
            <button type="button" onClick={setupPrinter}>
              {printerInstallHelpOpen ? 'Yo‘riqnomani yopish' : 'Windows dasturi orqali printer ulash'}
            </button>
            {printerInstallHelpOpen && (
              <div className="pharmacy-pos-printer-setup">
                <strong>Dorixona printerini ulash</strong>
                <ol>
                  <li><code>GMedPrinterInstaller.exe</code> dasturini Windows kompyuteriga o‘rnating va ishga tushiring.</li>
                  <li>Dasturda <strong>Dorixona</strong>-ni tanlang, G-MED server manzili, dorixona login-emaili va parolini kiriting.</li>
                  <li>Dastur dorixonaga xavfsiz ulanib, printer xizmatini o‘zi sozlaydi. Windows administrator ruxsatini so‘rasa tasdiqlang.</li>
                </ol>
                <p>Printer kompyuterda ishlay boshlagach, holati shu oynada avtomatik “Tayyor” bo‘lib yangilanadi. Qabulxona printeri va uning login oqimi o‘zgarishsiz.</p>
              </div>
            )}
        </section>
        </>
        )}

        {showSales && <section className="pharmacy-pos-layout">
          <div className="pharmacy-pos-products">
            <label htmlFor="pharmacy-pos-search">Dori qidirish</label>
            <input
              id="pharmacy-pos-search"
              type="search"
              autoComplete="off"
              placeholder="Dori nomi, doza yoki ishlab chiqaruvchi..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            {!online && <p className="pharmacy-pos-offline-hint">Qidiruv ushbu kompyuterdagi lokal nusxada ishlayapti.</p>}
            <div className="pharmacy-pos-product-list">
              {filteredProducts.map((product) => (
                <button
                  className="pharmacy-pos-product"
                  type="button"
                  key={product.id}
                  onClick={() => addToBasket(product)}
                  disabled={!device?.is_active}
                >
                  <span>
                    <strong>{product.name} {product.strength}</strong>
                    <small>{[product.dosageForm, product.country, product.category].filter(Boolean).join(' · ')}</small>
                  </span>
                  <span className="pharmacy-pos-price">
                    <strong>{formatMoney(product.price)}</strong>
                    <small>Qoldiq: {product.quantity}</small>
                  </span>
                </button>
              ))}
              {filteredProducts.length === 0 && (
                <p className="pharmacy-pos-empty">
                  {products.length ? 'Qidiruv bo‘yicha dori topilmadi.' : 'Bu kompyuterda dori bazasi yo‘q. Internetga ulanib bazani yuklang.'}
                </p>
              )}
            </div>
          </div>

          <aside className="pharmacy-pos-cart">
            <div className="pharmacy-pos-cart-heading">
              <h2>Sotuv savati</h2>
              <span>{basketLines.length} xil</span>
            </div>
            <div className="pharmacy-pos-cart-lines">
              {basketLines.map(({ product, quantity }) => (
                <div className="pharmacy-pos-cart-line" key={product.id}>
                  <div>
                    <strong>{product.name} {product.strength}</strong>
                    <small>{formatMoney(product.price)} × {quantity}</small>
                    {quantity > product.quantity && (
                      <small className="pharmacy-pos-stock-warning">
                        Keshdagi qoldiqdan {quantity - product.quantity} ta ko‘p. Offline sotuv qayd qilinadi, internet qaytgach tafovut egasiga ko‘rsatiladi.
                      </small>
                    )}
                  </div>
                  <div className="pharmacy-pos-quantity">
                    <button type="button" aria-label="Kamaytirish" onClick={() => changeQuantity(product.id, -1)}>−</button>
                    <span>{quantity}</span>
                    <button type="button" aria-label="Ko‘paytirish" onClick={() => changeQuantity(product.id, 1)}>+</button>
                  </div>
                </div>
              ))}
              {!basketLines.length && <p className="pharmacy-pos-empty">Savat bo‘sh. Dorini qidirib tanlang.</p>}
            </div>
            <div className="pharmacy-pos-total">
              <span>Jami</span>
              <strong>{formatMoney(total)}</strong>
            </div>
            <button
              type="button"
              className="pharmacy-pos-checkout"
              onClick={completeSale}
              disabled={!basketLines.length || busy || !device?.is_active}
            >
              {busy ? 'Saqlanmoqda...' : 'Sotish va chek chiqarish'}
            </button>
          </aside>
        </section>}

      </div>

      {showSales && lastSale && (
        <article className="pharmacy-pos-receipt" aria-label="Sotuv cheki">
          <h2>{currentPharmacy.name}</h2>
          {(pharmacyInfo ? pharmacyInfo.receipt_show_address : currentPharmacy.receipt_show_address)
            && (pharmacyInfo ? pharmacyInfo.address : currentPharmacy.address)
            && <p>Manzil: {pharmacyInfo ? pharmacyInfo.address : currentPharmacy.address}</p>}
          {(pharmacyInfo ? pharmacyInfo.receipt_show_phone : currentPharmacy.receipt_show_phone)
            && (pharmacyInfo ? pharmacyInfo.phone_number : currentPharmacy.phone_number)
            && <p>Telefon: {pharmacyInfo ? pharmacyInfo.phone_number : currentPharmacy.phone_number}</p>}
          {(pharmacyInfo ? pharmacyInfo.receipt_show_website : currentPharmacy.receipt_show_website)
            && (pharmacyInfo ? pharmacyInfo.website : currentPharmacy.website)
            && <p>Sayt: {pharmacyInfo ? pharmacyInfo.website : currentPharmacy.website}</p>}
          {(pharmacyInfo ? pharmacyInfo.receipt_show_instagram : currentPharmacy.receipt_show_instagram)
            && (pharmacyInfo ? pharmacyInfo.receipt_instagram_url : currentPharmacy.receipt_instagram_url)
            && <p>Instagram: {pharmacyInfo ? pharmacyInfo.receipt_instagram_url : currentPharmacy.receipt_instagram_url}</p>}
          <hr />
          <p>Chek: {lastSale.id.slice(0, 8).toUpperCase()}</p>
          <p>Sana: {new Date(lastSale.sold_at).toLocaleString()}</p>
          <hr />
          <table>
            <thead><tr><th>Dori</th><th>Soni</th><th>Narxi</th><th>Jami</th></tr></thead>
            <tbody>
              {lastSale.lines.map((line) => (
                <tr key={`${lastSale.id}-${line.inventory_id}`}>
                  <td>{line.medicine_name}</td>
                  <td>{line.quantity}</td>
                  <td>{formatMoney(line.unit_price)}</td>
                  <td>{formatMoney(line.line_total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <hr />
          <strong>Jami: {formatMoney(lastSale.total)}</strong>
          <p>Xaridingiz uchun rahmat!</p>
        </article>
      )}
    </main>
  )
}

export default PharmacyPos
