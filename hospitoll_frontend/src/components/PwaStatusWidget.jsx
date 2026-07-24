import { useEffect, useMemo, useState } from 'react'
import { useLocation } from 'react-router-dom'
import './PwaStatusWidget.css'

const isStandalone = () => {
  return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true
}

const isMobileDevice = () => {
  return window.matchMedia('(max-width: 900px)').matches && window.matchMedia('(pointer: coarse)').matches
}

const getManualInstallHint = () => {
  const ua = window.navigator.userAgent || ''
  const isIOS = /iPad|iPhone|iPod/.test(ua)

  if (isIOS) {
    return "Safari menyusidagi Share tugmasini bosib 'Add to Home Screen' ni tanlang."
  }

  return "Brauzer menyusini ochib 'Install app' yoki 'Add to Home screen' ni tanlang."
}

const PwaStatusWidget = () => {
  const location = useLocation()
  const [deferredPrompt, setDeferredPrompt] = useState(null)
  const [isOnline, setIsOnline] = useState(window.navigator.onLine)
  const [isInstalled, setIsInstalled] = useState(isStandalone())
  const [offlineReady, setOfflineReady] = useState(false)
  const [isMobile, setIsMobile] = useState(isMobileDevice())
  const [bottomOffset, setBottomOffset] = useState(16)
  const [installHelp, setInstallHelp] = useState('')

  useEffect(() => {
    let readyTimeoutId = null

    const handleBeforeInstallPrompt = (event) => {
      event.preventDefault()
      setDeferredPrompt(event)
    }

    const handleInstalled = () => {
      setIsInstalled(true)
      setDeferredPrompt(null)
    } 

    const handleOnline = () => setIsOnline(true)
    const handleOffline = () => setIsOnline(false)
    const handleOfflineReady = () => {
      setOfflineReady(true)
      if (readyTimeoutId) {
        window.clearTimeout(readyTimeoutId)
      }
      readyTimeoutId = window.setTimeout(() => setOfflineReady(false), 5000)
    }
    const mediaQuery = window.matchMedia('(max-width: 900px) and (pointer: coarse)')
    const handleViewportChange = () => setIsMobile(mediaQuery.matches)

    const calculateBottomOffset = () => {
      const viewportHeight = window.innerHeight
      const candidates = Array.from(document.body.querySelectorAll('*')).filter((element) => {
        const htmlElement = element
        if (!htmlElement || htmlElement.className?.toString().includes('pwa-')) {
          return false
        }

        const style = window.getComputedStyle(htmlElement)
        if (style.display === 'none' || style.visibility === 'hidden') {
          return false
        }

        if (!['fixed', 'sticky'].includes(style.position)) {
          return false
        }

        const rect = htmlElement.getBoundingClientRect()
        if (rect.height < 24 || rect.height > 180) {
          return false
        }

        const nearBottom = viewportHeight - rect.bottom <= 20
        const wideEnough = rect.width >= window.innerWidth * 0.35
        return nearBottom && wideEnough
      })

      const maxBottomHeight = candidates.reduce((maxHeight, element) => {
        const rect = element.getBoundingClientRect()
        return Math.max(maxHeight, rect.height)
      }, 0)

      setBottomOffset(maxBottomHeight > 0 ? maxBottomHeight + 16 : 16)
    }

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    window.addEventListener('appinstalled', handleInstalled)
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    window.addEventListener('pwa-offline-ready', handleOfflineReady)
    window.addEventListener('resize', calculateBottomOffset)
    mediaQuery.addEventListener('change', handleViewportChange)

    const mutationObserver = new MutationObserver(calculateBottomOffset)
    mutationObserver.observe(document.body, { childList: true, subtree: true, attributes: true })

    calculateBottomOffset()

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
      window.removeEventListener('appinstalled', handleInstalled)
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
      window.removeEventListener('pwa-offline-ready', handleOfflineReady)
      window.removeEventListener('resize', calculateBottomOffset)
      mediaQuery.removeEventListener('change', handleViewportChange)
      mutationObserver.disconnect()
      if (readyTimeoutId) {
        window.clearTimeout(readyTimeoutId)
      }
    }
  }, [])

  const isWorkDashboardRoute = useMemo(() => {
    const path = location?.pathname || ''
    return /^\/(doctor-dashboard|clinic-dashboard|admin-dashboard|pharmacy-owner-dashboard)(\/|$)/.test(path)
  }, [location?.pathname])

  const canInstall = useMemo(
    () => !isWorkDashboardRoute && isMobile && !isInstalled,
    [isWorkDashboardRoute, isMobile, isInstalled]
  )

  const handleInstall = async () => {
    if (!deferredPrompt) {
      setInstallHelp(getManualInstallHint())
      window.setTimeout(() => setInstallHelp(''), 7000)
      return
    }

    deferredPrompt.prompt()
    const choice = await deferredPrompt.userChoice
    if (choice?.outcome === 'accepted') {
      setIsInstalled(true)
    }
    setDeferredPrompt(null)
    setInstallHelp('')
  }

  return (
    <>
      {!isOnline && (
        <div className="pwa-offline-banner" role="status" aria-live="polite">
          Internet yo'q. Ilova offline rejimda ishlayapti.
        </div>
      )}

      {offlineReady && (
        <div className="pwa-ready-toast" style={{ bottom: `${bottomOffset + 48}px` }} role="status" aria-live="polite">
          Offline rejim tayyor ✅
        </div>
      )}

      {installHelp && (
        <div className="pwa-install-help" style={{ bottom: `${bottomOffset + 52}px` }} role="status" aria-live="polite">
          {installHelp}
        </div>
      )}

      {canInstall && (
        <button className="pwa-install-btn" style={{ bottom: `${bottomOffset}px` }} onClick={handleInstall}>
          📲 Ilovani o'rnatish
        </button>
      )}
    </>
  )
}

export default PwaStatusWidget
