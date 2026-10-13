import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { childSafetyApi } from '../services/api'
import './ChildSafety.css'

const VOTE_CHOICES = [
  { value: 'safe', label: 'Xavfsiz', tone: 'safe', countKey: 'safe_votes' },
  { value: 'caution', label: 'Ehtiyot bo‘lish kerak', tone: 'caution', countKey: 'caution_votes' },
  { value: 'danger', label: 'Xavfsizlik muammolari bor', tone: 'danger', countKey: 'danger_votes' },
]

const hasLoginToken = () => Boolean(
  localStorage.getItem('access_token') || sessionStorage.getItem('doctor_access_token')
)

const ChildSafety = () => {
  const [regions, setRegions] = useState([])
  const [districts, setDistricts] = useState([])
  const [mahallas, setMahallas] = useState([])
  const [regionId, setRegionId] = useState('')
  const [districtId, setDistrictId] = useState('')
  const [mahallaId, setMahallaId] = useState('')
  const [statistics, setStatistics] = useState(null)
  const [hasVoted, setHasVoted] = useState(false)
  const [loginRequired, setLoginRequired] = useState(false)
  const [loading, setLoading] = useState(true)
  const [votePending, setVotePending] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    let cancelled = false
    childSafetyApi.getRegions()
      .then((data) => {
        if (!cancelled) setRegions(Array.isArray(data) ? data : [])
      })
      .catch(() => {
        if (!cancelled) setError('Hududlar yuklanmadi. Keyinroq qayta urinib ko‘ring.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  const selectedRegionId = mahallaId || districtId || regionId

  useEffect(() => {
    if (!selectedRegionId) {
      setStatistics(null)
      setHasVoted(false)
      return undefined
    }

    let cancelled = false
    childSafetyApi.getStatistics(selectedRegionId)
      .then((data) => {
        if (cancelled) return
        setStatistics(data)
        setHasVoted(Boolean(data?.has_voted))
      })
      .catch(() => {
        if (!cancelled) setError('Hudud natijalari yuklanmadi.')
      })
    return () => { cancelled = true }
  }, [selectedRegionId])

  const handleRegionChange = async (event) => {
    const nextId = event.target.value
    setRegionId(nextId)
    setDistrictId('')
    setMahallaId('')
    setDistricts([])
    setMahallas([])
    setNotice('')
    if (!nextId) return
    try {
      const data = await childSafetyApi.getRegions(nextId)
      setDistricts(Array.isArray(data) ? data : [])
    } catch {
      setError('Tumanlar yuklanmadi.')
    }
  }

  const handleDistrictChange = async (event) => {
    const nextId = event.target.value
    setDistrictId(nextId)
    setMahallaId('')
    setMahallas([])
    setNotice('')
    if (!nextId) return
    try {
      const data = await childSafetyApi.getRegions(nextId)
      setMahallas(Array.isArray(data) ? data : [])
    } catch {
      setError('Mahallalar yuklanmadi.')
    }
  }

  const handleVote = async (choice) => {
    if (!selectedRegionId || votePending || hasVoted) return
    setError('')
    setNotice('')
    setVotePending(true)
    try {
      const response = await childSafetyApi.castVote({ region_id: selectedRegionId, choice })
      setStatistics((current) => ({ ...current, ...response.statistics }))
      setHasVoted(true)
      setNotice('Ovozingiz qabul qilindi. Rahmat!')
    } catch (voteError) {
      const status = voteError?.response?.status
      if (status === 401) {
        setLoginRequired(true)
      } else if (status === 409) {
        setHasVoted(true)
        setError('Siz bu hudud uchun allaqachon ovoz bergansiz.')
      } else if (status === 429) {
        setError('Ovoz berish limiti tugadi. Keyinroq urinib ko‘ring.')
      } else {
        setError(voteError?.message || 'Ovoz yuborilmadi. Qayta urinib ko‘ring.')
      }
    } finally {
      setVotePending(false)
    }
  }

  const currentRegion = [...mahallas, ...districts, ...regions].find((region) => region.id === selectedRegionId)
  const score = statistics?.community_score

  return (
    <section className="child-safety-section" aria-labelledby="child-safety-title">
      <div className="container">
        <Link to="/" className="child-safety-back">Asosiy sahifaga qaytish</Link>
        <div className="child-safety-heading">
          <span className="child-safety-kicker">Bolalar xavfsizligi</span>
          <h1 id="child-safety-title">Hududiy jamoatchilik bahosi</h1>
          <p>
            Hududingiz bo‘yicha jamoatchilik fikrini bildiring va mavjud ovozlar natijasini ko‘ring.
          </p>
        </div>

        <div className="child-safety-panel">
          <div className="child-safety-selector">
            <label>
              <span className="child-safety-step-label"><span>01</span> Hududni belgilang</span>
              <span className="child-safety-field-title">Viloyat / shahar</span>
              <select value={regionId} onChange={handleRegionChange} disabled={loading}>
                <option value="">Hududni tanlang</option>
                {regions.map((region) => <option key={region.id} value={region.id}>{region.name}</option>)}
              </select>
            </label>
            {districts.length > 0 ? (
              <label>
                <span className="child-safety-step-label"><span>02</span> Aniqlashtiring</span>
                <span className="child-safety-field-title">Tuman / shahar</span>
                <select value={districtId} onChange={handleDistrictChange}>
                  <option value="">Tumanni tanlang</option>
                  {districts.map((district) => <option key={district.id} value={district.id}>{district.name}</option>)}
                </select>
              </label>
            ) : null}
            {mahallas.length > 0 ? (
              <label>
                <span className="child-safety-step-label"><span>03</span> Ixtiyoriy bosqich</span>
                <span className="child-safety-field-title">Mahalla</span>
                <select value={mahallaId} onChange={(event) => { setMahallaId(event.target.value); setNotice('') }}>
                  <option value="">Mahallani tanlang (ixtiyoriy)</option>
                  {mahallas.map((mahalla) => <option key={mahalla.id} value={mahalla.id}>{mahalla.name}</option>)}
                </select>
              </label>
            ) : null}
          </div>

          {selectedRegionId ? (
            <>
              <div className="child-safety-result-heading">
                <div className="child-safety-region-summary">
                  <span className="child-safety-kicker">Jamoatchilik bahosi</span>
                  <h2>{currentRegion?.name || 'Tanlangan hudud'}</h2>
                  <span className="child-safety-community-tag">Rasmiy indeks emas</span>
                </div>
                <div
                  className="child-safety-score"
                  role="img"
                  aria-label={`Jamoatchilik bahosi: ${score === null || score === undefined ? 'hozircha yo‘q' : `${Number(score).toFixed(1)} / 10`}`}
                  style={{ '--score-angle': `${((Number(score) || 0) / 10) * 360}deg` }}
                >
                  <div className="child-safety-score-inner" aria-live="polite">
                    <strong>{score === null || score === undefined ? '—' : Number(score).toFixed(1)}</strong>
                    <span>/ 10</span>
                  </div>
                </div>
              </div>

              <div className="child-safety-results" aria-live="polite">
                {VOTE_CHOICES.map((choice) => {
                  const count = statistics?.[choice.countKey] || 0
                  const percent = statistics?.total_votes ? (count / statistics.total_votes) * 100 : 0
                  return (
                    <div className={`child-safety-result ${choice.tone}`} key={choice.value}>
                      <div className="child-safety-result-label">
                        <span>{choice.label}</span>
                        <strong>{count.toLocaleString('uz-UZ')}</strong>
                      </div>
                      <div className="child-safety-meter" aria-hidden="true">
                        <span style={{ width: `${percent}%` }} />
                      </div>
                    </div>
                  )
                })}
              </div>
              <div className="child-safety-total">Jami: {(statistics?.total_votes || 0).toLocaleString('uz-UZ')} ta ovoz</div>

              <div className="child-safety-vote-box">
                <h3>Bu hudud bolalar uchun qanchalik xavfsiz?</h3>
                {hasVoted ? (
                  <p className="child-safety-feedback">Siz bu hudud uchun ovoz berib bo‘lgansiz.</p>
                ) : loginRequired || !hasLoginToken() ? (
                  <p className="child-safety-feedback">
                    Ovoz berish uchun tizimga kiring. <Link to="/patient-login">Kirish</Link>
                  </p>
                ) : (
                  <div className="child-safety-vote-options">
                    {VOTE_CHOICES.map((choice) => (
                      <button
                        type="button"
                        className={`child-safety-vote-button ${choice.tone}`}
                        key={choice.value}
                        onClick={() => handleVote(choice.value)}
                        disabled={votePending}
                      >
                        <span className="child-safety-vote-icon" aria-hidden="true">
                          {choice.value === 'safe' ? '✓' : choice.value === 'caution' ? '!' : '×'}
                        </span>
                        <span>{choice.label}</span>
                        <span className="child-safety-vote-arrow" aria-hidden="true">→</span>
                      </button>
                    ))}
                  </div>
                )}
                {notice ? <p className="child-safety-feedback success" role="status">{notice}</p> : null}
                {error ? <p className="child-safety-feedback error" role="alert">{error}</p> : null}
              </div>
            </>
          ) : (
            <p className="child-safety-empty">{loading ? 'Hududlar yuklanmoqda...' : 'Natijalarni ko‘rish uchun viloyat yoki shaharni tanlang.'}</p>
          )}
        </div>

        <div className="child-safety-note child-safety-disclaimer">
          <p>
            Ushbu ko‘rsatkich foydalanuvchilarning anonim ovozlari asosida shakllantirilgan va hududdagi real jinoyatchilik statistikasi yoki alohida shaxslar haqida xulosa hisoblanmaydi.
          </p>
          <div className="child-safety-formula">
            <strong>Hisoblash usuli</strong>
            <span>Xavfsiz = 10, ehtiyot = 5, muammo = 0 ball.</span>
            <span>Jamoatchilik bahosi = (xavfsiz × 10 + ehtiyot × 5 + muammo × 0) ÷ jami ovoz.</span>
            <span>Rasmiy xavfsizlik indeksi emas. Rasmiy ma’lumotlar integratsiya qilinmagan.</span>
          </div>
        </div>
      </div>
    </section>
  )
}

export default ChildSafety