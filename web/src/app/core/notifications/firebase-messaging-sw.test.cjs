const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { runInNewContext } = require('node:vm');

const source = readFileSync(join(__dirname, '../../../../public/firebase-messaging-sw.js'), 'utf8');
const config = {
  apiKey: 'public-key', authDomain: 'example.firebaseapp.com', projectId: 'example',
  messagingSenderId: '123456', appId: '1:123456:web:example',
};

function worker(options = {}) {
  const events = {};
  const displayed = [];
  const opened = [];
  const imported = [];
  let background;
  let initialized;
  const firebase = {
    initializeApp: (value) => { initialized = value; },
    messaging: () => ({ onBackgroundMessage: (callback) => { background = callback; } }),
  };
  const url = new URL('https://situr.example/app/firebase-messaging-sw.js');
  url.searchParams.set('firebase', options.rawConfig ?? JSON.stringify(config));
  const self = {
    location: url,
    addEventListener: (event, callback) => { events[event] = callback; },
    registration: { showNotification: async (title, value) => { displayed.push({ title, ...value }); } },
    clients: {
      matchAll: async () => options.windows ?? [],
      openWindow: async (target) => { opened.push(target); },
    },
    skipWaiting: async () => {},
  };
  runInNewContext(source, { self, URL, firebase, importScripts: (...urls) => {
    assert.ok(events.notificationclick, 'click handler must precede Firebase imports');
    imported.push(...urls);
  } });
  return { events, displayed, opened, imported, get initialized() { return initialized; },
    receive: (payload) => background(payload),
    async click(data) {
      let stopped = false;
      let closed = false;
      let task;
      events.notificationclick({
        notification: { data, close: () => { closed = true; } },
        stopImmediatePropagation: () => { stopped = true; },
        waitUntil: (promise) => { task = promise; },
      });
      await task;
      assert.ok(stopped && closed);
    },
  };
}

test('inert worker tolerates missing or invalid public config', () => {
  for (const rawConfig of ['null', '{', '{}', JSON.stringify({ ...config, appId: '' })]) {
    assert.equal(worker({ rawConfig }).imported.length, 0);
  }
});

test('passes only public Firebase fields to the SDK', () => {
  const instance = worker({ rawConfig: JSON.stringify({ ...config, unexpected: 'discard' }) });
  assert.deepEqual(JSON.parse(JSON.stringify(instance.initialized)), config);
  assert.equal(instance.imported.length, 2);
  assert.ok(instance.imported.every((url) => url.startsWith('https://www.gstatic.com/firebasejs/13.4.0/')));
});

test('does not duplicate FCM automatic notification messages', async () => {
  const instance = worker();
  await instance.receive({ notification: { title: 'Hello', body: 'World' }, data: { ruta: '/notificaciones' } });
  assert.equal(instance.displayed.length, 0);
});

test('shows data-only messages with a safe route and supports their click', async () => {
  const instance = worker();
  await instance.receive({ data: { titulo: 'Nuevo aviso', mensaje: 'Detalle', ruta: '/notificaciones', notificacion_id: '42' } });
  assert.equal(instance.displayed.length, 1);
  assert.equal(instance.displayed[0].title, 'Nuevo aviso');
  assert.equal(instance.displayed[0].body, 'Detalle');
  assert.equal(instance.displayed[0].tag, '42');
  await instance.click(instance.displayed[0].data);
  assert.deepEqual(instance.opened, ['https://situr.example/notificaciones']);
});

test('opens an internal ruta from an automatic FCM notification', async () => {
  const instance = worker();
  await instance.click({ FCM_MSG: { data: { ruta: '/notificaciones?aviso=42#detalle' } } });
  assert.deepEqual(instance.opened, ['https://situr.example/notificaciones?aviso=42#detalle']);
});

for (const route of ['https://evil.example/phish', '//evil.example/phish', '/\\evil.example',
  'javascript:alert(1)', '/\nevil', '', undefined, 42, 'https://situr.example/notificaciones']) {
  test(`uses local inbox fallback for unsafe or non-path ruta ${JSON.stringify(route)}`, async () => {
    const instance = worker();
    await instance.click({ FCM_MSG: { data: { ruta: route }, fcmOptions: { link: 'https://evil.example' } } });
    assert.deepEqual(instance.opened, ['https://situr.example/app/notificaciones']);
  });
}

test('reuses and focuses an existing app window', async () => {
  const navigated = [];
  let focused = false;
  const instance = worker({ windows: [{
    url: 'https://situr.example/app/dashboard',
    navigate: async (target) => {
      navigated.push(target);
      return { focus: async () => { focused = true; } };
    },
  }] });
  await instance.click({ ruta: '/app/notificaciones' });
  assert.deepEqual(navigated, ['https://situr.example/app/notificaciones']);
  assert.ok(focused);
  assert.equal(instance.opened.length, 0);
});

test('opens a window when the matching tab closes during the click', async () => {
  const instance = worker({ windows: [{
    url: 'https://situr.example/app/dashboard',
    navigate: async () => { throw new Error('closed'); },
  }] });
  await instance.click({ ruta: '/app/notificaciones' });
  assert.deepEqual(instance.opened, ['https://situr.example/app/notificaciones']);
});
