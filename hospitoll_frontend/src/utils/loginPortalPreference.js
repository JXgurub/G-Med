const LOGIN_PORTAL_STORAGE_KEY = 'preferred_login_portal'
const DEFAULT_LOGIN_PORTAL = 'doctor'

export const LOGIN_PORTAL_PATHS = Object.freeze({
  doctor: '/doctor-login',
  clinic: '/clinic-owner-login',
  pharmacy: '/pharmacy-owner-login',
  admin: '/admin-login',
})

const normalizePortal = (portalOrPath) => {
  const value = String(portalOrPath || '').trim().toLowerCase()
  if (!value) return null

  if (value in LOGIN_PORTAL_PATHS) {
    return value
  }

  const matched = Object.entries(LOGIN_PORTAL_PATHS).find(([, path]) => path === value)
  return matched ? matched[0] : null
}

export const setPreferredLoginPortal = (portalOrPath) => {
  if (typeof window === 'undefined') return
  const normalizedPortal = normalizePortal(portalOrPath)
  if (!normalizedPortal) return
  window.localStorage.setItem(LOGIN_PORTAL_STORAGE_KEY, normalizedPortal)
}

export const hasPreferredLoginPortal = () => {
  if (typeof window === 'undefined') return false
  return Boolean(normalizePortal(window.localStorage.getItem(LOGIN_PORTAL_STORAGE_KEY)))
}

export const getPreferredLoginPortal = () => {
  if (typeof window === 'undefined') return DEFAULT_LOGIN_PORTAL
  const savedValue = window.localStorage.getItem(LOGIN_PORTAL_STORAGE_KEY)
  return normalizePortal(savedValue) || DEFAULT_LOGIN_PORTAL
}

export const getPreferredLoginPath = () => {
  const portal = getPreferredLoginPortal()
  return LOGIN_PORTAL_PATHS[portal] || LOGIN_PORTAL_PATHS[DEFAULT_LOGIN_PORTAL]
}
