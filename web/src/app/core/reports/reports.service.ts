import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { ReportFilters, ReportResponse } from './reports.models';

@Injectable({ providedIn: 'root' })
export class ReportsService {
  private readonly http = inject(HttpClient);

  get(tenantId: number | null, filters: ReportFilters): Observable<ReportResponse> {
    return this.http.get<ReportResponse>(`${environment.apiUrl}/reportes/`, {
      headers: tenantId ? { 'X-Tenant-ID': tenantId.toString() } : {},
      params: this.params(filters),
    });
  }

  export(tenantId: number | null, filters: ReportFilters, format: 'csv' | 'xlsx' | 'pdf'): Observable<Blob> {
    const suffix = format === 'csv' ? '' : `${format === 'xlsx' ? 'excel' : 'pdf'}/`;
    return this.http.get(`${environment.apiUrl}/reportes/exportar/${suffix}`, {
      headers: tenantId ? { 'X-Tenant-ID': tenantId.toString() } : {},
      params: this.params(filters),
      responseType: 'blob',
    });
  }

  private params(filters: ReportFilters): HttpParams {
    let params = new HttpParams().set('tipo', filters.tipo);
    for (const [key, value] of Object.entries(filters)) {
      if (key !== 'tipo' && value) params = params.set(key, value);
    }
    return params;
  }
}
