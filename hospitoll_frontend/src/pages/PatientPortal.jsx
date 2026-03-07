import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePatient } from '../context/PatientContext'
import PasswordInput from '../components/PasswordInput'
import './PatientPortal.css'

const PatientPortal = () => {
  const navigate = useNavigate()
  const { patientAuth, patientData, updateDoctorRating, updatePatientProfile, changePatientPassword } = usePatient()
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
  const [passwordForm, setPasswordForm] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  })
  const [savingPassword, setSavingPassword] = useState(false)

  const { profile, history, doctors, ratings, lastUpdated } = patientData

  useEffect(() => {
    if (!patientAuth) {
      navigate('/patient-login', { replace: true })
    }
  }, [patientAuth, navigate])

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
              <p className="patient-meta">Email: {profile.email || patientAuth?.email || '—'} · Pasport: {profile.passportId} · {profile.phone}</p>
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
            className={`tab-btn ${activeTab === 'profile' ? 'active' : ''}`}
            onClick={() => setActiveTab('profile')}
          >
            Profilim
          </button>
        </div>

        {activeTab === 'history' && (
          <div className="history-grid">
            {history.map((entry) => (
              <article key={entry.id} className="history-card">
                <div className="history-header">
                  <span className="history-date">{entry.date}</span>
                  <span className="history-diagnosis">{entry.diagnosis}</span>
                </div>
                <div className="history-body">
                  <div className="history-row doctor-row">
                    <span>👨‍⚕️ Tashxis qo'ygan shifokor</span>
                    <strong>{entry.doctorName}</strong>
                  </div>
                  {entry.doctorSpecialization && (
                    <div className="history-row specialization-row">
                      <span>Ixtisoslash</span>
                      <strong>{entry.doctorSpecialization}</strong>
                    </div>
                  )}
                  <div className="history-row">
                    <span>Klinika</span>
                    <strong>{entry.clinic}</strong>
                  </div>
                  {entry.medications && entry.medications.length > 0 && (
                    <div className="history-medications">
                      <p>💊 Yozilgan dorilar</p>
                      <div className="medication-tags">
                        {entry.medications.map((medication) => (
                          <span key={medication} className="medication-tag">
                            {medication}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </article>
            ))}
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

        {activeTab === 'profile' && (
          <div className="profile-forms-stack">
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
