import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import {
  LucideBriefcaseBusiness,
  LucideBuilding2,
  LucideChevronDown,
  LucideCircleAlert,
  LucideCrown,
  LucideGlobe2,
  LucidePlus,
  LucideRefreshCw,
  LucideSearch,
  LucideShieldCheck,
  LucideUserRound,
} from '@lucide/angular';
import { RbacService } from '../../../core/rbac/rbac.service';
import { Role } from '../../../core/rbac/rbac.models';

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
    LucideBriefcaseBusiness,
    LucideBuilding2,
    LucideChevronDown,
    LucideCircleAlert,
    LucideCrown,
    LucideGlobe2,
    LucidePlus,
    LucideRefreshCw,
    LucideSearch,
    LucideShieldCheck,
    LucideUserRound,
  ],
  templateUrl: './roles.html',
  styleUrl: './roles.css',
})
export class Roles implements OnInit {
  private readonly rbac = inject(RbacService);

  protected readonly roles = signal<Role[]>([]);
  protected readonly loading = signal(true);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly searchTerm = signal('');
  protected readonly scopeFilter = signal<ScopeFilter>('ALL');
  protected readonly expandedRoleIds = signal<ReadonlySet<number>>(new Set<number>());

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
    this.loading.set(true);
    this.errorMessage.set(null);

    this.rbac.listRoles().subscribe({
      next: (roles) => {
        this.roles.set(roles);
        this.loading.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        this.errorMessage.set(
          error.error?.error?.message ?? 'No fue posible cargar los roles desde el backend.',
        );
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
