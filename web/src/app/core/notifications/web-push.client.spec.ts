import { TestBed } from '@angular/core/testing';
import { WEB_PUSH_CLIENT, WebPushClient } from './web-push.client';
import { WebPushFirebaseConfig } from './web-push.models';

describe('FirebaseWebPushClient cleanup after reload', () => {
  let client: WebPushClient;
  const config: WebPushFirebaseConfig = {
    apiKey: 'public-key', authDomain: 'example.firebaseapp.com', projectId: 'example',
    messagingSenderId: '123456', appId: '1:123456:web:example',
  };

  beforeEach(() => {
    TestBed.configureTestingModule({});
    client = TestBed.inject(WEB_PUSH_CLIENT);
  });

  it('unsubscribes the dedicated worker without creating an unconfigured default worker or asking permission', async () => {
    const scope = new URL('firebase-cloud-messaging-push-scope/', document.baseURI).href;
    const unsubscribe = jasmine.createSpy('unsubscribe').and.resolveTo(true);
    const getSubscription = jasmine.createSpy('getSubscription').and.resolveTo({ unsubscribe });
    const getRegistration = spyOn(navigator.serviceWorker, 'getRegistration').and.resolveTo({
      scope, pushManager: { getSubscription },
    } as unknown as ServiceWorkerRegistration);
    const register = spyOn(navigator.serviceWorker, 'register');
    const permission = spyOn(Notification, 'requestPermission');
    await client.deactivate(config);
    expect(getRegistration).toHaveBeenCalledOnceWith(scope);
    expect(unsubscribe).toHaveBeenCalledTimes(1);
    expect(register).not.toHaveBeenCalled();
    expect(permission).not.toHaveBeenCalled();
  });

  it('leaves a different application worker untouched', async () => {
    const getSubscription = jasmine.createSpy('getSubscription');
    spyOn(navigator.serviceWorker, 'getRegistration').and.resolveTo({
      scope: new URL('./', document.baseURI).href, pushManager: { getSubscription },
    } as unknown as ServiceWorkerRegistration);
    await client.deactivate(config);
    expect(getSubscription).not.toHaveBeenCalled();
  });

  it('succeeds if the push subscription is already gone', async () => {
    spyOn(navigator.serviceWorker, 'getRegistration').and.resolveTo(undefined);
    await expectAsync(client.deactivate(config)).toBeResolved();
  });

  it('reports an unsubscribe failure so session cleanup can retry', async () => {
    const scope = new URL('firebase-cloud-messaging-push-scope/', document.baseURI).href;
    spyOn(navigator.serviceWorker, 'getRegistration').and.resolveTo({
      scope, pushManager: { getSubscription: async () => ({ unsubscribe: async () => { throw new Error('offline'); } }) },
    } as unknown as ServiceWorkerRegistration);
    await expectAsync(client.deactivate(config)).toBeRejectedWithError('offline');
  });
});
