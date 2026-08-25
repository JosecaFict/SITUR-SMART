import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { CreateTenantUserPayload, TenantUser, UpdateTenantUserPayload } from './users.models';

@Injectable({ providedIn: 'root' })
export class UsersService {
  private readonly http = inject(HttpClient);

  private tenantHeaders(tenantId: number): Record<string, string> {
    return { 'X-Tenant-ID': tenantId.toString() };
  }

  listUsers(tenantId: number): Observable<TenantUser[]> {
    return this.http.get<TenantUser[]>(`${environment.apiUrl}/usuarios/`, {
      headers: this.tenantHeaders(tenantId),
    });
  }

  createUser(tenantId: number, payload: CreateTenantUserPayload): Observable<TenantUser> {
    return this.http.post<TenantUser>(`${environment.apiUrl}/usuarios/`, payload, {
      headers: this.tenantHeaders(tenantId),
    });
  }

  updateUser(
    tenantId: number,
    userId: number,
    payload: UpdateTenantUserPayload,
  ): Observable<TenantUser> {
    return this.http.patch<TenantUser>(`${environment.apiUrl}/usuarios/${userId}/`, payload, {
      headers: this.tenantHeaders(tenantId),
    });
  }

  deactivateUser(tenantId: number, userId: number): Observable<void> {
    return this.http.delete<void>(`${environment.apiUrl}/usuarios/${userId}/`, {
      headers: this.tenantHeaders(tenantId),
    });
  }
}
