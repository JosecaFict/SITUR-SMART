import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import {
  LucideBriefcaseBusiness,
  LucideBuilding2,
  LucideChevronDown,
  LucideCircleAlert,
  LucidePencil,
  LucidePlus,
  LucideRefreshCw,
  LucideSearch,
  LucideShieldCheck,
  LucideTrash2,
  LucideX,
} from '@lucide/angular';
import { forkJoin } from 'rxjs';
import { AuthService } from '../../../core/auth/auth.service';
import { CompaniesService } from '../../../core/companies/companies.service';
import { Permission, Role } from '../../../core/rbac/rbac.models';
import { RbacService } from '../../../core/rbac/rbac.service';

interface CompanyChoice { id: number; name: string; }
interface PermissionGroup { module: string; permissions: Permission[]; }

const FORBIDDEN_COMPANY_PERMISSIONS = new Set([
  'TENANTS_LEER', 'TENANTS_GESTIONAR', 'SUSCRIPCIONES_GESTIONAR', 'REPORTES_GLOBALES',
]);

@Component({
  selector: 'situr-roles',
  imports: [
    ReactiveFormsModule, LucideBriefcaseBusiness, LucideBuilding2, LucideChevronDown,
    LucideCircleAlert, LucidePencil, LucidePlus, LucideRefreshCw, LucideSearch,
    LucideShieldCheck, LucideTrash2, LucideX,
  ],
  templateUrl: './roles.html',
  styleUrl: './roles.css',
})
export class Roles implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly companiesService = inject(CompaniesService);
  private readonly rbac = inject(RbacService);
  private readonly fb = inject(FormBuilder);

  protected readonly companies = signal<CompanyChoice[]>([]);
  protected readonly selectedCompanyId = signal<number | null>(null);
  protected readonly roles = signal<Role[]>([]);
  protected readonly permissions = signal<Permission[]>([]);
  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly successMessage = signal<string | null>(null);
  protected readonly formError = signal<string | null>(null);
  protected readonly searchTerm = signal('');
  protected readonly expandedRoleIds = signal<ReadonlySet<number>>(new Set<number>());
  protected readonly showForm = signal(false);
  protected readonly editingRole = signal<Role | null>(null);
  protected readonly selectedPermissions = signal<ReadonlySet<string>>(new Set<string>());

  protected readonly isSuperAdmin = computed(
    () => this.auth.session()?.user.roles.includes('SUPER_ADMIN') ?? false,
  );
  protected readonly selectedCompany = computed(() =>
    this.companies().find((company) => company.id === this.selectedCompanyId()),
  );
  protected readonly customRoleCount = computed(
    () => this.roles().filter((role) => !role.is_system).length,
  );
  protected readonly permissionGroups = computed<PermissionGroup[]>(() => {
    const grouped = new Map<string, Permission[]>();
    for (const permission of this.permissions()) {
      if (FORBIDDEN_COMPANY_PERMISSIONS.has(permission.code)) continue;
      const group = grouped.get(permission.module) ?? [];
      group.push(permission);
      grouped.set(permission.module, group);
    }
    return [...grouped.entries()].map(([module, permissions]) => ({ module, permissions }));
  });
  protected readonly filteredRoles = computed(() => {
    const query = this.searchTerm().trim().toLocaleLowerCase('es');
    return this.roles().filter((role) =>
      [role.code, role.name, ...role.permissions].join(' ').toLocaleLowerCase('es').includes(query),
    );
  });

  protected readonly roleForm = this.fb.nonNullable.group({
    code: ['', [Validators.required, Validators.pattern(/^[A-Za-z][A-Za-z0-9_]{2,59}$/)]],
    name: ['', [Validators.required, Validators.maxLength(120)]],
  });

  ngOnInit(): void {
    const sessionCompanies =
      this.auth.session()?.user.tenants.map((tenant) => ({ id: tenant.id, name: tenant.name })) ?? [];
    if (this.isSuperAdmin()) {
      this.companiesService.list('', 'ACTIVO').subscribe({
        next: (companies) => {
          const choices = companies.map((company) => ({ id: company.id, name: company.nombre_comercial }));
          this.companies.set(choices);
          this.selectInitialCompany(choices);
        },
        error: () => {
          this.loading.set(false);
          this.errorMessage.set('No fue posible cargar las empresas disponibles.');
        },
      });
    } else {
      this.companies.set(sessionCompanies);
      this.selectInitialCompany(sessionCompanies);
    }
  }

  private selectInitialCompany(companies: CompanyChoice[]): void {
    if (!companies.length) {
      this.loading.set(false);
      this.errorMessage.set('Tu cuenta no tiene una empresa activa asignada.');
      return;
    }
    this.selectedCompanyId.set(companies[0].id);
    this.loadRoles();
  }

  protected changeCompany(event: Event): void {
    this.selectedCompanyId.set(Number((event.target as HTMLSelectElement).value));
    this.cancelForm();
    this.loadRoles();
  }

  protected loadRoles(): void {
    const companyId = this.selectedCompanyId();
    if (!companyId) return;
    this.loading.set(true);
    this.errorMessage.set(null);
    forkJoin({
      roles: this.rbac.listRoles(companyId),
      permissions: this.rbac.listPermissions(companyId),
    }).subscribe({
      next: ({ roles, permissions }) => {
        this.roles.set(roles);
        this.permissions.set(permissions);
        this.loading.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        this.errorMessage.set(this.apiMessage(error, 'No fue posible cargar los roles y permisos.'));
      },
    });
  }

  protected startCreate(): void {
    this.editingRole.set(null);
    this.roleForm.reset();
    this.roleForm.controls.code.enable();
    this.selectedPermissions.set(new Set());
    this.formError.set(null);
    this.showForm.set(true);
  }

  protected startEdit(role: Role): void {
    if (role.is_system) return;
    this.editingRole.set(role);
    this.roleForm.setValue({ code: role.code, name: role.name });
    this.roleForm.controls.code.disable();
    this.selectedPermissions.set(new Set(role.permissions));
    this.formError.set(null);
    this.showForm.set(true);
  }

  protected cancelForm(): void {
    this.showForm.set(false);
    this.editingRole.set(null);
    this.roleForm.controls.code.enable();
    this.roleForm.reset();
    this.selectedPermissions.set(new Set());
  }

  protected togglePermission(code: string): void {
    const next = new Set(this.selectedPermissions());
    next.has(code) ? next.delete(code) : next.add(code);
    this.selectedPermissions.set(next);
  }

  protected submitRole(): void {
    const companyId = this.selectedCompanyId();
    if (!companyId || this.roleForm.invalid) {
      this.roleForm.markAllAsTouched();
      return;
    }
    const raw = this.roleForm.getRawValue();
    const editing = this.editingRole();
    const permissions = [...this.selectedPermissions()];
    this.saving.set(true);
    this.formError.set(null);
    const request = editing
      ? this.rbac.updateRole(companyId, editing.id, { name: raw.name.trim(), permissions })
      : this.rbac.createRole(companyId, {
          code: raw.code.trim().toUpperCase(), name: raw.name.trim(), permissions,
        });
    request.subscribe({
      next: (role) => {
        this.roles.update((roles) =>
          editing ? roles.map((current) => (current.id === role.id ? role : current)) : [...roles, role],
        );
        this.successMessage.set(editing ? 'Rol actualizado correctamente.' : 'Rol creado correctamente.');
        this.saving.set(false);
        this.cancelForm();
      },
      error: (error: HttpErrorResponse) => {
        this.saving.set(false);
        this.formError.set(this.apiMessage(error, 'No fue posible guardar el rol.'));
      },
    });
  }

  protected deleteRole(role: Role): void {
    const companyId = this.selectedCompanyId();
    if (!companyId || role.is_system || !confirm(`¿Eliminar el rol "${role.name}"?`)) return;
    this.rbac.deleteRole(companyId, role.id).subscribe({
      next: () => {
        this.roles.update((roles) => roles.filter((current) => current.id !== role.id));
        this.successMessage.set('Rol eliminado correctamente.');
      },
      error: (error: HttpErrorResponse) =>
        this.errorMessage.set(this.apiMessage(error, 'No fue posible eliminar el rol.')),
    });
  }

  protected updateSearch(event: Event): void {
    this.searchTerm.set((event.target as HTMLInputElement).value);
  }

  protected toggleRole(roleId: number): void {
    const next = new Set(this.expandedRoleIds());
    next.has(roleId) ? next.delete(roleId) : next.add(roleId);
    this.expandedRoleIds.set(next);
  }

  protected isExpanded(roleId: number): boolean { return this.expandedRoleIds().has(roleId); }

  protected permissionName(code: string): string {
    return this.permissions().find((permission) => permission.code === code)?.name ?? code;
  }

  private apiMessage(error: HttpErrorResponse, fallback: string): string {
    const details = error.error?.error?.details;
    if (details && typeof details === 'object') {
      const first = Object.values(details).flat()[0];
      if (typeof first === 'string') return first;
    }
    return error.error?.error?.message ?? fallback;
  }
}
