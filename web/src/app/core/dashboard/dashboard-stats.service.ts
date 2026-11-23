import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { DashboardStats } from './dashboard-stats.models';

@Injectable({ providedIn: 'root' })
export class DashboardStatsService {
  private readonly http = inject(HttpClient);

  /**
   * La empresa manda su X-Tenant-ID; el SuperAdmin no, y puede pasar las
   * empresas a filtrar (una) o comparar (dos a cuatro).
   */
  get(tenantId: number | null, companies: number[] = []): Observable<DashboardStats> {
    let params = new HttpParams();
    if (companies.length) params = params.set('empresas', companies.join(','));
    return this.http.get<DashboardStats>(`${environment.apiUrl}/dashboard/`, {
      headers: tenantId ? { 'X-Tenant-ID': tenantId.toString() } : {},
      params,
    });
  }
}
