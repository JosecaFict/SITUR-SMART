import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuditLogFilters, AuditLogResponse } from './audit.models';

@Injectable({ providedIn: 'root' })
export class AuditService {
  private readonly http = inject(HttpClient);

  list(tenantId: number | null, filters: AuditLogFilters = {}): Observable<AuditLogResponse> {
    let params = new HttpParams();
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== null && value !== '') {
        params = params.set(key, String(value));
      }
    }
    return this.http.get<AuditLogResponse>(`${environment.apiUrl}/bitacora/`, {
      headers: tenantId ? { 'X-Tenant-ID': tenantId.toString() } : {},
      params,
    });
  }
}
