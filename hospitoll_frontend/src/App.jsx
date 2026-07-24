import { Suspense, lazy } from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { Navigate } from 'react-router-dom'
import { ClinicProvider } from './context/ClinicContext'
import { DoctorProvider } from './context/DoctorContext'
import { AdminProvider } from './context/AdminContext'
import { PatientProvider } from './context/PatientContext'
import { PharmacyProvider } from './context/PharmacyContext'
import { PaymentProvider } from './context/PaymentContext'
const Layout = lazy(() => import('./layouts/Layout'))
const Home = lazy(() => import('./pages/Home'))
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
const SecretLoginHub = lazy(() => import('./pages/SecretLoginHub'))
const PaymentPage = lazy(() => import('./pages/PaymentPage'))
const SubscriptionPaymentPage = lazy(() => import('./pages/SubscriptionPaymentPage'))
const SubscriptionBlockedPage = lazy(() => import('./pages/SubscriptionBlockedPage'))
const PaymentSuccess = lazy(() => import('./pages/PaymentSuccess'))
const PaymentHistory = lazy(() => import('./components/PaymentHistory'))
import PwaStatusWidget from './components/PwaStatusWidget'
const Contact = lazy(() => import('./pages/Contact'))

const RouteLoader = () => <div style={{ padding: '2rem', textAlign: 'center' }}>Yuklanmoqda...</div>

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
                <Suspense fallback={<RouteLoader />}>
                  <Routes>
                    <Route path="/" element={<Layout />}>
                      <Route index element={<Home />} />
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
                    <Route path="/pharmacy-search" element={<Navigate to="/" replace />} />
                    <Route path="/pharmacy-owner-login" element={<PharmacyOwnerLogin />} />
                    <Route path="/pharmacy-owner-forgot-password" element={<PharmacyOwnerForgotPassword />} />
                    <Route path="/pharmacy-owner-dashboard" element={<PharmacyOwnerDashboard />} />
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
