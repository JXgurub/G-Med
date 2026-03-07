import { useEffect, useRef } from 'react'

const randomBetween = (min, max) => {
  if (max <= min) return min
  return Math.floor(Math.random() * (max - min + 1)) + min
}

export const useSmartAutoRefresh = ({
  enabled = true,
  callback,
  minIntervalMs = 45000,
  maxIntervalMs = 60000,
  immediate = true,
  maxBackoffMs = 180000,
}) => {
  const timerRef = useRef(null)
  const inFlightRef = useRef(false)
  const stoppedRef = useRef(false)
  const failureCountRef = useRef(0)
  const callbackRef = useRef(callback)

  useEffect(() => {
    callbackRef.current = callback
  }, [callback])

  useEffect(() => {
    if (!enabled || typeof callbackRef.current !== 'function') return

    stoppedRef.current = false

    const clearTimer = () => {
      if (timerRef.current) {
        window.clearTimeout(timerRef.current)
        timerRef.current = null
      }
    }

    const getDelay = () => {
      const baseDelay = randomBetween(minIntervalMs, maxIntervalMs)
      const backoffFactor = Math.min(2 ** failureCountRef.current, 4)
      return Math.min(baseDelay * backoffFactor, maxBackoffMs)
    }

    const scheduleNext = () => {
      if (stoppedRef.current) return
      clearTimer()
      timerRef.current = window.setTimeout(() => {
        void execute()
      }, getDelay())
    }

    const execute = async () => {
      if (stoppedRef.current || !enabled) return
      if (inFlightRef.current) {
        scheduleNext()
        return
      }

      if (typeof document !== 'undefined' && document.hidden) {
        scheduleNext()
        return
      }

      if (typeof navigator !== 'undefined' && navigator.onLine === false) {
        scheduleNext()
        return
      }

      inFlightRef.current = true
      try {
        await callbackRef.current()
        failureCountRef.current = 0
      } catch (error) {
        failureCountRef.current += 1
      } finally {
        inFlightRef.current = false
        scheduleNext()
      }
    }

    const handleVisibilityChange = () => {
      if (document.hidden) return
      clearTimer()
      void execute()
    }

    const handleOnline = () => {
      clearTimer()
      void execute()
    }

    if (immediate) {
      void execute()
    } else {
      scheduleNext()
    }

    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', handleVisibilityChange)
    }
    if (typeof window !== 'undefined') {
      window.addEventListener('online', handleOnline)
    }

    return () => {
      stoppedRef.current = true
      clearTimer()
      if (typeof document !== 'undefined') {
        document.removeEventListener('visibilitychange', handleVisibilityChange)
      }
      if (typeof window !== 'undefined') {
        window.removeEventListener('online', handleOnline)
      }
    }
  }, [enabled, immediate, minIntervalMs, maxIntervalMs, maxBackoffMs])
}

export default useSmartAutoRefresh
