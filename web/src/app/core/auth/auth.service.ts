import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, catchError, finalize, tap, throwError } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  ApiErrorResponse,
  AuthSession,
  AuthUser,
  LoginPayload,
  PasswordResetConfirmPayload,
  PasswordResetResponse,
  ProfileUpdatePayload,
  RegisterPayload,
} from './auth.models';

const STORAGE_KEY = 'situr_smart_session';

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly sessionSignal = signal<AuthSession | null>(this.restoreSession());

  readonly session = this.sessionSignal.asReadonly();
  readonly isAuthenticated = computed(() => this.sessionSignal() !== null);
  readonly isSuperAdmin = computed(
    () => this.sessionSignal()?.user.roles.includes('SUPER_ADMIN') ?? false,
  );
  readonly roles = computed(() => this.sessionSignal()?.user.roles ?? []);
  readonly permissions = computed(() => this.sessionSignal()?.user.permisos ?? []);
  readonly accessToken = computed(() => this.sessionSignal()?.access ?? null);

  login(payload: LoginPayload): Observable<AuthSession> {
    return this.http
      .post<AuthSession>(`${environment.apiUrl}/auth/login/`, {
        email: payload.email.trim().toLowerCase(),
        password: payload.password,
      })
      .pipe(
        tap((session) => this.persistSession(session, payload.remember)),
        catchError((error: HttpErrorResponse) => this.handleError(error)),
      );
  }

  register(payload: RegisterPayload): Observable<AuthSession> {
    return this.http
      .post<AuthSession>(`${environment.apiUrl}/auth/register/`, {
        nombres: payload.nombres.trim(),
        apellidos: payload.apellidos.trim(),
        email: payload.email.trim().toLowerCase(),
        password: payload.password,
        telefono: payload.telefono?.trim() || null,
      })
      .pipe(
        tap((session) => this.persistSession(session, true)),
        catchError((error: HttpErrorResponse) => this.handleError(error)),
      );
  }

  updateProfile(payload: ProfileUpdatePayload): Observable<AuthUser> {
    return this.http
      .patch<AuthUser>(`${environment.apiUrl}/auth/me/`, payload)
      .pipe(
        tap((updatedUser) => {
          const current = this.sessionSignal();
          if (current) {
            const updatedSession: AuthSession = {
              ...current,
              user: updatedUser,
            };
            this.persistSession(updatedSession, true);
          }
        }),
        catchError((error: HttpErrorResponse) => this.handleError(error)),
      );
  }

  requestPasswordResetOtp(email: string): Observable<PasswordResetResponse> {
    return this.http
      .post<PasswordResetResponse>(`${environment.apiUrl}/auth/password-reset/request/`, {
        email: email.trim().toLowerCase(),
      })
      .pipe(catchError((error: HttpErrorResponse) => this.handleError(error)));
  }

  verifyPasswordResetOtp(email: string, code: string): Observable<PasswordResetResponse> {
    return this.http
      .post<PasswordResetResponse>(`${environment.apiUrl}/auth/password-reset/verify/`, {
        email: email.trim().toLowerCase(),
        code: code.trim(),
      })
      .pipe(catchError((error: HttpErrorResponse) => this.handleError(error)));
  }

  confirmPasswordReset(payload: PasswordResetConfirmPayload): Observable<PasswordResetResponse> {
    return this.http
      .post<PasswordResetResponse>(`${environment.apiUrl}/auth/password-reset/confirm/`, {
        email: payload.email.trim().toLowerCase(),
        code: payload.code.trim(),
        new_password: payload.new_password,
        new_password_confirm: payload.new_password_confirm,
      })
      .pipe(catchError((error: HttpErrorResponse) => this.handleError(error)));
  }

  refreshSession(): Observable<AuthSession> {
    const current = this.sessionSignal();
    if (!current) {
      return throwError(() => new Error('La sesión ha finalizado.'));
    }

    const remember = localStorage.getItem(STORAGE_KEY) !== null;
    return this.http
      .post<AuthSession>(`${environment.apiUrl}/auth/refresh/`, { refresh: current.refresh })
      .pipe(tap((session) => this.persistSession(session, remember)));
  }

  loadCurrentUser(): Observable<AuthUser> {
    return this.http.get<AuthUser>(`${environment.apiUrl}/auth/me/`).pipe(
      tap((user) => {
        const current = this.sessionSignal();
        if (current) {
          this.persistSession(
            { ...current, user },
            localStorage.getItem(STORAGE_KEY) !== null,
          );
        }
      }),
    );
  }

  logout(): void {
    const refresh = this.sessionSignal()?.refresh;
    this.clearSession();

    if (refresh) {
      this.http
        .post<void>(`${environment.apiUrl}/auth/logout/`, { refresh })
        .pipe(finalize(() => this.clearSession()))
        .subscribe({ error: () => undefined });
    }
  }

  clearSession(): void {
    localStorage.removeItem(STORAGE_KEY);
    sessionStorage.removeItem(STORAGE_KEY);
    this.sessionSignal.set(null);
  }

  private persistSession(session: AuthSession, remember: boolean): void {
    localStorage.removeItem(STORAGE_KEY);
    sessionStorage.removeItem(STORAGE_KEY);
    const storage = remember ? localStorage : sessionStorage;
    storage.setItem(STORAGE_KEY, JSON.stringify(session));
    this.sessionSignal.set(session);
  }

  private restoreSession(): AuthSession | null {
    const raw = localStorage.getItem(STORAGE_KEY) ?? sessionStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }

    try {
      const session = JSON.parse(raw) as Partial<AuthSession>;
      if (
        typeof session.access === 'string' &&
        typeof session.refresh === 'string' &&
        typeof session.user?.email === 'string'
      ) {
        return session as AuthSession;
      }
    } catch {
      // Una sesión dañada o de la versión mock se elimina a continuación.
    }

    localStorage.removeItem(STORAGE_KEY);
    sessionStorage.removeItem(STORAGE_KEY);
    return null;
  }

  private handleError(error: HttpErrorResponse): Observable<never> {
    if (error.status === 0) {
      return throwError(
        () => new Error('No se pudo conectar con el backend. Verifica que Django esté iniciado.'),
      );
    }

    const response = error.error as
      | (ApiErrorResponse & { detail?: string; error?: { message?: string; details?: unknown } })
      | undefined;

    let fieldMsg = '';
    const details = response?.error?.details;
    if (typeof details === 'object' && details !== null) {
      const record = details as Record<string, unknown>;
      const firstKey = Object.keys(record)[0];
      if (firstKey) {
        const val = record[firstKey];
        if (Array.isArray(val) && val.length > 0) {
          fieldMsg = String(val[0]);
        } else if (typeof val === 'string') {
          fieldMsg = val;
        }
      }
    }

    let rawError = '';
    if (typeof error.error === 'string') {
      if (
        error.error.includes('<html') ||
        error.error.includes('<!doctype') ||
        error.error.includes('<title>')
      ) {
        rawError = `El servidor no encontró el servicio solicitado (Error ${error.status}). El backend en Railway está actualizándose o reiniciando.`;
      } else {
        rawError = error.error;
      }
    }

    const message =
      fieldMsg ||
      response?.error?.message ||
      response?.detail ||
      rawError ||
      'Ocurrió un error inesperado al procesar la solicitud.';
    return throwError(() => new Error(message));
  }
}
