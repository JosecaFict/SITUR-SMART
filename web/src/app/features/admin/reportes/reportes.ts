import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import {
  LucideChartNoAxesCombined,
  LucideCircleAlert,
  LucideDownload,
} from '@lucide/angular';
import { AuthService } from '../../../core/auth/auth.service';
import { CompaniesService } from '../../../core/companies/companies.service';
import { apiErrorMessage } from '../../../core/http/api-error';
import { ReportFilters, ReportResponse, ReportType } from '../../../core/reports/reports.models';
import { ReportsService } from '../../../core/reports/reports.service';

interface CompanyChoice { id: number; name: string }

const REPORTS: { value: ReportType; label: string; description: string }[] = [
  { value: 'plataforma', label: 'Empresas y planes', description: 'Estado de empresas y condiciones contratadas.' },
  { value: 'catalogo', label: 'Catálogo', description: 'Productos registrados y publicados.' },
  { value: 'hospedajes', label: 'Hospedajes', description: 'Oferta declarada de habitaciones y capacidades.' },
  { value: 'actividad', label: 'Actividad', description: 'Movimientos registrados en la bitácora.' },
];

@Component({
  selector: 'situr-reportes',
  imports: [ReactiveFormsModule, LucideChartNoAxesCombined, LucideCircleAlert, LucideDownload],
  templateUrl: './reportes.html',
  styleUrl: './reportes.css',
})
export class Reportes implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly companiesService = inject(CompaniesService);
  private readonly reportsService = inject(ReportsService);
  private readonly fb = inject(FormBuilder);

  protected readonly reportChoices = REPORTS;
  protected readonly isSuperAdmin = computed(() => this.auth.session()?.user.roles.includes('SUPER_ADMIN') ?? false);
  protected readonly companies = signal<CompanyChoice[]>([]);
  protected readonly selectedCompanyId = signal<number | null>(null);
  protected readonly report = signal<ReportResponse | null>(null);
  protected readonly loading = signal(true);
  protected readonly exporting = signal<'csv' | 'xlsx' | 'pdf' | null>(null);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly form = this.fb.nonNullable.group({
    tipo: ['plataforma' as ReportType],
    desde: [''],
    hasta: [''],
    estado: [''],
  });

  ngOnInit(): void {
    if (this.isSuperAdmin()) {
      this.companiesService.list().subscribe({
        next: (companies) => this.companies.set(companies.map((company) => ({ id: company.id, name: company.nombre_comercial }))),
        error: () => undefined,
      });
    } else {
      const tenant = this.auth.session()?.user.tenants[0];
      if (!tenant) {
        this.loading.set(false);
        this.errorMessage.set('Tu cuenta no tiene una empresa asignada.');
        return;
      }
      this.selectedCompanyId.set(tenant.id);
    }
    this.load();
  }

  protected changeCompany(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.selectedCompanyId.set(value ? Number(value) : null);
    this.load();
  }

  protected changeType(type: ReportType): void {
    this.form.patchValue({ tipo: type, estado: '' });
    this.load();
  }

  protected load(): void {
    this.loading.set(true);
    this.errorMessage.set(null);
    this.reportsService.get(this.selectedCompanyId(), this.filters()).subscribe({
      next: (report) => { this.report.set(report); this.loading.set(false); },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        this.errorMessage.set(apiErrorMessage(error, 'No fue posible generar el reporte.'));
      },
    });
  }

  protected clear(): void {
    this.form.patchValue({ desde: '', hasta: '', estado: '' });
    this.load();
  }

  protected exportFile(format: 'csv' | 'xlsx' | 'pdf'): void {
    if (this.exporting()) return;
    this.exporting.set(format);
    this.reportsService.export(this.selectedCompanyId(), this.filters(), format).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = `reporte-${this.form.controls.tipo.value}.${format}`;
        anchor.click();
        URL.revokeObjectURL(url);
        this.exporting.set(null);
      },
      error: (error: HttpErrorResponse) => {
        this.exporting.set(null);
        this.errorMessage.set(apiErrorMessage(error, 'No fue posible descargar el reporte.'));
      },
    });
  }

  protected cell(row: Record<string, unknown>, key: string): string {
    const value = row[key];
    if (value === null || value === undefined || value === '') return '—';
    if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(value)) {
      return new Intl.DateTimeFormat('es-BO', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value));
    }
    return String(value);
  }

  protected reportLabel(type: ReportType): string {
    return REPORTS.find((report) => report.value === type)?.label ?? 'Reporte';
  }

  private filters(): ReportFilters {
    const raw = this.form.getRawValue();
    return { tipo: raw.tipo, desde: raw.desde, hasta: raw.hasta, estado: raw.estado };
  }
}
