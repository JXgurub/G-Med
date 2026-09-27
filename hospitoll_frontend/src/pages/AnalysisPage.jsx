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
  "oq qon": { min: 4.5, max: 11.0, unit: "×10⁹/L" },
  "qizil qon": { min: 4.5, max: 5.5, unit: "×10¹²/L" },
  "trombosit": { min: 150, max: 400, unit: "×10⁹/L" },
  "hematokrit": { min: 35, max: 45, unit: "%" },
  "xolesterin": { min: 0, max: 5.18, unit: "mmol/L" },
  "triglicerid": { min: 0, max: 1.7, unit: "mmol/L" },
  "alt": { min: 0, max: 40, unit: "U/L" },
  "ast": { min: 0, max: 40, unit: "U/L" },
  "kreatinin": { min: 44, max: 106, unit: "µmol/L" },
  "ureia": { min: 2.5, max: 7.1, unit: "mmol/L" },
}

const parseHealthIndicators = (text) => {
  if (!text) return []
  const lines = text.split('\n')
  const indicators = []

  lines.forEach((line) => {
    const match = line.match(/([a-zA-Z0-9\s]+?)[:\s]+\*?(\d+(?:\.\d+)?)\s*([a-zA-Z/°\-].*?)(?:\s*\(|$)/i)
    if (!match) return

    const name = match[1].trim()
    const value = parseFloat(match[2])
    const unit = (match[3] || "").trim()

    const nameLower = name.toLowerCase()
    const key = Object.keys(HEALTH_INDICATOR_RANGES).find((k) =>
      nameLower.includes(k) || k.includes(nameLower.split(" ")[0])
    )

    if (key && !isNaN(value)) {
      const range = HEALTH_INDICATOR_RANGES[key]
      let status = "normal"
      if (value < range.min * 0.9 || value > range.max * 1.1) {
        status = "critical"
      } else if (value < range.min * 0.95 || value > range.max * 1.05) {
        status = "warning"
      }

      indicators.push({
        name,
        value,
        unit: unit || range.unit,
        minNormal: range.min,
        maxNormal: range.max,
        status,
      })
    }
  })

  return indicators
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
                  {/* Indicators Chart / List if parsed */}
                  {indicators.length > 0 && (
                    <div className="indicators-section">
                      <h3>📈 Aniqlangan Salomatlik Ko'rsatkichlari</h3>
                      <div className="indicators-grid">
                        {indicators.map((ind, idx) => (
                          <div key={idx} className={`indicator-card ${ind.status}`}>
                            <div className="ind-header">
                              <span className="ind-name">{ind.name}</span>
                              <span className={`ind-badge ${ind.status}`}>
                                {ind.status === 'normal' ? 'ME\'YORDA' : ind.status === 'warning' ? 'OGOHLANTIRISH' : 'XAVFLI'}
                              </span>
                            </div>
                            <div className="ind-value-box">
                              <strong>{ind.value}</strong> <small>{ind.unit}</small>
                            </div>
                            <div className="ind-range">
                              Normal diapazon: {ind.minNormal} - {ind.maxNormal} {ind.unit}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Complete AI Result Text Box */}
                  <div className="result-text-card">
                    <h3>📑 Shifokor AI Xulosasi va Tavsiyalar</h3>
                    <div className="result-formatted-text">
                      {currentAnalysis.result_text ? (
                        currentAnalysis.result_text.split('\n\n').map((paragraph, idx) => (
                          <div key={idx} className="result-paragraph">
                            {paragraph.split('\n').map((line, lIdx) => (
                              <p key={lIdx}>{line}</p>
                            ))}
                          </div>
                        ))
                      ) : (
                        <p>Xulosa matni mavjud emas.</p>
                      )}
                    </div>
                  </div>
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
