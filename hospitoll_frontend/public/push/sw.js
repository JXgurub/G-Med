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
    tag: payload.id || 'gmed-broadcast',
    data: { url: payload.url || '/' },
  }))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const targetUrl = new URL(event.notification.data?.url || '/', self.location.origin).href
  event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
    const existingClient = clients.find((client) => new URL(client.url).origin === self.location.origin)
    if (existingClient) {
      return existingClient.focus().then(() => existingClient.navigate(targetUrl))
    }
    return self.clients.openWindow(targetUrl)
  }))
})