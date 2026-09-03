import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import {
  LucideBuilding2, LucideCircleAlert, LucidePencil, LucidePlus, LucideRefreshCw,
  LucideSearch, LucideTrash2, LucideUserRound, LucideUsers, LucideX,
} from '@lucide/angular';
import { forkJoin } from 'rxjs';
import { AuthService } from '../../../core/auth/auth.service';
import { Role } from '../../../core/rbac/rbac.models';
import { RbacService } from '../../../core/rbac/rbac.service';
import { TenantUser } from '../../../core/users/users.models';
import { UsersService } from '../../../core/users/users.service';

interface CompanyChoice { id: number; name: string; }

@Component({
  selector: 'situr-usuarios',
  imports: [
    ReactiveFormsModule, LucideBuilding2, LucideCircleAlert, LucidePencil, LucidePlus,
    LucideRefreshCw, LucideSearch, LucideTrash2, LucideUserRound, LucideUsers, LucideX,
  ],
  templateUrl: './usuarios.html',
  styleUrl: './usuarios.css',
})
export class Usuarios implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly rbac = inject(RbacService);
  private readonly usersService = inject(UsersService);
  private readonly fb = inject(FormBuilder);

  protected readonly companies = signal<CompanyChoice[]>([]);
  protected readonly selectedCompanyId = signal<number | null>(null);
  protected readonly users = signal<TenantUser[]>([]);
  protected readonly roles = signal<Role[]>([]);
  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly successMessage = signal<string | null>(null);
  protected readonly formError = signal<string | null>(null);
  protected readonly showForm = signal(false);
  protected readonly editingUser = signal<TenantUser | null>(null);
  protected readonly searchTerm = signal('');

  protected readonly selectedCompany = computed(() =>
    this.companies().find((company) => company.id === this.selectedCompanyId()),
  );
  protected readonly roleOptions = computed(() =>
    this.roles().filter((role) => role.scope === 'TENANT' && role.code !== 'TENANT_ADMIN'),
  );
  protected readonly filteredUsers = computed(() => {
    const query = this.searchTerm().trim().toLocaleLowerCase('es');
    return this.users().filter((user) =>
      [user.email, user.nombres, user.apellidos, ...user.roles]
        .join(' ').toLocaleLowerCase('es').includes(query),
    );
  });

  protected readonly userForm = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    first_names: ['', Validators.required],
    last_names: ['', Validators.required],
    phone: [''],
    password: [''],
    role_code: ['', Validators.required],
  });

  ngOnInit(): void {
    const sessionCompanies =
      this.auth.session()?.user.tenants.map((tenant) => ({ id: tenant.id, name: tenant.name })) ?? [];
    this.companies.set(sessionCompanies);
    this.selectInitialCompany(sessionCompanies);
  }

  private selectInitialCompany(companies: CompanyChoice[]): void {
    if (!companies.length) {
      this.loading.set(false);
      this.errorMessage.set('Tu cuenta no tiene una empresa activa asignada.');
      return;
    }
    this.selectedCompanyId.set(companies[0].id);
    this.loadUsers();
  }

  protected changeCompany(event: Event): void {
    this.selectedCompanyId.set(Number((event.target as HTMLSelectElement).value));
    this.cancelForm();
    this.loadUsers();
  }

  protected loadUsers(): void {
    const companyId = this.selectedCompanyId();
    if (!companyId) return;
    this.loading.set(true);
    this.errorMessage.set(null);
    forkJoin({
      users: this.usersService.listUsers(companyId),
      roles: this.rbac.listRoles(companyId),
    }).subscribe({
      next: ({ users, roles }) => {
        this.users.set(users);
        this.roles.set(roles);
        this.loading.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        this.errorMessage.set(this.apiMessage(error, 'No fue posible cargar los empleados.'));
      },
    });
  }

  protected startCreate(): void {
    const defaultRole = this.roleOptions()[0]?.code ?? '';
    this.editingUser.set(null);
    this.userForm.reset({ role_code: defaultRole });
    this.userForm.controls.email.enable();
    this.formError.set(null);
    this.showForm.set(true);
  }

  protected startEdit(user: TenantUser): void {
    if (user.roles.includes('TENANT_ADMIN')) return;
    this.editingUser.set(user);
    this.userForm.reset({
      email: user.email, first_names: user.nombres, last_names: user.apellidos,
      phone: user.telefono ?? '', password: '', role_code: user.roles[0] ?? '',
    });
    this.userForm.controls.email.disable();
    this.formError.set(null);
    this.showForm.set(true);
  }

  protected cancelForm(): void {
    this.showForm.set(false);
    this.editingUser.set(null);
    this.userForm.controls.email.enable();
    this.userForm.reset();
  }

  protected submitUser(): void {
    const companyId = this.selectedCompanyId();
    if (!companyId || this.userForm.invalid) {
      this.userForm.markAllAsTouched();
      return;
    }
    const raw = this.userForm.getRawValue();
    const editing = this.editingUser();
    this.saving.set(true);
    this.formError.set(null);
    const request = editing
      ? this.usersService.updateUser(companyId, editing.id, {
          first_names: raw.first_names.trim(), last_names: raw.last_names.trim(),
          phone: raw.phone.trim() || undefined, role_code: raw.role_code,
        })
      : this.usersService.createUser(companyId, {
          email: raw.email.trim().toLowerCase(), first_names: raw.first_names.trim(),
          last_names: raw.last_names.trim(), phone: raw.phone.trim() || undefined,
          password: raw.password || undefined, role_code: raw.role_code,
        });
    request.subscribe({
      next: (user) => {
        this.users.update((users) =>
          editing ? users.map((current) => (current.id === user.id ? user : current)) : [...users, user],
        );
        this.saving.set(false);
        this.successMessage.set(editing ? 'Empleado actualizado correctamente.' : 'Empleado creado correctamente.');
        this.cancelForm();
      },
      error: (error: HttpErrorResponse) => {
        this.saving.set(false);
        this.formError.set(this.apiMessage(error, 'No fue posible guardar el empleado.'));
      },
    });
  }

  protected deactivateUser(user: TenantUser): void {
    const companyId = this.selectedCompanyId();
    if (!companyId || user.roles.includes('TENANT_ADMIN')) return;
    if (!confirm(`¿Quitar a ${user.nombres} ${user.apellidos} de esta empresa?`)) return;
    this.usersService.deactivateUser(companyId, user.id).subscribe({
      next: () => {
        this.users.update((users) => users.filter((current) => current.id !== user.id));
        this.successMessage.set('Empleado retirado de la empresa.');
      },
      error: (error: HttpErrorResponse) =>
        this.errorMessage.set(this.apiMessage(error, 'No fue posible retirar al empleado.')),
    });
  }

  protected updateSearch(event: Event): void {
    this.searchTerm.set((event.target as HTMLInputElement).value);
  }

  protected roleName(code: string): string {
    return this.roles().find((role) => role.code === code)?.name ?? code;
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
