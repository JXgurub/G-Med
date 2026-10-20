import { useEffect, useState } from 'react'
import { patientsApi } from '../services/api'
import './PatientLiverJournal.css'

const SYMPTOMS = [
  ['jaundice', 'Sariqlik'],
  ['abdominal_swelling', 'Qorin shishishi'],
  ['fatigue', 'Charchoq'],
  ['itching', 'Qichishish'],
  ['dark_urine', 'Qorong‘i siydik'],
  ['weight_change', 'Vazn o‘zgarishi'],
  ['bloody_vomit', 'Qon qusish'],
  ['black_stool', 'Qora najas'],
  ['confusion', 'Chalkashlik'],
]
const EMERGENCY_SYMPTOMS = new Set(['bloody_vomit', 'black_stool', 'confusion'])
const emptyForm = {
  symptoms: [],
  weight_kg: '',
  abdominal_circumference_cm: '',
  salt_grams: '',
  fluid_ml: '',
  note: '',
}

const getErrorMessage = (error, fallback = 'Kundalik yozuvini saqlab bo‘lmadi.') => {
  const data = error?.response?.data
  if (typeof data === 'string') return data
  if (data?.detail) return data.detail
  if (data && typeof data === 'object') {
    const first = Object.values(data).find((value) => Array.isArray(value) && value.length)
    if (first) return first[0]
  }
  return fallback
}

const formatDate = (value) => new Date(value).toLocaleString('uz-UZ', {
  day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
})

const PatientLiverJournal = () => {
  const [entries, setEntries] = useState([])
  const [form, setForm] = useState(emptyForm)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const loadEntries = async () => {
    try {
      const response = await patientsApi.getLiverJournal()
      const items = response?.results || response
      setEntries(Array.isArray(items) ? items : [])
      setError('')
    } catch (loadError) {
      setError(getErrorMessage(loadError, 'Kundalik yozuvlarini yuklab bo‘lmadi.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadEntries()
  }, [])

  const emergencySelected = form.symptoms.some((symptom) => EMERGENCY_SYMPTOMS.has(symptom))

  const toggleSymptom = (symptom) => {
    setForm((current) => ({
      ...current,
      symptoms: current.symptoms.includes(symptom)
        ? current.symptoms.filter((item) => item !== symptom)
        : [...current.symptoms, symptom],
    }))
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    const payload = {
      symptoms: form.symptoms,
      note: form.note.trim(),
    }
    for (const key of ['weight_kg', 'abdominal_circumference_cm', 'salt_grams', 'fluid_ml']) {
      if (form[key] !== '') payload[key] = Number(form[key])
    }
    try {
      const entry = await patientsApi.createLiverJournalEntry(payload)
      setEntries((current) => [entry, ...current])
      setForm(emptyForm)
    } catch (saveError) {
      setError(getErrorMessage(saveError))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Bu kundalik yozuvi o‘chirilsinmi?')) return
    try {
      await patientsApi.deleteLiverJournalEntry(id)
      setEntries((current) => current.filter((entry) => entry.id !== id))
    } catch (deleteError) {
      setError(getErrorMessage(deleteError, 'Yozuvni o‘chirib bo‘lmadi.'))
    }
  }

  return (
    <section className="liver-journal">
      <header className="liver-journal-heading">
        <span className="liver-journal-heading-icon" aria-hidden="true">📝</span>
        <div>
          <h2>Kundalik kuzatuv</h2>
          <p>Bugungi belgilar va o‘lchovlarni qayd etib boring.</p>
        </div>
      </header>

      {emergencySelected && (
        <div className="liver-emergency-alert" role="alert" aria-live="assertive">
          <strong>Shoshilinch yordam kerak bo‘lishi mumkin.</strong>
          <span>Qon qusish, qora najas yoki chalkashlik bo‘lsa, darhol 103 ga qo‘ng‘iroq qiling yoki yaqin shoshilinch yordam bo‘limiga boring. Bu yerda javob kutmang.</span>
        </div>
      )}

      {error && <p className="liver-journal-error" role="alert">{error}</p>}

      <form className="liver-journal-form" onSubmit={handleSubmit}>
        <div className="liver-journal-form-heading">
          <strong>Bugungi qayd</strong>
          <span>Ma’lumot kiritish ixtiyoriy. O‘zingiz kuzatmoqchi bo‘lganlarini tanlang.</span>
        </div>
        <fieldset className="liver-symptoms">
          <legend>Belgilar</legend>
          <p className="liver-symptoms-hint">Kuzatgan belgilaringizni belgilang.</p>
          {SYMPTOMS.map(([value, label]) => (
            <label className={EMERGENCY_SYMPTOMS.has(value) ? 'emergency-symptom' : ''} key={value}>
              <input
                type="checkbox"
                checked={form.symptoms.includes(value)}
                onChange={() => toggleSymptom(value)}
              />
              {label}
            </label>
          ))}
        </fieldset>

        <div className="liver-journal-fields">
          <label>
            Vazn (kg)
            <input
              type="number" min="0.1" max="500" step="0.1"
              value={form.weight_kg}
              onChange={(event) => setForm((current) => ({ ...current, weight_kg: event.target.value }))}
            />
          </label>
          <label>
            Qorin aylanasi (cm)
            <input
              type="number" min="1" max="400" step="0.1"
              value={form.abdominal_circumference_cm}
              onChange={(event) => setForm((current) => ({ ...current, abdominal_circumference_cm: event.target.value }))}
            />
          </label>
          <label>
            Tuz miqdori (g, ixtiyoriy)
            <input
              type="number" min="0" max="100" step="0.1"
              value={form.salt_grams}
              onChange={(event) => setForm((current) => ({ ...current, salt_grams: event.target.value }))}
            />
          </label>
          <label>
            Suyuqlik (ml, ixtiyoriy)
            <input
              type="number" min="0" step="1"
              value={form.fluid_ml}
              onChange={(event) => setForm((current) => ({ ...current, fluid_ml: event.target.value }))}
            />
          </label>
        </div>
        <label className="liver-journal-note">
          Izoh (ixtiyoriy)
          <textarea
            rows="2" maxLength="300"
            value={form.note}
            onChange={(event) => setForm((current) => ({ ...current, note: event.target.value }))}
          />
        </label>
        <button type="submit" disabled={saving}>
          {saving ? 'Saqlanmoqda...' : 'Bugungi yozuvni saqlash'}
        </button>
      </form>

      <p className="liver-journal-disclaimer">
        Tuz va suyuqlik bo‘yicha miqdorni shifokoringiz belgilaydi. Sirroz bo‘lsa, cheklovlarni
        o‘zboshimchalik bilan boshlamang yoki o‘zgartirmang.
      </p>

      {loading ? (
        <p className="liver-journal-empty">Yozuvlar yuklanmoqda...</p>
      ) : entries.length === 0 ? (
        <p className="liver-journal-empty">Hozircha kundalik yozuvlari yo‘q.</p>
      ) : (
        <ul className="liver-journal-list">
          {entries.map((entry) => (
            <li key={entry.id}>
              <div>
                <strong>{formatDate(entry.recorded_at)}</strong>
                {entry.symptoms?.length > 0 && (
                  <span>{entry.symptoms.map((symptom) => SYMPTOMS.find(([key]) => key === symptom)?.[1] || symptom).join(', ')}</span>
                )}
                {(entry.weight_kg || entry.abdominal_circumference_cm) && (
                  <span>
                    {entry.weight_kg && `Vazn: ${entry.weight_kg} kg`}
                    {entry.weight_kg && entry.abdominal_circumference_cm && ' · '}
                    {entry.abdominal_circumference_cm && `Qorin: ${entry.abdominal_circumference_cm} cm`}
                  </span>
                )}
                {(entry.salt_grams != null || entry.fluid_ml != null) && (
                  <span>
                    {entry.salt_grams != null && `Tuz: ${entry.salt_grams} g`}
                    {entry.salt_grams != null && entry.fluid_ml != null && ' · '}
                    {entry.fluid_ml != null && `Suyuqlik: ${entry.fluid_ml} ml`}
                  </span>
                )}
                {entry.note && <span>{entry.note}</span>}
              </div>
              <button type="button" onClick={() => handleDelete(entry.id)} aria-label="Yozuvni o‘chirish">
                O‘chirish
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default PatientLiverJournal
