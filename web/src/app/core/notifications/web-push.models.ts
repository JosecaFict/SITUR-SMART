export interface WebPushFirebaseConfig {
  apiKey: string;
  authDomain: string;
  projectId: string;
  messagingSenderId: string;
  appId: string;
}

export interface WebPushConfig {
  habilitado: boolean;
  firebase: WebPushFirebaseConfig;
  vapid_key: string;
}

export type WebPushStatus =
  | 'idle' | 'loading' | 'unsupported' | 'unavailable' | 'denied' | 'inactive'
  | 'activating' | 'active' | 'deactivating' | 'error';

export function hasFirebaseConfig(value: unknown): value is WebPushFirebaseConfig {
  if (!value || typeof value !== 'object') return false;
  const config = value as Record<string, unknown>;
  return ['apiKey', 'authDomain', 'projectId', 'messagingSenderId', 'appId'].every(
    (key) => typeof config[key] === 'string' && (config[key] as string).trim().length > 0,
  );
}

export function hasPushConfig(value: unknown): value is WebPushConfig {
  if (!value || typeof value !== 'object') return false;
  const config = value as Partial<WebPushConfig>;
  return config.habilitado === true && hasFirebaseConfig(config.firebase)
    && typeof config.vapid_key === 'string' && /^[A-Za-z0-9_-]{87}={0,2}$/.test(config.vapid_key);
}
