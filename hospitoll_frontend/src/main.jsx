import React from 'react'
import ReactDOM from 'react-dom/client'
import { registerSW } from 'virtual:pwa-register'
import App from './App.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import { api } from './services/api'
import './index.css'

registerSW({
  immediate: true,
  onOfflineReady() {
    window.dispatchEvent(new Event('pwa-offline-ready'))
  },
})

if (typeof window !== 'undefined' && 'caches' in window) {
  caches.keys().then((keys) => {
    keys
      .filter((key) => key.includes('api-cache'))
      .forEach((key) => caches.delete(key))
  })
}

if (typeof window !== 'undefined' && !window.__hospitollGlobalErrorHandlersInstalled) {
  window.__hospitollGlobalErrorHandlersInstalled = true

  window.addEventListener('error', (event) => {
    void api.reportClientError({
      alert_type: 'frontend_runtime_error',
      message: event?.message || 'Unhandled window error',
      severity: 'error',
      context: {
        file: event?.filename || '',
        line: event?.lineno || 0,
        column: event?.colno || 0,
      },
      traceback: event?.error?.stack || '',
    })
  })

  window.addEventListener('unhandledrejection', (event) => {
    const reason = event?.reason
    const reasonMessage = typeof reason === 'string' ? reason : (reason?.message || 'Unhandled promise rejection')
    void api.reportClientError({
      alert_type: 'frontend_unhandled_rejection',
      message: reasonMessage,
      severity: 'error',
      context: {
        reason_type: typeof reason,
      },
      traceback: reason?.stack || '',
    })
  })
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
)
