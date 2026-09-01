import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Permission, Role, RoleCreatePayload, RoleUpdatePayload } from './rbac.models';

@Injectable({ providedIn: 'root' })
export class RbacService {
  private readonly http = inject(HttpClient);

  private tenantHeaders(tenantId?: number): Record<string, string> {
    return tenantId ? { 'X-Tenant-ID': tenantId.toString() } : {};
  }

  listRoles(tenantId?: number): Observable<Role[]> {
    return this.http.get<Role[]>(`${environment.apiUrl}/roles/`, {
      headers: this.tenantHeaders(tenantId),
    });
  }

  listPermissions(tenantId?: number): Observable<Permission[]> {
    return this.http.get<Permission[]>(`${environment.apiUrl}/permissions/`, {
      headers: this.tenantHeaders(tenantId),
    });
  }

  createRole(tenantId: number, payload: RoleCreatePayload): Observable<Role> {
    return this.http.post<Role>(`${environment.apiUrl}/roles/`, payload, {
      headers: this.tenantHeaders(tenantId),
    });
  }

  updateRole(tenantId: number, roleId: number, payload: RoleUpdatePayload): Observable<Role> {
    return this.http.patch<Role>(`${environment.apiUrl}/roles/${roleId}/`, payload, {
      headers: this.tenantHeaders(tenantId),
    });
  }

  deleteRole(tenantId: number, roleId: number): Observable<void> {
    return this.http.delete<void>(`${environment.apiUrl}/roles/${roleId}/`, {
      headers: this.tenantHeaders(tenantId),
    });
  }
}
