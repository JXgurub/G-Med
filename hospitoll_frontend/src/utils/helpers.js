// Utility functions

// Format date to readable format
export const formatDate = (dateString) => {
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}

// Format time to readable format
export const formatTime = (timeString) => {
  const date = new Date(timeString)
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit'
  })
}

// Validate email
export const isValidEmail = (email) => {
  const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return regex.test(email)
}

// Get user role from token or storage
export const getUserRole = () => {
  // TODO: Implement actual role retrieval from auth token
  return localStorage.getItem('userRole')
}

// Check if user is authenticated
export const isAuthenticated = () => {
  // TODO: Implement actual authentication check
  return !!localStorage.getItem('authToken')
}
