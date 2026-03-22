// API service utilities
// This will contain functions to interact with the backend API

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const CLIENT_ALERT_ENDPOINT = '/site-settings/system-alerts/client/'
const ACCESS_TOKEN_KEY = 'access_token'
const REFRESH_TOKEN_KEY = 'refresh_token'
const DOCTOR_ACCESS_TOKEN_KEY = 'doctor_access_token'
const DOCTOR_REFRESH_TOKEN_KEY = 'doctor_refresh_token'

let refreshPromise = null
let isReportingClientError = false

const getApiOrigin = () => {
  try {
    if (/^https?:\/\//i.test(API_BASE_URL)) {
      return new URL(API_BASE_URL).origin
    }
    if (typeof window !== 'undefined' && window.location?.origin) {
      return window.location.origin
    }
  } catch (error) {
    // no-op
  }
  return ''
}

export const resolveMediaUrl = (value) => {
  if (!value) return ''
  const raw = String(value).trim()
  if (!raw) return ''

  if (/^(data:|blob:)/i.test(raw)) {
    return raw
  }

  const origin = getApiOrigin()

  if (/^https?:\/\//i.test(raw)) {
    try {
      const parsed = new URL(raw)
      const isLocalHost = ['localhost', '127.0.0.1', '0.0.0.0'].includes(parsed.hostname)
      if (isLocalHost && origin) {
        return `${origin}${parsed.pathname}${parsed.search}${parsed.hash}`
      }
    } catch (error) {
      // keep original URL when parsing fails
    }
    return raw
  }

  if (!origin) return raw

  if (raw.startsWith('/')) {
    return `${origin}${raw}`
  }

  return `${origin}/${raw}`
}

// Helper: Get storage based on user role (doctors use sessionStorage for multi-tab support)
const getStorage = () => {
  const userRole = sessionStorage.getItem('user_role') || localStorage.getItem('user_role')
  return userRole === 'doctor' ? sessionStorage : localStorage
}

// Helper: Get token key based on storage type
const getTokenKey = (baseKey) => {
  const storage = getStorage()
  if (storage === sessionStorage) {
    return baseKey === ACCESS_TOKEN_KEY ? DOCTOR_ACCESS_TOKEN_KEY : DOCTOR_REFRESH_TOKEN_KEY
  }
  return baseKey
}

const isAuthEndpoint = (endpoint) => {
  return endpoint.startsWith('/users/token') || endpoint.startsWith('/users/patient-token')
}

const shouldReportApiError = (endpoint, status) => {
  if (!endpoint || endpoint.includes(CLIENT_ALERT_ENDPOINT)) return false

  const normalizedEndpoint = String(endpoint || '')
  const endpointPath = normalizedEndpoint.split('?')[0]
  const suppressedPollingPrefixes = [
    '/site-settings/contact-leads/admin/',
    '/site-settings/system-alerts/admin/',
    '/medical/appointments/clinic_dashboard_stats/',
  ]

  if (suppressedPollingPrefixes.some((prefix) => endpointPath.startsWith(prefix))) {
    return false
  }

  if (isAuthEndpoint(endpointPath) && [400, 401].includes(status)) {
    return false
  }

  if (
    (endpointPath.startsWith('/clinics/my/') || endpointPath.startsWith('/pharmacies/my/'))
    && [401, 403, 404].includes(status)
  ) {
    return false
  }

  return true
}

const refreshAccessToken = async () => {
  // If a refresh is already in progress, wait for it instead of making a new request
  if (refreshPromise) {
    return refreshPromise
  }

  const storage = getStorage()
  const refreshTokenKey = getTokenKey(REFRESH_TOKEN_KEY)
  const accessTokenKey = getTokenKey(ACCESS_TOKEN_KEY)
  const refreshToken = storage.getItem(refreshTokenKey)
  if (!refreshToken) return null

  refreshPromise = (async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/users/token/refresh/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ refresh: refreshToken })
      })

      if (!response.ok) {
        storage.removeItem(accessTokenKey)
        storage.removeItem(refreshTokenKey)
        return null
      }

      const data = await response.json()
      if (data?.access) {
        storage.setItem(accessTokenKey, data.access)
        return data.access
      }
      return null
    } finally {
      refreshPromise = null
    }
  })()

  return refreshPromise
}

export const api = {
  reportClientError: async (payload = {}) => {
    if (isReportingClientError) return
    try {
      isReportingClientError = true
      await fetch(`${API_BASE_URL}${CLIENT_ALERT_ENDPOINT}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        keepalive: true,
        body: JSON.stringify({
          alert_type: String(payload.alert_type || 'frontend_error').slice(0, 120),
          message: String(payload.message || 'Unknown frontend error').slice(0, 3000),
          severity: payload.severity || 'error',
          url: typeof window !== 'undefined' ? window.location?.href : '',
          context: payload.context || {},
          traceback: String(payload.traceback || ''),
        }),
      })
    } catch (error) {
      // no-op: avoid reporting loop
    } finally {
      isReportingClientError = false
    }
  },

  // Generic request handler
  request: async (endpoint, options = {}) => {
    const url = `${API_BASE_URL}${endpoint}`
    const storage = getStorage()
    const accessTokenKey = getTokenKey(ACCESS_TOKEN_KEY)
    const token = storage.getItem(accessTokenKey)
    const isRetry = options._retry === true
    const isFormData = typeof FormData !== 'undefined' && options?.body instanceof FormData
    const providedHeaders = options.headers || {}
    const method = (options.method || 'GET').toUpperCase()
    const shouldSetJsonContentType = !isFormData && !Object.prototype.hasOwnProperty.call(providedHeaders, 'Content-Type')
    const contentTypeHeader = shouldSetJsonContentType ? { 'Content-Type': 'application/json' } : {}
    
    try {
      const response = await fetch(url, {
        ...options,
        cache: method === 'GET' ? 'no-store' : options.cache,
        headers: {
          ...contentTypeHeader,
          ...(token && { 'Authorization': `Bearer ${token}` }),
          ...providedHeaders,
        },
        credentials: 'include',
      })

      if (response.status === 401 && !isRetry && !isAuthEndpoint(endpoint)) {
        console.log(`[API] 401 received for ${endpoint}, attempting refresh...`)
        const newToken = await refreshAccessToken()
        if (newToken) {
          console.log(`[API] Token refreshed successfully, retrying ${endpoint}`)
          return api.request(endpoint, { ...options, _retry: true })
        } else {
          console.warn(`[API] Token refresh failed for ${endpoint}, tokens cleared`)
        }
      }
      
      if (!response.ok) {
        let errorMessage = `HTTP error! status: ${response.status}`
        let errorData = {}
        try {
          errorData = await response.json()
          errorMessage = errorData.detail || errorData.message || JSON.stringify(errorData)
        } catch (e) {
          // If parsing JSON fails, use status text
          errorMessage = response.statusText || errorMessage
        }
        const error = new Error(errorMessage)
        error.response = { status: response.status, data: errorData }
        console.error(`[API] Request failed: ${endpoint} - ${response.status}`, errorMessage)

        if (shouldReportApiError(endpoint, response.status)) {
          void api.reportClientError({
            alert_type: 'frontend_api_error',
            message: errorMessage,
            severity: response.status >= 500 ? 'error' : 'warning',
            context: {
              endpoint,
              method,
              status: response.status,
              response_data: errorData,
            },
            traceback: error?.stack || '',
          })
        }

        throw error
      }
      
      // Handle 204 No Content (e.g., DELETE requests)
      if (response.status === 204) {
        return null
      }
      
      return await response.json()
    } catch (error) {
      console.error('[API] Request error:', endpoint, error)

      if (shouldReportApiError(endpoint, error?.response?.status)) {
        void api.reportClientError({
          alert_type: 'frontend_network_error',
          message: error?.message || 'Network/API request failed',
          severity: 'error',
          context: {
            endpoint,
            method,
          },
          traceback: error?.stack || '',
        })
      }

      throw error
    }
  },

  // GET request
  get: (endpoint, params) => {
    if (params && Object.keys(params).length > 0) {
      const query = new URLSearchParams(params).toString()
      return api.request(`${endpoint}?${query}`)
    }
    return api.request(endpoint)
  },

  // POST request
  post: (endpoint, data) => 
    api.request(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // PUT request
  put: (endpoint, data) =>
    api.request(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  // PATCH request
  patch: (endpoint, data) =>
    api.request(endpoint, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  // PATCH multipart/form-data
  patchForm: (endpoint, formData) =>
    api.request(endpoint, {
      method: 'PATCH',
      body: formData,
    }),

  // DELETE request
  delete: (endpoint) =>
    api.request(endpoint, {
      method: 'DELETE',
    }),
}

// Auth API endpoints
export const authApi = {
  login: (credentials) => api.post('/users/token/', credentials),
  patientLogin: (credentials) => api.post('/users/patient-token/', credentials),
  refresh: (token) => api.post('/users/token/refresh/', { refresh: token }),
  getProfile: () => api.get('/users/profile/'),
  changePassword: (current_password, new_password) => api.post('/users/change-password/', { current_password, new_password }),
  patientPasswordResetRequest: (passport_id, phone_number) => api.post('/users/password-reset/request/', { passport_id, phone_number }),
  patientPasswordResetVerify: (passport_id, phone_number, code) => api.post('/users/password-reset/verify/', { passport_id, phone_number, code }),
  patientPasswordResetConfirm: (token, new_password) => api.post('/users/password-reset/confirm/', { token, new_password }),
  doctorPasswordResetRequest: (passport_id, birth_date, pinfl) => api.post('/users/doctor-password-reset/request/', { passport_id, birth_date, pinfl }),
  doctorPasswordResetVerify: (passport_id, birth_date, pinfl, code) => api.post('/users/doctor-password-reset/verify/', { passport_id, birth_date, pinfl, code }),
  doctorPasswordResetConfirm: (token, new_password, new_email) => api.post('/users/doctor-password-reset/confirm/', { token, new_password, ...(new_email ? { new_email } : {}) }),
  clinicPasswordResetRequest: (clinic_number, passport_id, phone_number) => api.post('/users/clinic-password-reset/request/', { clinic_number, passport_id, phone_number }),
  clinicPasswordResetVerify: (clinic_number, passport_id, phone_number, code) => api.post('/users/clinic-password-reset/verify/', { clinic_number, passport_id, phone_number, code }),
  clinicPasswordResetConfirm: (token, new_password, new_email) => api.post('/users/clinic-password-reset/confirm/', { token, new_password, ...(new_email ? { new_email } : {}) }),
  pharmacyPasswordResetRequest: (pharmacy_number, passport_id, phone_number) => api.post('/users/pharmacy-password-reset/request/', { pharmacy_number, passport_id, phone_number }),
  pharmacyPasswordResetVerify: (pharmacy_number, passport_id, phone_number, code) => api.post('/users/pharmacy-password-reset/verify/', { pharmacy_number, passport_id, phone_number, code }),
  pharmacyPasswordResetConfirm: (token, new_password, new_email) => api.post('/users/pharmacy-password-reset/confirm/', { token, new_password, ...(new_email ? { new_email } : {}) }),
}

// Clinic API endpoints
export const clinicsApi = {
  getAll: (params) => api.get('/clinics/', params),
  getById: (id, params) => api.get(`/clinics/${id}/`, params),
  getMy: (params) => api.get('/clinics/my/', params),
  create: (data) => api.post('/clinics/', data),
  update: (id, data) => api.patch(`/clinics/${id}/`, data),
  updateMyBanner: (formData) => api.patchForm('/clinics/my/banner/', formData),
  updateMy: (data) => api.patch('/clinics/my/update/', data),
  sendStaffMessage: (data) => api.post('/clinics/my/staff-messages/', data),
  getStaffInboxMessages: (params) => api.get('/clinics/staff-messages/', params),
  markStaffInboxMessageRead: (id) => api.patch(`/clinics/staff-messages/${id}/read/`, {}),
  delete: (id) => api.delete(`/clinics/${id}/`),
}

// Clinic Services API endpoints
export const clinicServicesApi = {
  getAll: (params) => api.get('/clinics/services/', params),
  getById: (id) => api.get(`/clinics/services/${id}/`),
  create: (data) => api.post('/clinics/services/', data),
  update: (id, data) => api.patch(`/clinics/services/${id}/`, data),
  delete: (id) => api.delete(`/clinics/services/${id}/`),
}

// Clinic Departments API endpoints
export const clinicDepartmentsApi = {
  getAll: (params) => api.get('/clinics/departments/', params),
  getById: (id) => api.get(`/clinics/departments/${id}/`),
  create: (data) => api.post('/clinics/departments/', data),
  update: (id, data) => api.patch(`/clinics/departments/${id}/`, data),
  delete: (id) => api.delete(`/clinics/departments/${id}/`),
}

// Doctor API endpoints
export const doctorsApi = {
  getAll: (params) => api.get('/doctors/', params),
  getById: (id) => api.get(`/doctors/${id}/`),
  identityCheck: (data) => api.post('/doctors/identity-check/', data),
  getMy: () => api.get('/doctors/my/'),
  updateMyProfile: (data) => api.patch('/doctors/my/update/', data),
  updateMyProfileForm: (formData) => api.patchForm('/doctors/my/update/', formData),
  create: (data) => api.post('/doctors/', data),
  update: (id, data) => api.patch(`/doctors/${id}/`, data),
  updateForm: (id, formData) => api.patchForm(`/doctors/${id}/`, formData),
  delete: (id) => api.delete(`/doctors/${id}/`),
  terminate: (id) => api.post(`/doctors/${id}/terminate/`, {}),
  checkIn: () => api.post('/doctors/check_in/', {}),
  checkOut: () => api.post('/doctors/check_out/', {}),
  getWorkStats: () => api.get('/doctors/work_stats/'),
  getRatings: (params) => api.get('/doctors/ratings/', typeof params === 'string' ? { doctor: params } : params),
  addRating: (data) => api.post('/doctors/ratings/', data),
  updateRating: (id, data) => api.patch(`/doctors/ratings/${id}/`, data),
  getSpecializations: () => api.get('/doctors/specializations/'),
  createSpecialization: (data) => api.post('/doctors/specializations/', data),
  getMySpecializations: () => api.get('/doctors/specialty-prices/my_specializations/'),
  updateSpecialtyPrice: (specialtyPriceId, data) => api.patch(`/doctors/specialty-prices/${specialtyPriceId}/`, data),
  getAvailability: (params) => api.get('/doctors/availability/available/', params),
}

// Patient API endpoints
export const patientsApi = {
  getAll: (params) => api.get('/patients/', params),
  getById: (id) => api.get(`/patients/${id}/`),
  getMy: () => api.get('/patients/my/'),
  create: (data) => api.post('/patients/', data),
  update: (id, data) => api.patch(`/patients/${id}/`, data),
  setPassword: (id, data) => api.post(`/patients/${id}/set_password/`, data),
  delete: (id) => api.delete(`/patients/${id}/`),
}

// Pharmacy API endpoints
export const pharmaciesApi = {
  getAll: () => api.get('/pharmacies/'),
  getById: (id) => api.get(`/pharmacies/${id}/`),
  getMy: () => api.get('/pharmacies/my/'),
  create: (data) => api.post('/pharmacies/', data),
  update: (id, data) => api.patch(`/pharmacies/${id}/`, data),
  updateForm: (id, formData) => api.patchForm(`/pharmacies/${id}/`, formData),
  delete: (id) => api.delete(`/pharmacies/${id}/`),
}

export const medicinesApi = {
  getAll: (params) => api.get('/pharmacies/medicines/', params),
  create: (data) => api.post('/pharmacies/medicines/', data),
  update: (id, data) => api.patch(`/pharmacies/medicines/${id}/`, data),
  delete: (id) => api.delete(`/pharmacies/medicines/${id}/`),
  clearAll: () => api.delete('/pharmacies/medicines/clear-all/'),
  getNameAlerts: () => api.get('/pharmacies/medicines/name-alerts/'),
  confirmNameAlert: (id) => api.patch(`/pharmacies/medicines/name-alerts/${id}/confirm/`, {}),
  confirmAllNameAlerts: () => api.patch('/pharmacies/medicines/name-alerts/confirm-all/', {}),
  correctNameAlert: (id, data) => api.patch(`/pharmacies/medicines/name-alerts/${id}/correct/`, data),
  search: (query, limit = 10) => api.get('/pharmacies/medicines/search/', { q: query, limit }),
}

export const pharmacyInventoryApi = {
  getAll: (params) => api.get('/pharmacies/inventory/', params),
  create: (data) => api.post('/pharmacies/inventory/', data),
  update: (id, data) => api.patch(`/pharmacies/inventory/${id}/`, data),
  delete: (id) => api.delete(`/pharmacies/inventory/${id}/`),
  clearAll: () => api.delete('/pharmacies/inventory/clear-all/'),
}

// Medical API endpoints
export const medicalApi = {
  getAppointments: (params) => api.get('/medical/appointments/', params),
  getTodaysAppointments: () => api.get('/medical/appointments/today/'),
  getDoctorDashboardStats: () => api.get('/medical/appointments/doctor_dashboard_stats/', { _t: Date.now() }),
  getClinicDashboardStats: () => api.get('/medical/appointments/clinic_dashboard_stats/', { _t: Date.now() }),
  getAppointmentsMonthlyStats: (params) => api.get('/medical/appointments/monthly_stats/', params),
  getAppointmentById: (id) => api.get(`/medical/appointments/${id}/`),
  createAppointment: (data) => api.post('/medical/appointments/', data),
  updateAppointment: (id, data) => api.patch(`/medical/appointments/${id}/`, data),
  notifyAppointmentReady: (id, data = {}) => api.post(`/medical/appointments/${id}/notify_ready/`, data),
  queueDecision: (id, data = {}) => api.post(`/medical/appointments/${id}/queue_decision/`, data),
  bookOnline: (data) => api.post('/medical/appointments/online_booking/', data),
}

export const medicalRecordsApi = {
  getAll: (params) => api.get('/medical/records/', params),
  getById: (id) => api.get(`/medical/records/${id}/`),
  create: (data) => api.post('/medical/records/', data),
  update: (id, data) => api.patch(`/medical/records/${id}/`, data),
  delete: (id) => api.delete(`/medical/records/${id}/`),
}

// Site settings endpoints (public + admin)
export const siteSettingsApi = {
  getHomeContact: () => api.get('/site-settings/home-contact/'),
  updateHomeContact: (formData) => api.patchForm('/site-settings/home-contact/', formData),
  createContactLead: (data) => api.post('/site-settings/contact-leads/', data),
  adminGetContactLeads: (params) => api.get('/site-settings/contact-leads/admin/', params),
  adminMarkContactLeadRead: (id) => api.patch(`/site-settings/contact-leads/${id}/read/`, {}),
  adminGetSystemAlerts: (params) => api.get('/site-settings/system-alerts/admin/', params),
  adminResolveSystemAlert: (id) => api.patch(`/site-settings/system-alerts/${id}/resolve/`, {}),
}

export const prescriptionsApi = {
  getAll: (params) => api.get('/medical/prescriptions/', params),
  getById: (id) => api.get(`/medical/prescriptions/${id}/`),
  create: (data) => api.post('/medical/prescriptions/', data),
  update: (id, data) => api.patch(`/medical/prescriptions/${id}/`, data),
  delete: (id) => api.delete(`/medical/prescriptions/${id}/`),
}

// Subscription API endpoints
export const subscriptionsApi = {
  getAll: () => api.get('/subscriptions/'),
  getById: (id) => api.get(`/subscriptions/${id}/`),
  create: (data) => api.post('/subscriptions/', data),
}

// Payment API endpoints
export const paymentsApi = {
  getAll: () => api.get('/payments/'),
  getById: (id) => api.get(`/payments/${id}/`),
  create: (data) => api.post('/payments/', data),
}

export default api

