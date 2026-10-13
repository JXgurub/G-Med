import { Suspense, lazy, useCallback, useEffect, useRef, useState } from 'react'
import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom'
import { Navigate } from 'react-router-dom'
import { ClinicProvider } from './context/ClinicContext'
import { DoctorProvider } from './context/DoctorContext'
import { AdminProvider } from './context/AdminContext'
import { PatientProvider } from './context/PatientContext'
import { PharmacyProvider } from './context/PharmacyContext'
import { PaymentProvider } from './context/PaymentContext'
import { authApi, patientsApi, siteSettingsApi } from './services/api'
import { useNotifications } from './hooks/useWebSocket'
const Layout = lazy(() => import('./layouts/Layout'))
const Home = lazy(() => import('./pages/Home'))
const ChildSafety = lazy(() => import('./pages/ChildSafety'))
const AnalysisPage = lazy(() => import('./pages/AnalysisPage'))
const LoginRedirect = lazy(() => import('./pages/LoginRedirect'))
const ClinicDetailPage = lazy(() => import('./pages/ClinicDetailPage'))
const ClinicOwnerLogin = lazy(() => import('./pages/ClinicOwnerLogin'))
const ClinicOwnerForgotPassword = lazy(() => import('./pages/ClinicOwnerForgotPassword'))
const ClinicOwnerDashboard = lazy(() => import('./pages/ClinicOwnerDashboard'))
const DoctorLogin = lazy(() => import('./pages/DoctorLogin'))
const DoctorForgotPassword = lazy(() => import('./pages/DoctorForgotPassword'))
const DoctorDashboard = lazy(() => import('./pages/DoctorDashboard'))
const AdminLogin = lazy(() => import('./pages/AdminLogin'))
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'))
const PatientPortal = lazy(() => import('./pages/PatientPortal'))
const PatientLogin = lazy(() => import('./pages/PatientLogin'))
const PatientForgotPassword = lazy(() => import('./pages/PatientForgotPassword'))
const PharmacyOwnerLogin = lazy(() => import('./pages/PharmacyOwnerLogin'))
const PharmacyOwnerForgotPassword = lazy(() => import('./pages/PharmacyOwnerForgotPassword'))
const PharmacyOwnerDashboard = lazy(() => import('./pages/PharmacyOwnerDashboard'))
const ReceptionLogin = lazy(() => import('./pages/ReceptionLogin'))
const ReceptionDashboard = lazy(() => import('./pages/ReceptionDashboard'))
const SecretLoginHub = lazy(() => import('./pages/SecretLoginHub'))
const PaymentPage = lazy(() => import('./pages/PaymentPage'))
const SubscriptionPaymentPage = lazy(() => import('./pages/SubscriptionPaymentPage'))
const SubscriptionBlockedPage = lazy(() => import('./pages/SubscriptionBlockedPage'))
const PaymentSuccess = lazy(() => import('./pages/PaymentSuccess'))
const PaymentHistory = lazy(() => import('./components/PaymentHistory'))
import PwaStatusWidget from './components/PwaStatusWidget'
import LizaAssistant from './components/LizaAssistant'
const Contact = lazy(() => import('./pages/Contact'))

const RouteLoader = () => <div style={{ padding: '2rem', textAlign: 'center' }}>Yuklanmoqda...</div>

const BroadcastNotificationListener = () => {
  const location = useLocation()
  const [userId, setUserId] = useState(null)
  const [notice, setNotice] = useState(null)
  const [noticeQueue, setNoticeQueue] = useState([])
  const [pushConfig, setPushConfig] = useState(null)
  const [pushStatus, setPushStatus] = useState('checking')
  const resolvedToken = useRef('')
  const seenNotificationIds = useRef(new Set())

  const enqueueNotifications = useCallback((notifications) => {
    setNoticeQueue((current) => {
      const pendingIds = new Set(current.map((notification) => notification.id))
      const unseen = notifications.filter((notification) => (
        notification.id
        && !seenNotificationIds.current.has(notification.id)
        && !pendingIds.has(notification.id)
      ))
      unseen.forEach((notification) => seenNotificationIds.current.add(notification.id))
      return [...current, ...unseen]
    })
  }, [])

  useEffect(() => {
    const token = sessionStorage.getItem('doctor_access_token')
      || sessionStorage.getItem('access_token')
      || localStorage.getItem('access_token')
    const role = sessionStorage.getItem('user_role') || localStorage.getItem('user_role')
    if (!token || role === 'admin') {
      resolvedToken.current = ''
      setUserId(null)
      return
    }
    if (resolvedToken.current === token && userId) return

    let cancelled = false
    authApi.getProfile()
      .then((profile) => {
        if (!cancelled) {
          resolvedToken.current = token
          setUserId(profile?.id || null)
        }
      })
      .catch(() => {
        if (!cancelled) setUserId(null)
      })
    return () => { cancelled = true }
  }, [location.pathname, userId])

  useEffect(() => {
    if (!userId) {
      seenNotificationIds.current.clear()
      setNotice(null)
      setNoticeQueue([])
      setPushConfig(null)
      setPushStatus('checking')
      return
    }
    let cancelled = false
    siteSettingsApi.getBroadcastInbox()
      .then((notifications) => {
        if (!cancelled) enqueueNotifications(Array.isArray(notifications) ? notifications : [])
      })
      .catch((error) => console.error('Bildirishnomalarni yuklashda xatolik:', error))
    return () => { cancelled = true }
  }, [enqueueNotifications, userId])

  const registerPushDevice = useCallback(async (config) => {
    if (!config?.enabled || !userId || !('serviceWorker' in navigator) || !('PushManager' in window)) {
      setPushStatus('unsupported')
      return
    }
    try {
      const registration = await navigator.serviceWorker.register('/push/sw.js', { scope: '/push/' })
      let subscription = await registration.pushManager.getSubscription()
      if (!subscription) {
        subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: decodeVapidPublicKey(config.public_key),
        })
      }
      await siteSettingsApi.registerWebPushSubscription(subscription.toJSON())
      setPushStatus('enabled')
    } catch (error) {
      console.error('Telefon bildirishnomasini sozlashda xatolik:', error)
      setPushStatus('error')
    }
  }, [userId])

  useEffect(() => {
    if (!userId) return undefined
    let cancelled = false
    siteSettingsApi.getWebPushConfig()
      .then((config) => {
        if (cancelled) return
        setPushConfig(config)
        if (!config?.enabled) {
          setPushStatus('unavailable')
        } else if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
          setPushStatus('unsupported')
        } else if (Notification.permission === 'granted') {
          void registerPushDevice(config)
        } else if (Notification.permission === 'denied') {
          setPushStatus('denied')
        } else {
          setPushStatus('prompt')
        }
      })
      .catch(() => setPushStatus('error'))
    return () => { cancelled = true }
  }, [registerPushDevice, userId])

  const enablePushNotifications = async () => {
    if (!pushConfig?.enabled || !('Notification' in window)) return
    const permission = await Notification.requestPermission()
    if (permission === 'granted') {
      await registerPushDevice(pushConfig)
    } else {
      setPushStatus(permission === 'denied' ? 'denied' : 'prompt')
    }
  }

  const handleBroadcast = useCallback((event) => {
    const notification = event.detail?.data
    if (notification?.notification_type === 'admin_broadcast') {
      const payload = notification.payload || {}
      enqueueNotifications([{
        id: payload.notification_id,
        title: payload.title,
        message: payload.message,
        data: payload.data || {},
      }])
    }
  }, [enqueueNotifications])

  useEffect(() => {
    window.addEventListener('hospitoll:notification', handleBroadcast)
    return () => window.removeEventListener('hospitoll:notification', handleBroadcast)
  }, [handleBroadcast])

  useEffect(() => {
    if (!('serviceWorker' in navigator)) return undefined
    const handleServiceWorkerMessage = (event) => {
      if (event.data?.type !== 'medication-reminder-acknowledged') return
      const { acknowledgement_token: acknowledgementToken } = event.data
      setNotice((current) => (
        current?.data?.acknowledgement_token === acknowledgementToken ? null : current
      ))
      setNoticeQueue((current) => current.filter(
        (notification) => notification.data?.acknowledgement_token !== acknowledgementToken,
      ))
    }
    navigator.serviceWorker.addEventListener('message', handleServiceWorkerMessage)
    return () => navigator.serviceWorker.removeEventListener('message', handleServiceWorkerMessage)
  }, [])

  useEffect(() => {
    if (notice || noticeQueue.length === 0) return
    setNotice(noticeQueue[0])
    setNoticeQueue((current) => current.slice(1))
  }, [notice, noticeQueue])

  useEffect(() => {
    if (!notice) return undefined
    const timeout = window.setTimeout(() => setNotice(null), 10000)
    return () => window.clearTimeout(timeout)
  }, [notice])

  useNotifications(userId)

  return (
    <>
      {pushStatus === 'prompt' ? (
        <aside className="push-permission-prompt" role="status">
          <div>
            <strong>Telefon bildirishnomalarini yoqing</strong>
            <p>G-MED xabarlarini telefoningizning bildirishnomalar qatorida oling.</p>
          </div>
          <button type="button" onClick={enablePushNotifications}>Yoqish</button>
        </aside>
      ) : null}
      {pushStatus === 'denied' ? (
        <aside className="push-permission-prompt" role="status">
          <div>
            <strong>Bildirishnomalar ruxsat etilmagan</strong>
            <p>Telefon yoki brauzer sozlamalaridan G-MED bildirishnomalariga ruxsat bering.</p>
          </div>
        </aside>
      ) : null}
      {notice ? (
        <aside className="admin-broadcast-toast" role="status" aria-live="polite">
          <div>
            <strong>{notice.title || 'Bildirishnoma'}</strong>
            <p>{notice.message || ''}</p>
            {notice.data?.notification_type === 'medication_reminder'
              && notice.data.acknowledgement_token ? (
                <button
                  type="button"
                  className="admin-broadcast-ack"
                  onClick={() => {
                    patientsApi.acknowledgeMedicationReminder(notice.data.acknowledgement_token)
                      .then(() => setNotice(null))
                      .catch((error) => console.error('Dori eslatmasini tasdiqlab bo‘lmadi:', error))
                  }}
                >
                  Ichdingizmi?
                </button>
              ) : null}
          </div>
          <button
            type="button"
            aria-label="Bildirishnomani yopish"
            onClick={() => {
              const dismissed = notice
              setNotice(null)
              if (dismissed.id) {
                siteSettingsApi.markBroadcastRead(dismissed.id)
                  .catch((error) => console.error('Bildirishnomani o‘qilgan deb belgilab bo‘lmadi:', error))
              }
            }}
          >×</button>
        </aside>
      ) : null}
    </>
  )
}

const decodeVapidPublicKey = (base64Key) => {
  const padding = '='.repeat((4 - (base64Key.length % 4)) % 4)
  const decoded = atob((base64Key + padding).replace(/-/g, '+').replace(/_/g, '/'))
  return Uint8Array.from(decoded, (character) => character.charCodeAt(0))
}

function App() {
  return (
    <AdminProvider>
      <ClinicProvider>
        <DoctorProvider>
          <PatientProvider>
            <PharmacyProvider>
              <PaymentProvider>
                <Router>
                <PwaStatusWidget />
                <LizaAssistant />
                <BroadcastNotificationListener />
                <Suspense fallback={<RouteLoader />}>
                  <Routes>
                    <Route path="/" element={<Layout />}>
                      <Route index element={<Home />} />
                      <Route path="child-safety" element={<ChildSafety />} />
                      <Route path="login" element={<LoginRedirect />} />
                      <Route path="patient-login" element={<PatientLogin />} />
                      <Route path="patient-forgot-password" element={<PatientForgotPassword />} />
                      <Route path="contact" element={<Contact />} />
                      <Route path="clinic/:clinicId" element={<ClinicDetailPage />} />
                      <Route path="patient" element={<PatientPortal />} />
                      <Route path="pharmacy/*" element={<Navigate to="/" replace />} />
                    </Route>
                    <Route path="/clinic-owner-login" element={<ClinicOwnerLogin />} />
                    <Route path="/clinic-owner-forgot-password" element={<ClinicOwnerForgotPassword />} />
                    <Route path="/clinic-dashboard" element={<ClinicOwnerDashboard />} />
                    <Route path="/clinic-dashboard/directions" element={<Navigate to="/clinic-dashboard/services" replace />} />
                    <Route path="/clinic-dashboard/*" element={<ClinicOwnerDashboard />} />
                    <Route path="/doctor-login" element={<DoctorLogin />} />
                    <Route path="/doctor-forgot-password" element={<DoctorForgotPassword />} />
                    <Route path="/doctor-dashboard" element={<DoctorDashboard />} />
                    <Route path="/admin-login" element={<AdminLogin />} />
                    <Route path="/admin-dashboard" element={<AdminDashboard />} />
                    <Route path="/JXgroup" element={<SecretLoginHub />} />
                    <Route path="/analiz-tahlili/*" element={<AnalysisPage />} />
                    <Route path="/pharmacy-search" element={<Navigate to="/" replace />} />
                    <Route path="/pharmacy-owner-login" element={<PharmacyOwnerLogin />} />
                    <Route path="/pharmacy-owner-forgot-password" element={<PharmacyOwnerForgotPassword />} />
                    <Route path="/pharmacy-owner-dashboard" element={<PharmacyOwnerDashboard />} />
                    <Route path="/reception-login" element={<ReceptionLogin />} />
                    <Route path="/reception-dashboard" element={<ReceptionDashboard />} />
                    <Route path="/payment" element={<PaymentPage />} />
                    <Route path="/subscription-payment" element={<SubscriptionPaymentPage />} />
                    <Route path="/subscription-blocked" element={<SubscriptionBlockedPage />} />
                    <Route path="/payment/success" element={<PaymentSuccess />} />
                    <Route path="/payment-history" element={<PaymentHistory />} />
                  </Routes>
                </Suspense>
                </Router>
              </PaymentProvider>
            </PharmacyProvider>
          </PatientProvider>
        </DoctorProvider>
      </ClinicProvider>
    </AdminProvider>
  )
}

export default App
