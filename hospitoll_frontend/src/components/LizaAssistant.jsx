import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { usePatient } from '../context/PatientContext'
import { api, medicalRecordsApi } from '../services/api'
import './LizaAssistant.css'

const ENABLED_KEY = 'gmed_liza_wake_enabled'
const PHARMACY_PRESCRIPTION_KEY = 'gmed-pharmacy-prescription-search'
const WAKE_SEGMENT_SECONDS = 2.5
const COMMAND_MAX_MS = 12000
const BOOKING_CONFIRMATION_MAX_MS = 6500
const SILENCE_END_MS = 1300
const WAKE_OVERLAP_SECONDS = 0.5
const PRESCRIPTION_DIGIT_WORDS = Object.freeze({
  nol: '0',
  noil: '0',
  nival: '0',
  bir: '1',
  bar: '1',
  ikki: '2',
  uch: '3',
  tort: '4',
  besh: '5',
  olti: '6',
  yetti: '7',
  sakkiz: '8',
  toqqiz: '9',
})

const extractPrescriptionCode = (text) => {
  const normalized = String(text || '')
    .toLowerCase()
    .replace(/[‘’ʻ`]/g, "'")
    .replace(/to'qqiz/g, 'toqqiz')
    .replace(/to'rt/g, 'tort')
  const tokens = normalized.match(/\d+|[a-z']+/g) || []
  const candidates = []
  let digits = ''
  let invalidRun = false

  const finishRun = () => {
    if (!invalidRun && digits.length === 8) candidates.push(digits)
    digits = ''
    invalidRun = false
  }

  tokens.forEach((token) => {
    const isNumber = /^\d+$/.test(token)
    const hasWordDigit = Object.prototype.hasOwnProperty.call(PRESCRIPTION_DIGIT_WORDS, token)
    const tokenDigits = isNumber
      ? token
      : hasWordDigit
        ? PRESCRIPTION_DIGIT_WORDS[token]
        : undefined
    if (tokenDigits !== undefined) {
      if (invalidRun) return
      digits += tokenDigits
      if (digits.length > 8) {
        digits = ''
        invalidRun = true
      }
    } else {
      finishRun()
    }
  })
  finishRun()

  const uniqueCandidates = [...new Set(candidates)]
  return uniqueCandidates.length === 1 ? uniqueCandidates[0] : null
}

const resolvePrescriptionResult = (result, fallbackText = '') => {
  const role = sessionStorage.getItem('user_role') || localStorage.getItem('user_role')
  const prescriptionCode = extractPrescriptionCode(result?.transcript || fallbackText)
  const canRecoverPrescriptionAction = !result.action
    || result.action === 'prescription_code_required'
    || (
      result.action === 'search_prescription'
      && !/^\d{8}$/.test(String(result.prescription_code || ''))
    )
  if (
    !prescriptionCode
    || role !== 'patient'
    || !canRecoverPrescriptionAction
  ) {
    return result
  }

  return {
    ...result,
    action: 'search_prescription',
    prescription_code: prescriptionCode,
    reply: 'Retsept raqamini tekshirib, undagi dorilarni dorixonalardan qidiryapman.',
  }
}

const getAccessToken = () => {
  const role = sessionStorage.getItem('user_role') || localStorage.getItem('user_role')
  return role === 'doctor'
    ? sessionStorage.getItem('doctor_access_token')
    : localStorage.getItem('access_token')
}

const joinFrames = (frames, length) => {
  const samples = new Float32Array(length)
  let offset = 0
  frames.forEach((frame) => {
    const count = Math.min(frame.length, length - offset)
    if (count > 0) samples.set(frame.subarray(0, count), offset)
    offset += count
  })
  return samples
}

const createWav = (samples, inputRate) => {
  const outputRate = 16000
  const outputLength = Math.round(samples.length * outputRate / inputRate)
  const pcm = new Int16Array(outputLength)
  for (let index = 0; index < outputLength; index += 1) {
    const sourceIndex = index * inputRate / outputRate
    const left = Math.floor(sourceIndex)
    const right = Math.min(left + 1, samples.length - 1)
    const fraction = sourceIndex - left
    const value = samples[left] * (1 - fraction) + samples[right] * fraction
    pcm[index] = value < 0 ? value * 0x8000 : value * 0x7fff
  }

  const buffer = new ArrayBuffer(44 + pcm.length * 2)
  const view = new DataView(buffer)
  const writeText = (position, text) => {
    for (let index = 0; index < text.length; index += 1) {
      view.setUint8(position + index, text.charCodeAt(index))
    }
  }
  writeText(0, 'RIFF')
  view.setUint32(4, 36 + pcm.length * 2, true)
  writeText(8, 'WAVE')
  writeText(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, outputRate, true)
  view.setUint32(28, outputRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeText(36, 'data')
  view.setUint32(40, pcm.length * 2, true)
  for (let index = 0; index < pcm.length; index += 1) {
    view.setInt16(44 + index * 2, pcm[index], true)
  }
  return new Blob([buffer], { type: 'audio/wav' })
}

const splitSpeechText = (text, maxLength = 1700) => {
  const words = String(text || '').split(/\s+/).filter(Boolean)
  const chunks = []
  let current = ''
  words.forEach((word) => {
    if (word.length > maxLength) {
      if (current) chunks.push(current)
      current = ''
      for (let index = 0; index < word.length; index += maxLength) {
        chunks.push(word.slice(index, index + maxLength))
      }
      return
    }
    if (current && current.length + word.length + 1 > maxLength) {
      chunks.push(current)
      current = word
    } else {
      current = current ? `${current} ${word}` : word
    }
  })
  if (current) chunks.push(current)
  return chunks
}

const speakWithBrowser = (text) => new Promise((resolve) => {
  const speechSynthesis = window.speechSynthesis
  if (!speechSynthesis || typeof window.SpeechSynthesisUtterance !== 'function') {
    resolve(false)
    return
  }

  const utterance = new window.SpeechSynthesisUtterance(text)
  utterance.lang = 'uz-UZ'
  utterance.rate = 1
  utterance.volume = 1
  const uzbekVoice = speechSynthesis.getVoices().find((voice) => voice.lang.toLowerCase().startsWith('uz'))
  if (uzbekVoice) utterance.voice = uzbekVoice

  let timeout
  let finished = false
  const finish = (played) => {
    if (finished) return
    finished = true
    window.clearTimeout(timeout)
    resolve(played)
  }
  utterance.onend = () => finish(true)
  utterance.onerror = () => finish(false)
  timeout = window.setTimeout(() => {
    speechSynthesis.cancel()
    finish(false)
  }, Math.min(120000, Math.max(12000, text.length * 180)))

  try {
    speechSynthesis.cancel()
    speechSynthesis.speak(utterance)
  } catch {
    finish(false)
  }
})

const LizaAssistant = () => {
  const location = useLocation()
  const navigate = useNavigate()
  const { patientData } = usePatient()
  const lastPrescriptionCode = patientData.history.find((entry) => /^\d{8}$/.test(String(entry.prescriptionCode || '')))?.prescriptionCode
  const isAssistantAvailable = localStorage.getItem('user_role') === 'patient' && Boolean(getAccessToken())
  const currentPathRef = useRef(location.pathname)
  currentPathRef.current = location.pathname
  const [enabled, setEnabled] = useState(() => localStorage.getItem(ENABLED_KEY) === 'true')
  const [isVisible, setIsVisible] = useState(() => document.visibilityState === 'visible')
  const [phase, setPhase] = useState('off')
  const [status, setStatus] = useState('')
  const [lastReply, setLastReply] = useState('')
  const [lastTranscript, setLastTranscript] = useState('')
  const [lastWakeTranscript, setLastWakeTranscript] = useState('')
  const [prescriptionDialogOpen, setPrescriptionDialogOpen] = useState(false)
  const [prescriptionCodeInput, setPrescriptionCodeInput] = useState('')
  const [prescriptionDialogError, setPrescriptionDialogError] = useState('')
  const [prescriptionLookupLoading, setPrescriptionLookupLoading] = useState(false)
  const streamRef = useRef(null)
  const contextRef = useRef(null)
  const processorRef = useRef(null)
  const sourceRef = useRef(null)
  const pendingStreamRef = useRef(null)
  const speechAudioRef = useRef(null)
  const speechUrlRef = useRef(null)
  const rateLimitTimeoutRef = useRef(null)
  const modeRef = useRef('off')
  const sessionOpenRef = useRef(false)
  const confirmationChoiceHandlerRef = useRef(null)
  const activeRef = useRef(false)
  const generationRef = useRef(0)
  const enableRequestRef = useRef(0)
  const wakeFramesRef = useRef([])
  const wakeCountRef = useRef(0)
  const wakeSegmentSamplesRef = useRef(40000)
  const wakeHopSamplesRef = useRef(32000)
  const wakeHasVoiceRef = useRef(false)
  const wakeRequestRef = useRef(false)
  const pendingWakeSegmentRef = useRef(null)
  const commandFramesRef = useRef([])
  const commandCountRef = useRef(0)
  const commandStartedRef = useRef(false)
  const commandLastVoiceRef = useRef(0)
  const commandStartedAtRef = useRef(0)
  const finishingCommandRef = useRef(false)
  const prescriptionDialogCancelHandlerRef = useRef(null)

  const lookupPrescriptionByCode = async (code) => {
    if (!/^\d{8}$/.test(code)) {
      throw new Error('Retsept raqami 8 ta raqamdan iborat bo‘lishi kerak.')
    }
    const prescription = await medicalRecordsApi.lookupPrescription(code)
    if (!prescription.medicines?.length) {
      throw new Error('Bu retsept raqamida dorilar ro‘yxati topilmadi.')
    }
    localStorage.setItem(PHARMACY_PRESCRIPTION_KEY, JSON.stringify(prescription))
    setStatus('Retseptdagi dorilar dorixonalar bo‘yicha qidirilmoqda.')
    navigate('/#pharmacy-section')
  }

  const submitPrescriptionCode = async (event) => {
    event.preventDefault()
    setPrescriptionDialogError('')
    setPrescriptionLookupLoading(true)
    try {
      await lookupPrescriptionByCode(prescriptionCodeInput)
      setPrescriptionDialogOpen(false)
    } catch (error) {
      setPrescriptionDialogError(
        error?.response?.data?.error || error.message || 'Retsept bo‘yicha dorilarni topib bo‘lmadi.',
      )
    } finally {
      setPrescriptionLookupLoading(false)
    }
  }

  const closePrescriptionDialog = () => {
    if (prescriptionLookupLoading) return
    setPrescriptionDialogOpen(false)
    setPrescriptionDialogError('')
    prescriptionDialogCancelHandlerRef.current?.()
  }

  useEffect(() => {
    const updateVisibility = () => setIsVisible(document.visibilityState === 'visible')
    document.addEventListener('visibilitychange', updateVisibility)
    return () => document.removeEventListener('visibilitychange', updateVisibility)
  }, [])

  useEffect(() => {
    if (!enabled) return undefined
    if (!isAssistantAvailable) {
      sessionOpenRef.current = false
      localStorage.removeItem(ENABLED_KEY)
      setEnabled(false)
      setPhase('off')
      setStatus('')
      return undefined
    }
    if (!isVisible) {
      setPhase('paused')
      setStatus('Ilova fonda. Qaytganingizda mikrofon davom etadi.')
      return undefined
    }
    if (!getAccessToken()) {
      setPhase('error')
      setStatus('Avval G-MED hisobingizga kiring.')
      return undefined
    }
    if (!navigator.mediaDevices?.getUserMedia || !(window.AudioContext || window.webkitAudioContext)) {
      setPhase('error')
      setStatus('Bu brauzer mikrofonni uzluksiz tinglashni qo‘llamaydi.')
      return undefined
    }

    let cancelled = false
    const generation = ++generationRef.current
    const setMode = (mode, label) => {
      modeRef.current = mode
      setPhase(mode)
      setStatus(label)
    }
    const clearFrames = () => {
      wakeFramesRef.current = []
      wakeCountRef.current = 0
      wakeHasVoiceRef.current = false
      pendingWakeSegmentRef.current = null
      commandFramesRef.current = []
      commandCountRef.current = 0
    }
    const beginConversationCommand = () => {
      if (!activeRef.current || generationRef.current !== generation) return
      commandFramesRef.current = []
      commandCountRef.current = 0
      commandStartedRef.current = false
      commandStartedAtRef.current = Date.now()
      commandLastVoiceRef.current = commandStartedAtRef.current
      finishingCommandRef.current = false
      setMode('command', 'Liza suhbatda. Buyruqni ayting. To‘xtatish uchun “Liza, to‘xta” deng.')
    }
    const resumeWakeListening = () => {
      if (!activeRef.current || generationRef.current !== generation) return
      clearFrames()
      finishingCommandRef.current = false
      if (sessionOpenRef.current) {
        beginConversationCommand()
        return
      }
      setMode('wake', 'Liza tinglayapti. Uyg‘otish uchun “Liza” deng.')
    }
    prescriptionDialogCancelHandlerRef.current = resumeWakeListening
    const speakMadina = async (text, onEnd) => {
      let failed = false
      let browserFallback = false
      try {
        for (const chunk of splitSpeechText(text)) {
          let requestTimeout
          let result
          try {
            result = await Promise.race([
              api.post('/liza/speech/', { text: chunk }),
              new Promise((resolve, reject) => {
                requestTimeout = window.setTimeout(
                  () => reject(new Error('Madina ovoz xizmati vaqtida javob bermadi.')),
                  15000,
                )
              }),
            ])
          } finally {
            window.clearTimeout(requestTimeout)
          }
          if (!activeRef.current || generationRef.current !== generation) return
          const audioBytes = Uint8Array.from(atob(result.audio), (character) => character.charCodeAt(0))
          const audioUrl = URL.createObjectURL(new Blob([audioBytes], { type: result.content_type || 'audio/mpeg' }))
          speechUrlRef.current = audioUrl
          const player = new Audio(audioUrl)
          speechAudioRef.current = player
          await new Promise((resolve) => {
            let playbackTimeout
            const finish = () => {
              window.clearTimeout(playbackTimeout)
              player.onended = null
              player.onerror = null
              if (speechAudioRef.current === player) speechAudioRef.current = null
              if (speechUrlRef.current === audioUrl) speechUrlRef.current = null
              URL.revokeObjectURL(audioUrl)
              resolve()
            }
            player.onended = finish
            player.onerror = () => {
              failed = true
              finish()
            }
            playbackTimeout = window.setTimeout(() => {
              failed = true
              player.pause()
              finish()
            }, Math.min(120000, Math.max(12000, chunk.length * 120)))
            player.play().catch(() => {
              failed = true
              finish()
            })
          })
          if (failed) break
        }
      } catch (error) {
        failed = true
      }
      if (!activeRef.current || generationRef.current !== generation) return
      if (failed) {
        setStatus('Madina server ovozi ishlamadi. Qurilma ovozidan foydalanishga urinayapman.')
        browserFallback = await speakWithBrowser(text).catch(() => false)
      }
      if (!activeRef.current || generationRef.current !== generation) return
      onEnd?.()
      if (failed) {
        setStatus(browserFallback
          ? 'Madina server ovozi ishlamadi; qurilma ovozidan foydalanildi.'
          : 'Madina ovozi ijro etilmadi. Javob matni ekranda ko‘rsatilgan.')
      }
    }
    const handleAnalysisReadout = (event) => {
      const text = String(event.detail?.text || '').trim()
      if (!text) return
      modeRef.current = 'reply'
      setPhase('reply')
      setStatus('AI tahlil javobi Madina ovozida o‘qilyapti...')
      void speakMadina(text, resumeWakeListening)
    }
    const handleLizaStatus = (event) => {
      const message = String(event.detail?.message || '').trim()
      if (!message) return
      modeRef.current = 'reply'
      setPhase('reply')
      setStatus(message)
      void speakMadina(message, resumeWakeListening)
    }
    window.addEventListener('gmed:liza-readout', handleAnalysisReadout)
    window.addEventListener('gmed:liza-status', handleLizaStatus)
    const postAudio = async (url, samples, sampleRate) => {
      const formData = new FormData()
      formData.append('audio', createWav(samples, sampleRate), 'liza-audio.wav')
      return api.request(url, { method: 'POST', body: formData })
    }
    const handleWakeWord = () => {
      if (modeRef.current !== 'wake') return
      sessionOpenRef.current = true
      clearFrames()
      setMode('prompt', 'Liza uyg‘ondi. Buyruqni ayting.')
      void speakMadina('Ha, eshitaman. Savolingizni ayting.', () => {
        beginConversationCommand()
      })
    }
    const beginBookingConfirmation = () => {
      if (!activeRef.current || generationRef.current !== generation) return
      sessionOpenRef.current = true
      commandFramesRef.current = []
      commandCountRef.current = 0
      commandStartedRef.current = false
      commandStartedAtRef.current = Date.now()
      commandLastVoiceRef.current = commandStartedAtRef.current
      finishingCommandRef.current = false
      setMode('confirmation', 'Hozir “ha” yoki “yo‘q” deb javob bering.')
    }
    const beginDoctorSelection = () => {
      if (!activeRef.current || generationRef.current !== generation) return
      sessionOpenRef.current = true
      commandFramesRef.current = []
      commandCountRef.current = 0
      commandStartedRef.current = false
      commandStartedAtRef.current = Date.now()
      commandLastVoiceRef.current = commandStartedAtRef.current
      finishingCommandRef.current = false
      setMode('selection', 'Doktor ismini yoki 1, 2, 3 raqamini ayting.')
    }
    const pauseForRateLimit = (error, resume) => {
      if (error?.response?.status !== 429) return false
      const detail = String(error?.response?.data?.detail || error.message || '')
      const match = detail.match(/available in\s+(\d+(?:\.\d+)?)\s+seconds?/i)
      const waitSeconds = Math.min(
        match ? Math.max(1, Math.ceil(Number(match[1]))) : 60,
        2147480,
      )
      const waitMinutes = Math.floor(waitSeconds / 60)
      const remainingSeconds = waitSeconds % 60
      const waitLabel = waitMinutes
        ? `${waitMinutes} daqiqa${remainingSeconds ? ` ${remainingSeconds} soniya` : ''}`
        : `${waitSeconds} soniya`

      window.clearTimeout(rateLimitTimeoutRef.current)
      clearFrames()
      finishingCommandRef.current = true
      setMode('cooldown', `Ovozli so‘rovlar limiti tugadi. ${waitLabel} kuting; shu paytda yangi audio yuborilmaydi.`)
      rateLimitTimeoutRef.current = window.setTimeout(() => {
        rateLimitTimeoutRef.current = null
        if (!activeRef.current || generationRef.current !== generation) return
        resume?.()
      }, waitSeconds * 1000)
      return true
    }
    const handleCommandAction = async (action, booking, prescriptionCode) => {
      if (action === 'open_profile') {
        if (currentPathRef.current === '/patient') {
          window.dispatchEvent(new window.CustomEvent('gmed:liza-action', { detail: { action } }))
        } else {
          navigate('/patient?tab=profile')
        }
      } else if (action === 'open_booking') {
        if (!booking?.clinic_id || !booking?.doctor_id) {
          setStatus('Stomatolog qabul oynasini ochish ma’lumoti topilmadi.')
          return
        }
        const params = new URLSearchParams({
          lizaDoctor: booking.doctor_id,
          lizaSpecialtyPriceIds: (booking.specialty_price_ids || []).join(','),
        })
        navigate(`/clinic/${booking.clinic_id}?${params.toString()}`)
      } else if (action === 'read_analysis') {
        window.dispatchEvent(new window.CustomEvent('gmed:liza-action', { detail: { action } }))
      } else if (action === 'search_prescription') {
        await lookupPrescriptionByCode(prescriptionCode)
      } else if (action === 'prescription_code_required') {
        sessionOpenRef.current = false
        setPrescriptionCodeInput('')
        setPrescriptionDialogError('')
        setPrescriptionDialogOpen(true)
        setMode('reply', 'Retsept raqamini kiriting.')
      }
    }
    const handleCommandText = async (message) => {
      if (!activeRef.current || !message) return
      modeRef.current = 'processing'
      setPhase('processing')
      setLastTranscript(message)
      setStatus('Buyruq bajarilmoqda...')
      try {
        const response = await api.post('/liza/command/', { message })
        const result = resolvePrescriptionResult(response, message)
        if (!activeRef.current || generationRef.current !== generation) return
        setLastReply(result.reply || '')
        setStatus(result.reply ? 'Javob tayyor.' : 'Buyruq bajarildi.')
        await handleCommandAction(result.action, result.booking, result.prescription_code)
        if (result.action === 'prescription_code_required') {
          modeRef.current = 'reply'
          setPhase('reply')
          void speakMadina(result.reply || 'Retsept raqamini kiriting.', () => {
            modeRef.current = 'reply'
            setPhase('reply')
          })
          return
        }
        if (result.action === 'stop_listening') {
          sessionOpenRef.current = false
          void speakMadina(result.reply || 'Liza suhbatni to‘xtatdi.', () => {
            localStorage.removeItem(ENABLED_KEY)
            setEnabled(false)
            setPhase('off')
          })
          return
        }
        if (result.action === 'read_analysis') {
          modeRef.current = 'reply'
          setPhase('reply')
          return
        }
        modeRef.current = 'reply'
        setPhase('reply')
        const afterReply = result.action === 'await_booking_confirmation'
          ? beginBookingConfirmation
          : result.action === 'await_doctor_selection'
            ? beginDoctorSelection
            : resumeWakeListening
        void speakMadina(result.reply || 'Buyruq bajarildi.', afterReply)
      } catch (error) {
        if (pauseForRateLimit(error, resumeWakeListening)) return
        setStatus(error?.response?.data?.error || error.message || 'Buyruq bajarilmadi.')
        resumeWakeListening()
      }
    }
    const textAfterWakeWord = (transcript) => {
      const words = String(transcript || '')
        .toLowerCase()
        .replace(/[^a-z0-9' ]/g, ' ')
        .split(/\s+/)
        .filter(Boolean)
      const wakeIndex = words.findIndex((word) => ['liza', 'lisa', 'liz', 'lizza', 'lizaa'].includes(word))
      return wakeIndex < 0 ? '' : words.slice(wakeIndex + 1).join(' ').trim()
    }
    const checkWakeWord = async (samples, inputRate) => {
      if (!activeRef.current) return
      if (wakeRequestRef.current) {
        pendingWakeSegmentRef.current = { samples, inputRate }
        return
      }
      wakeRequestRef.current = true
      try {
        const result = await postAudio('/liza/wake/', samples, inputRate)
        if (result.transcript) setLastWakeTranscript(result.transcript)
        if (result.action === 'open_profile') {
          sessionOpenRef.current = true
          clearFrames()
          void handleCommandText(result.transcript)
        } else if (result.action === 'stop_listening') {
          sessionOpenRef.current = true
          clearFrames()
          void handleCommandText(result.transcript)
        } else if (result.wake) {
          sessionOpenRef.current = true
          const command = textAfterWakeWord(result.transcript)
          if (command) {
            clearFrames()
            void handleCommandText(command)
          } else {
            handleWakeWord()
          }
        }
      } catch (error) {
        if ([401, 403].includes(error?.response?.status)) {
          localStorage.removeItem(ENABLED_KEY)
          setEnabled(false)
          setStatus('G-MED sessiyasi tugadi. Qayta kiring.')
        } else if (pauseForRateLimit(error, resumeWakeListening)) {
          return
        } else {
          console.warn('Liza wake-word tekshiruvi bajarilmadi:', error)
        }
      } finally {
        wakeRequestRef.current = false
        const pendingSegment = pendingWakeSegmentRef.current
        pendingWakeSegmentRef.current = null
        if (pendingSegment && activeRef.current && modeRef.current === 'wake') {
          void checkWakeWord(pendingSegment.samples, pendingSegment.inputRate)
        }
      }
    }
    const finishCommand = async (inputRate) => {
      if (finishingCommandRef.current || !activeRef.current) return
      const inputMode = modeRef.current
      finishingCommandRef.current = true
      modeRef.current = 'processing'
      setPhase('processing')
      setStatus('Buyruq mahalliy ravishda aniqlanmoqda...')
      const samples = joinFrames(commandFramesRef.current, commandCountRef.current)
      commandFramesRef.current = []
      commandCountRef.current = 0
      if (
        samples.length < inputRate * (inputMode === 'confirmation' || inputMode === 'selection' ? 0.12 : 0.35)
        || (!commandStartedRef.current && inputMode !== 'confirmation' && inputMode !== 'selection')
      ) {
        setStatus(inputMode === 'confirmation'
          ? 'Javob eshitilmadi. “Ha” yoki “yo‘q” deb ayting.'
          : inputMode === 'selection'
            ? 'Doktor tanlovi eshitilmadi. Ismini yoki 1, 2, 3 raqamini ayting.'
            : 'Ovoz aniqlanmadi. Qayta “Liza” deng.')
        if (inputMode === 'confirmation') {
          beginBookingConfirmation()
          return
        }
        if (inputMode === 'selection') {
          beginDoctorSelection()
          return
        }
        resumeWakeListening()
        return
      }

      try {
        const response = await postAudio('/liza/voice/', samples, inputRate)
        const result = resolvePrescriptionResult(response)
        setLastTranscript(result.transcript || '')
        setLastReply(result.reply || '')
        setStatus(result.reply ? 'Javob tayyor.' : 'Javob topilmadi.')
        await handleCommandAction(result.action, result.booking, result.prescription_code)
        if (result.action === 'prescription_code_required') {
          modeRef.current = 'reply'
          setPhase('reply')
          void speakMadina(result.reply || 'Retsept raqamini kiriting.', () => {
            modeRef.current = 'reply'
            setPhase('reply')
          })
          return
        }
        if (result.action === 'stop_listening') {
          sessionOpenRef.current = false
          void speakMadina(result.reply || 'Liza suhbatni to‘xtatdi.', () => {
            localStorage.removeItem(ENABLED_KEY)
            setEnabled(false)
            setPhase('off')
          })
          return
        }
        if (result.action === 'open_booking') {
          setStatus('Qabulga yozilish oynasi ochilyapti.')
          modeRef.current = 'reply'
          setPhase('reply')
          void speakMadina(result.reply || 'Qabul oynasi ochildi.', resumeWakeListening)
          return
        }
        if (result.action === 'read_analysis') {
          modeRef.current = 'reply'
          setPhase('reply')
          return
        }
        if (result.action === 'await_booking_confirmation') {
          modeRef.current = 'reply'
          setPhase('reply')
          void speakMadina(result.reply || 'Ha yoki yo‘q deb javob bering.', beginBookingConfirmation)
          return
        }
        if (result.action === 'await_doctor_selection') {
          modeRef.current = 'reply'
          setPhase('reply')
          void speakMadina(
            result.reply || 'Doktor ismini yoki 1, 2, 3 raqamini ayting.',
            beginDoctorSelection,
          )
          return
        }
        if (result.action === 'open_profile') {
          setStatus('Bemor profilingiz ochildi. ' + (result.reply || ''))
        }
        modeRef.current = 'reply'
        setPhase('reply')
        void speakMadina(result.reply || 'Kechirasiz, javob topilmadi.', resumeWakeListening)
      } catch (error) {
        if (pauseForRateLimit(
          error,
          inputMode === 'confirmation'
            ? beginBookingConfirmation
            : inputMode === 'selection'
              ? beginDoctorSelection
              : resumeWakeListening,
        )) return
        const message = error?.response?.data?.error || error.message || 'Ovozli buyruq bajarilmadi.'
        setStatus(message)
        if (inputMode === 'confirmation') beginBookingConfirmation()
        else if (inputMode === 'selection') beginDoctorSelection()
        else resumeWakeListening()
      }
    }
    confirmationChoiceHandlerRef.current = (answer) => {
      if (modeRef.current === 'confirmation') void handleCommandText(answer)
    }

    const start = async () => {
      let stream = pendingStreamRef.current
      pendingStreamRef.current = null
      try {
        if (!stream) stream = await navigator.mediaDevices.getUserMedia({
          audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
        })
        if (cancelled || generationRef.current !== generation) {
          stream.getTracks().forEach((track) => track.stop())
          return
        }

        streamRef.current = stream
        const AudioContextClass = window.AudioContext || window.webkitAudioContext
        const context = new AudioContextClass({ sampleRate: 16000 })
        contextRef.current = context
        await context.resume()
        if (cancelled || generationRef.current !== generation) return
        wakeSegmentSamplesRef.current = Math.round(context.sampleRate * WAKE_SEGMENT_SECONDS)
        wakeHopSamplesRef.current = Math.round(context.sampleRate * (WAKE_SEGMENT_SECONDS - WAKE_OVERLAP_SECONDS))
        const source = context.createMediaStreamSource(stream)
        const processor = context.createScriptProcessor(4096, 1, 1)
        const silentOutput = context.createGain()
        silentOutput.gain.value = 0
        sourceRef.current = source
        processorRef.current = processor
        processor.onaudioprocess = (event) => {
          if (!activeRef.current) return
          const frame = new Float32Array(event.inputBuffer.getChannelData(0))
          let energy = 0
          for (let index = 0; index < frame.length; index += 1) energy += frame[index] * frame[index]
          const mode = modeRef.current
          const voiceThreshold = mode === 'confirmation' || mode === 'selection' ? 0.0035 : 0.0045
          const hasVoice = Math.sqrt(energy / frame.length) > voiceThreshold

          if (mode === 'wake') {
            wakeFramesRef.current.push(frame)
            wakeCountRef.current += frame.length
            wakeHasVoiceRef.current = wakeHasVoiceRef.current || hasVoice
            if (wakeCountRef.current >= wakeSegmentSamplesRef.current) {
              const combined = joinFrames(wakeFramesRef.current, wakeCountRef.current)
              const segment = combined.slice(0, wakeSegmentSamplesRef.current)
              const remainder = combined.slice(wakeHopSamplesRef.current)
              const shouldCheck = wakeHasVoiceRef.current
              wakeFramesRef.current = remainder.length ? [remainder] : []
              wakeCountRef.current = remainder.length
              let remainderEnergy = 0
              for (let index = 0; index < remainder.length; index += 1) {
                remainderEnergy += remainder[index] * remainder[index]
              }
              wakeHasVoiceRef.current = remainder.length > 0
                && Math.sqrt(remainderEnergy / remainder.length) > voiceThreshold
              if (shouldCheck) void checkWakeWord(segment, context.sampleRate)
            }
          } else if (mode === 'command' || mode === 'confirmation' || mode === 'selection') {
            commandFramesRef.current.push(frame)
            commandCountRef.current += frame.length
            if (hasVoice) {
              commandStartedRef.current = true
              commandLastVoiceRef.current = Date.now()
            }
            const now = Date.now()
            if (commandStartedRef.current && now - commandLastVoiceRef.current >= SILENCE_END_MS) {
              void finishCommand(context.sampleRate)
            } else if (now - commandStartedAtRef.current >= (
              mode === 'confirmation' ? BOOKING_CONFIRMATION_MAX_MS : COMMAND_MAX_MS
            )) {
              void finishCommand(context.sampleRate)
            }
          }
        }
        source.connect(processor)
        processor.connect(silentOutput)
        silentOutput.connect(context.destination)
        activeRef.current = true
        setMode('wake', 'Liza tinglayapti. Uyg‘otish uchun “Liza” deng.')
      } catch (error) {
        stream?.getTracks().forEach((track) => track.stop())
        if (!cancelled) {
          localStorage.removeItem(ENABLED_KEY)
          setEnabled(false)
          setPhase('error')
          setStatus(error.name === 'NotAllowedError'
            ? 'Mikrofon ruxsatini bering va Liza tugmasini qayta yoqing.'
            : 'Mikrofon ishga tushmadi. Brauzer ruxsatlarini tekshiring.')
        }
      }
    }

    void start()
    return () => {
      cancelled = true
      activeRef.current = false
      modeRef.current = 'off'
      sessionOpenRef.current = false
      confirmationChoiceHandlerRef.current = null
      prescriptionDialogCancelHandlerRef.current = null
      window.clearTimeout(rateLimitTimeoutRef.current)
      rateLimitTimeoutRef.current = null
      generationRef.current += 1
      window.removeEventListener('gmed:liza-readout', handleAnalysisReadout)
      window.removeEventListener('gmed:liza-status', handleLizaStatus)
      clearFrames()
      speechAudioRef.current?.pause()
      speechAudioRef.current = null
      if (speechUrlRef.current) {
        URL.revokeObjectURL(speechUrlRef.current)
        speechUrlRef.current = null
      }
      if (processorRef.current) {
        processorRef.current.onaudioprocess = null
        processorRef.current.disconnect()
        processorRef.current = null
      }
      sourceRef.current?.disconnect()
      sourceRef.current = null
      streamRef.current?.getTracks().forEach((track) => track.stop())
      streamRef.current = null
      if (contextRef.current) {
        void contextRef.current.close()
        contextRef.current = null
      }
    }
  }, [enabled, isAssistantAvailable, isVisible])

  const toggleAssistant = async () => {
    if (enabled) {
      enableRequestRef.current += 1
      sessionOpenRef.current = false
      localStorage.removeItem(ENABLED_KEY)
      pendingStreamRef.current?.getTracks().forEach((track) => track.stop())
      pendingStreamRef.current = null
      setEnabled(false)
      setPhase('off')
      setStatus('Liza tinglashi to‘xtatildi.')
      return
    }
    if (!isAssistantAvailable) return
    if (!getAccessToken()) {
      setPhase('error')
      setStatus('Avval G-MED hisobingizga kiring.')
      return
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setPhase('error')
      setStatus('Mikrofon uchun HTTPS yoki localhost kerak.')
      return
    }

    const requestId = ++enableRequestRef.current
    setPhase('connecting')
    setStatus('Mikrofon ruxsatini kutyapman...')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      })
      if (requestId !== enableRequestRef.current) {
        stream.getTracks().forEach((track) => track.stop())
        return
      }
      pendingStreamRef.current = stream
      localStorage.setItem(ENABLED_KEY, 'true')
      setEnabled(true)
    } catch (error) {
      setPhase('error')
      setStatus(error.name === 'NotAllowedError'
        ? 'Mikrofon ruxsati berilmadi. Brauzer sozlamasidan ruxsat bering.'
        : 'Mikrofon ulanmagan yoki brauzer uni qo‘llamaydi.')
    }
  }

  if (!isAssistantAvailable) return null

  const assistantButton = (
    <button
      type="button"
      className="liza-assistant-button"
      data-enabled={enabled}
      aria-pressed={enabled}
      aria-label={enabled ? 'Liza tinglashini to‘xtatish' : 'Liza ovozli yordamchisini yoqish'}
      onClick={toggleAssistant}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="9" y="3" width="6" height="12" rx="3" />
        <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3m-4 0h8" />
      </svg>
      <span>{enabled ? (phase === 'wake' ? 'Liza tinglayapti' : 'Liza') : 'Liza'}</span>
      <span className="liza-assistant-indicator" aria-hidden="true" />
    </button>
  )

  return (
    <div className="liza-assistant" data-phase={phase}>
      {status ? (
        <div className="liza-assistant-status" role="status" aria-live="polite">
          <span className="liza-assistant-status-title">{phase === 'wake' ? 'Liza tayyor' : 'Liza'}</span>
          <span className="liza-assistant-status-message">{status}</span>
          {lastWakeTranscript && phase === 'wake' ? <span className="liza-assistant-last-reply">Oxirgi eshitilgan: {lastWakeTranscript}</span> : null}
          {lastTranscript ? <span className="liza-assistant-last-reply">Aniqlangan buyruq: {lastTranscript}</span> : null}
          {lastReply && phase !== 'wake' ? <span className="liza-assistant-last-reply">{lastReply}</span> : null}
          {phase === 'confirmation' ? (
            <div className="liza-assistant-confirmation-actions">
              <button type="button" onClick={() => confirmationChoiceHandlerRef.current?.('ha')}>Ha</button>
              <button type="button" onClick={() => confirmationChoiceHandlerRef.current?.('yo‘q')}>Yo‘q</button>
            </div>
          ) : null}
        </div>
      ) : null}
      {prescriptionDialogOpen ? (
        <div
          className="liza-prescription-dialog-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closePrescriptionDialog()
          }}
        >
          <section
            className="liza-prescription-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="liza-prescription-dialog-title"
          >
            <div className="liza-prescription-dialog-header">
              <div>
                <h2 id="liza-prescription-dialog-title">Retsept raqamini kiriting</h2>
                <p>Dorilarni retsept raqami bo‘yicha dorixonalardan qidiramiz.</p>
              </div>
              <button
                type="button"
                className="liza-prescription-dialog-close"
                aria-label="Oynani yopish"
                onClick={closePrescriptionDialog}
                disabled={prescriptionLookupLoading}
              >
                ×
              </button>
            </div>
            <form onSubmit={submitPrescriptionCode}>
              {lastPrescriptionCode ? (
                <div className="liza-prescription-last-code">
                  <span>Oxirgi retsept raqami</span>
                  <strong>{lastPrescriptionCode}</strong>
                  <button type="button" onClick={() => {
                    setPrescriptionCodeInput(lastPrescriptionCode)
                    setPrescriptionDialogError('')
                  }}>
                    Shu raqamni ishlatish
                  </button>
                </div>
              ) : null}
              <label htmlFor="liza-prescription-code">8 xonali retsept raqami</label>
              <input
                id="liza-prescription-code"
                type="text"
                inputMode="numeric"
                autoComplete="off"
                autoFocus
                maxLength={8}
                value={prescriptionCodeInput}
                onChange={(event) => {
                  setPrescriptionCodeInput(event.target.value.replace(/\D/g, '').slice(0, 8))
                  setPrescriptionDialogError('')
                }}
                aria-invalid={Boolean(prescriptionDialogError)}
                aria-describedby={prescriptionDialogError ? 'liza-prescription-code-error' : undefined}
                placeholder="Masalan: 12345678"
              />
              {prescriptionDialogError ? (
                <p className="liza-prescription-dialog-error" id="liza-prescription-code-error" role="alert">
                  {prescriptionDialogError}
                </p>
              ) : null}
              <div className="liza-prescription-dialog-actions">
                <button
                  type="button"
                  className="liza-prescription-dialog-cancel"
                  onClick={closePrescriptionDialog}
                  disabled={prescriptionLookupLoading}
                >
                  Bekor qilish
                </button>
                <button
                  type="submit"
                  className="liza-prescription-dialog-submit"
                  disabled={prescriptionLookupLoading || prescriptionCodeInput.length !== 8}
                >
                  {prescriptionLookupLoading ? 'Qidirilmoqda...' : 'Dorilarni qidirish'}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
      {assistantButton}
    </div>
  )
}

export default LizaAssistant