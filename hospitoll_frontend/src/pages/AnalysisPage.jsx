import { useEffect, useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import { aiDoctorApi } from '../services/api'
import './AnalysisPage.css'

const getSessionKey = () => {
  let key = localStorage.getItem('gmed_ai_session_key')
  if (!key || key.length > 64) {
    const randomBytes = window.crypto.getRandomValues(new Uint8Array(28))
    key = `sess_${Array.from(randomBytes, (byte) => byte.toString(16).padStart(2, '0')).join('')}`
    localStorage.setItem('gmed_ai_session_key', key)
  }
  return key
}

const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (character) => ({
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
})[character])

const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

const HEALTH_INDICATOR_RANGES = {
  "glukoza": { min: 3.9, max: 5.5, unit: "mmol/L" },
  "gemoglobin": { min: 120, max: 160, unit: "g/L" },
  "hemoglobin": { min: 120, max: 160, unit: "g/L" },
  "hb": { min: 120, max: 160, unit: "g/L" },
  "oq qon": { min: 4.5, max: 11.0, unit: "×10⁹/L" },
  "leykotsit": { min: 4.0, max: 10.0, unit: "×10⁹/L" },
  "leukocyte": { min: 4.0, max: 10.0, unit: "×10⁹/L" },
  "wbc": { min: 4.0, max: 10.0, unit: "×10⁹/L" },
  "qizil qon": { min: 4.5, max: 5.5, unit: "×10¹²/L" },
  "eritrotsit": { min: 4.0, max: 5.5, unit: "×10¹²/L" },
  "rbc": { min: 4.0, max: 5.5, unit: "×10¹²/L" },
  "trombosit": { min: 150, max: 400, unit: "×10⁹/L" },
  "plt": { min: 150, max: 400, unit: "×10⁹/L" },
  "esr": { min: 0, max: 20, unit: "mm/soat" },
  "hematokrit": { min: 35, max: 45, unit: "%" },
  "xolesterin": { min: 0, max: 5.18, unit: "mmol/L" },
  "triglicerid": { min: 0, max: 1.7, unit: "mmol/L" },
  "alt": { min: 0, max: 40, unit: "U/L" },
  "ast": { min: 0, max: 40, unit: "U/L" },
  "kreatinin": { min: 44, max: 106, unit: "µmol/L" },
  "ureia": { min: 2.5, max: 7.1, unit: "mmol/L" },
}

const PARASITOLOGY_INDICATORS = [
  { name: "Ichak amyobasi", keys: ["entamoeba coli", "ichak amyobasi"] },
  { name: "Dizenteriya amyobasi", keys: ["entamoeba histolytica", "dizenteriya amyobasi"] },
  { name: "Lyambliya", keys: ["lamblia intestinalis", "giardia intestinalis", "giardia lamblia", "lyambliya"] },
  { name: "Trichomonada", keys: ["trichomonas", "trixomonada", "trichomonada"] },
  { name: "Ostritsa", keys: ["enterobius vermicularis", "ostritsa", "enterobius"] },
  { name: "Askarida", keys: ["ascaris lumbricoides", "askarida", "ascaris"] },
  { name: "Kuchuk askaridasi", keys: ["toxocara canis", "kuchuk askaridasi"] },
  { name: "Mushuk askaridasi", keys: ["toxocara cati", "mushuk askaridasi"] },
  { name: "Ankilostoma", keys: ["ancylostoma", "ankilostoma"] },
  { name: "Qilbosh gijja", keys: ["trichocephalus", "trichuris trichiura", "qilbosh gijja"] },
  { name: "Cho'chqa tasmasi", keys: ["taenia solium", "cho'chqa tasmasi"] },
  { name: "Qoramol tasmasi", keys: ["taeniarhynchus", "taenia saginata", "qoramol tasmasi"] },
  { name: "Pakana gijja", keys: ["hymenolepis nana", "pakana gijja"] },
  { name: "Kalamush tasmasi", keys: ["hymenolepis diminuta", "kalamush tasmasi"] },
  { name: "Keng lentasimon gijja", keys: ["diphyllobothrium", "keng lentasimon gijja"] },
  { name: "Jigar so'rg'ichi", keys: ["fasciola hepatica", "jigar so'rg'ichi"] },
  { name: "Shistosoma", keys: ["schistosoma", "shistosoma"] },
  { name: "Lansetsimon so'rg'ich", keys: ["dicrocoelium", "lansetsimon"] },
  { name: "Miaz", keys: ["miaz", "myiasis"] },
  { name: "Echinococcus", keys: ["echinococcus", "exinokokk"] },
]

const normalizeAnalysisText = (text) => text
  .toLowerCase()
  .replace(/ё/g, 'е')
  .replace(/ʻ|ʼ|’|`/g, "'")

const parseHealthIndicators = (text) => {
  if (!text) return []
  const lines = text.split('\n')
  const indicators = []

  lines.forEach((sourceLine) => {
    const line = sourceLine
      .replace(/[*_`]/g, '')
      .replace(/^\s*[-•]\s*/, '')
      .replace(/^\s*\d{1,2}\s*[.)]\s*/, '')
      .trim()
    if (!line) return

    const normalizedLine = normalizeAnalysisText(line)
    const healthKey = Object.keys(HEALTH_INDICATOR_RANGES).find((key) =>
      normalizedLine.includes(key)
    )

    if (healthKey) {
      const valueMatch = line.match(/[+-]?\d+(?:[.,]\d+)?/)
      if (!valueMatch || valueMatch.index === undefined) return

      const name = line.slice(0, valueMatch.index).replace(/[:：\-–—]\s*$/, '').trim()
      const value = Number(valueMatch[0].replace(',', '.'))
      if (!name || !Number.isFinite(value)) return

      const range = HEALTH_INDICATOR_RANGES[healthKey]
      const restOfLine = line.slice(valueMatch.index + valueMatch[0].length)
      const referenceRangeMatch = restOfLine.match(
        /\(\s*(?:[^)]*?(?:me['’]?yor|normal|referens|reference)[^)]*?)?([+-]?\d+(?:[.,]\d+)?)\s*[-–—]\s*([+-]?\d+(?:[.,]\d+)?)/i
      )
      const minNormal = referenceRangeMatch
        ? Number(referenceRangeMatch[1].replace(',', '.'))
        : range.min
      const maxNormal = referenceRangeMatch
        ? Number(referenceRangeMatch[2].replace(',', '.'))
        : range.max
      const unitMatch = restOfLine.match(
        /^\s*((?:[×x]\s*)?10(?:\^[⁰-⁹0-9]+)?\/[a-zA-Zµμ⁰-⁹0-9]+|[a-zA-Zµμ%°][a-zA-Zµμ%°/⁰-⁹0-9^]*)/u
      )
      const unit = unitMatch?.[1]?.replace(/\s+/g, '') || range.unit

      let status = "normal"
      if (value < minNormal * 0.9 || value > maxNormal * 1.1) {
        status = "critical"
      } else if (value < minNormal * 0.95 || value > maxNormal * 1.05) {
        status = "warning"
      }

      indicators.push({
        name,
        value,
        unit,
        minNormal,
        maxNormal,
        status,
        kind: "quantitative",
      })
      return
    }

    const parasite = PARASITOLOGY_INDICATORS
      .flatMap((indicator) => indicator.keys.map((key) => ({ indicator, key })))
      .sort((a, b) => b.key.length - a.key.length)
      .find(({ key }) => normalizedLine.includes(key))
    if (!parasite) return

    const parasiteText = normalizedLine.slice(normalizedLine.indexOf(parasite.key) + parasite.key.length)
    const resultText = parasiteText.split(/\b(?:me['’]?yor|normal|referens|reference|norma)\b/i)[0]
    const positiveResult = /(?:\b(?:ijobiy|musbat|positive|topildi|aniqlandi)\b|\+\s*\d*(?:[.,]\d+)?|\b\d+(?:[.,]\d+)?\s*(?:ta|dona|sht)?\b)/i.test(resultText)
    const negativeResult = /(?:\b(?:manfiy|negative|aniqlanmadi|topilmadi|yo'q|yoq|bo'lmaydi|mavjud emas|not detected|absent)\b|-\s*(?:\d|$))/i.test(resultText)
    if (!positiveResult && !negativeResult) return

    const positiveCount = resultText.match(/\+\s*(\d+(?:[.,]\d+)?)/)
      || resultText.match(/\b(\d+(?:[.,]\d+)?)\s*(?:ta|dona|sht)\b/)
    const result = negativeResult
      ? "Aniqlanmadi"
      : positiveCount
        ? `+${positiveCount[1].replace(',', '.')}`
        : "Aniqlandi"

    indicators.push({
      name: parasite.indicator.name,
      value: result,
      unit: "",
      minNormal: null,
      maxNormal: null,
      status: negativeResult ? "normal" : "warning",
      kind: "qualitative",
      result,
    })
  })

  return indicators
}

const extractAiConclusion = (text) => {
  if (!text) return ''

  const conclusion = []
  let readingConclusion = false
  const lines = text.split(/\r?\n/)

  for (const sourceLine of lines) {
    const line = sourceLine
      .replace(/[*_`]/g, '')
      .replace(/^\s*-{2,}\s*|\s*-{2,}\s*$/g, '')
      .trim()

    if (!readingConclusion && /(?:qisqa|umumiy|ai)\s+xulosa/i.test(line)) {
      readingConclusion = true
      const content = line.replace(/.*?(?:qisqa|umumiy|ai)\s+xulosa/i, '').replace(/^[:\s-]+/, '').trim()
      if (content) conclusion.push(content)
      continue
    }

    if (readingConclusion && /^(?:muhim topilmalar|nima qilish kerak|tavsiyalar|important findings|what to do)\b/i.test(line)) {
      break
    }

    if (readingConclusion && line) conclusion.push(line)
  }

  return conclusion.join(' ').trim()
}

const getGaugePoint = (ratio) => {
  const angle = Math.PI * (1 - ratio)
  return {
    x: 50 + 38 * Math.cos(angle),
    y: 48 - 38 * Math.sin(angle),
  }
}

const getIndicatorIcon = (name) => {
  const normalizedName = name.toLowerCase()
  if (PARASITOLOGY_INDICATORS.some((indicator) => indicator.name.toLowerCase() === normalizedName)) return '🦠'
  if (normalizedName.includes('gemoglobin')) return '🩸'
  if (normalizedName.includes('eritrotsit')) return '🔴'
  if (normalizedName.includes('leykotsit')) return '🟣'
  if (normalizedName.includes('trombosit')) return '🟡'
  return '🧪'
}

const IndicatorGauge = ({ indicator }) => {
  if (indicator.kind === "qualitative") {
    const detected = indicator.status !== "normal"
    const resultLabel = detected ? "Aniqlandi" : "Aniqlanmadi"

    return (
      <article className={`indicator-chart-card qualitative ${indicator.status}`}>
        <div className="indicator-chart-heading">
          <span className="indicator-chart-icon" aria-hidden="true">{getIndicatorIcon(indicator.name)}</span>
          <span className="indicator-chart-name">{indicator.name}</span>
        </div>
        <div className={`qualitative-result-visual ${detected ? 'detected' : 'not-detected'}`}>
          <span aria-hidden="true">{detected ? '!' : '✓'}</span>
          <strong>{indicator.result}</strong>
        </div>
        <div className={`indicator-chart-status ${indicator.status}`}>{resultLabel}</div>
        <div className="indicator-chart-range">Me'yor: aniqlanmasligi kerak</div>
      </article>
    )
  }

  const range = indicator.maxNormal - indicator.minNormal
  const scaleMin = indicator.minNormal - range * 0.5
  const scaleMax = indicator.maxNormal + range * 0.5
  const valueRatio = Math.max(0, Math.min(1, (indicator.value - scaleMin) / (scaleMax - scaleMin)))
  const valuePoint = getGaugePoint(valueRatio)
  const rangeStart = getGaugePoint(0.25)
  const rangeEnd = getGaugePoint(0.75)
  const statusLabel = indicator.status === 'normal'
    ? "Me'yorida"
    : indicator.value < indicator.minNormal ? 'Past' : 'Yuqori'

  return (
    <article className={`indicator-chart-card ${indicator.status}`}>
      <div className="indicator-chart-heading">
        <span className="indicator-chart-icon" aria-hidden="true">{getIndicatorIcon(indicator.name)}</span>
        <span className="indicator-chart-name">{indicator.name}</span>
      </div>
      <div className="indicator-gauge" role="img" aria-label={`${indicator.name}: ${indicator.value} ${indicator.unit}; me'yor ${indicator.minNormal} dan ${indicator.maxNormal} gacha`}>
        <svg viewBox="0 0 100 58" aria-hidden="true">
          <path className="gauge-track" d="M 12 48 A 38 38 0 0 1 88 48" />
          <path
            className="gauge-normal-range"
            d={`M ${rangeStart.x} ${rangeStart.y} A 38 38 0 0 1 ${rangeEnd.x} ${rangeEnd.y}`}
          />
          <circle className="gauge-value-marker" cx={valuePoint.x} cy={valuePoint.y} r="3.2" />
        </svg>
        <div className="gauge-reading">
          <strong>{indicator.value}</strong>
          <span>{indicator.unit}</span>
        </div>
      </div>
      <div className={`indicator-chart-status ${indicator.status}`}>{statusLabel}</div>
      <div className="indicator-chart-range">
        {indicator.minNormal} – {indicator.maxNormal} {indicator.unit}
      </div>
    </article>
  )
}

const AnalysisPage = () => {
  const [file, setFile] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [currentAnalysis, setCurrentAnalysis] = useState(null)
  const [history, setHistory] = useState([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const fileInputRef = useRef(null)

  const sessionKey = getSessionKey()

  const clearSelectedFile = () => {
    setFile(null)
    setPreviewUrl((currentUrl) => {
      if (currentUrl) URL.revokeObjectURL(currentUrl)
      return null
    })
    setUploadProgress(0)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const loadHistory = async () => {
    setHistoryLoading(true)
    try {
      const data = await aiDoctorApi.getAnalyses({ session_key: sessionKey })
      setHistory(Array.isArray(data) ? data : [])
    } catch (err) {
      console.warn('Failed to load analysis history', err)
    } finally {
      setHistoryLoading(false)
    }
  }

  useEffect(() => {
    loadHistory()
  }, [])

  useEffect(() => {
    const handleLizaAction = (event) => {
      if (event.detail?.action !== 'read_analysis') return
      const resultText = currentAnalysis?.status === 'completed'
        ? String(currentAnalysis.result_text || '').trim()
        : ''
      if (!resultText) {
        window.dispatchEvent(new window.CustomEvent('gmed:liza-status', {
          detail: { message: 'Avval AI tahlilni yuklang yoki tarixdan tayyor natijani tanlang.' },
        }))
        return
      }
      window.dispatchEvent(new window.CustomEvent('gmed:liza-readout', { detail: { text: resultText } }))
    }

    window.addEventListener('gmed:liza-action', handleLizaAction)
    return () => window.removeEventListener('gmed:liza-action', handleLizaAction)
  }, [currentAnalysis])

  const handleFileChange = (e) => {
    const selected = e.target.files?.[0]
    if (!selected) return

    if (selected.size > 20 * 1024 * 1024) {
      setError("Fayl hajmi 20MB dan oshmasligi kerak.")
      return
    }

    setFile(selected)
    setError('')

    if (selected.type.startsWith('image/')) {
      setPreviewUrl(URL.createObjectURL(selected))
    } else {
      setPreviewUrl(null)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    const droppedFile = e.dataTransfer.files?.[0]
    if (droppedFile) {
      if (droppedFile.size > 20 * 1024 * 1024) {
        setError("Fayl hajmi 20MB dan oshmasligi kerak.")
        return
      }
      setFile(droppedFile)
      setError('')
      if (droppedFile.type.startsWith('image/')) {
        setPreviewUrl(URL.createObjectURL(droppedFile))
      } else {
        setPreviewUrl(null)
      }
    }
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    e.stopPropagation()
  }

  const pollAnalysisResult = async (analysisId) => {
    let attempts = 0
    const maxAttempts = 30

    const interval = setInterval(async () => {
      attempts += 1
      try {
        const res = await aiDoctorApi.getAnalysis(analysisId, { session_key: sessionKey })
        if (res.status === 'completed' || res.status === 'failed') {
          clearInterval(interval)
          setLoading(false)
          setCurrentAnalysis(res)
          clearSelectedFile()
          loadHistory()
        } else if (attempts >= maxAttempts) {
          clearInterval(interval)
          setLoading(false)
          setError("Tahlil jarayoni vaqti tugadi. Qayta urinib ko'ring.")
        }
      } catch (err) {
        clearInterval(interval)
        setLoading(false)
        setError("Tahlil natijasini olishda xatolik yuz berdi.")
      }
    }, 2000)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!file) {
      setError("Iltimos, tahlil faylini tanlang (Rasm, PDF, Excel, Word, HTML).")
      return
    }

    setLoading(true)
    setError('')
    setUploadProgress(0)
    setCurrentAnalysis(null)

    const formData = new FormData()
    formData.append('file', file)
    formData.append('session_key', sessionKey)

    try {
      const response = await aiDoctorApi.uploadFile(formData, setUploadProgress)
      const analysisData = response.analysis

      if (response.async && analysisData?.id) {
        pollAnalysisResult(analysisData.id)
      } else if (analysisData) {
        setLoading(false)
        setCurrentAnalysis(analysisData)
        clearSelectedFile()
        loadHistory()
      } else {
        setLoading(false)
        setError("Tahlilni qayta ishlashda xatolik yuz berdi.")
      }
    } catch (err) {
      setLoading(false)
      setUploadProgress(0)
      const message = err?.message || "Faylni yuklashda xatolik yuz berdi."
      setError(message.includes('429') || message.toLowerCase().includes('throttled')
        ? "So'rovlar ko'p yuborildi. Biroz kutib, qayta urinib ko'ring."
        : message)
    }
  }

  const handleSpeakText = (text) => {
    if (!window.speechSynthesis) {
      alert("Sizning brauzeringizda ovozli o'qish funksiyasi qo'llab-quvvatlanmaydi.")
      return
    }

    if (speaking) {
      window.speechSynthesis.cancel()
      setSpeaking(false)
      return
    }

    const cleanText = text.replace(/[*#\-_]/g, '').trim()
    const utterance = new SpeechSynthesisUtterance(cleanText)
    utterance.lang = 'uz-UZ'
    utterance.rate = 0.95

    utterance.onend = () => setSpeaking(false)
    utterance.onerror = () => setSpeaking(false)

    setSpeaking(true)
    window.speechSynthesis.speak(utterance)
  }

  const handlePrintReport = () => {
    if (!currentAnalysis) return
    const printWindow = window.open('', '_blank')
    if (!printWindow) return

    const html = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>G-MED AI Doktor Tahlil Natijasi</title>
        <style>
          body { font-family: 'Segoe UI', Tahoma, sans-serif; padding: 25px; color: #18293d; line-height: 1.6; }
          h1 { color: #1765b0; border-bottom: 2px solid #2775d6; padding-bottom: 8px; font-size: 22px; }
          .meta { font-size: 13px; color: #61768d; margin-bottom: 20px; }
          .result-box { background: #f8fbff; border: 1px solid #d4dfeb; padding: 18px; border-radius: 8px; white-space: pre-wrap; font-size: 14px; }
          .disclaimer { margin-top: 25px; padding: 12px; background: #fff8eb; border: 1px solid #fcd34d; border-radius: 6px; font-size: 12px; color: #92400e; }
        </style>
      </head>
      <body>
        <h1>G-MED AI DOKTOR — TAHLIL XULOSASI</h1>
        <div class="meta">
          Sana: ${new Date(currentAnalysis.created_at).toLocaleString('uz-UZ')}<br/>
          Fayl turi: ${(currentAnalysis.file_type || 'fayl').toUpperCase()}
        </div>
        <div class="result-box">${escapeHtml(currentAnalysis.result_text || 'Xulosa matni yo\'q.')}</div>
        <div class="disclaimer">
          ⚠️ ESLAТMA: Ushbu AI xulosasi faqat ma'lumot berish uchun bo'lib, rasmiy tibbiy diagnoz o'rnini bosa olmaydi.
        </div>
        <script>window.print();</script>
      </body>
      </html>
    `
    printWindow.document.write(html)
    printWindow.document.close()
  }

  const handleDeleteHistory = async (id, e) => {
    e.stopPropagation()
    if (!window.confirm("Ushbu tahlil tarixini o'chirmoqchimisiz?")) return
    try {
      await aiDoctorApi.deleteAnalysis(id, { session_key: sessionKey })
      if (currentAnalysis?.id === id) {
        setCurrentAnalysis(null)
      }
      loadHistory()
    } catch (err) {
      alert("O'chirishda xatolik yuz berdi")
    }
  }

  const indicators = currentAnalysis ? parseHealthIndicators(currentAnalysis.result_text) : []
  const normalIndicators = indicators.filter((indicator) => indicator.status === 'normal').length
  const attentionIndicators = indicators.length - normalIndicators
  const normalPercentage = indicators.length ? Math.round((normalIndicators / indicators.length) * 100) : 0
  const aiConclusion = currentAnalysis ? extractAiConclusion(currentAnalysis.result_text) : ''

  return (
    <div className="analysis-page">
      <div className="analysis-header">
        <Link to="/" className="back-link">← Asosiy sahifaga qaytish</Link>
        <div className="header-badge">🤖 SUN'IY INTELLEKT TIBBIY YORDAMCHISI</div>
        <h1>AI DOKTOR — LABORATORIYA TAHLILLARI</h1>
        <p>
          Laboratoriya va tibbiy tahlillaringizni (Rasm, PDF, Excel, Word, HTML) yuklang va sekundlar ichida tushunarli xulosaga ega bo'ling.
        </p>
      </div>

      <div className="analysis-container">
        {/* Left Column: Upload & History */}
        <div className="analysis-sidebar">
          <div className="upload-card">
            <h3>🔬 Yangi Tahlil Yuklash</h3>
            <p className="upload-subtitle">Rasm, PDF, Excel, Word yoki HTML fayl yuklang. Tahlil uchun Google Gemini xizmatiga yuboriladi; maxfiy ma'lumotlarni yoping.</p>

            <form onSubmit={handleSubmit}>
              <div
                className={`dropzone ${file ? 'has-file' : ''}`}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*,.pdf,.xlsx,.xls,.docx,.doc,.html,.htm"
                  onChange={handleFileChange}
                  style={{ display: 'none' }}
                />

                {previewUrl ? (
                  <div className="file-preview-box">
                    <img src={previewUrl} alt="Tahlil fayli" className="file-preview-img" />
                    <span>{file?.name}</span>
                  </div>
                ) : file ? (
                  <div className="file-preview-box text-file">
                    <div className="file-icon-badge">📄</div>
                    <span className="file-name">{file.name}</span>
                    <small>{formatFileSize(file.size)}</small>
                  </div>
                ) : (
                  <div className="dropzone-placeholder">
                    <div className="dropzone-icon">📁</div>
                    <strong>Faylni shu yerga tashlang yoki tanlang</strong>
                    <span className="file-formats">JPG, PNG, PDF, XLSX, DOCX, HTML (Max 20MB)</span>
                  </div>
                )}
              </div>

              {error && <div className="analysis-error-alert">{error}</div>}

              {loading && (
                <div className="upload-progress" aria-live="polite">
                  <div className="upload-progress-labels">
                    <span>{uploadProgress < 100 ? 'Fayl yuklanmoqda' : 'AI tahlil qilmoqda'}</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <div className="upload-progress-track">
                    <div className="upload-progress-value" style={{ width: `${uploadProgress}%` }} />
                  </div>
                </div>
              )}

              <button type="submit" className="btn-analyze-submit" disabled={loading || !file}>
                {loading ? (
                  <>
                    <span className="spinner-dot"></span>
                    AI Tahlil qilmoqda...
                  </>
                ) : (
                  '🔍 AI Tahlilni Boshlash'
                )}
              </button>
            </form>
          </div>

          {/* Past Analyses History */}
          <div className="history-card">
            <div className="history-header">
              <h4>📜 Tahlillar Tarixi</h4>
              {historyLoading && <small>Yuklanmoqda...</small>}
            </div>

            {history.length === 0 ? (
              <p className="no-history-text">Hali tahlillar tarixi yo'q</p>
            ) : (
              <div className="history-list">
                {history.map((item) => (
                  <div
                    key={item.id}
                    className={`history-item ${currentAnalysis?.id === item.id ? 'active' : ''}`}
                    onClick={() => setCurrentAnalysis(item)}
                  >
                    <div className="history-item-info">
                      <span className={`status-pill ${item.status}`}>
                        {item.status === 'completed' ? '✓ Bajarildi' : item.status === 'pending' ? '⏳ Tahlil qilinmoqda' : '❌ Xatolik'}
                      </span>
                      <span className="history-date">
                        {new Date(item.created_at).toLocaleDateString('uz-UZ', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                    <button className="btn-delete-history" title="O'chirish" onClick={(e) => handleDeleteHistory(item.id, e)}>
                      🗑️
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Active Analysis Results */}
        <div className="analysis-main-content">
          {loading ? (
            <div className="analysis-loading-box">
              <div className="pulse-loader">🤖</div>
              <h3>Sun'iy Intellekt Tahlil Etmoqda...</h3>
              <p>Tahlil fayli tekshirilmoqda, ko'rsatkichlar me'yorlar bilan solishtirilmoqda.</p>
              <div className="loading-steps">
                <span>✓ Fayl muvaffaqiyatli o'qildi</span>
                <span>⏳ Tahlillar me'yori solishtirilmoqda...</span>
                <span>⏳ Tibbiy xulosa tayyorlanmoqda...</span>
              </div>
            </div>
          ) : currentAnalysis ? (
            <div className="analysis-result-view">
              <div className="result-top-bar">
                <div className="result-title-group">
                  <h2>📊 Tahlil Natijasi va Xulosa</h2>
                  <span className="result-date">
                    {new Date(currentAnalysis.created_at).toLocaleString('uz-UZ')}
                  </span>
                </div>
                <div className="result-actions">
                  <button
                    className={`btn-action-speech ${speaking ? 'speaking' : ''}`}
                    onClick={() => handleSpeakText(currentAnalysis.result_text || '')}
                  >
                    {speaking ? '⏹️ To\'xtatish' : '🔊 Ovozli O\'qish'}
                  </button>
                  <button className="btn-action-print" onClick={handlePrintReport}>
                    🖨️ Chop etish / PDF
                  </button>
                </div>
              </div>

              {/* Status Header */}
              {currentAnalysis.status === 'failed' ? (
                <div className="analysis-failed-box">
                  ⚠️ <strong>Xatolik:</strong> {currentAnalysis.result_text || "Tahlil faylini qayta ishlashda xatolik yuz berdi."}
                </div>
              ) : (
                <>
                  {indicators.length > 0 ? (
                    <div className="analysis-visual-report">
                      <section className="analysis-overview" aria-label="Tahlilning umumiy holati">
                        <div className={`overview-condition ${attentionIndicators ? 'attention' : ''}`}>
                          <span className="overview-condition-icon" aria-hidden="true">
                            {attentionIndicators ? '!' : '✓'}
                          </span>
                          <div>
                            <span className="overview-label">Umumiy holat</span>
                            <strong>{attentionIndicators ? 'DIQQAT' : 'YAXSHI'}</strong>
                            <small>
                              {attentionIndicators
                                ? `${attentionIndicators} ta ko'rsatkich me'yordan tashqarida`
                                : "Barcha ko'rsatkichlar me'yorida"}
                            </small>
                          </div>
                        </div>
                        <div className="overview-score">
                          <div
                            className={`overview-score-ring ${attentionIndicators ? 'attention' : ''}`}
                            role="img"
                            aria-label={`${normalPercentage}% ko'rsatkich me'yorida`}
                          >
                            <strong>{normalPercentage}%</strong>
                          </div>
                          <div>
                            <strong>Tahlil ko'rsatkichlari</strong>
                            <span>{normalIndicators} / {indicators.length} ko'rsatkich me'yorida</span>
                            <div className="overview-progress">
                              <span style={{ width: `${normalPercentage}%` }} />
                            </div>
                          </div>
                        </div>
                        <div className="overview-legend" aria-label="Ko'rsatkichlar taqsimoti">
                          <div><span className="legend-dot normal" />Me'yorida<strong>{normalIndicators}</strong></div>
                          <div><span className="legend-dot attention" />Diqqat<strong>{attentionIndicators}</strong></div>
                        </div>
                      </section>

                      <section className="indicators-section">
                        <h3>📊 Tahlil ko'rsatkichlari</h3>
                        <div className="indicators-grid">
                          {indicators.map((indicator, idx) => (
                            <IndicatorGauge key={`${indicator.name}-${idx}`} indicator={indicator} />
                          ))}
                        </div>
                      </section>

                      <section className={`analysis-summary ${attentionIndicators ? 'attention' : ''}`}>
                        <span className="analysis-summary-icon" aria-hidden="true">
                          {attentionIndicators ? '📋' : '✅'}
                        </span>
                        <div>
                          <strong>AI XULOSASI</strong>
                          <p>
                            {aiConclusion || (attentionIndicators
                              ? `${indicators.length} ta ko'rsatkichdan ${attentionIndicators} tasi laboratoriya me'yoridan farq qiladi. Natijalarni shifokor bilan muhokama qiling.`
                              : `Aniqlangan ${indicators.length} ta ko'rsatkich laboratoriya me'yoriy chegaralarida.`)}
                          </p>
                        </div>
                      </section>
                    </div>
                  ) : (
                    <div className="result-text-card analysis-text-fallback">
                      <h3>📑 Shifokor AI Xulosasi va Tavsiyalar</h3>
                      <div className="result-formatted-text">
                        {currentAnalysis.result_text ? (
                          currentAnalysis.result_text.split(/\r?\n\s*\r?\n/).map((paragraph, idx) => (
                            <div key={idx} className="result-paragraph">
                              {paragraph.split(/\r?\n/).map((line, lineIdx) => (
                                <p key={lineIdx}>{line}</p>
                              ))}
                            </div>
                          ))
                        ) : (
                          <p>Xulosa matni mavjud emas.</p>
                        )}
                      </div>
                    </div>
                  )}
                </>
              )}

              {/* Disclaimer Banner */}
              <div className="analysis-disclaimer-banner">
                <span className="disclaimer-icon">⚠️</span>
                <div>
                  <strong>DIQQAT:</strong> Ushbu AI xulosasi faqat axborot va ma'lumot berish maqsadida taqdim etiladi. Sun'iy intellekt rasmiy vrachlik diagnozi o'rnini bosa olmaydi. Shifokor bilan uchrashib maslahat oling.
                </div>
              </div>
            </div>
          ) : (
            <div className="analysis-empty-state">
              <div className="empty-icon">📊</div>
              <h3>Laboratoriya Analizingizni Yuklang</h3>
              <p>
                Chap tomondagi oynaga qon, siydik yoki boshqa laboratoriya tahlillaringiz faylini kiriting.
                AI sizga har bir ko'rsatkichni oddiy tilda tushuntirib beradi.
              </p>
              <div className="supported-types-tags">
                <span>📸 Qon analiz rasmlari</span>
                <span>📄 PDF laboratoriya varaqalari</span>
                <span>📊 Excel tahlillar</span>
                <span>📝 Word fayllar</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default AnalysisPage
