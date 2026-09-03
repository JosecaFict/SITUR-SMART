import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Permission, Role } from './rbac.models';

@Injectable({ providedIn: 'root' })
export class RbacService {
  private readonly http = inject(HttpClient);

  listRoles(tenantId?: number): Observable<Role[]> {
    return this.http.get<Role[]>(`${environment.apiUrl}/roles/`, {
      headers: tenantId ? { 'X-Tenant-ID': tenantId.toString() } : {},
    });
  }

  listPermissions(tenantId?: number): Observable<Permission[]> {
    return this.http.get<Permission[]>(`${environment.apiUrl}/permissions/`, {
      headers: tenantId ? { 'X-Tenant-ID': tenantId.toString() } : {},
    });
  }

  createRole(
    tenantId: number,
    payload: { code: string; name: string; permissions: string[] },
  ): Observable<Role> {
    return this.http.post<Role>(`${environment.apiUrl}/roles/`, payload, {
      headers: { 'X-Tenant-ID': tenantId.toString() },
    });
  }

  updateRole(
    tenantId: number,
    roleId: number,
    payload: { name?: string; permissions?: string[] },
  ): Observable<Role> {
    return this.http.patch<Role>(`${environment.apiUrl}/roles/${roleId}/`, payload, {
      headers: { 'X-Tenant-ID': tenantId.toString() },
    });
  }

  deleteRole(tenantId: number, roleId: number): Observable<void> {
    return this.http.delete<void>(`${environment.apiUrl}/roles/${roleId}/`, {
      headers: { 'X-Tenant-ID': tenantId.toString() },
    });
  }
}
