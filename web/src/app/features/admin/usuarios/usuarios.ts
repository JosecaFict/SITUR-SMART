import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { AuthService } from '../../../core/auth/auth.service';
import { UsersService } from '../../../core/users/users.service';
import { TenantUser } from '../../../core/users/users.models';

const SUPERADMIN_ROLE_OPTIONS = ['TENANT_ADMIN', 'TENANT_EMPLOYEE', 'GUIA'];
const TENANT_ADMIN_ROLE_OPTIONS = ['TENANT_EMPLOYEE', 'GUIA'];

@Component({
  selector: 'situr-usuarios',
  imports: [ReactiveFormsModule],
  templateUrl: './usuarios.html',
  styleUrl: './usuarios.css',
})
export class Usuarios implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly usersService = inject(UsersService);
  private readonly fb = inject(FormBuilder);

  protected readonly users = signal<TenantUser[]>([]);
  protected readonly loading = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly showForm = signal(false);
  protected readonly saving = signal(false);
  protected readonly formError = signal<string | null>(null);
  protected readonly editingUser = signal<TenantUser | null>(null);

  protected readonly isSuperAdmin = computed(
    () => this.auth.session()?.user.roles.includes('SUPER_ADMIN') ?? false,
  );
  protected readonly roleOptions = computed(() =>
    this.isSuperAdmin() ? SUPERADMIN_ROLE_OPTIONS : TENANT_ADMIN_ROLE_OPTIONS,
  );

  protected readonly tenantForm = this.fb.nonNullable.group({
    tenantId: [this.auth.session()?.user.tenants[0]?.id ?? null, Validators.required],
  });

  protected readonly userForm = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    first_names: ['', Validators.required],
    last_names: ['', Validators.required],
    phone: [''],
    password: [''],
    role_code: ['TENANT_EMPLOYEE', Validators.required],
  });

  ngOnInit(): void {
    if (this.tenantForm.value.tenantId) {
      this.loadUsers();
    }
  }

  protected loadUsers(): void {
    const tenantId = this.tenantForm.value.tenantId;
    if (!tenantId) {
      this.errorMessage.set('Ingresa el ID de la empresa (tenant) para consultar.');
      return;
    }

    this.loading.set(true);
    this.errorMessage.set(null);

    this.usersService.listUsers(tenantId).subscribe({
      next: (users) => {
        this.users.set(users);
        this.loading.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        this.errorMessage.set(
          error.error?.error?.message ?? 'No fue posible cargar los usuarios desde el backend.',
        );
      },
    });
  }

  protected startCreate(): void {
    this.editingUser.set(null);
    this.userForm.reset({ role_code: 'TENANT_EMPLOYEE' });
    this.userForm.controls.email.enable();
    this.formError.set(null);
    this.showForm.set(true);
  }

  protected startEdit(user: TenantUser): void {
    this.editingUser.set(user);
    this.userForm.reset({
      email: user.email,
      first_names: user.nombres,
      last_names: user.apellidos,
      phone: user.telefono ?? '',
      password: '',
      role_code: user.roles[0] ?? this.roleOptions()[0],
    });
    this.userForm.controls.email.disable();
    this.formError.set(null);
    this.showForm.set(true);
  }

  protected cancelForm(): void {
    this.showForm.set(false);
    this.editingUser.set(null);
    this.userForm.controls.email.enable();
    this.userForm.reset({ role_code: 'TENANT_EMPLOYEE' });
  }

  protected submitUser(): void {
    const tenantId = this.tenantForm.value.tenantId;
    if (!tenantId) {
      this.formError.set('Primero ingresa y carga un tenant válido.');
      return;
    }
    if (this.userForm.invalid) {
      this.userForm.markAllAsTouched();
      return;
    }

    const raw = this.userForm.getRawValue();
    const editing = this.editingUser();
    this.saving.set(true);
    this.formError.set(null);

    const request = editing
      ? this.usersService.updateUser(tenantId, editing.id, {
          first_names: raw.first_names.trim(),
          last_names: raw.last_names.trim(),
          phone: raw.phone.trim() || undefined,
          role_code: raw.role_code,
        })
      : this.usersService.createUser(tenantId, {
          email: raw.email.trim().toLowerCase(),
          first_names: raw.first_names.trim(),
          last_names: raw.last_names.trim(),
          phone: raw.phone.trim() || undefined,
          password: raw.password.trim() || undefined,
          role_code: raw.role_code,
        });

    request.subscribe({
      next: (user) => {
        this.users.update((current) =>
          editing ? current.map((u) => (u.id === user.id ? user : u)) : [...current, user],
        );
        this.saving.set(false);
        this.cancelForm();
      },
      error: (error: HttpErrorResponse) => {
        this.saving.set(false);
        this.formError.set(
          error.error?.error?.message ??
            (editing
              ? 'No fue posible actualizar el usuario en el backend.'
              : 'No fue posible crear el usuario en el backend.'),
        );
      },
    });
  }

  protected deactivateUser(user: TenantUser): void {
    const tenantId = this.tenantForm.value.tenantId;
    if (!tenantId) {
      return;
    }
    if (!confirm(`¿Quitar a ${user.email} de esta empresa?`)) {
      return;
    }

    this.usersService.deactivateUser(tenantId, user.id).subscribe({
      next: () => this.users.update((current) => current.filter((u) => u.id !== user.id)),
      error: (error: HttpErrorResponse) => {
        this.errorMessage.set(
          error.error?.error?.message ?? 'No fue posible desactivar al usuario.',
        );
      },
    });
  }
}
