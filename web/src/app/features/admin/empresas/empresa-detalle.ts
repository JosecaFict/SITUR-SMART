import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import {
  LucideArrowLeft,
  LucideBuilding2,
  LucideCalendarDays,
  LucideCheck,
  LucideCircleAlert,
  LucideCreditCard,
  LucideMail,
  LucideMapPin,
  LucidePencil,
  LucidePhone,
  LucideRefreshCw,
  LucideShieldCheck,
  LucideUserRound,
  LucideX,
} from '@lucide/angular';
import { AuthService } from '../../../core/auth/auth.service';
import {
  City,
  Company,
  CompanyStatus,
  CompanySubscriptionInfo,
  OwnerPayload,
  Plan,
} from '../../../core/companies/companies.models';
import { CompaniesService } from '../../../core/companies/companies.service';
import { apiErrorMessage } from '../../../core/http/api-error';

interface StatusOption {
  value: CompanyStatus;
  label: string;
  description: string;
  tone: 'positive' | 'warning' | 'danger';
}

const TRANSITIONS: Record<CompanyStatus, CompanyStatus[]> = {
  PENDIENTE: ['ACTIVO', 'INACTIVO'],
  ACTIVO: ['SUSPENDIDO', 'INACTIVO'],
  SUSPENDIDO: ['ACTIVO', 'INACTIVO'],
  INACTIVO: ['ACTIVO'],
};

const STATUS_OPTIONS: Record<CompanyStatus, StatusOption> = {
  ACTIVO: {
    value: 'ACTIVO',
    label: 'Activar empresa',
    description: 'La empresa podrá volver a operar y administrar sus servicios.',
    tone: 'positive',
  },
  SUSPENDIDO: {
    value: 'SUSPENDIDO',
    label: 'Suspender temporalmente',
    description: 'Sus usuarios podrán ingresar, pero no operar dentro de esta empresa.',
    tone: 'warning',
  },
  INACTIVO: {
    value: 'INACTIVO',
    label: 'Marcar como inactiva',
    description: 'La empresa dejará de operar hasta que la plataforma la reactive.',
    tone: 'danger',
  },
  PENDIENTE: {
    value: 'PENDIENTE',
    label: 'Dejar pendiente',
    description: 'La empresa seguirá esperando revisión de la plataforma.',
    tone: 'warning',
  },
};

@Component({
  selector: 'situr-empresa-detalle',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    LucideArrowLeft,
    LucideBuilding2,
    LucideCalendarDays,
    LucideCheck,
    LucideCircleAlert,
    LucideCreditCard,
    LucideMail,
    LucideMapPin,
    LucidePencil,
    LucidePhone,
    LucideRefreshCw,
    LucideShieldCheck,
    LucideUserRound,
    LucideX,
  ],
  templateUrl: './empresa-detalle.html',
  styleUrl: './empresa-detalle.css',
})
export class EmpresaDetalle implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly companiesService = inject(CompaniesService);
  private readonly auth = inject(AuthService);
  private readonly fb = inject(FormBuilder);

  protected readonly company = signal<Company | null>(null);
  protected readonly cities = signal<City[]>([]);
  protected readonly subscription = signal<CompanySubscriptionInfo | null>(null);
  protected readonly plans = signal<Plan[]>([]);
  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly loadingSubscription = signal(true);
  protected readonly editing = signal(false);
  protected readonly ownerEditing = signal(false);
  protected readonly planEditing = signal(false);
  protected readonly selectedPlanCode = signal('');
  protected readonly autoRenew = signal(false);
  protected readonly pendingStatus = signal<StatusOption | null>(null);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly successMessage = signal<string | null>(null);

  protected readonly canManage = computed(() => {
    const user = this.auth.session()?.user;
    return Boolean(
      user?.roles.includes('SUPER_ADMIN') || user?.permisos.includes('TENANTS_GESTIONAR'),
    );
  });

  protected readonly canManageSubscriptions = computed(() => {
    const user = this.auth.session()?.user;
    return Boolean(
      user?.roles.includes('SUPER_ADMIN') ||
        user?.permisos.includes('SUSCRIPCIONES_GESTIONAR'),
    );
  });

  protected readonly availableTransitions = computed(() => {
    const current = this.company()?.estado;
    return current ? TRANSITIONS[current].map((status) => STATUS_OPTIONS[status]) : [];
  });

  protected readonly companyForm = this.fb.nonNullable.group({
    nombre_comercial: ['', [Validators.required, Validators.maxLength(180)]],
    razon_social: ['', [Validators.required, Validators.maxLength(180)]],
    nit: ['', Validators.maxLength(30)],
    ciudad_id: [''],
    email_contacto: ['', Validators.email],
    telefono: ['', Validators.maxLength(30)],
  });

  protected readonly ownerForm = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    nombres: ['', [Validators.required, Validators.maxLength(120)]],
    apellidos: ['', [Validators.required, Validators.maxLength(120)]],
    telefono: ['', Validators.maxLength(30)],
    password: ['', Validators.minLength(8)],
  });

  ngOnInit(): void {
    const companyId = Number(this.route.snapshot.paramMap.get('id'));
    if (!Number.isInteger(companyId) || companyId < 1) {
      this.loading.set(false);
      this.errorMessage.set('El identificador de la empresa no es válido.');
      return;
    }
    this.loadCompany(companyId);
    this.loadSubscription(companyId);
    this.companiesService.listCities().subscribe({
      next: (cities) => this.cities.set(cities),
      error: () => this.cities.set([]),
    });
    this.companiesService.listPlans().subscribe({
      next: (plans) => this.plans.set(plans),
      error: () => this.plans.set([]),
    });
  }

  protected startEdit(): void {
    const company = this.company();
    if (!company || !this.canManage()) return;
    this.companyForm.reset({
      nombre_comercial: company.nombre_comercial,
      razon_social: company.razon_social,
      nit: company.nit ?? '',
      ciudad_id: company.ciudad_id?.toString() ?? '',
      email_contacto: company.email_contacto ?? '',
      telefono: company.telefono ?? '',
    });
    this.errorMessage.set(null);
    this.successMessage.set(null);
    this.editing.set(true);
  }

  protected cancelEdit(): void {
    this.editing.set(false);
  }

  protected startOwnerEdit(): void {
    const owner = this.company()?.propietario;
    if (!this.canManage()) return;
    this.ownerForm.reset({
      email: owner?.email ?? '',
      nombres: owner?.nombres ?? '',
      apellidos: owner?.apellidos ?? '',
      telefono: owner?.telefono ?? '',
      password: '',
    });
    this.successMessage.set(null);
    this.errorMessage.set(null);
    this.ownerEditing.set(true);
  }

  protected cancelOwnerEdit(): void {
    this.ownerEditing.set(false);
  }

  protected submitOwner(): void {
    const company = this.company();
    if (!company || !this.canManage()) return;
    this.ownerForm.markAllAsTouched();
    if (this.ownerForm.invalid) return;

    const value = this.ownerForm.getRawValue();
    const owner: OwnerPayload = {
      email: value.email.trim().toLowerCase(),
      nombres: value.nombres.trim(),
      apellidos: value.apellidos.trim(),
      telefono: value.telefono.trim() || undefined,
      password: value.password || undefined,
    };
    this.saving.set(true);
    this.errorMessage.set(null);
    this.companiesService.assignOwner(company.id, owner).subscribe({
      next: (updated) => {
        this.company.set(updated);
        this.ownerEditing.set(false);
        this.saving.set(false);
        this.successMessage.set('El propietario de la empresa se actualizó correctamente.');
      },
      error: (error: HttpErrorResponse) => {
        this.saving.set(false);
        this.errorMessage.set(apiErrorMessage(error, 'No fue posible asignar el propietario.'));
      },
    });
  }

  protected startPlanEdit(): void {
    if (!this.canManageSubscriptions()) return;
    const active = this.subscription()?.suscripcion;
    this.selectedPlanCode.set(active?.plan.codigo ?? '');
    this.autoRenew.set(active?.renovacion_automatica ?? false);
    this.successMessage.set(null);
    this.errorMessage.set(null);
    this.planEditing.set(true);
  }

  protected cancelPlanEdit(): void {
    this.planEditing.set(false);
  }

  protected selectPlan(code: string): void {
    this.selectedPlanCode.set(code);
  }

  protected updateAutoRenew(event: Event): void {
    this.autoRenew.set((event.target as HTMLInputElement).checked);
  }

  protected submitPlan(): void {
    const company = this.company();
    const planCode = this.selectedPlanCode();
    if (!company || !planCode || !this.canManageSubscriptions()) return;

    this.saving.set(true);
    this.errorMessage.set(null);
    this.companiesService
      .changeSubscription(company.id, planCode, this.autoRenew())
      .subscribe({
        next: (subscription) => {
          this.subscription.update((current) => ({
            suscripcion: subscription,
            uso: current?.uso ?? { usuarios: 0, productos: 0 },
          }));
          this.planEditing.set(false);
          this.saving.set(false);
          this.successMessage.set('El plan y sus nuevas condiciones contratadas fueron actualizados.');
        },
        error: (error: HttpErrorResponse) => {
          this.saving.set(false);
          this.errorMessage.set(apiErrorMessage(error, 'No fue posible cambiar el plan.'));
        },
      });
  }

  protected submitEdit(): void {
    const company = this.company();
    if (!company || !this.canManage()) return;
    this.companyForm.markAllAsTouched();
    if (this.companyForm.invalid) return;

    const value = this.companyForm.getRawValue();
    this.saving.set(true);
    this.errorMessage.set(null);
    this.companiesService
      .update(company.id, {
        nombre_comercial: value.nombre_comercial.trim(),
        razon_social: value.razon_social.trim(),
        nit: value.nit.trim(),
        ciudad_id: value.ciudad_id ? Number(value.ciudad_id) : null,
        email_contacto: value.email_contacto.trim().toLowerCase(),
        telefono: value.telefono.trim(),
      })
      .subscribe({
        next: (updated) => {
          this.company.set(updated);
          this.editing.set(false);
          this.saving.set(false);
          this.successMessage.set('Los datos de la empresa se actualizaron correctamente.');
        },
        error: (error: HttpErrorResponse) => {
          this.saving.set(false);
          this.errorMessage.set(apiErrorMessage(error, 'No fue posible actualizar la empresa.'));
        },
      });
  }

  protected requestStatusChange(option: StatusOption): void {
    if (!this.canManage()) return;
    this.pendingStatus.set(option);
    this.successMessage.set(null);
    this.errorMessage.set(null);
  }

  protected cancelStatusChange(): void {
    this.pendingStatus.set(null);
  }

  protected confirmStatusChange(): void {
    const company = this.company();
    const option = this.pendingStatus();
    if (!company || !option || !this.canManage()) return;

    this.saving.set(true);
    this.errorMessage.set(null);
    this.companiesService.updateStatus(company.id, option.value).subscribe({
      next: (updated) => {
        this.company.set(updated);
        this.pendingStatus.set(null);
        this.saving.set(false);
        this.successMessage.set(`El estado cambió a ${this.statusLabel(updated.estado).toLowerCase()}.`);
      },
      error: (error: HttpErrorResponse) => {
        this.saving.set(false);
        this.errorMessage.set(
          apiErrorMessage(error, 'No fue posible cambiar el estado de la empresa.'),
        );
      },
    });
  }

  protected statusLabel(status: CompanyStatus): string {
    return {
      ACTIVO: 'Activa',
      INACTIVO: 'Inactiva',
      PENDIENTE: 'Pendiente',
      SUSPENDIDO: 'Suspendida',
    }[status];
  }

  protected formatDate(value: string): string {
    return new Intl.DateTimeFormat('es-BO', { dateStyle: 'medium' }).format(new Date(value));
  }

  protected periodicityLabel(value: string | null | undefined): string {
    return value === 'ANUAL' ? 'Anual' : 'Mensual';
  }

  private loadCompany(companyId: number): void {
    this.loading.set(true);
    this.companiesService.get(companyId).subscribe({
      next: (company) => {
        this.company.set(company);
        this.loading.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        this.errorMessage.set(apiErrorMessage(error, 'No fue posible cargar la empresa.'));
      },
    });
  }

  private loadSubscription(companyId: number): void {
    this.loadingSubscription.set(true);
    this.companiesService.getSubscription(companyId).subscribe({
      next: (subscription) => {
        this.subscription.set(subscription);
        this.loadingSubscription.set(false);
      },
      error: () => {
        this.subscription.set(null);
        this.loadingSubscription.set(false);
      },
    });
  }
}
