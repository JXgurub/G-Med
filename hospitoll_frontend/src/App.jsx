import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { Navigate } from 'react-router-dom'
import { ClinicProvider } from './context/ClinicContext'
import { DoctorProvider } from './context/DoctorContext'
import { AdminProvider } from './context/AdminContext'
import { PatientProvider } from './context/PatientContext'
import { PharmacyProvider } from './context/PharmacyContext'
import { PaymentProvider } from './context/PaymentContext'
import Layout from './layouts/Layout'
import Home from './pages/Home'
import ClinicDetailPage from './pages/ClinicDetailPage'
import ClinicOwnerLogin from './pages/ClinicOwnerLogin'
import ClinicOwnerDashboard from './pages/ClinicOwnerDashboard'
import DirectionsPage from './pages/DirectionsPage'
import DoctorLogin from './pages/DoctorLogin'
import DoctorDashboard from './pages/DoctorDashboard'
import AdminLogin from './pages/AdminLogin'
import AdminDashboard from './pages/AdminDashboard'
import PatientPortal from './pages/PatientPortal'
import PatientLogin from './pages/PatientLogin'
import PatientForgotPassword from './pages/PatientForgotPassword'
import PharmacyOwnerLogin from './pages/PharmacyOwnerLogin'
import PharmacyOwnerDashboard from './pages/PharmacyOwnerDashboard'
import SecretLoginHub from './pages/SecretLoginHub'
import PaymentPage from './pages/PaymentPage'
import SubscriptionPaymentPage from './pages/SubscriptionPaymentPage'
import SubscriptionBlockedPage from './pages/SubscriptionBlockedPage'
import PaymentSuccess from './pages/PaymentSuccess'
import PaymentHistory from './components/PaymentHistory'
import PwaStatusWidget from './components/PwaStatusWidget'
import Contact from './pages/Contact'

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
                <Routes>
                  <Route path="/" element={<Layout />}>
                    <Route index element={<Home />} />
                    <Route path="login" element={<DoctorLogin />} />
                    <Route path="patient-login" element={<PatientLogin />} />
                    <Route path="patient-forgot-password" element={<PatientForgotPassword />} />
                    <Route path="contact" element={<Contact />} />
                    <Route path="clinic/:clinicId" element={<ClinicDetailPage />} />
                    <Route path="patient" element={<PatientPortal />} />
                    <Route path="pharmacy/*" element={<Navigate to="/" replace />} />
                  </Route>
                  <Route path="/clinic-owner-login" element={<ClinicOwnerLogin />} />
                  <Route path="/clinic-dashboard" element={<ClinicOwnerDashboard />} />
                  <Route path="/clinic-dashboard/directions" element={<DirectionsPage />} />
                  <Route path="/clinic-dashboard/*" element={<ClinicOwnerDashboard />} />
                  <Route path="/doctor-login" element={<DoctorLogin />} />
                  <Route path="/doctor-dashboard" element={<DoctorDashboard />} />
                  <Route path="/admin-login" element={<AdminLogin />} />
                  <Route path="/admin-dashboard" element={<AdminDashboard />} />
                  <Route path="/JXgroup" element={<SecretLoginHub />} />
                  <Route path="/pharmacy-search" element={<Navigate to="/" replace />} />
                  <Route path="/pharmacy-owner-login" element={<PharmacyOwnerLogin />} />
                  <Route path="/pharmacy-owner-dashboard" element={<PharmacyOwnerDashboard />} />
                  <Route path="/payment" element={<PaymentPage />} />
                  <Route path="/subscription-payment" element={<SubscriptionPaymentPage />} />
                  <Route path="/subscription-blocked" element={<SubscriptionBlockedPage />} />
                  <Route path="/payment/success" element={<PaymentSuccess />} />
                  <Route path="/payment-history" element={<PaymentHistory />} />
                </Routes>
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
