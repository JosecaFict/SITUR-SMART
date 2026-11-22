import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { DestroyRef, Injectable, NgZone, computed, effect, inject, signal, untracked } from '@angular/core';
import type { MessagePayload } from 'firebase/messaging';
import { Subject, firstValueFrom, timeout } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuthService } from '../auth/auth.service';
import { apiErrorMessage } from '../http/api-error';
import { WEB_PUSH_CLIENT } from './web-push.client';
import { WebPushConfig, WebPushFirebaseConfig, WebPushStatus, hasFirebaseConfig, hasPushConfig } from './web-push.models';

export type { WebPushConfig, WebPushFirebaseConfig, WebPushStatus } from './web-push.models';

interface SavedDevice {
  token: string;
  userId: number;
  firebase: WebPushFirebaseConfig;
  registered: boolean;
}

const STORAGE_KEY = 'situr_web_push_device';
const REQUEST_TIMEOUT = 15000;

@Injectable({ providedIn: 'root' })
export class WebPushService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly client = inject(WEB_PUSH_CLIENT);
  private readonly zone = inject(NgZone);
  private readonly baseUrl = environment.apiUrl.replace(/\/$/, '');
  private readonly statusSignal = signal<WebPushStatus>('idle');
  private readonly configSignal = signal<WebPushConfig | null>(null);
  private readonly errorSignal = signal<string | null>(null);
  private readonly permissionSignal = signal(this.client.permission());
  private readonly supportedSignal = signal(this.client.supported());
  private readonly device = signal<SavedDevice | null>(this.restoreDevice());
  private readonly messages = new Subject<MessagePayload>();
  private configRequest?: Promise<WebPushConfig | null>;
  private activation?: Promise<boolean>;
  private deactivation?: Promise<boolean>;
  private restoration?: Promise<boolean>;

  readonly status = this.statusSignal.asReadonly();
  readonly config = this.configSignal.asReadonly();
  readonly error = this.errorSignal.asReadonly();
  readonly permission = this.permissionSignal.asReadonly();
  readonly supported = this.supportedSignal.asReadonly();
  readonly busy = computed(() => ['loading', 'activating', 'deactivating'].includes(this.status()));
  readonly enabled = computed(() => this.device()?.registered === true
    && this.device()?.userId === this.auth.session()?.user.id && this.permission() === 'granted');
  readonly foregroundMessages$ = this.messages.asObservable();

  constructor() {
    const retrySessionCleanup = () => {
      const device = this.device();
      if (device && device.userId !== this.auth.session()?.user.id) void this.deactivate();
    };
    if (typeof window !== 'undefined') window.addEventListener('online', retrySessionCleanup);
    // Also covers session expiration, account deletion and account switches outside the logout button.
    effect(() => {
      const device = this.device();
      const userId = this.auth.session()?.user.id;
      if (device && device.userId !== userId) {
        untracked(() => { void this.deactivate(); });
      }
    });
    inject(DestroyRef).onDestroy(() => {
      if (typeof window !== 'undefined') window.removeEventListener('online', retrySessionCleanup);
      this.client.destroy();
      this.messages.complete();
    });
  }

  /** Load on tray initialization. Does not initialize Firebase or ask for permission. */
  loadConfig(): Promise<WebPushConfig | null> {
    if (this.configRequest) return this.configRequest;
    this.configRequest = this.fetchConfig().finally(() => { this.configRequest = undefined; });
    return this.configRequest;
  }

  /** Call from a user click; preload config to preserve Safari's permission gesture. */
  activate(): Promise<boolean> {
    return this.startActivation(true);
  }

  /** Reattach foreground delivery after reload, only for a previously opted-in account. Never prompts. */
  restore(): Promise<boolean> {
    if (this.restoration) return this.restoration;
    this.permissionSignal.set(this.client.permission());
    const device = this.device();
    if (!device || !this.canRestore(device) || this.deactivation) return Promise.resolve(false);
    this.restoration = this.restoreRegistration(device).finally(() => { this.restoration = undefined; });
    return this.restoration;
  }

  private startActivation(allowPermissionPrompt: boolean): Promise<boolean> {
    if (this.activation) return this.activation;
    if (this.deactivation) return allowPermissionPrompt
      ? this.deactivation.then(() => this.activate()) : Promise.resolve(false);
    this.activation = this.register(allowPermissionPrompt).finally(() => { this.activation = undefined; });
    return this.activation;
  }

  /** Await before logout, while the API session is still valid. No config fetch or permission prompt. */
  deactivate(): Promise<boolean> {
    if (this.deactivation) return this.deactivation;
    if (this.activation) return this.activation.then(() => this.deactivate());
    this.deactivation = this.unregister().finally(() => { this.deactivation = undefined; });
    return this.deactivation;
  }

  private async fetchConfig(): Promise<WebPushConfig | null> {
    const operating = ['activating', 'deactivating'].includes(this.status());
    if (!operating) this.statusSignal.set('loading');
    this.errorSignal.set(null);
    try {
      const config = await firstValueFrom(this.http.get<WebPushConfig>(
        `${this.baseUrl}/notificaciones/push-config/`,
      ).pipe(timeout(REQUEST_TIMEOUT)));
      // Copy only the documented public fields. Never pass arbitrary endpoint fields to the worker.
      this.configSignal.set(config && typeof config.habilitado === 'boolean' ? {
        habilitado: config.habilitado,
        firebase: this.publicFirebase(config.firebase),
        vapid_key: config.vapid_key,
      } : null);
      this.permissionSignal.set(this.client.permission());
      if (!operating) this.availabilityStatus();
      return this.config();
    } catch (error) {
      this.configSignal.set(null);
      this.errorSignal.set(error instanceof HttpErrorResponse && error.status === 404
        ? 'Las notificaciones push aún no están configuradas en el servidor.'
        : this.message(error, 'No se pudo cargar la configuración push.'));
      if (!operating) this.statusSignal.set(this.supported() ? 'unavailable' : 'unsupported');
      return null;
    }
  }

  private canRestore(device: SavedDevice): boolean {
    return this.supported() && device.registered && this.device()?.token === device.token
      && this.device()?.registered === true && this.device()?.userId === device.userId
      && device.userId === this.auth.session()?.user.id
      && this.client.permission() === 'granted';
  }

  private async restoreRegistration(device: SavedDevice): Promise<boolean> {
    const config = this.config() ?? await this.loadConfig();
    if (!hasPushConfig(config) || !this.canRestore(device) || this.deactivation) return false;
    return this.startActivation(false);
  }

  private async register(allowPermissionPrompt: boolean): Promise<boolean> {
    this.errorSignal.set(null);
    if (!this.supported()) {
      this.statusSignal.set('unsupported');
      return false;
    }
    const userId = this.auth.session()?.user.id;
    if (!userId) return this.fail('Inicia sesión para activar las notificaciones push.');
    this.statusSignal.set('activating');
    try {
      const previous = this.device();
      if (previous && previous.userId !== userId && !(await this.unregister())) return false;
      this.statusSignal.set('activating');
      const config = this.config() ?? await this.loadConfig();
      if (!hasPushConfig(config)) {
        this.statusSignal.set('unavailable');
        return false;
      }
      // With preloaded config, invoke requestPermission before the first asynchronous boundary.
      const currentPermission = this.client.permission();
      const permission = currentPermission === 'default' && allowPermissionPrompt
        ? await this.client.requestPermission() : currentPermission;
      this.permissionSignal.set(permission);
      if (permission !== 'granted') {
        this.statusSignal.set(permission === 'denied' ? 'denied' : 'inactive');
        return false;
      }
      if (!(await this.client.isSupported())) {
        this.supportedSignal.set(false);
        this.statusSignal.set('unsupported');
        return false;
      }
      if (this.client.permission() !== 'granted') {
        this.permissionSignal.set(this.client.permission());
        this.statusSignal.set(this.permission() === 'denied' ? 'denied' : 'inactive');
        return false;
      }
      const token = await this.client.activate(config, (payload) => {
        if (this.enabled() && this.auth.session()?.user.id === userId) {
          this.zone.run(() => this.messages.next(payload));
        }
      });
      if (!token) throw new Error('Firebase no devolvió un token de notificaciones.');
      const registered = previous?.registered === true && previous.userId === userId && previous.token === token;
      this.saveDevice({ token, userId, firebase: config.firebase, registered });
      if (this.auth.session()?.user.id !== userId) {
        await this.client.deactivate(config.firebase);
        this.saveDevice(null);
        throw new Error('La sesión cambió. Vuelve a activar las notificaciones.');
      }
      await firstValueFrom(this.http.post<void>(`${this.baseUrl}/me/dispositivos/`, {
        token, plataforma: 'WEB',
      }).pipe(timeout(REQUEST_TIMEOUT)));
      if (this.auth.session()?.user.id !== userId) {
        await this.client.deactivate(config.firebase);
        this.saveDevice(null);
        throw new Error('La sesión cambió durante el registro push.');
      }
      this.saveDevice({ token, userId, firebase: config.firebase, registered: true });
      this.statusSignal.set('active');
      return true;
    } catch (error) {
      return this.fail(this.message(error, 'No se pudieron activar las notificaciones push.'));
    }
  }

  private async unregister(): Promise<boolean> {
    this.errorSignal.set(null);
    this.statusSignal.set('deactivating');
    const device = this.device();
    if (!device) {
      this.statusSignal.set('inactive');
      return true;
    }
    if (device.userId !== this.auth.session()?.user.id) {
      // The former account's bearer is gone: revoke FCM without sending its token as the new user.
      this.client.destroy();
      try {
        await this.client.deactivate(device.firebase);
        this.saveDevice(null);
        this.statusSignal.set('inactive');
        return true;
      } catch (error) {
        return this.fail(this.message(error, 'No se pudo revocar el push de la sesión anterior. Reinténtalo.'));
      }
    }
    // Try both removals even when the API is unreachable, to stop delivery locally.
    const results = await Promise.allSettled([
      firstValueFrom(this.http.post<void>(`${this.baseUrl}/me/dispositivos/quitar/`, {
        token: device.token,
      }).pipe(timeout(REQUEST_TIMEOUT))),
      this.client.deactivate(device.firebase),
    ]);
    const failure = results.find((result) => result.status === 'rejected');
    if (results[0].status === 'fulfilled' || results[1].status === 'fulfilled') {
      this.saveDevice({ ...device, registered: false });
    }
    if (failure?.status === 'rejected') {
      // Retain token + public config so a later call can retry the incomplete cleanup.
      return this.fail(this.message(failure.reason, 'No se pudo completar la desactivación. Reinténtalo.'));
    }
    this.saveDevice(null);
    this.permissionSignal.set(this.client.permission());
    this.statusSignal.set('inactive');
    return true;
  }

  private availabilityStatus(): void {
    this.statusSignal.set(!this.supported() ? 'unsupported'
      : !hasPushConfig(this.config()) ? 'unavailable'
      : this.permission() === 'denied' ? 'denied'
      : this.enabled() ? 'active' : 'inactive');
  }

  private publicFirebase(config: WebPushFirebaseConfig | undefined): WebPushFirebaseConfig {
    return {
      apiKey: config?.apiKey ?? '', authDomain: config?.authDomain ?? '',
      projectId: config?.projectId ?? '', messagingSenderId: config?.messagingSenderId ?? '',
      appId: config?.appId ?? '',
    };
  }

  private fail(message: string): false {
    this.errorSignal.set(message);
    this.statusSignal.set('error');
    return false;
  }

  private message(error: unknown, fallback: string): string {
    return error instanceof HttpErrorResponse ? apiErrorMessage(error, fallback) : fallback;
  }

  private saveDevice(device: SavedDevice | null): void {
    this.device.set(device);
    try {
      if (device) localStorage.setItem(STORAGE_KEY, JSON.stringify(device));
      else localStorage.removeItem(STORAGE_KEY);
    } catch { /* Storage blocked: the in-memory device still supports deactivation. */ }
  }

  private restoreDevice(): SavedDevice | null {
    try {
      const device = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null') as SavedDevice | null;
      return device && typeof device.token === 'string' && device.token.length > 0
        && typeof device.userId === 'number' && typeof device.registered === 'boolean'
        && hasFirebaseConfig(device.firebase) ? device : null;
    } catch { return null; }
  }
}
