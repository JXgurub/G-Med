import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { doctorsApi, receptionStaffApi, medicalApi, printersApi, normalizeUzPhoneWithPrefix } from '../services/api'
import './ReceptionDashboard.css'

const buildTempPatientNumber = () => `GM${Date.now().toString().slice(-8)}`

const getLocalDateValue = () => {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}

const formatPhoneInput = (digits) => {
  const d = String(digits || '').slice(0, 9)
  const p1 = d.slice(0, 2)
  const p2 = d.slice(2, 5)
  const p3 = d.slice(5, 7)
  const p4 = d.slice(7, 9)
  return [p1, p2, p3, p4].filter(Boolean).join(' ')
}

const ReceptionDashboard = () => {
  const navigate = useNavigate()
  let staff = null
  try {
    staff = JSON.parse(localStorage.getItem('reception_staff') || 'null')
  } catch {
    staff = null
  }

  const [doctors, setDoctors] = useState([])
  const [patientSearch, setPatientSearch] = useState('')
  const [patientResults, setPatientResults] = useState([])
  const [patientLookupLoading, setPatientLookupLoading] = useState(false)
  const [form, setForm] = useState({
    full_name: '',
    phone_number: '',
    date_of_birth: '',
    doctor: '',
    specialty_price_ids: [],
    date: getLocalDateValue(),
    slot_id: '',
  })
  const [message, setMessage] = useState('')
  const [stats, setStats] = useState(null)
  const [generatedPatientNumber, setGeneratedPatientNumber] = useState(buildTempPatientNumber())
  const [reportDate, setReportDate] = useState(new Date().toISOString().slice(0, 10))
  const [reportFormat, setReportFormat] = useState('xlsx')
  const [showReportPanel, setShowReportPanel] = useState(false)
  const [isDownloading, setIsDownloading] = useState(false)
  const [attendance, setAttendance] = useState({ today_checked_in_at: null, today_checked_out_at: null })
  const [attendanceLoading, setAttendanceLoading] = useState(false)
  const [lastQueueNumber, setLastQueueNumber] = useState(null)
  const [cancelLoadingId, setCancelLoadingId] = useState('')
  const [cancelConfirmPatient, setCancelConfirmPatient] = useState(null)
  const [servicePatient, setServicePatient] = useState(null)
  const [serviceSelection, setServiceSelection] = useState([])
  const [serviceSaving, setServiceSaving] = useState(false)
  const [onlineAppointments, setOnlineAppointments] = useState([])
  const [onlineAppointmentId, setOnlineAppointmentId] = useState('')
  const [showPrinterPanel, setShowPrinterPanel] = useState(false)
  const [printerStatus, setPrinterStatus] = useState({ devices: [] })
  const [printerLoading, setPrinterLoading] = useState(false)
  const [printerTesting, setPrinterTesting] = useState(false)
  const [printerRegistering, setPrinterRegistering] = useState(false)
  const [printerToken, setPrinterToken] = useState(() => localStorage.getItem('gmed_printer_device_token') || '')
  const [printerTokenCopied, setPrinterTokenCopied] = useState(false)

  const selectedDoctor = doctors.find((item) => String(item.id) === String(form.doctor))
  const specialtyPrices = selectedDoctor?.specialty_prices || []
  const selectedPrices = specialtyPrices.filter((item) => form.specialty_price_ids.includes(String(item.id)))
  const totalPrice = selectedPrices.reduce((sum, item) => sum + Number(item.consultation_fee || 0), 0)
  const todayIso = getLocalDateValue()

  useEffect(() => {
    const query = patientSearch.trim()
    const timer = window.setTimeout(() => {
      setPatientLookupLoading(true)
      receptionStaffApi.searchPatients(query)
        .then((data) => setPatientResults(Array.isArray(data) ? data : []))
        .catch(() => setPatientResults([]))
        .finally(() => setPatientLookupLoading(false))
    }, query ? 250 : 0)
    return () => window.clearTimeout(timer)
  }, [patientSearch])

  useEffect(() => {
    const name = form.full_name.trim().toLowerCase()
    const phone = form.phone_number.trim()
    const birthDate = form.date_of_birth
    if (!name || !phone || !birthDate) return

    const timer = window.setTimeout(() => {
      receptionStaffApi.searchPatients(phone)
        .then((data) => {
          const match = (Array.isArray(data) ? data : []).find((patient) => (
            String(patient.phone_number || '').replace(/\D/g, '').endsWith(phone)
            && String(patient.full_name || '').trim().toLowerCase() === name
            && patient.date_of_birth === birthDate
          ))
          setGeneratedPatientNumber(match?.patient_number || buildTempPatientNumber())
        })
        .catch(() => {})
    }, 250)
    return () => window.clearTimeout(timer)
  }, [form.full_name, form.phone_number, form.date_of_birth])

  const loadTodayStats = () => {
    receptionStaffApi.getStats({ date: todayIso }).then(setStats).catch(() => setStats(null))
  }

  const loadOnlineAppointments = () => {
    receptionStaffApi.getOnlineAppointments().then((data) => setOnlineAppointments(Array.isArray(data) ? data : [])).catch(() => setOnlineAppointments([]))
  }

  const loadAttendance = () => {
    receptionStaffApi.getMe()
      .then((data) => {
        setAttendance({
          today_checked_in_at: data?.today_checked_in_at || null,
          today_checked_out_at: data?.today_checked_out_at || null,
        })
      })
      .catch(() => {
        setAttendance({ today_checked_in_at: null, today_checked_out_at: null })
      })
  }

  const loadPrinterStatus = () => {
    setPrinterLoading(true)
    printersApi.getStatus()
      .then((data) => {
        const devices = Array.isArray(data?.devices) ? data.devices : []
        setPrinterStatus({ devices })
        const activeDevice = devices.find((device) => device?.device_token) || null
        if (activeDevice?.device_token) {
          persistPrinterToken(activeDevice.device_token)
        }
      })
      .catch(() => {
        setPrinterStatus({ devices: [] })
      })
      .finally(() => setPrinterLoading(false))
  }

  useEffect(() => {
    loadPrinterStatus()
    const printerInterval = window.setInterval(loadPrinterStatus, 30000)
    return () => window.clearInterval(printerInterval)
  }, [])

  useEffect(() => {
    if (!staff?.clinic_id && !staff?.clinic) return
    receptionStaffApi.getDoctors()
      .then((data) => setDoctors(Array.isArray(data) ? data : data?.results || []))
      .catch((error) => setMessage(error?.message || "Doktorlarni yuklab bo'lmadi"))
  }, [staff?.clinic_id])

  useEffect(() => {
    loadTodayStats()
    loadAttendance()
    loadOnlineAppointments()
  }, [message])

  useEffect(() => {
    const statsInterval = window.setInterval(loadTodayStats, 10000)
    return () => window.clearInterval(statsInterval)
  }, [])

  if (!localStorage.getItem('reception_session_token') || !staff) {
    navigate('/reception-login', { replace: true })
    return null
  }

  const logout = () => {
    localStorage.removeItem('reception_session_token')
    localStorage.removeItem('reception_staff')
    navigate('/reception-login', { replace: true })
  }

  const handlePhoneChange = (value) => {
    const normalized = normalizeUzPhoneWithPrefix(value)
    setForm((prev) => ({ ...prev, phone_number: normalized }))
  }

  const selectPatientForBooking = (patient) => {
    const digits = String(patient.phone_number || '').replace(/\D/g, '')
    const localPhone = digits.startsWith('998') ? digits.slice(3) : digits
    setForm((prev) => ({
      ...prev,
      full_name: patient.full_name || '',
      phone_number: localPhone,
      date_of_birth: patient.date_of_birth || '',
      doctor: '',
      specialty_price_ids: [],
      slot_id: '',
    }))
    setGeneratedPatientNumber(patient.patient_number || buildTempPatientNumber())
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const buildReportRows = (reportStats) => (reportStats?.accepted_patients || []).map((item) => ({
    'F.I.O': item.patient_name,
    "Tug'ilgan yil": item.birth_year || '-',
    "To'lov summasi": Number(item.amount || 0),
  }))

  const downloadReport = async () => {
    if (!reportDate) {
      setMessage('Hisobot uchun sanani kiriting.')
      return
    }
    setIsDownloading(true)
    try {
      const reportStats = await receptionStaffApi.getStats({ date: reportDate })
      const reportRows = buildReportRows(reportStats)
      if (reportRows.length === 0) {
        setMessage("Tanlangan sanada ushbu xodim tomonidan qabul qilingan bemorlar topilmadi.")
        return
      }

      const fileDate = reportDate
      if (reportFormat === 'xlsx') {
        const XLSX = await import('xlsx')
        const workbook = XLSX.utils.book_new()
        XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(reportRows), 'Bemorlar')
        XLSX.writeFile(workbook, `qabulxona-bemorlar-${fileDate}.xlsx`)
      } else {
        const rows = reportRows.map((row) => `<tr><td>${row['F.I.O']}</td><td>${row["Tug'ilgan yil"]}</td><td>${Number(row["To'lov summasi"]).toLocaleString()} so'm</td></tr>`).join('')
        const html = `<html><meta charset="utf-8"><body><h1>Qabulxona xodimi bemorlar ro'yxati</h1><p>Sana: ${fileDate}</p><table border="1" cellspacing="0" cellpadding="6"><tr><th>F.I.O</th><th>Tug'ilgan yil</th><th>To'lov summasi</th></tr>${rows}</table></body></html>`

        if (reportFormat === 'doc') {
          const link = document.createElement('a')
          link.href = URL.createObjectURL(new Blob([html], { type: 'application/msword' }))
          link.download = `qabulxona-bemorlar-${fileDate}.doc`
          link.click()
          URL.revokeObjectURL(link.href)
        }

        if (reportFormat === 'pdf') {
          const printWindow = window.open('', '_blank')
          if (printWindow) {
            printWindow.document.write(html)
            printWindow.document.close()
            printWindow.focus()
            printWindow.print()
          }
        }
      }

      setMessage('Hisobot muvaffaqiyatli yuklab olindi.')
      setShowReportPanel(false)
    } catch (error) {
      setMessage(error?.message || 'Hisobotni yuklab olishda xatolik')
    } finally {
      setIsDownloading(false)
    }
  }

  const submitRegistration = async (event) => {
    event.preventDefault()
    setMessage('')
    if (!form.doctor || form.specialty_price_ids.length === 0) {
      setMessage("Doktor va yo'nalishni tanlang.")
      return
    }

    const [first_name, ...lastParts] = form.full_name.trim().split(/\s+/)
    try {
      if (onlineAppointmentId) {
        const response = await receptionStaffApi.confirmOnlineAppointment(onlineAppointmentId)
        setMessage(response?.detail || 'Onlayn navbat tasdiqlandi va printerga yuborildi.')
        setOnlineAppointmentId('')
        setOnlineAppointments((items) => items.filter((item) => item.id !== onlineAppointmentId))
        setForm((prev) => ({ ...prev, full_name: '', phone_number: '', date_of_birth: '', specialty_price_ids: [], slot_id: '' }))
        setGeneratedPatientNumber(buildTempPatientNumber())
        loadTodayStats()
        return
      }
      const bookingResponse = await medicalApi.bookOnline({
        clinic: staff.clinic_id,
        doctor: form.doctor,
        specialty_price_ids: form.specialty_price_ids,
        first_name,
        last_name: lastParts.join(' ') || '-',
        phone_number: `+998${form.phone_number}`,
        date_of_birth: form.date_of_birth || null,
        source: 'reception',
        reception_staff_id: staff.id,
        patient_number: generatedPatientNumber,
      })
      const patientNumber = bookingResponse?.patient_number || bookingResponse?.appointment?.patient_number
      const queueNumber = Number(bookingResponse?.queue_position || bookingResponse?.queue_number || 0)
      if (queueNumber > 0) setLastQueueNumber(queueNumber)
      setMessage(patientNumber ? `Bemor navbatga muvaffaqiyatli yozildi. Raqami: ${patientNumber}` : 'Bemor navbatga muvaffaqiyatli yozildi')
      setForm((prev) => ({ ...prev, full_name: '', phone_number: '', date_of_birth: '', specialty_price_ids: [], slot_id: '' }))
      setGeneratedPatientNumber(buildTempPatientNumber())
      loadTodayStats()
      loadAttendance()
    } catch (error) {
      setMessage(error?.message || 'Navbat olishda xatolik')
    }
  }

  const handleCheckIn = async () => {
    setAttendanceLoading(true)
    try {
      const response = await receptionStaffApi.checkIn()
      const staffData = response?.staff || {}
      setAttendance({
        today_checked_in_at: staffData?.today_checked_in_at || attendance.today_checked_in_at,
        today_checked_out_at: staffData?.today_checked_out_at || null,
      })
      setMessage(response?.detail || 'Ishga kelish vaqti saqlandi.')
    } catch (error) {
      setMessage(error?.message || "Ishga kelishni saqlab bo'lmadi")
    } finally {
      setAttendanceLoading(false)
    }
  }

  const handleCheckOut = async () => {
    setAttendanceLoading(true)
    try {
      const response = await receptionStaffApi.checkOut()
      const staffData = response?.staff || {}
      setAttendance({
        today_checked_in_at: staffData?.today_checked_in_at || attendance.today_checked_in_at,
        today_checked_out_at: staffData?.today_checked_out_at || attendance.today_checked_out_at,
      })
      setMessage(response?.detail || 'Ishdan ketish vaqti saqlandi.')
    } catch (error) {
      setMessage(error?.message || "Ishdan ketishni saqlab bo'lmadi")
    } finally {
      setAttendanceLoading(false)
    }
  }

  const canCheckIn = !attendance.today_checked_in_at || attendance.today_checked_out_at
  const canCheckOut = Boolean(attendance.today_checked_in_at) && !attendance.today_checked_out_at

  const persistPrinterToken = (token) => {
    const cleanToken = String(token || '').trim()
    if (!cleanToken) return
    setPrinterToken(cleanToken)
    localStorage.setItem('gmed_printer_device_token', cleanToken)
  }

  const copyPrinterToken = async () => {
    if (!printerToken) return
    try {
      await navigator.clipboard.writeText(printerToken)
      setPrinterTokenCopied(true)
      window.setTimeout(() => setPrinterTokenCopied(false), 1500)
    } catch (error) {
      setMessage('Token nusxalab bo‘lmadi. Tokenni qo‘lda ko‘chiring.')
    }
  }

  const handleRegisterPrinter = async () => {
    setPrinterRegistering(true)
    try {
      const response = await printersApi.register({
        clinic_id: staff?.clinic_id || staff?.clinic || null,
        reception_room_id: null,
        device_name: `${staff?.first_name || 'Windows'} ${staff?.last_name || 'PC'}`,
      })
      const token = response?.device_token || printerToken
      if (token) {
        persistPrinterToken(token)
      }
      setMessage(response?.detail || 'Printer uchun token yaratildi.')
      loadPrinterStatus()
    } catch (error) {
      setMessage(error?.message || 'Printerni ro‘yxatdan o‘tkazib bo‘lmadi')
    } finally {
      setPrinterRegistering(false)
    }
  }

  const handleTestPrint = async () => {
    setPrinterTesting(true)
    try {
      const response = await printersApi.testPrint()
      setMessage(response?.detail || 'Printerga test chop yaratildi.')
      loadPrinterStatus()
    } catch (error) {
      setMessage(error?.message || 'Test chop yaratib bo\'lmadi')
    } finally {
      setPrinterTesting(false)
    }
  }

  const openCancelConfirm = (patient) => setCancelConfirmPatient(patient)

  const handleReceptionCancel = async (appointmentId) => {
    if (!appointmentId) return
    setCancelLoadingId(String(appointmentId))
    try {
      await medicalApi.receptionCancelAppointment(appointmentId)
      setMessage('Qabul bekor qilindi')
      setCancelConfirmPatient(null)
      loadTodayStats()
    } catch (error) {
      setMessage(error?.message || 'Qabulni bekor qilib bo\'lmadi')
    } finally {
      setCancelLoadingId('')
    }
  }

  const openServiceModal = (patient) => {
    setServicePatient(patient)
    setServiceSelection([])
  }

  const selectOnlineAppointment = (appointment) => {
    const digits = String(appointment.phone || '').replace(/\D/g, '')
    setForm((prev) => ({
      ...prev,
      full_name: appointment.patient_name || '',
      phone_number: digits.startsWith('998') ? digits.slice(3) : digits,
      date_of_birth: appointment.date_of_birth || '',
      doctor: appointment.doctor_id || '',
      specialty_price_ids: (appointment.selected_specialties || []).map((item) => String(item.id)),
      slot_id: '',
    }))
    setGeneratedPatientNumber(appointment.patient_number || buildTempPatientNumber())
    setOnlineAppointmentId(appointment.id)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const cancelOnlineAppointment = async (appointment) => {
    if (!window.confirm(`${appointment.patient_name} navbati bekor qilinsinmi?`)) return
    try {
      await receptionStaffApi.cancelOnlineAppointment(appointment.id)
      setOnlineAppointments((items) => items.filter((item) => item.id !== appointment.id))
      setMessage('Onlayn navbat bekor qilindi.')
    } catch (error) {
      setMessage(error?.message || 'Onlayn navbatni bekor qilib bo‘lmadi')
    }
  }

  const handleAddServices = async () => {
    if (!servicePatient || serviceSelection.length === 0) return
    setServiceSaving(true)
    try {
      const response = await medicalApi.receptionAddServices(servicePatient.id, serviceSelection)
      setMessage(`${response?.detail || 'Xizmatlar saqlandi'} Jami: ${Number(response?.consultation_fee || 0).toLocaleString()} so'm`)
      setServicePatient(null)
      loadTodayStats()
    } catch (error) {
      setMessage(error?.message || 'Xizmatlarni saqlab bo‘lmadi')
    } finally {
      setServiceSaving(false)
    }
  }

  return (
    <main className="reception-dashboard-page">
      <header className="reception-dashboard-header">
        <div className="reception-profile-main">
          <div className="reception-profile-avatar">{staff.first_name?.charAt(0) || 'Q'}</div>
          <div>
            <span className="reception-eyebrow">QABULXONA</span>
            <h1>{staff.first_name} {staff.last_name}</h1>
            <p>{staff.email || 'Qabul xonasi xodimi'}</p>
            <p className="reception-attendance-line">Bugun: kelgan {attendance.today_checked_in_at || '-'} • ketgan {attendance.today_checked_out_at || '-'}</p>
            {lastQueueNumber ? <p className="reception-queue-badge">Navbat: #{lastQueueNumber}</p> : null}
          </div>
        </div>
        <div className="reception-header-actions">
          <button type="button" className="reception-printer-toggle" onClick={() => setShowPrinterPanel((prev) => !prev)}>
            Printer
          </button>
          <button type="button" className="reception-checkin-btn" onClick={handleCheckIn} disabled={!canCheckIn || attendanceLoading}>Ishga keldim</button>
          <button type="button" className="reception-checkout-btn" onClick={handleCheckOut} disabled={!canCheckOut || attendanceLoading}>Ishdan ketdim</button>
          <button type="button" className="reception-logout-button" onClick={logout}>Chiqish</button>
        </div>
      </header>

      <section className="reception-stat-summary">
        {[
          ['Bugungi qabul', stats?.accepted_count || 0],
          ['Bekor qilingan', stats?.cancelled_count || 0],
          ['Bir kunlik daromad', `${Number(stats?.daily_revenue || 0).toLocaleString()} so'm`],
          ['Bir oylik daromad', `${Number(stats?.monthly_revenue || 0).toLocaleString()} so'm`],
          [stats?.salary_type === 'percent' ? 'Oylik foiz' : 'Oylik maosh', stats?.salary_type === 'percent' ? `${Number(stats?.salary_value || 0)}%` : `${Number(stats?.salary_value || 0).toLocaleString()} so'm`],
        ].map(([label, value]) => (
          <div key={label} className="reception-stat-card">
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </section>

      <section className="reception-report-actions">
        <button type="button" onClick={() => setShowReportPanel((prev) => !prev)}>{showReportPanel ? 'Yopish' : 'Yuklab olish'}</button>
      </section>

      {showPrinterPanel && (
        <section className="reception-printer-panel">
          <div className="reception-printer-header">
            <div>
              <span className="reception-eyebrow">PRINTER</span>
              <h3>Printer holati</h3>
            </div>
            <div className="reception-printer-actions">
              <button type="button" className="reception-printer-button primary" onClick={handleRegisterPrinter} disabled={printerRegistering}>
                {printerRegistering ? 'Ro‘yxatdan o‘tilmoqda...' : 'Printer ulash'}
              </button>
              <button type="button" className="reception-printer-button secondary" onClick={handleTestPrint} disabled={printerTesting}>
                {printerTesting ? 'Chop etilmoqda...' : 'Test chop etish'}
              </button>
            </div>
          </div>

          {printerToken && (
            <div className="reception-printer-token-box">
              <div className="reception-printer-token-row">
                <div>
                  <div className="reception-printer-token-label">Device token</div>
                  <strong>{printerToken}</strong>
                </div>
                <button type="button" className="reception-printer-copy-btn" onClick={copyPrinterToken}>
                  {printerTokenCopied ? 'Nusxalandi' : 'Kopiya'}
                </button>
              </div>
            </div>
          )}

          {printerLoading ? (
            <p className="reception-printer-text">Printer holati tekshirilmoqda...</p>
          ) : printerStatus.devices.length === 0 ? (
            <p className="reception-printer-warning">Hech qanday lokal printer aniqlanmagan.</p>
          ) : (
            <div className="reception-printer-list">
              {printerStatus.devices.map((device) => (
                <div key={device.id} className="reception-printer-item">
                  <div>
                    <strong>{device.device_name || 'G-MED Printer'}</strong>
                    <p>{device.printer_name || 'Printer nomi yo‘q'}</p>
                  </div>
                  <span className={`reception-printer-badge ${device.status}`}>{device.status_label}</span>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {showReportPanel && (
        <section className="reception-report-panel">
          <label>
            Sana
            <input type="date" value={reportDate} onChange={(e) => setReportDate(e.target.value)} />
          </label>
          <label>
            Format
            <select value={reportFormat} onChange={(e) => setReportFormat(e.target.value)}>
              <option value="xlsx">Excel (.xlsx)</option>
              <option value="doc">Word (.doc)</option>
              <option value="pdf">PDF</option>
            </select>
          </label>
          <button type="button" onClick={downloadReport} disabled={isDownloading}>{isDownloading ? 'Yuklanmoqda...' : 'Yuklab olish'}</button>
        </section>
      )}

      {onlineAppointments.length > 0 && (
        <section className="reception-online-panel">
          <div className="reception-patients-heading"><h2>Onlayn navbatlar</h2><span>{onlineAppointments.length} ta</span></div>
          {onlineAppointments.map((appointment) => (
            <div className="reception-online-row" key={appointment.id}>
              <div><strong>{appointment.patient_name}</strong><span>{appointment.patient_number} • {appointment.phone} • Tug‘ilgan sana: {appointment.date_of_birth || '-'}</span><span>{appointment.doctor_name} • Navbat #{appointment.queue_position} • {Number(appointment.amount || 0).toLocaleString()} so‘m</span></div>
              <div className="reception-row-actions"><button type="button" className="reception-service-btn" onClick={() => selectOnlineAppointment(appointment)}>Tasdiqlash</button><button type="button" className="reception-cancel-btn" onClick={() => cancelOnlineAppointment(appointment)}>Bekor qilish</button></div>
            </div>
          ))}
        </section>
      )}

      <section className="reception-registration-panel">
        <div className="reception-section-heading">
          <div>
            <span className="reception-eyebrow">YANGI QABUL</span>
            <h2>Bemorni navbatga yozish</h2>
            <span className="reception-today-label">Bugun: {new Date().toLocaleDateString('uz-UZ')}</span>
          </div>
          <div className="reception-total">{totalPrice ? `${totalPrice.toLocaleString()} so'm` : '-'}</div>
        </div>

        <form className="reception-registration-form" onSubmit={submitRegistration}>
          <label>
            Bemor F.I.O
            <input required value={form.full_name} onChange={(e) => setForm((p) => ({ ...p, full_name: e.target.value }))} placeholder="Ism Familiya" />
          </label>

          <label>
            Telefon
            <div className="reception-phone-input">
              <span>+998</span>
              <input
                required
                inputMode="numeric"
                value={formatPhoneInput(form.phone_number)}
                onChange={(e) => handlePhoneChange(e.target.value)}
                placeholder="90 000 00 00"
              />
            </div>
          </label>

          <label>
            Bemor raqami
            <input value={generatedPatientNumber} readOnly />
          </label>

          <label>
            Tug'ilgan sana
            <input type="date" value={form.date_of_birth} onChange={(e) => setForm((p) => ({ ...p, date_of_birth: e.target.value }))} />
          </label>

          <label>
            Doktor
            <select required value={form.doctor} onChange={(e) => setForm((p) => ({ ...p, doctor: e.target.value, specialty_price_ids: [], slot_id: '' }))}>
              <option value="">Doktorni tanlang</option>
              {doctors.map((doctor) => (
                <option key={doctor.id} value={doctor.id}>{doctor.user?.first_name} {doctor.user?.last_name}</option>
              ))}
            </select>
          </label>

          <div className="reception-specialty-picker">
            <span>Davolash yo'nalishlari</span>
            {specialtyPrices.length === 0 ? (
              <small>{form.doctor ? "Bu doktorda yo'nalish topilmadi" : 'Avval doktorni tanlang'}</small>
            ) : (
              specialtyPrices.map((item) => {
                const selected = form.specialty_price_ids.includes(String(item.id))
                return (
                  <label className={`reception-specialty-option ${selected ? 'selected' : ''}`} key={item.id}>
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={() => setForm((p) => ({
                        ...p,
                        specialty_price_ids: selected
                          ? p.specialty_price_ids.filter((id) => id !== String(item.id))
                          : [...p.specialty_price_ids, String(item.id)],
                      }))}
                    />
                    <span>{item.custom_name || item.specialization?.name}</span>
                    <b>{Number(item.consultation_fee).toLocaleString()} so'm</b>
                  </label>
                )
              })
            )}
          </div>

          <div className="reception-auto-slot">
            <span>Avtomatik navbat vaqti</span>
            <strong>{form.doctor ? `Hozirgi vaqt: ${new Date().toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' })}` : 'Doktor tanlang'}</strong>
            <small>Navbat bosilganda real vaqt qayd etiladi</small>
          </div>

          <button type="submit" disabled={!form.doctor || form.specialty_price_ids.length === 0}>Navbatga yozish</button>
        </form>

        {message && <div className="reception-dashboard-message">{message}</div>}
      </section>

      <section className="reception-patient-lists">
        <div>
          <h2>Bugungi bemorlar</h2>
          {(stats?.queue_patients || stats?.accepted_patients || []).map((item) => (
            <div className="reception-patient-row" key={item.id}>
              <strong>#{Number(item.queue_position || 0)} • {item.patient_name}</strong>
              <span>{item.time} • {item.doctor_name}</span>
              <div className="reception-row-actions"><b>{Number(item.amount).toLocaleString()} so'm</b><button type="button" className="reception-service-btn" onClick={() => openServiceModal(item)}>Xizmat qo‘shish</button><button type="button" className="reception-cancel-btn" onClick={() => openCancelConfirm(item)} disabled={cancelLoadingId === String(item.id)}>{cancelLoadingId === String(item.id) ? 'Bekor...' : 'Bekor qilish'}</button></div>
            </div>
          ))}
        </div>
        <div>
          <div className="reception-patients-heading">
            <h2>Qabul qilinganlar</h2>
            <span>{patientResults.length} ta bemor</span>
          </div>
          <input
            className="reception-patient-search"
            value={patientSearch}
            onChange={(e) => setPatientSearch(e.target.value)}
            placeholder="Telefon, IFO yoki bemor raqami bo‘yicha qidiring"
          />
          {patientLookupLoading ? <p className="reception-search-status">Qidirilmoqda...</p> : null}
          {!patientLookupLoading && patientResults.length === 0 ? <p className="reception-search-status">Bemor topilmadi</p> : null}
          {patientResults.map((patient) => (
            <button
              type="button"
              className="reception-patient-row reception-directory-row reception-patient-select"
              key={patient.id}
              onClick={() => selectPatientForBooking(patient)}
            >
              <strong>{patient.full_name}</strong>
              <span>{patient.patient_number} • {patient.phone_number || 'Telefon kiritilmagan'} • Tug‘ilgan sana: {patient.date_of_birth || '-'}</span>
            </button>
          ))}
        </div>
      </section>

      {cancelConfirmPatient && (
        <div className="reception-modal-overlay" onClick={() => setCancelConfirmPatient(null)}>
          <div className="reception-modal" onClick={(event) => event.stopPropagation()}>
            <h3>Qabulni bekor qilish</h3>
            <div className="reception-modal-details">
              <strong>{cancelConfirmPatient.patient_name}</strong>
              <span>IFO: {cancelConfirmPatient.patient_name}</span>
              <span>Telefon: {cancelConfirmPatient.phone || '-'}</span>
              <span>Tug‘ilgan sana: {cancelConfirmPatient.date_of_birth || '-'}</span>
              <span>Jami to‘lov: {Number(cancelConfirmPatient.amount || 0).toLocaleString()} so‘m</span>
            </div>
            <p>Ushbu bemorning navbati bekor qilinsinmi?</p>
            <div className="reception-modal-actions">
              <button type="button" className="reception-cancel-btn" onClick={() => handleReceptionCancel(cancelConfirmPatient.id)} disabled={Boolean(cancelLoadingId)}>{cancelLoadingId ? 'Bekor qilinmoqda...' : 'Ha, bekor qilish'}</button>
              <button type="button" className="reception-modal-secondary" onClick={() => setCancelConfirmPatient(null)} disabled={Boolean(cancelLoadingId)}>Yo‘q</button>
            </div>
          </div>
        </div>
      )}

      {servicePatient && (
        <div className="reception-modal-overlay" onClick={() => setServicePatient(null)}>
          <div className="reception-modal" onClick={(event) => event.stopPropagation()}>
            <h3>Xizmat qo‘shish</h3>
            <p className="reception-modal-subtitle">{servicePatient.patient_name} • Hozirgi jami: {Number(servicePatient.amount || 0).toLocaleString()} so‘m</p>
            <div className="reception-service-options">
              {(doctors.find((doctor) => String(doctor.id) === String(servicePatient.doctor_id))?.specialty_prices || []).map((item) => {
                const selected = serviceSelection.includes(String(item.id))
                const alreadySelected = (servicePatient.selected_specialties || []).some((specialty) => String(specialty.id) === String(item.id))
                return (
                  <label key={item.id} className={alreadySelected ? 'disabled' : ''}>
                    <input type="checkbox" checked={selected || alreadySelected} disabled={alreadySelected || serviceSaving} onChange={() => setServiceSelection((previous) => selected ? previous.filter((id) => id !== String(item.id)) : [...previous, String(item.id)])} />
                    <span>{item.custom_name || item.specialization?.name}</span>
                    <b>{Number(item.consultation_fee || 0).toLocaleString()} so‘m</b>
                  </label>
                )
              })}
            </div>
            <div className="reception-modal-actions">
              <button type="button" className="reception-modal-primary" onClick={handleAddServices} disabled={serviceSaving || serviceSelection.length === 0}>{serviceSaving ? 'Saqlanmoqda...' : 'Saqlash'}</button>
              <button type="button" className="reception-modal-secondary" onClick={() => setServicePatient(null)} disabled={serviceSaving}>Bekor qilish</button>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}

export default ReceptionDashboard
