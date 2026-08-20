import { Injectable, computed, signal } from '@angular/core';
import { Observable, delay, of, throwError } from 'rxjs';
import {
  AuthSession,
  AuthUser,
  LoginPayload,
  RegisterPayload,
} from './auth.models';

const STORAGE_KEY = 'situr_smart_session';

/**
 * "Base de datos" en memoria. Se reemplaza por el backend real (FastAPI)
 * cuando exista; la forma de AuthSession ya coincide con la respuesta esperada.
 */
const MOCK_USERS: Array<AuthUser & { password: string }> = [
  {
    id: 'usr-demo-superadmin',
    nombre: 'Administrador SITUR',
    email: 'admin@situr.smart',
    password: 'Admin1234',
    role: 'superadmin',
    tenantId: null,
  },
];

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly sessionSignal = signal<AuthSession | null>(this.restoreSession());

  readonly session = this.sessionSignal.asReadonly();
  readonly isAuthenticated = computed(() => this.sessionSignal() !== null);

  login(payload: LoginPayload): Observable<AuthSession> {
    const match = MOCK_USERS.find(
      (u) => u.email.toLowerCase() === payload.email.toLowerCase() && u.password === payload.password,
    );

    if (!match) {
      return throwError(() => new Error('Credenciales incorrectas. Verifica tu correo y contraseña.')).pipe(
        delay(600),
      );
    }

    const session = this.buildSession(match);
    return of(session).pipe(delay(600), this.tapPersist(payload.remember));
  }

  register(payload: RegisterPayload): Observable<AuthSession> {
    const exists = MOCK_USERS.some((u) => u.email.toLowerCase() === payload.email.toLowerCase());

    if (exists) {
      return throwError(() => new Error('Ya existe una cuenta registrada con ese correo.')).pipe(delay(600));
    }

    const newUser: AuthUser & { password: string } = {
      id: `usr-${Date.now()}`,
      nombre: payload.nombre,
      email: payload.email,
      password: payload.password,
      role: 'cliente',
      tenantId: null,
    };
    MOCK_USERS.push(newUser);

    const session = this.buildSession(newUser);
    return of(session).pipe(delay(800), this.tapPersist(false));
  }

  requestPasswordReset(email: string): Observable<{ email: string }> {
    return of({ email }).pipe(delay(800));
  }

  logout(): void {
    localStorage.removeItem(STORAGE_KEY);
    sessionStorage.removeItem(STORAGE_KEY);
    this.sessionSignal.set(null);
  }

  private buildSession(user: AuthUser & { password: string }): AuthSession {
    const { password: _password, ...publicUser } = user;
    return {
      token: `mock-token.${btoa(user.id)}.${Date.now()}`,
      user: publicUser,
    };
  }

  private tapPersist(remember: boolean) {
    return (source: Observable<AuthSession>) =>
      new Observable<AuthSession>((subscriber) =>
        source.subscribe({
          next: (session) => {
            const storage = remember ? localStorage : sessionStorage;
            storage.setItem(STORAGE_KEY, JSON.stringify(session));
            this.sessionSignal.set(session);
            subscriber.next(session);
          },
          error: (err) => subscriber.error(err),
          complete: () => subscriber.complete(),
        }),
      );
  }

  private restoreSession(): AuthSession | null {
    const raw = localStorage.getItem(STORAGE_KEY) ?? sessionStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    try {
      return JSON.parse(raw) as AuthSession;
    } catch {
      return null;
    }
  }
}
