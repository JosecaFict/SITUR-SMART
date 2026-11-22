/* Public Firebase configuration only. No API session or server credentials belong here. */
'use strict';

const workerUrl = new URL(self.location.href);
const appBase = new URL('./', workerUrl);
const fallbackRoute = new URL('notificaciones', appBase).href;

function safeNotificationRoute(value) {
  // Accept /ruta only. Reject protocol-relative URLs, backslashes and control characters.
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//')
    || /[\\\u0000-\u0020\u007f]/.test(value)) return fallbackRoute;
  try {
    const route = new URL(value, self.location.origin);
    return route.origin === self.location.origin ? route.href : fallbackRoute;
  } catch { return fallbackRoute; }
}

// Register before importing Firebase: override its default link handling, including auto notifications.
self.addEventListener('notificationclick', (event) => {
  event.stopImmediatePropagation();
  event.notification.close();
  const notificationData = event.notification.data || {};
  const data = notificationData.FCM_MSG ? notificationData.FCM_MSG.data || {} : notificationData;
  const target = safeNotificationRoute(data.ruta);
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    const client = windows.find((item) => {
      const url = new URL(item.url);
      return url.origin === self.location.origin && url.pathname.startsWith(appBase.pathname);
    });
    if (client) {
      try {
        const navigated = await client.navigate(target);
        if (navigated) { await navigated.focus(); return; }
      } catch { /* A closing tab cannot be reused. */ }
    }
    await self.clients.openWindow(target);
  })());
});

self.addEventListener('install', (event) => event.waitUntil(self.skipWaiting()));

let publicConfig;
try {
  const input = JSON.parse(workerUrl.searchParams.get('firebase') || 'null');
  const fields = ['apiKey', 'authDomain', 'projectId', 'messagingSenderId', 'appId'];
  if (input && fields.every((key) => typeof input[key] === 'string' && input[key].trim())) {
    publicConfig = Object.fromEntries(fields.map((key) => [key, input[key]]));
  }
} catch { /* Without configuration the worker remains inert. */ }

if (publicConfig) {
  // Keep this version aligned with web/package.json. Compat runs without a worker bundler.
  importScripts('https://www.gstatic.com/firebasejs/13.4.0/firebase-app-compat.js');
  importScripts('https://www.gstatic.com/firebasejs/13.4.0/firebase-messaging-compat.js');
  firebase.initializeApp(publicConfig);
  firebase.messaging().onBackgroundMessage((payload) => {
    // FCM already displays notification payloads. Only data-only messages need a display here.
    if (payload.notification) return;
    const data = payload.data || {};
    return self.registration.showNotification(data.titulo || data.title || 'SITUR-SMART', {
      body: data.mensaje || data.body || '',
      icon: new URL('favicon.ico', appBase).href,
      data: { ruta: safeNotificationRoute(data.ruta).replace(self.location.origin, '') },
      tag: data.notificacion_id || payload.messageId,
    });
  });
}
