import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { doctorsApi, receptionStaffApi, medicalApi, normalizeUzPhoneWithPrefix } from '../services/api'
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
  const [slots, setSlots] = useState([])
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

  const selectedDoctor = doctors.find((item) => String(item.id) === String(form.doctor))
  const specialtyPrices = selectedDoctor?.specialty_prices || []
  const selectedPrices = specialtyPrices.filter((item) => form.specialty_price_ids.includes(String(item.id)))
  const totalPrice = selectedPrices.reduce((sum, item) => sum + Number(item.consultation_fee || 0), 0)
  const todayIso = getLocalDateValue()

  const loadTodayStats = () => {
    receptionStaffApi.getStats({ date: todayIso }).then(setStats).catch(() => setStats(null))
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

  useEffect(() => {
    if (!staff?.clinic_id && !staff?.clinic) return
    receptionStaffApi.getDoctors()
      .then((data) => setDoctors(Array.isArray(data) ? data : data?.results || []))
      .catch((error) => setMessage(error?.message || "Doktorlarni yuklab bo'lmadi"))
  }, [staff?.clinic_id])

  useEffect(() => {
    if (!form.doctor || !form.date) return
    let cancelled = false
    const loadAvailability = () => {
      doctorsApi.getAvailability({ doctor: form.doctor, date: form.date })
        .then((data) => {
          if (cancelled) return
          const now = new Date()
          const availableSlots = (data?.results || data || [])
            .filter((slot) => slot.status === 'available')
            .filter((slot) => {
              if (form.date !== getLocalDateValue()) return true
              const [hours, minutes] = String(slot.start_time || '').split(':').map(Number)
              const slotTime = new Date(now)
              slotTime.setHours(hours, minutes, 0, 0)
              return slotTime > now
            })
          setSlots(availableSlots)
          setForm((prev) => ({
            ...prev,
            slot_id: availableSlots.some((slot) => String(slot.id) === String(prev.slot_id))
              ? prev.slot_id
              : availableSlots[0]?.id || '',
          }))
        })
        .catch(() => {
          if (cancelled) return
          setSlots([])
          setForm((prev) => ({ ...prev, slot_id: '' }))
        })
    }
    loadAvailability()
    const refreshTimer = window.setInterval(loadAvailability, 30000)
    return () => {
      cancelled = true
      window.clearInterval(refreshTimer)
    }
  }, [form.doctor, form.date])

  useEffect(() => {
    loadTodayStats()
    loadAttendance()
  }, [message])

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
    if (!form.doctor || form.specialty_price_ids.length === 0 || !form.slot_id) {
      setMessage("Doktor, yo'nalish va bo'sh vaqtni tanlang.")
      return
    }

    const [first_name, ...lastParts] = form.full_name.trim().split(/\s+/)
    try {
      const bookingResponse = await medicalApi.bookOnline({
        clinic: staff.clinic_id,
        doctor: form.doctor,
        slot_id: form.slot_id,
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

  const handleReceptionCancel = async (appointmentId) => {
    if (!appointmentId) return
    setCancelLoadingId(String(appointmentId))
    try {
      await medicalApi.receptionCancelAppointment(appointmentId)
      setMessage('Qabul bekor qilindi')
      loadTodayStats()
    } catch (error) {
      setMessage(error?.message || 'Qabulni bekor qilib bo\'lmadi')
    } finally {
      setCancelLoadingId('')
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
                    <span>{item.specialization?.name}</span>
                    <b>{Number(item.consultation_fee).toLocaleString()} so'm</b>
                  </label>
                )
              })
            )}
          </div>

          <div className="reception-auto-slot">
            <span>Avtomatik navbat vaqti</span>
            <strong>{slots[0] ? `${String(slots[0].start_time).slice(0, 5)} - ${String(slots[0].end_time).slice(0, 5)}` : (form.doctor ? "Bo'sh vaqt topilmadi" : 'Doktor tanlang')}</strong>
            <small>Doktorning belgilangan intervali bo'yicha</small>
          </div>

          <button type="submit" disabled={!form.slot_id || form.specialty_price_ids.length === 0}>Navbatga yozish</button>
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
              <div className="reception-row-actions"><b>{Number(item.amount).toLocaleString()} so'm</b><button type="button" className="reception-cancel-btn" onClick={() => handleReceptionCancel(item.id)} disabled={cancelLoadingId === String(item.id)}>{cancelLoadingId === String(item.id) ? 'Bekor...' : 'Bekor qilish'}</button></div>
            </div>
          ))}
        </div>
        <div>
          <h2>Qabul qilinganlar</h2>
          {(stats?.doctor_accepted_patients || []).map((item) => (
            <div className="reception-patient-row" key={item.id}>
              <strong>#{Number(item.queue_position || 0)} • {item.patient_name}</strong>
              <span>{item.time} • {item.doctor_name}</span>
              <b>{Number(item.amount).toLocaleString()} so'm</b>
            </div>
          ))}
        </div>
      </section>
    </main>
  )
}

export default ReceptionDashboard
