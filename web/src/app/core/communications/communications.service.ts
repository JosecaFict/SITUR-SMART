import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Paged } from '../traveler/traveler.models';
import { AudiencePreview, Communication, CommunicationOptions, CommunicationOptionFilters, CommunicationPage, CommunicationPayload, CommunicationPreferences } from './communications.models';

@Injectable({ providedIn: 'root' })
export class CommunicationsService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/comunicaciones/`;

  private headers(tenantId?: number): Record<string, string> {
    return tenantId === undefined ? {} : { 'X-Tenant-ID': String(tenantId) };
  }

  list(tenantId?: number, page = 1, state = '', search = ''): Observable<CommunicationPage> {
    return this.http.get<Paged<Communication> | Communication[]>(this.base, {
      headers: this.headers(tenantId), params: { page, ...(state ? { estado: state } : {}), ...(search ? { buscar: search } : {}) },
    }).pipe(map((result) => Array.isArray(result)
      ? { count: result.length, next: null, previous: null, results: result }
      : result));
  }

  detail(id: number, tenantId?: number): Observable<Communication> {
    return this.http.get<Communication>(`${this.base}${id}/`, { headers: this.headers(tenantId) });
  }

  create(payload: CommunicationPayload, tenantId?: number): Observable<Communication> {
    return this.http.post<Communication>(this.base, payload, { headers: this.headers(tenantId) });
  }

  update(id: number, payload: CommunicationPayload, tenantId?: number): Observable<Communication> {
    return this.http.patch<Communication>(`${this.base}${id}/`, payload, { headers: this.headers(tenantId) });
  }

  preview(payload: CommunicationPayload, tenantId?: number): Observable<AudiencePreview> {
    return this.http.post<AudiencePreview>(`${this.base}audiencia/`, payload, { headers: this.headers(tenantId) });
  }

  publish(id: number, fingerprint: string, tenantId?: number): Observable<Communication> {
    return this.http.post<Communication>(`${this.base}${id}/publicar/`, { huella: fingerprint }, { headers: this.headers(tenantId) });
  }

  cancel(id: number, tenantId?: number): Observable<Communication> {
    return this.http.post<Communication>(`${this.base}${id}/cancelar/`, {}, { headers: this.headers(tenantId) });
  }

  preferences(): Observable<CommunicationPreferences> {
    return this.http.get<CommunicationPreferences>(`${environment.apiUrl}/me/comunicaciones/preferencias/`);
  }

  setPreference(companyId: number | null, enabled: boolean): Observable<CommunicationPreferences> {
    return this.http.patch<CommunicationPreferences>(`${environment.apiUrl}/me/comunicaciones/preferencias/`,
      { empresa_id: companyId, promociones: enabled });
  }

  emailPreview(id: number, tenantId?: number): Observable<{ asunto: string; html: string; texto: string }> {
    return this.http.get<{ asunto: string; html: string; texto: string }>(`${this.base}${id}/correo/`, { headers: this.headers(tenantId) });
  }

  options(tenantId?: number, search = '', filters?: CommunicationOptionFilters): Observable<CommunicationOptions> {
    return this.http.get<CommunicationOptions>(`${this.base}opciones/`, {
      headers: this.headers(tenantId), params: { ...(search.trim() ? { buscar: search.trim() } : {}),
        ...(filters ? { empresa_ids: filters.empresa_ids.join(','), rol_ids: filters.rol_ids.join(','), grupo: filters.grupo, tipo: filters.tipo } : {}), },
    });
  }
}
