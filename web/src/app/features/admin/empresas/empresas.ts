import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import {
  LucideBuilding2,
  LucideCheck,
  LucideCircleAlert,
  LucideCirclePlus,
  LucideCreditCard,
  LucideMapPin,
  LucidePencil,
  LucideRefreshCw,
  LucideSearch,
  LucideUserRoundCog,
  LucideX,
} from '@lucide/angular';
import {
  City,
  Company,
  CompanySubscriptionInfo,
  CompanyStatus,
  OwnerPayload,
  Plan,
} from '../../../core/companies/companies.models';
import { CompaniesService } from '../../../core/companies/companies.service';

type FormMode = 'create' | 'edit' | 'owner' | 'plan' | null;

@Component({
  selector: 'situr-empresas',
  imports: [
    ReactiveFormsModule,
    LucideBuilding2,
    LucideCheck,
    LucideCircleAlert,
    LucideCirclePlus,
    LucideCreditCard,
    LucideMapPin,
    LucidePencil,
    LucideRefreshCw,
    LucideSearch,
    LucideUserRoundCog,
    LucideX,
  ],
  templateUrl: './empresas.html',
  styleUrl: './empresas.css',
})
export class Empresas implements OnInit {
  private readonly companiesService = inject(CompaniesService);
  private readonly fb = inject(FormBuilder);

  protected readonly companies = signal<Company[]>([]);
  protected readonly cities = signal<City[]>([]);
  protected readonly planes = signal<Plan[]>([]);
  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly actionCompanyId = signal<number | null>(null);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly successMessage = signal<string | null>(null);
  protected readonly searchTerm = signal('');
  protected readonly statusFilter = signal('');
  protected readonly formMode = signal<FormMode>(null);
  protected readonly selectedCompany = signal<Company | null>(null);
  protected readonly subscriptionInfo = signal<CompanySubscriptionInfo | null>(null);
  protected readonly loadingSubscription = signal(false);
  protected readonly selectedPlanCodigo = signal('');

  protected readonly activeCount = computed(
    () => this.companies().filter((company) => company.estado === 'ACTIVO').length,
  );

  protected readonly companyForm = this.fb.nonNullable.group({
    razon_social: ['', [Validators.required, Validators.maxLength(180)]],
    nombre_comercial: ['', [Validators.required, Validators.maxLength(180)]],
    ciudad_id: [''],
    subdominio: ['', Validators.pattern(/^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$/)],
    nit: ['', Validators.maxLength(30)],
    email_contacto: ['', Validators.email],
    telefono: ['', Validators.maxLength(30)],
    owner_email: ['', [Validators.required, Validators.email]],
    owner_nombres: ['', Validators.required],
    owner_apellidos: ['', Validators.required],
    owner_telefono: [''],
    owner_password: ['', Validators.minLength(8)],
  });

  ngOnInit(): void {
    this.loadCompanies();
    this.companiesService.listCities().subscribe({
      next: (cities) => this.cities.set(cities),
      error: () => this.cities.set([]),
    });
    this.companiesService.listPlans().subscribe({
      next: (planes) => this.planes.set(planes),
      error: () => this.planes.set([]),
    });
  }

  protected loadCompanies(): void {
    this.loading.set(true);
    this.errorMessage.set(null);
    this.companiesService.list(this.searchTerm(), this.statusFilter()).subscribe({
      next: (companies) => {
        this.companies.set(companies);
        this.loading.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        this.errorMessage.set(this.apiMessage(error, 'No fue posible cargar las empresas.'));
      },
    });
  }

  protected updateSearch(event: Event): void {
    this.searchTerm.set((event.target as HTMLInputElement).value);
  }

  protected updateStatusFilter(event: Event): void {
    this.statusFilter.set((event.target as HTMLSelectElement).value);
    this.loadCompanies();
  }

  protected startCreate(): void {
    this.selectedCompany.set(null);
    this.formMode.set('create');
    this.successMessage.set(null);
    this.errorMessage.set(null);
    this.updateFormValidators('create');
    this.companyForm.reset();
  }

  protected startEdit(company: Company): void {
    this.selectedCompany.set(company);
    this.formMode.set('edit');
    this.successMessage.set(null);
    this.errorMessage.set(null);
    this.updateFormValidators('edit');
    this.companyForm.reset({
      razon_social: company.razon_social,
      nombre_comercial: company.nombre_comercial,
      ciudad_id: company.ciudad_id?.toString() ?? '',
      subdominio: company.subdominio,
      nit: company.nit ?? '',
      email_contacto: company.email_contacto ?? '',
      telefono: company.telefono ?? '',
    });
  }

  protected startOwnerChange(company: Company): void {
    this.selectedCompany.set(company);
    this.formMode.set('owner');
    this.successMessage.set(null);
    this.errorMessage.set(null);
    this.updateFormValidators('owner');
    this.companyForm.reset({
      razon_social: company.razon_social,
      nombre_comercial: company.nombre_comercial,
      owner_email: company.propietario?.email ?? '',
      owner_nombres: company.propietario?.nombres ?? '',
      owner_apellidos: company.propietario?.apellidos ?? '',
      owner_telefono: company.propietario?.telefono ?? '',
      owner_password: '',
    });
  }

  protected closeForm(): void {
    this.formMode.set(null);
    this.selectedCompany.set(null);
    this.saving.set(false);
    this.companyForm.reset();
    this.subscriptionInfo.set(null);
    this.selectedPlanCodigo.set('');
  }

  protected startPlanChange(company: Company): void {
    this.selectedCompany.set(company);
    this.formMode.set('plan');
    this.successMessage.set(null);
    this.errorMessage.set(null);
    this.subscriptionInfo.set(null);
    this.loadingSubscription.set(true);
    this.companiesService.getSubscription(company.id).subscribe({
      next: (info) => {
        this.subscriptionInfo.set(info);
        this.selectedPlanCodigo.set(info.suscripcion?.plan.codigo ?? '');
        this.loadingSubscription.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.loadingSubscription.set(false);
        this.errorMessage.set(this.apiMessage(error, 'No fue posible cargar la suscripción.'));
      },
    });
  }

  protected selectPlan(codigo: string): void {
    this.selectedPlanCodigo.set(codigo);
  }

  protected submitPlanChange(): void {
    const company = this.selectedCompany();
    if (!company || !this.selectedPlanCodigo()) {
      return;
    }
    this.saving.set(true);
    this.errorMessage.set(null);
    this.companiesService.changeSubscription(company.id, this.selectedPlanCodigo()).subscribe({
      next: () => {
        this.saving.set(false);
        this.closeForm();
        this.successMessage.set('Plan de la empresa actualizado.');
      },
      error: (error: HttpErrorResponse) => {
        this.saving.set(false);
        this.errorMessage.set(this.apiMessage(error, 'No fue posible cambiar el plan.'));
      },
    });
  }

  protected submit(): void {
    const mode = this.formMode();
    if (!mode) {
      return;
    }
    this.companyForm.markAllAsTouched();
    if (this.companyForm.invalid) {
      return;
    }

    const raw = this.companyForm.getRawValue();
    const owner: OwnerPayload = {
      email: raw.owner_email.trim().toLowerCase(),
      nombres: raw.owner_nombres.trim(),
      apellidos: raw.owner_apellidos.trim(),
      telefono: raw.owner_telefono.trim() || undefined,
      password: raw.owner_password || undefined,
    };
    this.saving.set(true);
    this.errorMessage.set(null);

    if (mode === 'create') {
      this.companiesService
        .create({
          razon_social: raw.razon_social.trim(),
          nombre_comercial: raw.nombre_comercial.trim(),
          ciudad_id: raw.ciudad_id ? Number(raw.ciudad_id) : null,
          subdominio: raw.subdominio.trim() || undefined,
          nit: raw.nit.trim() || undefined,
          email_contacto: raw.email_contacto.trim().toLowerCase() || undefined,
          telefono: raw.telefono.trim() || undefined,
          propietario: owner,
        })
        .subscribe(this.saveObserver('Empresa creada y propietario asignado.'));
      return;
    }

    const company = this.selectedCompany();
    if (!company) {
      this.saving.set(false);
      return;
    }
    if (mode === 'owner') {
      this.companiesService
        .assignOwner(company.id, owner)
        .subscribe(this.saveObserver('Propietario actualizado.'));
      return;
    }

    this.companiesService
      .update(company.id, {
        razon_social: raw.razon_social.trim(),
        nombre_comercial: raw.nombre_comercial.trim(),
        ciudad_id: raw.ciudad_id ? Number(raw.ciudad_id) : null,
        nit: raw.nit.trim(),
        email_contacto: raw.email_contacto.trim().toLowerCase(),
        telefono: raw.telefono.trim(),
      })
      .subscribe(this.saveObserver('Datos de la empresa actualizados.'));
  }

  protected toggleStatus(company: Company): void {
    const nextStatus: CompanyStatus = company.estado === 'ACTIVO' ? 'INACTIVO' : 'ACTIVO';
    this.actionCompanyId.set(company.id);
    this.errorMessage.set(null);
    this.companiesService.updateStatus(company.id, nextStatus).subscribe({
      next: (updated) => {
        this.replaceCompany(updated);
        this.actionCompanyId.set(null);
        this.successMessage.set(
          nextStatus === 'ACTIVO' ? 'Empresa activada.' : 'Empresa desactivada.',
        );
      },
      error: (error: HttpErrorResponse) => {
        this.actionCompanyId.set(null);
        this.errorMessage.set(this.apiMessage(error, 'No fue posible cambiar el estado.'));
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

  private updateFormValidators(mode: FormMode): void {
    const isOwner = mode === 'owner';
    const isEdit = mode === 'edit';
    const isCreate = mode === 'create';

    // Company fields: only required when creating or editing company
    if (isOwner) {
      this.companyForm.controls.razon_social.clearValidators();
      this.companyForm.controls.nombre_comercial.clearValidators();
    } else {
      this.companyForm.controls.razon_social.setValidators([
        Validators.required,
        Validators.maxLength(180),
      ]);
      this.companyForm.controls.nombre_comercial.setValidators([
        Validators.required,
        Validators.maxLength(180),
      ]);
    }
    this.companyForm.controls.razon_social.updateValueAndValidity();
    this.companyForm.controls.nombre_comercial.updateValueAndValidity();

    // Owner fields: required on create and owner mode
    if (isEdit) {
      this.companyForm.controls.owner_email.clearValidators();
      this.companyForm.controls.owner_nombres.clearValidators();
      this.companyForm.controls.owner_apellidos.clearValidators();
      this.companyForm.controls.owner_password.clearValidators();
    } else if (isOwner) {
      this.companyForm.controls.owner_email.setValidators([Validators.required, Validators.email]);
      this.companyForm.controls.owner_nombres.setValidators([Validators.required]);
      this.companyForm.controls.owner_apellidos.setValidators([Validators.required]);
      this.companyForm.controls.owner_password.setValidators([Validators.minLength(8)]);
    } else if (isCreate) {
      this.companyForm.controls.owner_email.setValidators([Validators.required, Validators.email]);
      this.companyForm.controls.owner_nombres.setValidators([Validators.required]);
      this.companyForm.controls.owner_apellidos.setValidators([Validators.required]);
      this.companyForm.controls.owner_password.setValidators([
        Validators.required,
        Validators.minLength(8),
      ]);
    }
    [
      this.companyForm.controls.owner_email,
      this.companyForm.controls.owner_nombres,
      this.companyForm.controls.owner_apellidos,
      this.companyForm.controls.owner_password,
    ].forEach((control) => control.updateValueAndValidity());
  }

  private saveObserver(successMessage: string) {
    return {
      next: (company: Company) => {
        this.replaceCompany(company);
        this.saving.set(false);
        this.closeForm();
        this.successMessage.set(successMessage);
      },
      error: (error: HttpErrorResponse) => {
        this.saving.set(false);
        this.errorMessage.set(this.apiMessage(error, 'No fue posible guardar la empresa.'));
      },
    };
  }

  private replaceCompany(company: Company): void {
    this.companies.update((current) => {
      const exists = current.some((item) => item.id === company.id);
      const next = exists
        ? current.map((item) => (item.id === company.id ? company : item))
        : [...current, company];
      return next.sort((a, b) => a.nombre_comercial.localeCompare(b.nombre_comercial, 'es'));
    });
  }

  private apiMessage(error: HttpErrorResponse, fallback: string): string {
    const errorObj = error.error?.error;
    if (errorObj?.details && typeof errorObj.details === 'object') {
      const extractFirst = (val: unknown): string | null => {
        if (typeof val === 'string') return val;
        if (Array.isArray(val) && val.length > 0) return extractFirst(val[0]);
        if (typeof val === 'object' && val !== null) {
          const keys = Object.keys(val);
          if (keys.length > 0) return extractFirst((val as Record<string, unknown>)[keys[0]]);
        }
        return null;
      };
      const extracted = extractFirst(errorObj.details);
      if (extracted) return extracted;
    }
    return errorObj?.message ?? error.error?.detail ?? fallback;
  }
}
