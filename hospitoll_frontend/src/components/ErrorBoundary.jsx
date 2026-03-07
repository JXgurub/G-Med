import React from 'react'
import { api } from '../services/api'

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('[ErrorBoundary]', error, errorInfo)
    void api.reportClientError({
      alert_type: 'frontend_react_error_boundary',
      message: error?.message || 'React component tree error',
      severity: 'critical',
      context: {
        component_stack: errorInfo?.componentStack || '',
      },
      traceback: error?.stack || '',
    })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '24px' }}>
          <div style={{ maxWidth: 920, margin: '0 auto' }}>
            <h2 style={{ margin: 0, fontSize: '20px' }}>Sahifada xatolik yuz berdi</h2>
            <p style={{ marginTop: '8px', color: '#5a6c7d' }}>
              Agar sizda PWA cache/Service Worker bo'lsa, brauzerda <strong>Hard Reload</strong> qiling yoki
              "Clear site data" qilib qayta oching.
            </p>
            <pre style={{ marginTop: '12px', padding: '12px', background: '#f5f8fa', borderRadius: '8px', overflowX: 'auto' }}>
              {String(this.state.error?.message || this.state.error || 'Unknown error')}
            </pre>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
