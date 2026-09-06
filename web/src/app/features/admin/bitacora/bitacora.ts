import { DatePipe, JsonPipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import {
  LucideChevronDown,
  LucideCircleAlert,
  LucideRefreshCw,
  LucideScrollText,
  LucideSearch,
} from '@lucide/angular';
import { AuthService } from '../../../core/auth/auth.service';
import { AuditService } from '../../../core/audit/audit.service';
import { AuditLogEntry } from '../../../core/audit/audit.models';
import { CompaniesService } from '../../../core/companies/companies.service';

interface CompanyChoice {
  id: number;
  name: string;
}

const PAGE_SIZE = 25;

const ACTION_LABELS: Record<string, string> = {
  CREAR: 'Creación',
  ACTUALIZAR: 'Actualización',
  ELIMINAR: 'Eliminación',
  DESACTIVAR: 'Desactivación',
  VINCULAR: 'Vinculación',
};

const ENTITY_LABELS: Record<string, string> = {
  usuario: 'Usuario',
  rol: 'Rol',
  empresa: 'Empresa',
  producto_turistico: 'Producto',
};

@Component({
  selector: 'situr-bitacora',
  imports: [
    ReactiveFormsModule,
    DatePipe,
    JsonPipe,
    LucideChevronDown,
    LucideCircleAlert,
    LucideRefreshCw,
    LucideScrollText,
    LucideSearch,
  ],
  templateUrl: './bitacora.html',
  styleUrl: './bitacora.css',
})
export class Bitacora implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly companiesService = inject(CompaniesService);
  private readonly auditService = inject(AuditService);
  private readonly fb = inject(FormBuilder);

  protected readonly isSuperAdmin = computed(
    () => this.auth.session()?.user.roles.includes('SUPER_ADMIN') ?? false,
  );

  protected readonly companies = signal<CompanyChoice[]>([]);
  /** null = todas las empresas (solo disponible para SUPER_ADMIN). */
  protected readonly selectedCompanyId = signal<number | null>(null);
  protected readonly logs = signal<AuditLogEntry[]>([]);
  protected readonly total = signal(0);
  protected readonly offset = signal(0);
  protected readonly loading = signal(true);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly expandedIds = signal<ReadonlySet<number>>(new Set<number>());

  protected readonly filterForm = this.fb.nonNullable.group({
    entidad: [''],
    accion: [''],
    usuario: [''],
    desde: [''],
    hasta: [''],
  });

  protected readonly hasNextPage = computed(() => this.offset() + PAGE_SIZE < this.total());
  protected readonly hasPrevPage = computed(() => this.offset() > 0);
  protected readonly currentPage = computed(() => Math.floor(this.offset() / PAGE_SIZE) + 1);
  protected readonly totalPages = computed(() => Math.max(1, Math.ceil(this.total() / PAGE_SIZE)));

  ngOnInit(): void {
    if (this.isSuperAdmin()) {
      this.companiesService.list('', 'ACTIVO').subscribe({
        next: (companies) => {
          this.companies.set(companies.map((c) => ({ id: c.id, name: c.nombre_comercial })));
        },
        error: () => undefined,
      });
      this.loadLogs();
      return;
    }

    const tenants = this.auth.session()?.user.tenants ?? [];
    if (!tenants.length) {
      this.loading.set(false);
      this.errorMessage.set('Tu cuenta no tiene una empresa activa asignada.');
      return;
    }
    this.selectedCompanyId.set(tenants[0].id);
    this.loadLogs();
  }

  protected changeCompany(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.selectedCompanyId.set(value ? Number(value) : null);
    this.offset.set(0);
    this.loadLogs();
  }

  protected applyFilters(): void {
    this.offset.set(0);
    this.loadLogs();
  }

  protected clearFilters(): void {
    this.filterForm.reset({ entidad: '', accion: '', usuario: '', desde: '', hasta: '' });
    this.offset.set(0);
    this.loadLogs();
  }

  protected nextPage(): void {
    if (!this.hasNextPage()) return;
    this.offset.update((value) => value + PAGE_SIZE);
    this.loadLogs();
  }

  protected prevPage(): void {
    if (!this.hasPrevPage()) return;
    this.offset.update((value) => Math.max(0, value - PAGE_SIZE));
    this.loadLogs();
  }

  protected loadLogs(): void {
    this.loading.set(true);
    this.errorMessage.set(null);
    const raw = this.filterForm.getRawValue();

    this.auditService
      .list(this.selectedCompanyId(), {
        entidad: raw.entidad,
        accion: raw.accion,
        usuario: raw.usuario.trim(),
        desde: raw.desde,
        hasta: raw.hasta,
        limit: PAGE_SIZE,
        offset: this.offset(),
      })
      .subscribe({
        next: (response) => {
          this.logs.set(response.resultados);
          this.total.set(response.total);
          this.loading.set(false);
        },
        error: (error: HttpErrorResponse) => {
          this.loading.set(false);
          this.errorMessage.set(error.error?.error?.message ?? 'No fue posible cargar la bitácora.');
        },
      });
  }

  protected toggleExpanded(id: number): void {
    const next = new Set(this.expandedIds());
    next.has(id) ? next.delete(id) : next.add(id);
    this.expandedIds.set(next);
  }

  protected isExpanded(id: number): boolean {
    return this.expandedIds().has(id);
  }

  protected actionLabel(action: string): string {
    return ACTION_LABELS[action] ?? action;
  }

  protected entityLabel(entity: string): string {
    return ENTITY_LABELS[entity] ?? entity;
  }
}
