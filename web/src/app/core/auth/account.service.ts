import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuthUser } from './auth.models';
import { AuthService } from './auth.service';

export interface AccountSession {
  id: number;
  dispositivo: string;
  ip: string | null;
  iniciada_en: string;
  actual: boolean;
}

/** Seguridad de la propia cuenta: correo, contraseña, sesiones y baja. */
@Injectable({ providedIn: 'root' })
export class AccountService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly base = `${environment.apiUrl}/auth`;

  sendEmailCode(): Observable<void> {
    return this.http.post<void>(`${this.base}/correo/enviar-codigo/`, null);
  }

  confirmEmail(codigo: string): Observable<AuthUser> {
    return this.http
      .post<AuthUser>(`${this.base}/correo/verificar/`, { codigo: codigo.trim() })
      .pipe(tap((user) => this.auth.replaceUser(user)));
  }

  changePassword(actual: string, nueva: string): Observable<{ access: string; refresh: string }> {
    return this.http
      .post<{ access: string; refresh: string }>(`${this.base}/me/contrasena/`, { actual, nueva })
      .pipe(tap((tokens) => this.auth.replaceTokens(tokens.access, tokens.refresh)));
  }

  sessions(): Observable<AccountSession[]> {
    const refresh = this.auth.session()?.refresh;
    return this.http.get<AccountSession[]>(`${this.base}/me/sesiones/`, {
      headers: refresh ? { 'X-Refresh-Token': refresh } : {},
    });
  }

  closeSession(id: number): Observable<void> {
    return this.http.post<void>(`${this.base}/me/sesiones/${id}/cerrar/`, null);
  }

  closeOthers(): Observable<{ cerradas: number }> {
    return this.http.post<{ cerradas: number }>(`${this.base}/me/sesiones/cerrar-otras/`, {
      refresh: this.auth.session()?.refresh ?? '',
    });
  }

  deleteAccount(password: string): Observable<void> {
    return this.http
      .post<void>(`${this.base}/me/eliminar/`, { password })
      .pipe(tap(() => this.auth.clearSession()));
  }
}
