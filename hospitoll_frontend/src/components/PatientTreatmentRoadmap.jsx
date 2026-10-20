import { useEffect, useState } from 'react'
import { patientsApi } from '../services/api'
import './PatientTreatmentRoadmap.css'

const getErrorMessage = (error, fallback) => {
  const data = error?.response?.data
  if (typeof data === 'string') return data
  if (data?.detail) return data.detail
  if (data && typeof data === 'object') {
    const firstError = Object.values(data).find((value) => Array.isArray(value) && value.length)
    if (firstError) return firstError[0]
  }
  return fallback
}

const formatDate = (value) => {
  if (!value) return ''
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('uz-UZ', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

const emptyPlanForm = {
  title: '',
  summary: '',
  start_date: '',
  target_date: '',
}

const PatientTreatmentRoadmap = () => {
  const [plans, setPlans] = useState([])
  const [loading, setLoading] = useState(true)
  const [savingPlan, setSavingPlan] = useState(false)
  const [savingStepFor, setSavingStepFor] = useState(null)
  const [updatingId, setUpdatingId] = useState(null)
  const [error, setError] = useState('')
  const [planForm, setPlanForm] = useState(emptyPlanForm)
  const [stepForms, setStepForms] = useState({})

  useEffect(() => {
    let cancelled = false
    patientsApi.getTreatmentPlans()
      .then((response) => {
        const items = response?.results || response
        if (!cancelled) setPlans(Array.isArray(items) ? items : [])
      })
      .catch((loadError) => {
        if (!cancelled) setError(getErrorMessage(loadError, 'Davolanish rejalarini yuklab bo‘lmadi.'))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  const handleCreatePlan = async (event) => {
    event.preventDefault()
    setSavingPlan(true)
    setError('')
    try {
      const created = await patientsApi.createTreatmentPlan({
        ...planForm,
        start_date: planForm.start_date || null,
        target_date: planForm.target_date || null,
      })
      setPlans((current) => [created, ...current])
      setPlanForm(emptyPlanForm)
    } catch (createError) {
      setError(getErrorMessage(createError, 'Rejani saqlab bo‘lmadi.'))
    } finally {
      setSavingPlan(false)
    }
  }

  const handleCreateStep = async (event, planId) => {
    event.preventDefault()
    const form = stepForms[planId] || { title: '', description: '', due_date: '' }
    setSavingStepFor(planId)
    setError('')
    try {
      const created = await patientsApi.createTreatmentStep({
        plan: planId,
        ...form,
        due_date: form.due_date || null,
      })
      setPlans((current) => current.map((plan) => (
        plan.id === planId ? { ...plan, steps: [...(plan.steps || []), created] } : plan
      )))
      setStepForms((current) => ({ ...current, [planId]: { title: '', description: '', due_date: '' } }))
    } catch (createError) {
      setError(getErrorMessage(createError, 'Qadamni qo‘shib bo‘lmadi.'))
    } finally {
      setSavingStepFor(null)
    }
  }

  const handleToggleStep = async (step) => {
    setUpdatingId(step.id)
    setError('')
    try {
      const updated = await patientsApi.updateTreatmentStep(step.id, { is_completed: !step.is_completed })
      setPlans((current) => current.map((plan) => ({
        ...plan,
        steps: (plan.steps || []).map((item) => item.id === updated.id ? updated : item),
      })))
    } catch (updateError) {
      setError(getErrorMessage(updateError, 'Qadam holatini yangilab bo‘lmadi.'))
    } finally {
      setUpdatingId(null)
    }
  }

  const handlePlanStatus = async (plan) => {
    const status = plan.status === 'completed' ? 'active' : 'completed'
    setUpdatingId(plan.id)
    setError('')
    try {
      const updated = await patientsApi.updateTreatmentPlan(plan.id, { status })
      setPlans((current) => current.map((item) => item.id === updated.id
        ? { ...item, ...updated, steps: item.steps || [] }
        : item))
    } catch (updateError) {
      setError(getErrorMessage(updateError, 'Reja holatini yangilab bo‘lmadi.'))
    } finally {
      setUpdatingId(null)
    }
  }

  const handleDeleteStep = async (planId, stepId) => {
    if (!window.confirm('Ushbu qadamni o‘chirmoqchimisiz?')) return
    setUpdatingId(stepId)
    setError('')
    try {
      await patientsApi.deleteTreatmentStep(stepId)
      setPlans((current) => current.map((plan) => (
        plan.id === planId
          ? { ...plan, steps: (plan.steps || []).filter((step) => step.id !== stepId) }
          : plan
      )))
    } catch (deleteError) {
      setError(getErrorMessage(deleteError, 'Qadamni o‘chirib bo‘lmadi.'))
    } finally {
      setUpdatingId(null)
    }
  }

  const handleDeletePlan = async (planId) => {
    if (!window.confirm('Reja va uning barcha qadamlarini o‘chirmoqchimisiz?')) return
    setUpdatingId(planId)
    setError('')
    try {
      await patientsApi.deleteTreatmentPlan(planId)
      setPlans((current) => current.filter((plan) => plan.id !== planId))
    } catch (deleteError) {
      setError(getErrorMessage(deleteError, 'Rejani o‘chirib bo‘lmadi.'))
    } finally {
      setUpdatingId(null)
    }
  }

  return (
    <section className="treatment-roadmap">
      <header className="roadmap-heading">
        <div>
          <h2>Davolanish yo‘l xaritasi</h2>
          <p>Shifokor bilan kelishilgan davolanish rejangizni va keyingi qadamlarni bir joyda kuzating.</p>
        </div>
        <span className="roadmap-heading-icon" aria-hidden="true">🩺</span>
      </header>

      {error && <p className="roadmap-error" role="alert">{error}</p>}

      <form className="roadmap-form" onSubmit={handleCreatePlan}>
        <h3>Yangi reja yaratish</h3>
        <div className="roadmap-form-grid">
          <label>
            Reja nomi
            <input
              type="text"
              maxLength="200"
              value={planForm.title}
              onChange={(event) => setPlanForm((current) => ({ ...current, title: event.target.value }))}
              placeholder="Masalan: Reabilitatsiya rejasi"
              required
            />
          </label>
          <label>
            Boshlanish sanasi
            <input
              type="date"
              value={planForm.start_date}
              onChange={(event) => setPlanForm((current) => ({ ...current, start_date: event.target.value }))}
            />
          </label>
          <label>
            Rejalashtirilgan yakun
            <input
              type="date"
              value={planForm.target_date}
              min={planForm.start_date || undefined}
              onChange={(event) => setPlanForm((current) => ({ ...current, target_date: event.target.value }))}
            />
          </label>
          <label className="roadmap-full-width">
            Izoh
            <textarea
              rows="2"
              maxLength="4000"
              value={planForm.summary}
              onChange={(event) => setPlanForm((current) => ({ ...current, summary: event.target.value }))}
              placeholder="Shifokor tavsiyasi yoki reja haqida qisqa izoh"
            />
          </label>
        </div>
        <button type="submit" className="roadmap-primary-button" disabled={savingPlan}>
          {savingPlan ? 'Saqlanmoqda...' : 'Reja yaratish'}
        </button>
      </form>

      {loading ? (
        <p className="roadmap-empty">Rejalar yuklanmoqda...</p>
      ) : plans.length === 0 ? (
        <div className="roadmap-empty">
          <strong>Hozircha davolanish rejasi yo‘q</strong>
          <span>Shifokor bilan kelishilgan rejangizni yuqorida yarating va unga bajariladigan qadamlarni qo‘shing.</span>
        </div>
      ) : (
        <div className="roadmap-plan-list">
          {plans.map((plan) => {
            const steps = plan.steps || []
            const completedCount = steps.filter((step) => step.is_completed).length
            const progress = steps.length ? Math.round((completedCount / steps.length) * 100) : 0
            const stepForm = stepForms[plan.id] || { title: '', description: '', due_date: '' }
            const planIsUpdating = updatingId === plan.id

            return (
              <article className={`roadmap-plan-card ${plan.status === 'completed' ? 'is-completed' : ''}`} key={plan.id}>
                <div className="roadmap-plan-header">
                  <div>
                    <span className={`roadmap-status ${plan.status === 'completed' ? 'done' : ''}`}>
                      {plan.status === 'completed' ? 'Yakunlangan' : 'Faol reja'}
                    </span>
                    <h3>{plan.title}</h3>
                  </div>
                  <button
                    type="button"
                    className="roadmap-text-button"
                    disabled={planIsUpdating}
                    onClick={() => handlePlanStatus(plan)}
                  >
                    {plan.status === 'completed' ? 'Qayta faollashtirish' : 'Rejani yakunlash'}
                  </button>
                </div>

                {(plan.start_date || plan.target_date) && (
                  <p className="roadmap-dates">
                    {plan.start_date ? `Boshlangan: ${formatDate(plan.start_date)}` : ''}
                    {plan.start_date && plan.target_date ? ' · ' : ''}
                    {plan.target_date ? `Maqsadli yakun: ${formatDate(plan.target_date)}` : ''}
                  </p>
                )}
                {plan.summary && <p className="roadmap-summary">{plan.summary}</p>}

                <div className="roadmap-progress-label">
                  <span>Reja bajarilishi</span>
                  <strong>{completedCount}/{steps.length} qadam · {progress}%</strong>
                </div>
                <div
                  className="roadmap-progress-track"
                  role="progressbar"
                  aria-label={`${plan.title} bajarilish darajasi`}
                  aria-valuemin="0"
                  aria-valuemax="100"
                  aria-valuenow={progress}
                >
                  <span style={{ width: `${progress}%` }} />
                </div>

                <div className="roadmap-step-list">
                  {steps.length ? steps.map((step) => (
                    <div className={`roadmap-step ${step.is_completed ? 'is-done' : ''}`} key={step.id}>
                      <button
                        type="button"
                        className="roadmap-step-check"
                        aria-label={step.is_completed ? `${step.title} bajarilmadi deb belgilash` : `${step.title} bajarildi deb belgilash`}
                        aria-pressed={step.is_completed}
                        disabled={updatingId === step.id}
                        onClick={() => handleToggleStep(step)}
                      >
                        {step.is_completed ? '✓' : ''}
                      </button>
                      <div className="roadmap-step-content">
                        <strong>{step.title}</strong>
                        {step.description && <p>{step.description}</p>}
                        {step.due_date && <span>{formatDate(step.due_date)}</span>}
                      </div>
                      <button
                        type="button"
                        className="roadmap-remove-button"
                        aria-label={`${step.title} qadamini o‘chirish`}
                        disabled={updatingId === step.id}
                        onClick={() => handleDeleteStep(plan.id, step.id)}
                      >
                        ×
                      </button>
                    </div>
                  )) : (
                    <p className="roadmap-no-steps">Hali qadam qo‘shilmagan.</p>
                  )}
                </div>

                <form className="roadmap-step-form" onSubmit={(event) => handleCreateStep(event, plan.id)}>
                  <h4>Keyingi qadamni qo‘shish</h4>
                  <div className="roadmap-form-grid">
                    <label>
                      Qadam nomi
                      <input
                        type="text"
                        maxLength="200"
                        value={stepForm.title}
                        onChange={(event) => setStepForms((current) => ({
                          ...current,
                          [plan.id]: { ...stepForm, title: event.target.value },
                        }))}
                        placeholder="Masalan: Nazorat ko‘rigiga borish"
                        required
                      />
                    </label>
                    <label>
                      Sana
                      <input
                        type="date"
                        value={stepForm.due_date}
                        onChange={(event) => setStepForms((current) => ({
                          ...current,
                          [plan.id]: { ...stepForm, due_date: event.target.value },
                        }))}
                      />
                    </label>
                    <label className="roadmap-full-width">
                      Qo‘shimcha izoh
                      <textarea
                        rows="2"
                        maxLength="4000"
                        value={stepForm.description}
                        onChange={(event) => setStepForms((current) => ({
                          ...current,
                          [plan.id]: { ...stepForm, description: event.target.value },
                        }))}
                      />
                    </label>
                  </div>
                  <button
                    type="submit"
                    className="roadmap-secondary-button"
                    disabled={savingStepFor === plan.id}
                  >
                    {savingStepFor === plan.id ? 'Qo‘shilmoqda...' : 'Qadam qo‘shish'}
                  </button>
                </form>

                <button
                  type="button"
                  className="roadmap-delete-plan"
                  disabled={planIsUpdating}
                  onClick={() => handleDeletePlan(plan.id)}
                >
                  Rejani o‘chirish
                </button>
              </article>
            )
          })}
        </div>
      )}

      <p className="roadmap-disclaimer">
        Bu bo‘lim kuzatuv va rejalashtirish uchun. U tashxis yoki davolash tavsiyasi bermaydi; tibbiy qadamlarni shifokoringiz bilan kelishib oling.
      </p>
    </section>
  )
}

export default PatientTreatmentRoadmap
