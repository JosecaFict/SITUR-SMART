import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed, fakeAsync, flushMicrotasks } from '@angular/core/testing';
import { signal } from '@angular/core';
import { environment } from '../../../environments/environment';
import { AuthService } from '../auth/auth.service';
import { WEB_PUSH_CLIENT, WebPushClient } from './web-push.client';
import { WebPushConfig, WebPushService } from './web-push.service';

const CONFIG: WebPushConfig = {
  habilitado: true,
  firebase: {
    apiKey: 'public-key', authDomain: 'example.firebaseapp.com', projectId: 'example',
    messagingSenderId: '123456', appId: '1:123456:web:example',
  },
  vapid_key: 'B' + 'a'.repeat(86),
};
const BASE = environment.apiUrl;
const STORAGE_KEY = 'situr_web_push_device';

describe('WebPushService', () => {
  let service: WebPushService;
  let http: HttpTestingController;
  let client: jasmine.SpyObj<WebPushClient>;
  const session = signal<{ user: { id: number } } | null>({ user: { id: 7 } });

  beforeEach(() => {
    localStorage.removeItem(STORAGE_KEY);
    session.set({ user: { id: 7 } });
    client = jasmine.createSpyObj<WebPushClient>('WebPushClient', [
      'supported', 'permission', 'requestPermission', 'isSupported', 'activate', 'deactivate', 'destroy',
    ]);
    client.supported.and.returnValue(true);
    client.permission.and.returnValue('granted');
    client.requestPermission.and.returnValue(Promise.resolve('granted'));
    client.isSupported.and.returnValue(Promise.resolve(true));
    client.activate.and.returnValue(Promise.resolve('fcm-token'));
    client.deactivate.and.returnValue(Promise.resolve());
    TestBed.configureTestingModule({ providers: [
      provideHttpClient(), provideHttpClientTesting(),
      { provide: AuthService, useValue: { session } },
      { provide: WEB_PUSH_CLIENT, useValue: client },
    ] });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
    localStorage.removeItem(STORAGE_KEY);
  });

  function init(config: object | null = CONFIG): void {
    service = TestBed.inject(WebPushService);
    service.loadConfig();
    http.expectOne(`${BASE}/notificaciones/push-config/`).flush(config);
    flushMicrotasks();
  }

  function register(): void {
    service.activate();
    flushMicrotasks();
    const request = http.expectOne(`${BASE}/me/dispositivos/`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ token: 'fcm-token', plataforma: 'WEB' });
    request.flush(null);
    flushMicrotasks();
  }

  it('carga configuración pública sin pedir permiso ni iniciar Firebase y agrupa consultas simultáneas', fakeAsync(() => {
    service = TestBed.inject(WebPushService);
    const first = service.loadConfig();
    expect(service.loadConfig()).toBe(first);
    http.expectOne(`${BASE}/notificaciones/push-config/`).flush({
      ...CONFIG, firebase: { ...CONFIG.firebase, unexpected: 'not-forwarded' },
    });
    flushMicrotasks();
    expect(service.config()).toEqual(CONFIG);
    expect(service.status()).toBe('inactive');
    expect(client.requestPermission).not.toHaveBeenCalled();
    expect(client.activate).not.toHaveBeenCalled();
  }));

  it('tolera el endpoint ausente y permite reintentar la configuración', fakeAsync(() => {
    service = TestBed.inject(WebPushService);
    service.activate().then((result) => expect(result).toBeFalse());
    http.expectOne(`${BASE}/notificaciones/push-config/`).flush({}, { status: 404, statusText: 'Not found' });
    flushMicrotasks();
    expect(service.status()).toBe('unavailable');
    expect(service.error()).toContain('configuradas');
    expect(client.requestPermission).not.toHaveBeenCalled();
    service.loadConfig();
    http.expectOne(`${BASE}/notificaciones/push-config/`).flush(CONFIG);
    flushMicrotasks();
    expect(service.status()).toBe('inactive');
  }));

  for (const config of [null, { habilitado: false }, { ...CONFIG, vapid_key: '' }, {
    ...CONFIG, firebase: { ...CONFIG.firebase, appId: '' },
  }]) {
    it(`no activa con configuración incompleta o deshabilitada: ${JSON.stringify(config)}`, fakeAsync(() => {
      init(config);
      service.activate().then((result) => expect(result).toBeFalse());
      flushMicrotasks();
      if (config === null) {
        http.expectOne(`${BASE}/notificaciones/push-config/`).flush(null);
        flushMicrotasks();
      }
      expect(service.status()).toBe('unavailable');
      expect(client.activate).not.toHaveBeenCalled();
      expect(client.requestPermission).not.toHaveBeenCalled();
    }));
  }

  it('no llama Firebase ni la API en navegador sin soporte', fakeAsync(() => {
    client.supported.and.returnValue(false);
    service = TestBed.inject(WebPushService);
    service.activate().then((result) => expect(result).toBeFalse());
    flushMicrotasks();
    expect(service.status()).toBe('unsupported');
    expect(client.activate).not.toHaveBeenCalled();
  }));

  it('respeta permiso denegado sin repetir el diálogo', fakeAsync(() => {
    client.permission.and.returnValue('denied');
    init();
    service.activate();
    flushMicrotasks();
    expect(service.status()).toBe('denied');
    expect(client.requestPermission).not.toHaveBeenCalled();
    expect(client.activate).not.toHaveBeenCalled();
  }));

  it('pide permiso durante el clic con configuración precargada y registra un token FCM', fakeAsync(() => {
    client.permission.and.returnValue('default');
    init();
    const first = service.activate();
    expect(client.requestPermission).toHaveBeenCalledTimes(1);
    expect(service.activate()).toBe(first);
    client.permission.and.returnValue('granted');
    flushMicrotasks();
    http.expectOne(`${BASE}/me/dispositivos/`).flush(null);
    flushMicrotasks();
    expect(service.status()).toBe('active');
    expect(service.enabled()).toBeTrue();
    expect(client.activate.calls.mostRecent().args[0]).toEqual(CONFIG);
  }));

  it('no registra si se cierra el diálogo sin conceder permiso', fakeAsync(() => {
    client.permission.and.returnValue('default');
    client.requestPermission.and.returnValue(Promise.resolve('default'));
    init();
    service.activate();
    flushMicrotasks();
    expect(service.status()).toBe('inactive');
    expect(client.activate).not.toHaveBeenCalled();
  }));

  it('no registra si falla la comprobación de soporte de IndexedDB/Firebase', fakeAsync(() => {
    client.isSupported.and.returnValue(Promise.resolve(false));
    init();
    service.activate();
    flushMicrotasks();
    expect(service.status()).toBe('unsupported');
    expect(client.activate).not.toHaveBeenCalled();
  }));

  it('publica avisos en primer plano solo para la cuenta que registró el token', fakeAsync(() => {
    init();
    register();
    const received = jasmine.createSpy('received');
    service.foregroundMessages$.subscribe(received);
    const onMessage = client.activate.calls.mostRecent().args[1];
    const payload = { messageId: 'notice', from: '123456', collapseKey: '', data: { ruta: '/notificaciones' } };
    onMessage(payload);
    expect(received).toHaveBeenCalledOnceWith(payload);
    session.set({ user: { id: 8 } });
    onMessage(payload);
    expect(received).toHaveBeenCalledTimes(1);
    expect(service.enabled()).toBeFalse();
  }));

  it('retira el token guardado tras recarga sin consultar configuración ni pedir permiso', fakeAsync(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      token: 'saved-fcm', userId: 7, firebase: CONFIG.firebase, registered: true,
    }));
    service = TestBed.inject(WebPushService);
    service.deactivate().then((result) => expect(result).toBeTrue());
    const request = http.expectOne(`${BASE}/me/dispositivos/quitar/`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ token: 'saved-fcm' });
    request.flush(null);
    flushMicrotasks();
    expect(client.deactivate).toHaveBeenCalledOnceWith(CONFIG.firebase);
    expect(client.requestPermission).not.toHaveBeenCalled();
    expect(service.status()).toBe('inactive');
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  }));

  it('revoca Firebase aunque falle la API y conserva lo necesario para reintentar', fakeAsync(() => {
    init();
    register();
    service.deactivate().then((result) => expect(result).toBeFalse());
    http.expectOne(`${BASE}/me/dispositivos/quitar/`).flush({}, { status: 503, statusText: 'Unavailable' });
    flushMicrotasks();
    expect(client.deactivate).toHaveBeenCalledTimes(1);
    expect(service.enabled()).toBeFalse();
    expect(service.status()).toBe('error');
    expect(localStorage.getItem(STORAGE_KEY)).not.toBeNull();
    service.deactivate().then((result) => expect(result).toBeTrue());
    http.expectOne(`${BASE}/me/dispositivos/quitar/`).flush(null);
    flushMicrotasks();
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  }));

  it('retiene el token para desactivar incluso cuando su registro HTTP falla', fakeAsync(() => {
    init();
    service.activate();
    flushMicrotasks();
    http.expectOne(`${BASE}/me/dispositivos/`).flush({}, { status: 500, statusText: 'Error' });
    flushMicrotasks();
    expect(service.enabled()).toBeFalse();
    service.deactivate();
    const request = http.expectOne(`${BASE}/me/dispositivos/quitar/`);
    expect(request.request.body).toEqual({ token: 'fcm-token' });
    request.flush(null);
    flushMicrotasks();
    expect(service.status()).toBe('inactive');
  }));

  it('revoca localmente al expirar la sesión sin usar credenciales de otra cuenta', fakeAsync(() => {
    init();
    register();
    TestBed.tick();
    session.set(null);
    TestBed.tick();
    flushMicrotasks();
    expect(client.deactivate).toHaveBeenCalledOnceWith(CONFIG.firebase);
    http.expectNone(`${BASE}/me/dispositivos/quitar/`);
    expect(service.enabled()).toBeFalse();
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  }));

  it('revoca el registro si cambia la cuenta durante la respuesta HTTP', fakeAsync(() => {
    init();
    service.activate().then((result) => expect(result).toBeFalse());
    flushMicrotasks();
    const request = http.expectOne(`${BASE}/me/dispositivos/`);
    session.set({ user: { id: 8 } });
    request.flush(null);
    flushMicrotasks();
    expect(client.deactivate).toHaveBeenCalled();
    expect(service.enabled()).toBeFalse();
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  }));

  it('reintenta al recuperar conexión la limpieza de una sesión expirada', fakeAsync(() => {
    init();
    register();
    TestBed.tick();
    client.deactivate.and.callFake(async () => { throw new Error('offline'); });
    session.set(null);
    TestBed.tick();
    flushMicrotasks();
    expect(localStorage.getItem(STORAGE_KEY)).not.toBeNull();
    client.deactivate.and.returnValue(Promise.resolve());
    window.dispatchEvent(new Event('online'));
    flushMicrotasks();
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
    http.expectNone(`${BASE}/me/dispositivos/quitar/`);
  }));

  it('espera un registro en curso antes de desactivarlo', fakeAsync(() => {
    init();
    service.activate();
    const removed = jasmine.createSpy('removed');
    service.deactivate().then(removed);
    flushMicrotasks();
    http.expectNone(`${BASE}/me/dispositivos/quitar/`);
    http.expectOne(`${BASE}/me/dispositivos/`).flush(null);
    flushMicrotasks();
    http.expectOne(`${BASE}/me/dispositivos/quitar/`).flush(null);
    flushMicrotasks();
    expect(removed).toHaveBeenCalledOnceWith(true);
    expect(service.status()).toBe('inactive');
  }));

  it('mantiene el token para reintentar si falla la revocación Firebase', fakeAsync(() => {
    init();
    register();
    client.deactivate.and.callFake(async () => { throw new Error('offline'); });
    service.deactivate().then((result) => expect(result).toBeFalse());
    http.expectOne(`${BASE}/me/dispositivos/quitar/`).flush(null);
    flushMicrotasks();
    expect(service.enabled()).toBeFalse();
    expect(localStorage.getItem(STORAGE_KEY)).not.toBeNull();
    client.deactivate.and.returnValue(Promise.resolve());
    service.deactivate().then((result) => expect(result).toBeTrue());
    http.expectOne(`${BASE}/me/dispositivos/quitar/`).flush(null);
    flushMicrotasks();
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  }));

  function savedDevice(overrides: object = {}): void {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      token: 'saved-fcm', userId: 7, firebase: CONFIG.firebase, registered: true, ...overrides,
    }));
    service = TestBed.inject(WebPushService);
  }

  it('restaura el listener foreground y renueva token tras reload para la cuenta ya habilitada sin pedir permiso', fakeAsync(() => {
    savedDevice();
    expect(client.activate).not.toHaveBeenCalled();
    const received = jasmine.createSpy('received');
    service.foregroundMessages$.subscribe(received);
    client.activate.and.returnValue(Promise.resolve('renewed-fcm'));
    const restore = service.restore();
    expect(service.restore()).toBe(restore);
    http.expectOne(`${BASE}/notificaciones/push-config/`).flush(CONFIG);
    flushMicrotasks();
    const register = http.expectOne(`${BASE}/me/dispositivos/`);
    expect(register.request.body).toEqual({ token: 'renewed-fcm', plataforma: 'WEB' });
    register.flush(null);
    flushMicrotasks();
    restore.then((result) => expect(result).toBeTrue());
    flushMicrotasks();
    const payload = { messageId: 'after-reload', from: '123456', collapseKey: '' };
    client.activate.calls.mostRecent().args[1](payload);
    expect(received).toHaveBeenCalledOnceWith(payload);
    expect(service.enabled()).toBeTrue();
    expect(client.requestPermission).not.toHaveBeenCalled();
  }));

  it('restore sin suscripción guardada no consulta config ni activa Firebase', fakeAsync(() => {
    service = TestBed.inject(WebPushService);
    service.restore().then((result) => expect(result).toBeFalse());
    flushMicrotasks();
    http.expectNone(`${BASE}/notificaciones/push-config/`);
    expect(client.activate).not.toHaveBeenCalled();
    expect(client.requestPermission).not.toHaveBeenCalled();
  }));

  it('conserva el registro conocido y el listener si falla revalidar el mismo token en la API', fakeAsync(() => {
    savedDevice();
    client.activate.and.returnValue(Promise.resolve('saved-fcm'));
    const received = jasmine.createSpy('received');
    service.foregroundMessages$.subscribe(received);
    service.restore();
    http.expectOne(`${BASE}/notificaciones/push-config/`).flush(CONFIG);
    flushMicrotasks();
    http.expectOne(`${BASE}/me/dispositivos/`).flush({}, { status: 503, statusText: 'Unavailable' });
    flushMicrotasks();
    expect(service.enabled()).toBeTrue();
    client.activate.calls.mostRecent().args[1]({ messageId: 'still-active', from: '123456', collapseKey: '' });
    expect(received).toHaveBeenCalledTimes(1);
    expect(client.requestPermission).not.toHaveBeenCalled();
  }));

  for (const options of [
    { userId: 8 }, { registered: false },
    { permission: 'default' as const }, { permission: 'denied' as const },
  ]) {
    it(`restore no actúa sin cuenta/consentimiento/permiso coincidente: ${JSON.stringify(options)}`, fakeAsync(() => {
      if ('permission' in options) client.permission.and.returnValue(options.permission!);
      savedDevice(options);
      service.restore().then((result) => expect(result).toBeFalse());
      flushMicrotasks();
      http.expectNone(`${BASE}/notificaciones/push-config/`);
      expect(client.activate).not.toHaveBeenCalled();
      expect(client.requestPermission).not.toHaveBeenCalled();
    }));
  }

  it('restore nunca solicita permiso si se revoca mientras espera configuración', fakeAsync(() => {
    savedDevice();
    service.restore().then((result) => expect(result).toBeFalse());
    client.permission.and.returnValue('default');
    http.expectOne(`${BASE}/notificaciones/push-config/`).flush(CONFIG);
    flushMicrotasks();
    expect(client.activate).not.toHaveBeenCalled();
    expect(client.requestPermission).not.toHaveBeenCalled();
  }));

  it('restore no activa si cambia la cuenta mientras espera configuración', fakeAsync(() => {
    savedDevice();
    service.restore().then((result) => expect(result).toBeFalse());
    session.set({ user: { id: 8 } });
    http.expectOne(`${BASE}/notificaciones/push-config/`).flush(CONFIG);
    flushMicrotasks();
    expect(client.activate).not.toHaveBeenCalled();
    expect(client.requestPermission).not.toHaveBeenCalled();
  }));

  it('no reactiva el token si el usuario desactiva durante restore', fakeAsync(() => {
    savedDevice();
    service.restore().then((result) => expect(result).toBeFalse());
    service.deactivate();
    http.expectOne(`${BASE}/me/dispositivos/quitar/`).flush(null);
    flushMicrotasks();
    http.expectOne(`${BASE}/notificaciones/push-config/`).flush(CONFIG);
    flushMicrotasks();
    expect(client.activate).not.toHaveBeenCalled();
    expect(service.enabled()).toBeFalse();
  }));

  it('no pide permiso ni inicia SDK si cambia permiso durante la comprobación de soporte', fakeAsync(() => {
    savedDevice();
    let resolveSupport!: (value: boolean) => void;
    client.isSupported.and.returnValue(new Promise((resolve) => { resolveSupport = resolve; }));
    service.restore().then((result) => expect(result).toBeFalse());
    http.expectOne(`${BASE}/notificaciones/push-config/`).flush(CONFIG);
    flushMicrotasks();
    client.permission.and.returnValue('default');
    resolveSupport(true);
    flushMicrotasks();
    expect(client.activate).not.toHaveBeenCalled();
    expect(client.requestPermission).not.toHaveBeenCalled();
  }));
});
