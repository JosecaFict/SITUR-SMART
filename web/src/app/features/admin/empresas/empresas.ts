import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import {
  LucideBuilding2,
  LucideCheck,
  LucideCircleAlert,
  LucideCirclePlus,
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
  CompanyStatus,
  OwnerPayload,
} from '../../../core/companies/companies.models';
import { CompaniesService } from '../../../core/companies/companies.service';

type FormMode = 'create' | 'edit' | 'owner' | null;

@Component({
  selector: 'situr-empresas',
  imports: [
    ReactiveFormsModule,
    LucideBuilding2,
    LucideCheck,
    LucideCircleAlert,
    LucideCirclePlus,
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
  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly actionCompanyId = signal<number | null>(null);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly successMessage = signal<string | null>(null);
  protected readonly searchTerm = signal('');
  protected readonly statusFilter = signal('');
  protected readonly formMode = signal<FormMode>(null);
  protected readonly selectedCompany = signal<Company | null>(null);

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
    this.companyForm.reset();
    this.setOwnerValidators(true);
  }

  protected startEdit(company: Company): void {
    this.selectedCompany.set(company);
    this.formMode.set('edit');
    this.successMessage.set(null);
    this.companyForm.reset({
      razon_social: company.razon_social,
      nombre_comercial: company.nombre_comercial,
      ciudad_id: company.ciudad_id?.toString() ?? '',
      subdominio: company.subdominio,
      nit: company.nit ?? '',
      email_contacto: company.email_contacto ?? '',
      telefono: company.telefono ?? '',
    });
    this.setOwnerValidators(false);
  }

  protected startOwnerChange(company: Company): void {
    this.selectedCompany.set(company);
    this.formMode.set('owner');
    this.successMessage.set(null);
    this.companyForm.reset({
      owner_email: company.propietario?.email ?? '',
      owner_nombres: company.propietario?.nombres ?? '',
      owner_apellidos: company.propietario?.apellidos ?? '',
      owner_telefono: company.propietario?.telefono ?? '',
    });
    this.setOwnerValidators(true);
  }

  protected closeForm(): void {
    this.formMode.set(null);
    this.selectedCompany.set(null);
    this.saving.set(false);
    this.companyForm.reset();
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

  private setOwnerValidators(required: boolean): void {
    this.companyForm.controls.owner_email.setValidators(
      required ? [Validators.required, Validators.email] : [],
    );
    this.companyForm.controls.owner_nombres.setValidators(required ? [Validators.required] : []);
    this.companyForm.controls.owner_apellidos.setValidators(required ? [Validators.required] : []);
    [
      this.companyForm.controls.owner_email,
      this.companyForm.controls.owner_nombres,
      this.companyForm.controls.owner_apellidos,
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
    return error.error?.error?.message ?? fallback;
  }
}
