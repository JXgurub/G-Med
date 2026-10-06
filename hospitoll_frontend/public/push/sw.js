self.addEventListener('push', (event) => {
  let payload = {}
  try {
    payload = event.data ? event.data.json() : {}
  } catch {
    payload = { body: event.data?.text() || '' }
  }

  event.waitUntil(self.registration.showNotification(payload.title || 'G-MED', {
    body: payload.body || '',
    icon: '/pwa-icon.svg',
    badge: '/pwa-icon.svg',
    tag: payload.tag || payload.id || 'gmed-broadcast',
    renotify: Boolean(payload.renotify),
    actions: payload.actions || [],
    data: {
      url: payload.url || '/',
      ...(payload.data || {}),
    },
  }))
})

self.addEventListener('notificationclick', (event) => {
  const notification = event.notification
  const data = notification.data || {}
  if (event.action === 'taken' && data.acknowledgement_token) {
    event.waitUntil(fetch('/api/v1/patients/medication-reminders/acknowledge/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'omit',
      body: JSON.stringify({ acknowledgement_token: data.acknowledgement_token }),
    }).then(async (response) => {
      if (!response.ok) {
        throw new Error(`Medication reminder acknowledgement failed (${response.status})`)
      }
      notification.close()
      const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      clients.forEach((client) => client.postMessage({
        type: 'medication-reminder-acknowledged',
        acknowledgement_token: data.acknowledgement_token,
      }))
    }).catch((error) => {
      console.error('Medication reminder acknowledgement failed:', error)
    }))
    return
  }

  notification.close()
  const targetUrl = new URL(data.url || '/', self.location.origin).href
  event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
    const existingClient = clients.find((client) => new URL(client.url).origin === self.location.origin)
    if (existingClient) {
      return existingClient.focus().then(() => existingClient.navigate(targetUrl))
    }
    return self.clients.openWindow(targetUrl)
  }))
})