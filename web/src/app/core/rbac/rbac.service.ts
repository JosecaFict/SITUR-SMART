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
}
