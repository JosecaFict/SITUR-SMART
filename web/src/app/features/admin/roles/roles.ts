import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import {
  LucideBriefcaseBusiness,
  LucideBuilding2,
  LucideChevronDown,
  LucideCircleAlert,
  LucideCrown,
  LucideGlobe2,
  LucidePencil,
  LucidePlus,
  LucideRefreshCw,
  LucideSearch,
  LucideShieldCheck,
  LucideTrash2,
  LucideUserRound,
} from '@lucide/angular';
import { AuthService } from '../../../core/auth/auth.service';
import { RbacService } from '../../../core/rbac/rbac.service';
import { Permission, Role } from '../../../core/rbac/rbac.models';

type ScopeFilter = 'ALL' | Role['scope'];

const PERMISSION_GROUPS: Record<string, string> = {
  TENANTS_LEER: 'Empresas',
  TENANTS_GESTIONAR: 'Empresas',
  SUSCRIPCIONES_GESTIONAR: 'Suscripciones',
  USUARIOS_LEER: 'Usuarios',
  USUARIOS_GESTIONAR: 'Usuarios',
  ROLES_GESTIONAR: 'Roles',
  PRODUCTOS_LEER: 'Productos',
  PRODUCTOS_GESTIONAR: 'Productos',
  DISPONIBILIDAD_GESTIONAR: 'Disponibilidad',
  RESERVAS_LEER: 'Reservas',
  RESERVAS_GESTIONAR: 'Reservas',
  REPORTES_TENANT: 'Reportes',
  REPORTES_GLOBALES: 'Reportes globales',
  BITACORA_LEER: 'Bitácora',
};

@Component({
  selector: 'situr-roles',
  imports: [
    ReactiveFormsModule,
    LucideBriefcaseBusiness,
    LucideBuilding2,
    LucideChevronDown,
    LucideCircleAlert,
    LucideCrown,
    LucideGlobe2,
    LucidePencil,
    LucidePlus,
    LucideRefreshCw,
    LucideSearch,
    LucideShieldCheck,
    LucideTrash2,
    LucideUserRound,
  ],
  templateUrl: './roles.html',
  styleUrl: './roles.css',
})
export class Roles implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly rbac = inject(RbacService);
  private readonly fb = inject(FormBuilder);

  protected readonly roles = signal<Role[]>([]);
  protected readonly loading = signal(true);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly searchTerm = signal('');
  protected readonly scopeFilter = signal<ScopeFilter>('ALL');
  protected readonly expandedRoleIds = signal<ReadonlySet<number>>(new Set<number>());

  protected readonly permissionsCatalog = signal<Permission[]>([]);
  protected readonly showForm = signal(false);
  protected readonly saving = signal(false);
  protected readonly formError = signal<string | null>(null);
  protected readonly editingRole = signal<Role | null>(null);
  protected readonly selectedPermissions = signal<ReadonlySet<string>>(new Set<string>());

  protected readonly tenantForm = this.fb.nonNullable.group({
    tenantId: [this.auth.session()?.user.tenants[0]?.id ?? null, Validators.required],
  });

  protected readonly roleForm = this.fb.nonNullable.group({
    code: ['', [Validators.required, Validators.pattern(/^[A-Za-z][A-Za-z0-9_]{2,59}$/)]],
    name: ['', Validators.required],
  });

  /** Tenant que efectivamente se consultó (distinto de lo que haya escrito el usuario sin cargar). */
  protected readonly loadedTenantId = signal<number | null>(null);

  protected readonly globalRoleCount = computed(
    () => this.roles().filter((role) => role.scope === 'GLOBAL').length,
  );
  protected readonly tenantRoleCount = computed(
    () => this.roles().filter((role) => role.scope === 'TENANT').length,
  );
  protected readonly filteredRoles = computed(() => {
    const query = this.searchTerm().trim().toLocaleLowerCase('es');
    const scope = this.scopeFilter();

    return this.roles().filter((role) => {
      const matchesScope = scope === 'ALL' || role.scope === scope;
      const searchable = [role.code, role.name, this.roleDescription(role), ...role.permissions]
        .join(' ')
        .toLocaleLowerCase('es');
      return matchesScope && (!query || searchable.includes(query));
    });
  });

  ngOnInit(): void {
    this.loadRoles();
  }

  protected loadRoles(): void {
    const tenantId = this.tenantForm.value.tenantId ?? undefined;
    this.loading.set(true);
    this.errorMessage.set(null);

    this.rbac.listRoles(tenantId).subscribe({
      next: (roles) => {
        this.roles.set(roles);
        this.loadedTenantId.set(tenantId ?? null);
        this.loading.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        this.errorMessage.set(
          error.error?.error?.message ?? 'No fue posible cargar los roles desde el backend.',
        );
      },
    });

    if (tenantId) {
      this.rbac.listPermissions(tenantId).subscribe({
        next: (permissions) => this.permissionsCatalog.set(permissions),
        error: () => undefined,
      });
    }
  }

  protected isEditable(role: Role): boolean {
    const tenantId = this.loadedTenantId();
    return !role.is_system && tenantId !== null && role.tenant_id === tenantId;
  }

  protected togglePermission(code: string): void {
    const next = new Set(this.selectedPermissions());
    if (next.has(code)) {
      next.delete(code);
    } else {
      next.add(code);
    }
    this.selectedPermissions.set(next);
  }

  protected startCreateRole(): void {
    this.editingRole.set(null);
    this.roleForm.reset();
    this.roleForm.controls.code.enable();
    this.selectedPermissions.set(new Set());
    this.formError.set(null);
    this.showForm.set(true);
  }

  protected startEditRole(role: Role): void {
    this.editingRole.set(role);
    this.roleForm.reset({ code: role.code, name: role.name });
    this.roleForm.controls.code.disable();
    this.selectedPermissions.set(new Set(role.permissions));
    this.formError.set(null);
    this.showForm.set(true);
  }

  protected cancelRoleForm(): void {
    this.showForm.set(false);
    this.editingRole.set(null);
    this.roleForm.controls.code.enable();
    this.roleForm.reset();
  }

  protected submitRole(): void {
    const tenantId = this.loadedTenantId();
    if (!tenantId) {
      this.formError.set('Primero carga un tenant válido.');
      return;
    }
    if (this.roleForm.invalid) {
      this.roleForm.markAllAsTouched();
      return;
    }

    const raw = this.roleForm.getRawValue();
    const permissions = [...this.selectedPermissions()];
    const editing = this.editingRole();
    this.saving.set(true);
    this.formError.set(null);

    const request = editing
      ? this.rbac.updateRole(tenantId, editing.id, { name: raw.name.trim(), permissions })
      : this.rbac.createRole(tenantId, { code: raw.code.trim(), name: raw.name.trim(), permissions });

    request.subscribe({
      next: (role) => {
        this.roles.update((current) =>
          editing ? current.map((r) => (r.id === role.id ? role : r)) : [...current, role],
        );
        this.saving.set(false);
        this.cancelRoleForm();
      },
      error: (error: HttpErrorResponse) => {
        this.saving.set(false);
        this.formError.set(
          error.error?.error?.message ??
            (editing
              ? 'No fue posible actualizar el rol en el backend.'
              : 'No fue posible crear el rol en el backend.'),
        );
      },
    });
  }

  protected deleteRole(role: Role): void {
    const tenantId = this.loadedTenantId();
    if (!tenantId) {
      return;
    }
    if (!confirm(`¿Eliminar el rol "${role.name}"? Esta acción no se puede deshacer.`)) {
      return;
    }

    this.rbac.deleteRole(tenantId, role.id).subscribe({
      next: () => this.roles.update((current) => current.filter((r) => r.id !== role.id)),
      error: (error: HttpErrorResponse) => {
        this.errorMessage.set(error.error?.error?.message ?? 'No fue posible eliminar el rol.');
      },
    });
  }

  protected setScopeFilter(scope: ScopeFilter): void {
    this.scopeFilter.set(scope);
  }

  protected updateSearch(event: Event): void {
    this.searchTerm.set((event.target as HTMLInputElement).value);
  }

  protected toggleRole(roleId: number): void {
    const next = new Set(this.expandedRoleIds());
    if (next.has(roleId)) {
      next.delete(roleId);
    } else {
      next.add(roleId);
    }
    this.expandedRoleIds.set(next);
  }

  protected isExpanded(roleId: number): boolean {
    return this.expandedRoleIds().has(roleId);
  }

  protected permissionGroups(role: Role): string[] {
    return [...new Set(role.permissions.map((code) => PERMISSION_GROUPS[code] ?? code))];
  }

  protected roleDescription(role: Role): string {
    switch (role.code) {
      case 'SUPER_ADMIN':
        return 'Control total de la plataforma y sus empresas.';
      case 'CLIENTE':
        return 'Consulta y reserva servicios turísticos.';
      case 'TENANT_ADMIN':
        return 'Administra usuarios y operaciones de su empresa.';
      case 'TENANT_EMPLOYEE':
        return 'Gestiona las operaciones autorizadas de su empresa.';
      case 'GUIA':
        return 'Gestiona tours y servicios asignados dentro de su empresa.';
      default:
        return role.scope === 'GLOBAL'
          ? 'Rol de acceso global de la plataforma.'
          : 'Rol operativo configurable dentro de una empresa.';
    }
  }
}
