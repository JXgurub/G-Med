import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { usePatient } from '../context/PatientContext'
import { patientsApi } from '../services/api'
import PasswordInput from '../components/PasswordInput'
import DietTables from './DietTables'
import './PatientPortal.css'

const PHARMACY_PRESCRIPTION_KEY = 'gmed-pharmacy-prescription-search'

const formatHistoryDate = (value) => {
  if (!value) return 'Sana ko\'rsatilmagan'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleDateString('uz-UZ', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}

const formatReminderDate = (value) => {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return '—'
  return parsed.toLocaleString('uz-UZ', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const copyTextToClipboard = async (text) => {
  const value = String(text || '').trim()
  if (!value) return false

  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value)
    return true
  }

  const helper = document.createElement('textarea')
  helper.value = value
  helper.setAttribute('readonly', '')
  helper.style.position = 'absolute'
  helper.style.left = '-9999px'
  document.body.appendChild(helper)
  helper.select()
  const copied = document.execCommand('copy')
  document.body.removeChild(helper)
  return copied
}

const PatientPortal = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { patientAuth, patientData, updateDoctorRating, updatePatientProfile, changePatientPassword, logoutPatient } = usePatient()
  const [activeTab, setActiveTab] = useState('history')
  const [profileForm, setProfileForm] = useState({
    bloodType: '',
    birthDate: '',
    weightKg: '',
    heightCm: '',
    drugAllergies: '',
    animalAllergies: ''
  })
  const [savingProfile, setSavingProfile] = useState(false)
  const [medicationReminders, setMedicationReminders] = useState([])
  const [loadingReminders, setLoadingReminders] = useState(false)
  const [savingReminder, setSavingReminder] = useState(false)
  const [reminderError, setReminderError] = useState('')
  const [editingReminderId, setEditingReminderId] = useState(null)
  const [editingReminderScheduleType, setEditingReminderScheduleType] = useState('interval')
  const [editingReminderIntervalHours, setEditingReminderIntervalHours] = useState('8')
  const [editingReminderTimes, setEditingReminderTimes] = useState([])
  const [editingReminderTimeInput, setEditingReminderTimeInput] = useState('08:00')
  const [savingReminderTimes, setSavingReminderTimes] = useState(false)
  const [reminderForm, setReminderForm] = useState({
    medicationName: '',
    scheduleType: 'interval',
    intervalHours: '8',
    dailyTimes: [],
    dailyTimeInput: '08:00'
  })
  const [passwordForm, setPasswordForm] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  })
  const [savingPassword, setSavingPassword] = useState(false)

  const { profile, history, doctors, ratings, lastUpdated } = patientData

  useEffect(() => {
    if (!patientAuth) return undefined
    let cancelled = false
    setLoadingReminders(true)
    patientsApi.getMedicationReminders()
      .then((response) => {
        const reminders = response?.results || response
        if (!cancelled) setMedicationReminders(Array.isArray(reminders) ? reminders : [])
      })
      .catch(() => {
        if (!cancelled) setReminderError('Dori eslatmalarini yuklab bo‘lmadi. Sahifani yangilang.')
      })
      .finally(() => {
        if (!cancelled) setLoadingReminders(false)
      })
    return () => { cancelled = true }
  }, [patientAuth])

  useEffect(() => {
    if (!patientAuth) {
      navigate('/patient-login', { replace: true })
    }
  }, [patientAuth, navigate])

  useEffect(() => {
    const handleLizaAction = (event) => {
      if (!patientAuth || event.detail?.action !== 'open_profile') return
      setActiveTab('profile')
      window.requestAnimationFrame(() => {
        document.querySelector('.profile-forms-stack')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      })
    }
    window.addEventListener('gmed:liza-action', handleLizaAction)
    return () => window.removeEventListener('gmed:liza-action', handleLizaAction)
  }, [patientAuth])

  useEffect(() => {
    if (!patientAuth || new URLSearchParams(location.search).get('tab') !== 'profile') return
    setActiveTab('profile')
    window.requestAnimationFrame(() => {
      document.querySelector('.profile-forms-stack')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }, [location.search, patientAuth])

  useEffect(() => {
    if (!profile) return
    setProfileForm({
      bloodType: profile.bloodType ?? '',
      birthDate: profile.birthDate ?? '',
      weightKg: profile.weightKg ?? '',
      heightCm: profile.heightCm ?? '',
      drugAllergies: profile.drugAllergies ?? '',
      animalAllergies: profile.animalAllergies ?? ''
    })
  }, [profile])

  if (!patientAuth) {
    return null
  }

  const renderStars = (doctorId) => {
    const currentRating = ratings[doctorId]?.value || ratings[doctorId] || 0

    return Array.from({ length: 5 }).map((_, index) => {
      const value = index + 1
      const isActive = value <= currentRating

      return (
        <button
          key={`${doctorId}-${value}`}
          type="button"
          className={`rating-star ${isActive ? 'active' : ''}`}
          aria-label={`${value} yulduz`}
          onClick={() => updateDoctorRating(doctorId, value)}
        >
          ★
        </button>
      )
    })
  }

  const handleProfileSave = async (e) => {
    e.preventDefault()
    setSavingProfile(true)
    try {
      await updatePatientProfile(profileForm)
      alert('Profil maʼlumotlari saqlandi ✅')
    } catch (error) {
      const detail = error?.response?.data
      const message = typeof detail === 'string' ? detail : 'Profilni saqlashda xatolik yuz berdi'
      alert(message)
    } finally {
      setSavingProfile(false)
    }
  }

  const handleReminderCreate = async (event) => {
    event.preventDefault()
    if (reminderForm.scheduleType === 'daily' && reminderForm.dailyTimes.length === 0) {
      setReminderError('Kamida bitta aniq eslatma vaqtini qo‘shing.')
      return
    }
    setSavingReminder(true)
    setReminderError('')
    try {
      const reminder = await patientsApi.createMedicationReminder({
        medication_name: reminderForm.medicationName.trim(),
        interval_hours: reminderForm.scheduleType === 'interval'
          ? Number(reminderForm.intervalHours)
          : null,
        daily_times: reminderForm.scheduleType === 'daily' ? reminderForm.dailyTimes : []
      })
      setMedicationReminders((current) => [...current, reminder].sort(
        (first, second) => new Date(first.next_reminder_at || first.next_scheduled_reminder_at)
          - new Date(second.next_reminder_at || second.next_scheduled_reminder_at)
      ))
      setReminderForm({
        medicationName: '',
        scheduleType: 'interval',
        intervalHours: '8',
        dailyTimes: [],
        dailyTimeInput: '08:00'
      })
    } catch (error) {
      const details = error?.response?.data
      setReminderError(
        details?.medication_name?.[0]
        || details?.interval_hours?.[0]
        || details?.daily_times?.[0]
        || details?.non_field_errors?.[0]
        || details?.detail
        || 'Dori eslatmasini saqlashda xatolik yuz berdi.'
      )
    } finally {
      setSavingReminder(false)
    }
  }

  const handleAddReminderTime = () => {
    const time = reminderForm.dailyTimeInput
    if (!time || reminderForm.dailyTimes.includes(time)) return
    setReminderForm((current) => ({
      ...current,
      dailyTimes: [...current.dailyTimes, time].sort()
    }))
  }

  const handleRemoveReminderTime = (time) => {
    setReminderForm((current) => ({
      ...current,
      dailyTimes: current.dailyTimes.filter((item) => item !== time)
    }))
  }

  const startEditingReminderTimes = (reminder) => {
    setReminderError('')
    setEditingReminderId(reminder.id)
    setEditingReminderScheduleType(reminder.interval_hours == null ? 'daily' : 'interval')
    setEditingReminderIntervalHours(String(reminder.interval_hours || 8))
    setEditingReminderTimes(reminder.daily_times || [])
    setEditingReminderTimeInput('08:00')
  }

  const handleSaveReminderTimes = async (reminderId) => {
    setSavingReminderTimes(true)
    setReminderError('')
    try {
      const updated = await patientsApi.updateMedicationReminder(reminderId, {
        interval_hours: editingReminderScheduleType === 'interval'
          ? Number(editingReminderIntervalHours)
          : null,
        daily_times: editingReminderScheduleType === 'daily' ? editingReminderTimes : []
      })
      setMedicationReminders((current) => current.map((item) => item.id === updated.id ? updated : item))
      setEditingReminderId(null)
      setEditingReminderTimes([])
    } catch (error) {
      const details = error?.response?.data
      setReminderError(
        details?.daily_times?.[0]
        || details?.interval_hours?.[0]
        || details?.non_field_errors?.[0]
        || details?.detail
        || 'Dori ichish vaqtlarini saqlab bo‘lmadi.'
      )
    } finally {
      setSavingReminderTimes(false)
    }
  }

  const handleReminderToggle = async (reminder) => {
    setReminderError('')
    try {
      const updated = await patientsApi.updateMedicationReminder(reminder.id, {
        is_active: !reminder.is_active
      })
      setMedicationReminders((current) => current.map((item) => item.id === updated.id ? updated : item))
    } catch (error) {
      setReminderError(error?.response?.data?.detail || 'Eslatma holatini o‘zgartirib bo‘lmadi.')
    }
  }

  const handleReminderDelete = async (reminder) => {
    if (!window.confirm(`“${reminder.medication_name}” eslatmasini o‘chirmoqchimisiz?`)) return
    setReminderError('')
    try {
      await patientsApi.deleteMedicationReminder(reminder.id)
      setMedicationReminders((current) => current.filter((item) => item.id !== reminder.id))
    } catch (error) {
      setReminderError(error?.response?.data?.detail || 'Eslatmani o‘chirib bo‘lmadi.')
    }
  }

  const handlePasswordSave = async (e) => {
    e.preventDefault()

    if (!passwordForm.currentPassword || !passwordForm.newPassword || !passwordForm.confirmPassword) {
      alert('Iltimos, barcha parol maydonlarini to‘ldiring')
      return
    }

    if (passwordForm.newPassword.length < 6) {
      alert('Yangi parol kamida 6 ta belgidan iborat bo‘lishi kerak')
      return
    }

    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      alert('Yangi parol va tasdiqlash paroli mos emas')
      return
    }

    setSavingPassword(true)
    try {
      await changePatientPassword(passwordForm.currentPassword, passwordForm.newPassword)
      alert('Parol muvaffaqiyatli yangilandi ✅')
      setPasswordForm({
        currentPassword: '',
        newPassword: '',
        confirmPassword: ''
      })
    } catch (error) {
      const detail = error?.response?.data
      const firstFieldError = detail && typeof detail === 'object'
        ? Object.values(detail).find((value) => Array.isArray(value) && value.length > 0)?.[0]
        : null
      const message = firstFieldError || detail?.detail || 'Parolni yangilashda xatolik yuz berdi'
      alert(message)
    } finally {
      setSavingPassword(false)
    }
  }

  const handleCopyMedicines = async (entry) => {
    const medicinesText = (entry.medications || []).join('\n')
    if (!medicinesText) {
      alert('Bu yozuvda dorilar ro\'yxati yo\'q')
      return
    }

    try {
      const copied = await copyTextToClipboard(medicinesText)
      if (!copied) throw new Error('copy_failed')
      alert('Dorilar ro\'yxati nusxalandi ✅')
    } catch (error) {
      alert('Dorilar ro\'yxatini nusxalab bo\'lmadi')
    }
  }

  const handleSendMedicinesToPharmacy = (entry) => {
    if (!entry.medications || entry.medications.length === 0) {
      alert('Bu yozuvda dorilar ro\'yxati yo\'q')
      return
    }

    try {
      localStorage.setItem(PHARMACY_PRESCRIPTION_KEY, JSON.stringify({
        medicines: entry.medications,
        diagnosis: entry.diagnosis,
        complaint: entry.complaint,
        date: entry.date,
        doctorName: entry.doctorName,
        clinic: entry.clinic,
      }))
      navigate('/#pharmacy-section')
    } catch (error) {
      alert('Dorilar ro\'yxatini dorixonaga yuborishda xatolik yuz berdi')
    }
  }

  return (
    <div className="patient-portal">
      <header className="patient-hero">
        <div className="patient-hero-content">
          <div className="patient-profile">
            <div className="patient-avatar">
              {profile.fullName.split(' ').map(name => name[0]).join('')}
            </div>
            <div>
              <p className="patient-tag">Bemor sahifasi</p>
              <h1>{profile.fullName}</h1>
              <p className="patient-meta">Email: {profile.email || patientAuth?.email || '—'} · {profile.phone}</p>
            </div>
          </div>
          <div className="patient-status">
            <div className="status-card">
              <span>Oxirgi yangilanish</span>
              <strong>{lastUpdated}</strong>
            </div>
            <div className="status-card">
              <span>Kasallik tarixi</span>
              <strong>{history.length} ta yozuv</strong>
            </div>
          </div>
        </div>
      </header>

      <section className="patient-content">
        <div className="tabs">
          <button
            type="button"
            className={`tab-btn ${activeTab === 'history' ? 'active' : ''}`}
            onClick={() => setActiveTab('history')}
          >
            Kasallik tarixi
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'ratings' ? 'active' : ''}`}
            onClick={() => setActiveTab('ratings')}
          >
            Doktor baholash
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'medication-reminders' ? 'active' : ''}`}
            onClick={() => setActiveTab('medication-reminders')}
          >
            Dorilarni eslatish 💊
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'diet-tables' ? 'active' : ''}`}
            onClick={() => setActiveTab('diet-tables')}
          >
            Parhez stollari 🥗
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'profile' ? 'active' : ''}`}
            onClick={() => setActiveTab('profile')}
          >
            Profilim
          </button>
        </div>

        {activeTab === 'history' && (
          <div className="history-grid">
            {history.length > 0 ? history.map((entry) => (
              <article key={entry.id} className="history-card history-card-modern">
                <div className="history-header">
                  <span className="history-date">{formatHistoryDate(entry.date)}</span>
                  <span className="history-pill">{entry.medications?.length || 0} ta dori</span>
                </div>

                <div className="history-title-block">
                  <h3 className="history-diagnosis">{entry.diagnosis}</h3>
                  <p className="history-subtitle">Kasallik bo'yicha doktor xulosasi va resept tafsilotlari</p>
                </div>

                <div className="history-complaint-card">
                  <span className="history-section-kicker">Bemor shikoyati</span>
                  <p>{entry.complaint || 'Shikoyat kiritilmagan'}</p>
                </div>

                <div className="history-detail-grid">
                  <div className="history-detail-card history-detail-card-doctor">
                    <span className="history-detail-label">Tashxis qo'ygan shifokor</span>
                    <strong>{entry.doctorName}</strong>
                  </div>
                  {entry.doctorSpecialization && (
                    <div className="history-detail-card">
                      <span className="history-detail-label">Ixtisoslash</span>
                      <strong>{entry.doctorSpecialization}</strong>
                    </div>
                  )}
                  <div className="history-detail-card">
                    <span className="history-detail-label">Klinika</span>
                    <strong>{entry.clinic}</strong>
                  </div>
                </div>

                <div className="history-medications history-medications-panel">
                  <div className="history-medications-header">
                    <div>
                      <p>Yozilgan dorilar</p>
                      <span className="history-medication-hint">Ro'yxatni nusxalash yoki dorixona qidiruviga yuborish mumkin</span>
                    </div>
                    {entry.medications && entry.medications.length > 0 ? (
                      <div className="history-medication-actions">
                        <button
                          type="button"
                          className="history-action-btn history-action-btn-ghost"
                          onClick={() => handleCopyMedicines(entry)}
                        >
                          Nusxa olish
                        </button>
                        <button
                          type="button"
                          className="history-action-btn history-action-btn-primary"
                          onClick={() => handleSendMedicinesToPharmacy(entry)}
                        >
                          Dorixonadan qidirish
                        </button>
                      </div>
                    ) : null}
                  </div>

                  {entry.medications && entry.medications.length > 0 ? (
                    <div className="medication-tags">
                      {entry.medications.map((medication) => (
                        <span key={`${entry.id}-${medication}`} className="medication-tag">
                          {medication}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <div className="history-empty-inline">Bu yozuv uchun dori tavsiyasi kiritilmagan</div>
                  )}
                </div>
              </article>
            )) : (
              <div className="history-empty-state">
                <h3>Kasallik tarixi hali shakllanmagan</h3>
                <p>Ko'riklar tugagach, tashxis, shikoyat va yozilgan dorilar shu yerda ko'rinadi.</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'ratings' && (
          <div className="ratings-grid">
            {doctors.map((doctor) => (
              <article key={doctor.id} className="rating-card">
                <div className="rating-header">
                  <div className="doctor-avatar">
                    {doctor.name.split(' ').slice(1, 3).map(part => part[0]).join('')}
                  </div>
                  <div>
                    <h3>{doctor.name}</h3>
                    <p>{doctor.specialization} · {doctor.clinic}</p>
                  </div>
                </div>
                <div className="rating-meta">
                  <span>Umumiy baho: {doctor.rating}</span>
                </div>
                <div className="rating-stars">
                  {renderStars(doctor.id)}
                </div>
                <p className="rating-note">
                  Sizning bahoingiz: {ratings[doctor.id]?.value || ratings[doctor.id] ? `${ratings[doctor.id]?.value || ratings[doctor.id]}/5` : 'Baho berilmagan'}
                </p>
              </article>
            ))}
          </div>
        )}

        {activeTab === 'medication-reminders' && (
          <section className="patient-profile-form medication-reminders">
            <div className="reminders-heading">
              <div>
                <h3 className="password-form-title">Dorilarni eslatish 💊</h3>
                <p>Dori ichish tartibini tanlang: interval bo‘yicha yoki har kuni belgilangan aniq vaqtlarda. Ikkalasi bir vaqtda qo‘llanmaydi.</p>
              </div>
              <span className="reminder-push-status">
                Telefon bildirishnomalari uchun brauzer ruxsati kerak
              </span>
            </div>

            {reminderError && <p className="reminder-error" role="alert">{reminderError}</p>}

            <form className="profile-grid reminder-form" onSubmit={handleReminderCreate}>
              <div className="form-group">
                <label htmlFor="reminder-medication-name">Dori nomi</label>
                <input
                  id="reminder-medication-name"
                  type="text"
                  value={reminderForm.medicationName}
                  onChange={(event) => setReminderForm((current) => ({ ...current, medicationName: event.target.value }))}
                  placeholder="Masalan: Alsetro"
                  maxLength="255"
                  required
                />
              </div>
              <fieldset className="reminder-schedule-choice">
                <legend>Eslatma tartibi</legend>
                <label>
                  <input
                    type="radio"
                    name="reminder-schedule-type"
                    value="interval"
                    checked={reminderForm.scheduleType === 'interval'}
                    onChange={() => setReminderForm((current) => ({ ...current, scheduleType: 'interval' }))}
                  />
                  <span>Har necha soatda</span>
                </label>
                <label>
                  <input
                    type="radio"
                    name="reminder-schedule-type"
                    value="daily"
                    checked={reminderForm.scheduleType === 'daily'}
                    onChange={() => setReminderForm((current) => ({ ...current, scheduleType: 'daily' }))}
                  />
                  <span>Har kuni aniq vaqtda</span>
                </label>
              </fieldset>
              {reminderForm.scheduleType === 'interval' ? (
                <div className="form-group">
                  <label htmlFor="reminder-interval-hours">Ichish oralig‘i (soat)</label>
                  <input
                    id="reminder-interval-hours"
                    type="number"
                    value={reminderForm.intervalHours}
                    onChange={(event) => setReminderForm((current) => ({ ...current, intervalHours: event.target.value }))}
                    min="1"
                    max="168"
                    step="1"
                    required
                  />
                </div>
              ) : (
                <div className="form-group reminder-daily-times-field">
                  <label htmlFor="reminder-daily-time">Kunlik ichish vaqtlari</label>
                  <div className="reminder-time-input-row">
                    <input
                      id="reminder-daily-time"
                      type="time"
                      value={reminderForm.dailyTimeInput}
                      onChange={(event) => setReminderForm((current) => ({
                        ...current,
                        dailyTimeInput: event.target.value
                      }))}
                    />
                    <button
                      type="button"
                      className="history-action-btn history-action-btn-ghost"
                      onClick={handleAddReminderTime}
                      disabled={!reminderForm.dailyTimeInput || reminderForm.dailyTimes.includes(reminderForm.dailyTimeInput)}
                    >
                      Vaqt qo‘shish
                    </button>
                  </div>
                  {reminderForm.dailyTimes.length > 0 ? (
                    <div className="reminder-time-list" aria-label="Tanlangan kunlik eslatma vaqtlari">
                      {reminderForm.dailyTimes.map((time) => (
                        <span className="reminder-time-chip" key={time}>
                          🕒 {time}
                          <button
                            type="button"
                            aria-label={`${time} vaqtini olib tashlash`}
                            onClick={() => handleRemoveReminderTime(time)}
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="reminder-time-hint">Masalan, har kuni 08:00 va 20:00 da.</span>
                  )}
                </div>
              )}
              <div className="reminder-form-action">
                <button type="submit" className="save-profile-btn" disabled={savingReminder}>
                  {savingReminder ? 'Saqlanmoqda...' : 'Eslatma qo‘shish'}
                </button>
              </div>
            </form>

            {loadingReminders ? (
              <p className="reminder-empty">Eslatmalar yuklanmoqda...</p>
            ) : medicationReminders.length ? (
              <div className="reminder-list">
                {medicationReminders.map((reminder) => (
                  <article className={`reminder-card ${reminder.is_active ? '' : 'paused'}`} key={reminder.id}>
                    <div className="reminder-card-info">
                      <strong>💊 {reminder.medication_name}</strong>
                      {reminder.interval_hours != null ? (
                        <span>Har {reminder.interval_hours} soatda</span>
                      ) : (
                        <>
                          <span>Har kuni: {reminder.daily_times?.join(', ')}</span>
                          <span>Keyingi eslatma: {formatReminderDate(reminder.next_scheduled_reminder_at)}</span>
                        </>
                      )}
                      {reminder.interval_hours != null && (
                        <span>Keyingi eslatma: {reminder.is_active ? formatReminderDate(reminder.next_reminder_at) : 'Eslatma vaqtincha to‘xtatilgan'}</span>
                      )}
                      {!reminder.is_active && reminder.interval_hours == null && (
                        <span>Eslatma vaqtincha to‘xtatilgan</span>
                      )}
                    </div>
                    <div className="reminder-actions">
                      <button
                        type="button"
                        className="history-action-btn history-action-btn-ghost"
                        onClick={() => editingReminderId === reminder.id
                          ? setEditingReminderId(null)
                          : startEditingReminderTimes(reminder)}
                      >
                        {editingReminderId === reminder.id ? 'Yopish' : 'Soatlarni sozlash'}
                      </button>
                      <button type="button" className="history-action-btn history-action-btn-ghost" onClick={() => handleReminderToggle(reminder)}>
                        {reminder.is_active ? 'To‘xtatish' : 'Davom ettirish'}
                      </button>
                      <button type="button" className="history-action-btn reminder-delete-btn" onClick={() => handleReminderDelete(reminder)}>
                        O‘chirish
                      </button>
                    </div>
                    {editingReminderId === reminder.id && (
                      <div className="reminder-schedule-editor">
                        <strong>Eslatma tartibi</strong>
                        <div className="reminder-schedule-choice">
                          <label>
                            <input
                              type="radio"
                              name={`reminder-schedule-type-${reminder.id}`}
                              value="interval"
                              checked={editingReminderScheduleType === 'interval'}
                              onChange={() => setEditingReminderScheduleType('interval')}
                            />
                            <span>Har necha soatda</span>
                          </label>
                          <label>
                            <input
                              type="radio"
                              name={`reminder-schedule-type-${reminder.id}`}
                              value="daily"
                              checked={editingReminderScheduleType === 'daily'}
                              onChange={() => setEditingReminderScheduleType('daily')}
                            />
                            <span>Har kuni aniq vaqtda</span>
                          </label>
                        </div>
                        {editingReminderScheduleType === 'interval' ? (
                          <div className="form-group">
                            <label htmlFor={`reminder-edit-interval-${reminder.id}`}>Ichish oralig‘i (soat)</label>
                            <input
                              id={`reminder-edit-interval-${reminder.id}`}
                              type="number"
                              min="1"
                              max="168"
                              step="1"
                              value={editingReminderIntervalHours}
                              onChange={(event) => setEditingReminderIntervalHours(event.target.value)}
                            />
                          </div>
                        ) : (
                        <>
                        <p>Kunlik eslatma vaqtlarini tanlang. Toshkent vaqti bo‘yicha ishlaydi.</p>
                        <div className="reminder-time-input-row">
                          <input
                            type="time"
                            aria-label="Yangi kunlik eslatma vaqti"
                            value={editingReminderTimeInput}
                            onChange={(event) => setEditingReminderTimeInput(event.target.value)}
                          />
                          <button
                            type="button"
                            className="history-action-btn history-action-btn-ghost"
                            disabled={!editingReminderTimeInput || editingReminderTimes.includes(editingReminderTimeInput)}
                            onClick={() => {
                              setEditingReminderTimes((current) => [...current, editingReminderTimeInput].sort())
                            }}
                          >
                            Vaqt qo‘shish
                          </button>
                        </div>
                        <div className="reminder-time-list">
                          {editingReminderTimes.map((time) => (
                            <span className="reminder-time-chip" key={time}>
                              🕒 {time}
                              <button
                                type="button"
                                aria-label={`${time} vaqtini olib tashlash`}
                                onClick={() => setEditingReminderTimes((current) => current.filter((item) => item !== time))}
                              >
                                ×
                              </button>
                            </span>
                          ))}
                        </div>
                        </>
                        )}
                        <div className="reminder-schedule-actions">
                          <button
                            type="button"
                            className="history-action-btn history-action-btn-primary"
                            disabled={
                              savingReminderTimes
                              || (editingReminderScheduleType === 'daily' && editingReminderTimes.length === 0)
                              || (editingReminderScheduleType === 'interval'
                                && (!editingReminderIntervalHours
                                  || Number(editingReminderIntervalHours) < 1
                                  || Number(editingReminderIntervalHours) > 168))
                            }
                            onClick={() => handleSaveReminderTimes(reminder.id)}
                          >
                            {savingReminderTimes ? 'Saqlanmoqda...' : 'Vaqtlarni saqlash'}
                          </button>
                          <span className="reminder-time-hint">
                            Vaqtlar: {editingReminderTimes.length ? editingReminderTimes.join(', ') : 'tanlanmagan'}
                          </span>
                        </div>
                      </div>
                    )}
                  </article>
                ))}
              </div>
            ) : (
              <p className="reminder-empty">Hozircha dori eslatmalari yo‘q. Birinchi eslatmani qo‘shing.</p>
            )}
            <p className="reminder-disclaimer">Eslatmalar faqat telefoningizda bildirishnomalarga ruxsat berilganida yuboriladi. Dori qabul qilish tartibini shifokor tavsiyasiga muvofiq belgilang.</p>
          </section>
        )}

        <div hidden={activeTab !== 'diet-tables'}>
          <DietTables />
        </div>

        {activeTab === 'profile' && (
          <div className="profile-forms-stack">
            <div className="patient-account-actions">
              <div>
                <strong>Hisobingiz</strong>
                <p>Chiqmaguningizcha ushbu qurilmada profilingiz ochiq qoladi.</p>
              </div>
              <button
                type="button"
                className="patient-logout-button"
                onClick={() => {
                  logoutPatient()
                  navigate('/patient-login', { replace: true })
                }}
              >
                Chiqish
              </button>
            </div>

            <form className="patient-profile-form" onSubmit={handleProfileSave}>
              <div className="profile-grid">
                <div className="form-group">
                  <label>Qon guruhi</label>
                  <select
                    value={profileForm.bloodType}
                    onChange={(e) => setProfileForm((prev) => ({ ...prev, bloodType: e.target.value }))}
                  >
                    <option value="">Tanlang</option>
                    <option value="O+">O+</option>
                    <option value="O-">O-</option>
                    <option value="A+">A+</option>
                    <option value="A-">A-</option>
                    <option value="B+">B+</option>
                    <option value="B-">B-</option>
                    <option value="AB+">AB+</option>
                    <option value="AB-">AB-</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Tug'ilgan sana (yil-oy-kun)</label>
                  <input
                    type="date"
                    value={profileForm.birthDate}
                    onChange={(e) => setProfileForm((prev) => ({ ...prev, birthDate: e.target.value }))}
                  />
                </div>
                <div className="form-group">
                  <label>Vazni (kg)</label>
                  <input
                    type="number"
                    min="0"
                    step="0.1"
                    value={profileForm.weightKg}
                    onChange={(e) => setProfileForm((prev) => ({ ...prev, weightKg: e.target.value }))}
                    placeholder="Masalan: 72.5"
                  />
                </div>
                <div className="form-group">
                  <label>Bo'yi (cm)</label>
                  <input
                    type="number"
                    min="0"
                    step="0.1"
                    value={profileForm.heightCm}
                    onChange={(e) => setProfileForm((prev) => ({ ...prev, heightCm: e.target.value }))}
                    placeholder="Masalan: 175"
                  />
                </div>
                <div className="form-group full-width">
                  <label>Dorilarga allergiya</label>
                  <textarea
                    rows="3"
                    value={profileForm.drugAllergies}
                    onChange={(e) => setProfileForm((prev) => ({ ...prev, drugAllergies: e.target.value }))}
                    placeholder="Qaysi dorilarga allergiyangiz borligini kiriting"
                  />
                </div>
                <div className="form-group full-width">
                  <label>Hayvonlarga allergiya</label>
                  <textarea
                    rows="3"
                    value={profileForm.animalAllergies}
                    onChange={(e) => setProfileForm((prev) => ({ ...prev, animalAllergies: e.target.value }))}
                    placeholder="Qaysi hayvonlarga allergiyangiz borligini kiriting"
                  />
                </div>
              </div>

              <button type="submit" className="save-profile-btn" disabled={savingProfile}>
                {savingProfile ? 'Saqlanmoqda...' : 'Profilni saqlash'}
              </button>
            </form>

            <form className="patient-profile-form password-change-form" onSubmit={handlePasswordSave}>
              <h3 className="password-form-title">Parolni o‘zgartirish</h3>
              <div className="profile-grid">
                <div className="form-group">
                  <label>Joriy parol</label>
                  <PasswordInput
                    value={passwordForm.currentPassword}
                    onChange={(e) => setPasswordForm((prev) => ({ ...prev, currentPassword: e.target.value }))}
                    placeholder="Joriy parolingiz"
                    autoComplete="current-password"
                  />
                </div>
                <div className="form-group">
                  <label>Yangi parol</label>
                  <PasswordInput
                    value={passwordForm.newPassword}
                    onChange={(e) => setPasswordForm((prev) => ({ ...prev, newPassword: e.target.value }))}
                    placeholder="Kamida 6 ta belgi"
                    autoComplete="new-password"
                  />
                </div>
                <div className="form-group">
                  <label>Yangi parolni tasdiqlang</label>
                  <PasswordInput
                    value={passwordForm.confirmPassword}
                    onChange={(e) => setPasswordForm((prev) => ({ ...prev, confirmPassword: e.target.value }))}
                    placeholder="Yangi parolni qayta kiriting"
                    autoComplete="new-password"
                  />
                </div>
              </div>

              <button type="submit" className="save-profile-btn" disabled={savingPassword}>
                {savingPassword ? 'Yangilanmoqda...' : 'Parolni yangilash'}
              </button>
            </form>
          </div>
        )}

        <div className="patient-footer-note">
          Kasallik tarixi faqat ko'rish uchun. Profilim bo'limida esa shaxsiy sog'liq ma'lumotlarini yangilashingiz mumkin.
        </div>
      </section>
    </div>
  )
}

export default PatientPortal
