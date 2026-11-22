import { InjectionToken } from '@angular/core';
import type { Messaging, MessagePayload } from 'firebase/messaging';
import { WebPushConfig, WebPushFirebaseConfig } from './web-push.models';

/** Browser boundary kept injectable so activation can be checked without contacting FCM. */
export interface WebPushClient {
  supported(): boolean;
  permission(): NotificationPermission | 'unsupported';
  requestPermission(): Promise<NotificationPermission>;
  isSupported(): Promise<boolean>;
  activate(config: WebPushConfig, onMessage: (payload: MessagePayload) => void): Promise<string>;
  deactivate(config: WebPushFirebaseConfig): Promise<void>;
  destroy(): void;
}

class FirebaseWebPushClient implements WebPushClient {
  private unsubscribe?: () => void;
  private readonly boundMessaging = new Map<string, Messaging>();

  supported(): boolean {
    return typeof window !== 'undefined' && window.isSecureContext
      && 'Notification' in window && 'serviceWorker' in navigator && 'PushManager' in window;
  }

  permission(): NotificationPermission | 'unsupported' {
    return this.supported() ? Notification.permission : 'unsupported';
  }

  requestPermission(): Promise<NotificationPermission> {
    return Notification.requestPermission();
  }

  async isSupported(): Promise<boolean> {
    return this.supported() && (await import('firebase/messaging')).isSupported();
  }

  async activate(config: WebPushConfig, onMessage: (payload: MessagePayload) => void): Promise<string> {
    const messaging = await this.messaging(config.firebase);
    const sdk = await import('firebase/messaging');
    // Public config in the URL survives worker restarts with all browser windows closed.
    const workerUrl = new URL('firebase-messaging-sw.js', document.baseURI);
    workerUrl.searchParams.set('firebase', JSON.stringify(config.firebase));
    const registration = await navigator.serviceWorker.register(workerUrl.href, {
      scope: new URL('firebase-cloud-messaging-push-scope/', document.baseURI).pathname,
      updateViaCache: 'none',
    });
    await this.waitForActivation(registration);
    // getToken can prompt by itself. Check synchronously immediately before calling it,
    // including when permission was revoked while restore was awaiting SDK/worker setup.
    if (Notification.permission !== 'granted') {
      throw new Error('El permiso de notificaciones ya no está concedido.');
    }
    const token = await sdk.getToken(messaging, {
      vapidKey: config.vapid_key,
      serviceWorkerRegistration: registration,
    });
    this.boundMessaging.set(config.firebase.appId, messaging);
    this.unsubscribe?.();
    this.unsubscribe = sdk.onMessage(messaging, onMessage);
    return token;
  }

  async deactivate(config: WebPushFirebaseConfig): Promise<void> {
    this.destroy();
    // Unsubscribe first so a Firebase network failure cannot leave delivery active locally.
    const scope = new URL('firebase-cloud-messaging-push-scope/', document.baseURI).href;
    const registration = await navigator.serviceWorker.getRegistration(scope);
    if (registration?.scope === scope) {
      const subscription = await registration.pushManager.getSubscription();
      await subscription?.unsubscribe();
    }
    const messaging = this.boundMessaging.get(config.appId);
    if (messaging) {
      if (!(await (await import('firebase/messaging')).deleteToken(messaging))) {
        throw new Error('Firebase no pudo eliminar el token push.');
      }
      this.boundMessaging.delete(config.appId);
    }
    // After reload there is no SDK instance bound to our custom registration. Do not call
    // deleteToken then: it registers a different, default worker. Native unsubscribe plus
    // backend token removal stops delivery; getToken replaces the stale SDK token next time.
  }

  destroy(): void {
    this.unsubscribe?.();
    this.unsubscribe = undefined;
  }

  private async messaging(config: WebPushFirebaseConfig): Promise<Messaging> {
    const [appSdk, sdk] = await Promise.all([import('firebase/app'), import('firebase/messaging')]);
    const name = `situr-web-push-${config.appId}`;
    const app = appSdk.getApps().find((app) => app.name === name)
      ?? appSdk.initializeApp(config, name);
    return sdk.getMessaging(app);
  }

  private waitForActivation(registration: ServiceWorkerRegistration): Promise<void> {
    if (registration.active && !registration.installing && !registration.waiting) {
      return Promise.resolve();
    }
    const worker = registration.installing ?? registration.waiting ?? registration.active;
    if (!worker) return Promise.reject(new Error('No se pudo iniciar el worker de notificaciones.'));
    return new Promise<void>((resolve, reject) => {
      const finish = (error?: Error) => {
        clearTimeout(timer);
        worker.removeEventListener('statechange', check);
        error ? reject(error) : resolve();
      };
      const check = () => {
        if (worker.state === 'activated') finish();
        if (worker.state === 'redundant') finish(new Error('El worker de notificaciones no está disponible.'));
      };
      const timer = setTimeout(() => finish(new Error('El worker de notificaciones tardó demasiado.')), 15000);
      worker.addEventListener('statechange', check);
      check();
    });
  }
}

export const WEB_PUSH_CLIENT = new InjectionToken<WebPushClient>('WEB_PUSH_CLIENT', {
  providedIn: 'root',
  factory: () => new FirebaseWebPushClient(),
});
