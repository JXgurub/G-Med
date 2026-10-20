import { useEffect, useState } from 'react'
import { patientsApi } from '../services/api'
import './DoctorHealthAlerts.css'

const SEVERITY_LABELS = { attention: 'E’tibor talab', urgent: 'Shoshilinch' }

const LIVER_METRIC_LABELS = {
  liver_alt: 'ALT',
  liver_ast: 'AST',
  liver_bilirubin: 'Bilirubin',
  liver_albumin: 'Albumin',
  liver_ggt: 'GGT',
  liver_viral_load: 'Virus yuklamasi',
}

const valueText = (alert) => {
  if (alert.metric === 'blood_pressure') {
    return `Qon bosimi ${alert.systolic}/${alert.diastolic} mm sim. ust.`
  }
  if (alert.metric === 'blood_glucose') {
    return `Qon qandi ${alert.glucose_mmol} mmol/L`
  }
  return `${LIVER_METRIC_LABELS[alert.metric] || alert.metric}: ${alert.value} ${alert.unit} (me’yor: ${alert.reference_min ?? '—'}–${alert.reference_max ?? '—'})`
}

const DoctorHealthAlerts = () => {
  const [alerts, setAlerts] = useState([])
  const [error, setError] = useState('')
  const [loaded, setLoaded] = useState(false)

  const load = async () => {
    try {
      const response = await patientsApi.getHealthAlerts()
      const items = response?.results || response
      setAlerts(Array.isArray(items) ? items : [])
      setError('')
    } catch {
      setError('Kuzatuv ogohlantirishlarini yuklab bo‘lmadi.')
    } finally {
      setLoaded(true)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const handleReview = async (id) => {
    try {
      await patientsApi.reviewHealthAlert(id)
      setAlerts((current) => current.filter((item) => item.id !== id))
    } catch {
      setError('Belgilab bo‘lmadi.')
    }
  }

  if (loaded && !error && alerts.length === 0) return null

  return (
    <section className="health-monitor">
      <div className="health-monitor-header">
        <h2>Surunkali kuzatuv ogohlantirishlari</h2>
        <p>Bemorlar yuborgan chegaradan tashqari ko‘rsatkichlar. Bu ma’lumot tashxis emas.</p>
      </div>
      {error && <div className="health-monitor-error">{error}</div>}
      <ul className="health-monitor-list">
        {alerts.map((alert) => (
          <li key={alert.id} className={`health-monitor-item ${alert.severity}`}>
            <div>
              <strong>{alert.patient_name}</strong>
              <span>{valueText(alert)}</span>
              <small>{alert.alert_reason}</small>
              {alert.patient_phone && <small>{alert.patient_phone}</small>}
            </div>
            <span className={`health-badge ${alert.severity}`}>
              {SEVERITY_LABELS[alert.severity]}
            </span>
            <button type="button" onClick={() => handleReview(alert.id)}>
              Ko‘rib chiqdim
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}

export default DoctorHealthAlerts
