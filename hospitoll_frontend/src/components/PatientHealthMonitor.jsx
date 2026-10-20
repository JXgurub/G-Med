import { useEffect, useState } from 'react'
import { patientsApi } from '../services/api'
import './PatientHealthMonitor.css'

const SEVERITY_LABELS = {
  normal: 'Normal',
  attention: 'E’tibor talab',
  urgent: 'Shoshilinch',
}

const CONTEXT_LABELS = {
  fasting: 'Nahorga',
  after_meal: 'Ovqatdan keyin',
  random: 'Tasodifiy vaqt',
}

const LIVER_METRICS = {
  liver_alt: { label: 'ALT', suggestedUnit: 'U/L' },
  liver_ast: { label: 'AST', suggestedUnit: 'U/L' },
  liver_bilirubin: { label: 'Bilirubin', suggestedUnit: 'µmol/L' },
  liver_albumin: { label: 'Albumin', suggestedUnit: 'g/L' },
  liver_ggt: { label: 'GGT', suggestedUnit: 'U/L' },
  liver_viral_load: { label: 'Virus yuklamasi', suggestedUnit: 'IU/mL' },
}

const METRIC_LABELS = {
  blood_pressure: 'Qon bosimi',
  blood_glucose: 'Qon qandi',
  ...Object.fromEntries(Object.entries(LIVER_METRICS).map(([key, metric]) => [key, metric.label])),
}

const FILTERS = [
  ['', 'Hammasi'],
  ['blood_pressure', 'Qon bosimi'],
  ['blood_glucose', 'Qon qandi'],
  ...Object.entries(LIVER_METRICS).map(([key, metric]) => [key, metric.label]),
]

const getErrorMessage = (error, fallback) => {
  const data = error?.response?.data
  if (typeof data === 'string') return data
  if (data?.detail) return data.detail
  if (data && typeof data === 'object') {
    const first = Object.values(data).find((value) => Array.isArray(value) && value.length)
    if (first) return first[0]
  }
  return fallback
}

const formatDateTime = (value) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('uz-UZ', {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  })
}

const emptyForm = {
  metric: 'blood_pressure',
  systolic: '',
  diastolic: '',
  glucose_mmol: '',
  glucose_context: 'fasting',
  value: '',
  unit: '',
  reference_min: '',
  reference_max: '',
  measured_at: '',
  note: '',
  share_with_care_team: true,
}

const readingValue = (reading) => (
  reading.metric === 'blood_pressure'
    ? `${reading.systolic}/${reading.diastolic} mm sim. ust.`
    : reading.metric === 'blood_glucose'
      ? `${reading.glucose_mmol} mmol/L · ${CONTEXT_LABELS[reading.glucose_context] || ''}`
      : `${reading.value} ${reading.unit}`
)

const LiverTrendChart = ({ metric, readings }) => {
  const series = readings
    .filter((reading) => reading.metric === metric)
    .sort((first, second) => new Date(first.measured_at) - new Date(second.measured_at))
    .slice(-12)
  if (!series.length) return null

  const values = series.map((reading) => Number(reading.value))
  const min = Math.min(...values)
  const max = Math.max(...values)
  const spread = max - min || 1
  const points = series.map((reading, index) => ({
    x: series.length === 1 ? 200 : 24 + (index * 352) / (series.length - 1),
    y: 108 - ((Number(reading.value) - min) / spread) * 78,
    reading,
  }))
  const path = points.map((point, index) => `${index ? 'L' : 'M'} ${point.x} ${point.y}`).join(' ')

  return (
    <article className="liver-trend-card">
      <div className="liver-trend-title">
        <strong>{METRIC_LABELS[metric]}</strong>
        <span>{series[series.length - 1].unit}</span>
      </div>
      <svg viewBox="0 0 400 145" role="img" aria-label={`${METRIC_LABELS[metric]} natijalari vaqt bo‘yicha`}>
        <line x1="20" y1="110" x2="380" y2="110" />
        {points.length > 1 && <path className="liver-trend-line" d={path} />}
        {points.map(({ x, y, reading }) => (
          <circle key={reading.id} cx={x} cy={y} r="4">
            <title>{`${reading.value} ${reading.unit} · ${formatDateTime(reading.measured_at)}`}</title>
          </circle>
        ))}
        {points.map(({ x, reading }) => (
          <text key={`${reading.id}-date`} x={x} y="132" textAnchor="middle">
            {new Date(reading.measured_at).toLocaleDateString('uz-UZ', { day: 'numeric', month: 'short' })}
          </text>
        ))}
      </svg>
    </article>
  )
}

const PatientHealthMonitor = () => {
  const [readings, setReadings] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [lastResult, setLastResult] = useState(null)
  const [filter, setFilter] = useState('')
  const [form, setForm] = useState(emptyForm)

  const load = async (metric = filter) => {
    try {
      const response = await patientsApi.getHealthReadings(metric ? { metric } : undefined)
      const items = response?.results || response
      setReadings(Array.isArray(items) ? items : [])
      setError('')
    } catch (loadError) {
      setError(getErrorMessage(loadError, 'Ko‘rsatkichlarni yuklab bo‘lmadi.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load(filter)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter])

  const setField = (name, value) => setForm((current) => ({ ...current, [name]: value }))

  const handleSubmit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    const payload = {
      metric: form.metric,
      note: form.note,
      share_with_care_team: form.share_with_care_team,
    }
    if (form.measured_at) payload.measured_at = new Date(form.measured_at).toISOString()
    if (form.metric === 'blood_pressure') {
      payload.systolic = Number(form.systolic)
      payload.diastolic = Number(form.diastolic)
    } else if (form.metric === 'blood_glucose') {
      payload.glucose_mmol = form.glucose_mmol
      payload.glucose_context = form.glucose_context
    } else {
      payload.value = form.value
      payload.unit = form.unit.trim()
      payload.reference_min = form.reference_min === '' ? null : form.reference_min
      payload.reference_max = form.reference_max === '' ? null : form.reference_max
    }
    try {
      const created = await patientsApi.createHealthReading(payload)
      setLastResult(created)
      setForm((current) => ({
        ...emptyForm,
        metric: current.metric,
        unit: LIVER_METRICS[current.metric]?.suggestedUnit || '',
        share_with_care_team: current.share_with_care_team,
      }))
      await load(filter)
    } catch (saveError) {
      setError(getErrorMessage(saveError, 'Ko‘rsatkichni saqlab bo‘lmadi.'))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Bu ko‘rsatkich o‘chirilsinmi?')) return
    try {
      await patientsApi.deleteHealthReading(id)
      setReadings((current) => current.filter((item) => item.id !== id))
    } catch (deleteError) {
      setError(getErrorMessage(deleteError, 'O‘chirib bo‘lmadi.'))
    }
  }

  return (
    <div className="health-monitor">
      <div className="health-monitor-header">
        <span className="health-monitor-heading-icon" aria-hidden="true">🧪</span>
        <div>
          <h2>Jigar tahlillari</h2>
          <p>
            Natijalarni tahlil varaqasiga qarab kiriting. Bu kuzatuv tashxis o‘rnini bosmaydi.
          </p>
        </div>
      </div>

      {error && <div className="health-monitor-error">{error}</div>}

      {lastResult && lastResult.severity !== 'normal' && (
        <div className={`health-monitor-banner ${lastResult.severity}`}>
          <strong>{SEVERITY_LABELS[lastResult.severity]}</strong>
          <span>{lastResult.alert_reason}</span>
          <span>
            {lastResult.share_with_care_team
              ? 'Natija shifokoringizga yuborildi. '
              : 'Natija shifokorga yuborilmadi. '}
            {lastResult.severity === 'urgent' &&
              'Shifokor bilan bog‘laning; og‘ir belgilar bo‘lsa 103 ga qo‘ng‘iroq qiling.'}
          </span>
        </div>
      )}
      {lastResult && lastResult.severity === 'normal' && (
        <div className="health-monitor-banner normal">
          <strong>Me’yor doirasida</strong>
          <span>Natija saqlandi.</span>
        </div>
      )}

      <form className="health-monitor-form" onSubmit={handleSubmit}>
        <div className="health-monitor-form-heading health-monitor-wide">
          <strong>Yangi natija qo‘shish</strong>
          <span>O‘lchov turini tanlang va tahlil varaqasidagi ma’lumotlarni kiriting.</span>
        </div>
        <label>
          Ko‘rsatkich turi
          <select
            value={form.metric}
            onChange={(e) => setForm((current) => ({
              ...current,
              metric: e.target.value,
              unit: LIVER_METRICS[e.target.value]?.suggestedUnit || '',
            }))}
          >
            <option value="blood_pressure">Qon bosimi</option>
            <option value="blood_glucose">Qon qandi</option>
            {Object.entries(LIVER_METRICS).map(([value, metric]) => (
              <option key={value} value={value}>{metric.label}</option>
            ))}
          </select>
        </label>

        {form.metric === 'blood_pressure' ? (
          <>
            <label>
              Yuqori (sistolik)
              <input
                type="number" min="50" max="300" required
                value={form.systolic}
                onChange={(e) => setField('systolic', e.target.value)}
              />
            </label>
            <label>
              Pastki (diastolik)
              <input
                type="number" min="30" max="200" required
                value={form.diastolic}
                onChange={(e) => setField('diastolic', e.target.value)}
              />
            </label>
          </>
        ) : form.metric === 'blood_glucose' ? (
          <>
            <label>
              Qand (mmol/L)
              <input
                type="number" step="0.1" min="0.5" max="60" required
                value={form.glucose_mmol}
                onChange={(e) => setField('glucose_mmol', e.target.value)}
              />
            </label>
            <label>
              O‘lchash vaqti
              <select
                value={form.glucose_context}
                onChange={(e) => setField('glucose_context', e.target.value)}
              >
                {Object.entries(CONTEXT_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
          </>
        ) : (
          <>
            <label>
              Natija
              <input
                type="number" min="0" step="0.001" required
                value={form.value}
                onChange={(e) => setField('value', e.target.value)}
              />
            </label>
            <label>
              Birlik
              <input
                type="text" maxLength="30" required
                value={form.unit}
                onChange={(e) => setField('unit', e.target.value)}
                placeholder={LIVER_METRICS[form.metric]?.suggestedUnit || ''}
              />
            </label>
            <label>
              Me’yor pastki chegarasi
              <input
                type="number" min="0" step="0.001"
                value={form.reference_min}
                onChange={(e) => setField('reference_min', e.target.value)}
              />
            </label>
            <label>
              Me’yor yuqori chegarasi
              <input
                type="number" min="0" step="0.001"
                value={form.reference_max}
                onChange={(e) => setField('reference_max', e.target.value)}
              />
            </label>
            <p className="health-monitor-hint health-monitor-wide">
              Me’yor chegaralarini aynan laboratoriya blankasidan kiriting. Kamida bitta
              chegara kerak; virus yuklamasida laboratoriya belgilagan aniqlash chegarasini kiriting.
            </p>
          </>
        )}

        <label>
          O‘lchangan sana va vaqt
          <input
            type="datetime-local"
            value={form.measured_at}
            onChange={(e) => setField('measured_at', e.target.value)}
          />
        </label>

        <label className="health-monitor-wide">
          Izoh (ixtiyoriy)
          <input
            type="text" maxLength="255" value={form.note}
            onChange={(e) => setField('note', e.target.value)}
          />
        </label>

        <label className="health-monitor-check health-monitor-wide">
          <input
            type="checkbox"
            checked={form.share_with_care_team}
            onChange={(e) => setField('share_with_care_team', e.target.checked)}
          />
          Chegaradan tashqari natijani shifokor va klinikaga yuborishga roziman
        </label>

        <button type="submit" className="health-monitor-submit" disabled={saving}>
          {saving ? 'Saqlanmoqda...' : 'Saqlash'}
        </button>
      </form>

      <div className="health-monitor-results">
        <div className="health-monitor-results-heading">
          <div>
            <h3>Saqlangan natijalar</h3>
            <p>Tahlil ko‘rsatkichlarini turi bo‘yicha saralang.</p>
          </div>
          <span className="health-monitor-result-count">{readings.length}</span>
        </div>

        <div className="health-monitor-filters" aria-label="Natijalarni ko‘rsatkich turi bo‘yicha filtrlash">
          {FILTERS.map(([value, label]) => (
            <button
              key={value || 'all'}
              type="button"
              className={filter === value ? 'active' : ''}
              aria-pressed={filter === value}
              onClick={() => setFilter(value)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <p>Yuklanmoqda...</p>
      ) : readings.length === 0 ? (
        <p className="health-monitor-empty">Hozircha ko‘rsatkichlar yo‘q.</p>
      ) : (
        <>
        {Object.keys(LIVER_METRICS).some((metric) => readings.some((reading) => reading.metric === metric))
          && <div className="liver-trend-grid">
            {Object.keys(LIVER_METRICS).map((metric) => (
              <LiverTrendChart key={metric} metric={metric} readings={readings} />
            ))}
          </div>}
        <ul className="health-monitor-list">
          {readings.map((reading) => (
            <li key={reading.id} className={`health-monitor-item ${reading.severity}`}>
              <div>
                <strong>{METRIC_LABELS[reading.metric] || reading.metric}: {readingValue(reading)}</strong>
                <small>{formatDateTime(reading.measured_at)}</small>
                {LIVER_METRICS[reading.metric] && (
                  <small>
                    Laboratoriya me’yori: {reading.reference_min ?? '—'}–{reading.reference_max ?? '—'} {reading.unit}
                  </small>
                )}
                {reading.note && <small>{reading.note}</small>}
                {reading.severity !== 'normal' && <small>{reading.alert_reason}</small>}
              </div>
              <span className={`health-badge ${reading.severity}`}>
                {SEVERITY_LABELS[reading.severity]}
              </span>
              <button type="button" onClick={() => handleDelete(reading.id)} aria-label={`${METRIC_LABELS[reading.metric] || 'Ko‘rsatkich'} natijasini o‘chirish`}>
                O‘chirish
              </button>
            </li>
          ))}
        </ul>
        </>
      )}
    </div>
  )
}

export default PatientHealthMonitor
