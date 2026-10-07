import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { LucideCalendarCheck, LucideFileText, LucideFlag, LucideScanLine, LucideSearch, LucideX } from '@lucide/angular';
import { AuthService } from '../../../core/auth/auth.service';
import { CompaniesService } from '../../../core/companies/companies.service';
import {
  CompanyBooking,
  CompanyBookingPage,
  CompanyBookingsService,
  VoucherCheck,
} from '../../../core/company-bookings/company-bookings.service';
import { apiErrorMessage } from '../../../core/http/api-error';

const STATES: Record<string, string> = {
  CREADA: 'Pendiente de pago',
  PAGO_PARCIAL: 'Pago parcial',
  CONFIRMADA: 'Confirmada',
  COMPLETADA: 'Completada',
  CANCELADA: 'Cancelada',
  EXPIRADA_LIBERADA: 'Vencida',
};

/**
 * Reservas que recibe la empresa: quién reservó, para cuándo y si pagó.
 * Desde aquí se valida el voucher cuando el cliente llega y se reporta a un
 * cliente a la plataforma (que es quien decide si lo bloquea).
 */
@Component({
  selector: 'situr-reservas',
  imports: [DatePipe, LucideCalendarCheck, LucideFileText, LucideFlag, LucideScanLine, LucideSearch, LucideX],
  templateUrl: './reservas.html',
})
export class Reservas implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly companiesService = inject(CompaniesService);
  private readonly service = inject(CompanyBookingsService);

  protected readonly isSuperAdmin = computed(() => this.auth.session()?.user.roles.includes('SUPER_ADMIN') ?? false);
  protected readonly canManage = computed(() => {
    const user = this.auth.session()?.user;
    return !!user && (user.roles.includes('SUPER_ADMIN') || user.permisos.includes('RESERVAS_GESTIONAR'));
  });
  protected readonly companies = signal<{ id: number; name: string }[]>([]);
  protected readonly tenantId = signal<number | null>(null);

  protected readonly page = signal<CompanyBookingPage | null>(null);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly filters = signal({ buscar: '', estado: '', desde: '', hasta: '', llegadas: '' });
  protected readonly pageNumber = signal(1);

  protected readonly voucherCode = signal('');
  protected readonly voucher = signal<VoucherCheck | null>(null);
  protected readonly voucherError = signal<string | null>(null);
  protected readonly checking = signal(false);

  protected readonly selected = signal<CompanyBooking | null>(null);
  protected readonly reporting = signal(false);
  protected readonly reportReason = signal('');
  protected readonly working = signal(false);
  protected readonly message = signal<string | null>(null);
  protected readonly detailError = signal<string | null>(null);

  ngOnInit(): void {
    if (this.isSuperAdmin()) {
      this.companiesService.list().subscribe({
        next: (list) => this.companies.set(list.map((company) => ({ id: company.id, name: company.nombre_comercial }))),
        error: () => this.companies.set([]),
      });
      return;
    }
    const tenant = this.auth.session()?.user.tenants[0];
    if (!tenant) {
      this.error.set('Tu cuenta no tiene una empresa asignada.');
      return;
    }
    this.tenantId.set(tenant.id);
    this.load();
  }

  protected chooseCompany(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.tenantId.set(value ? Number(value) : null);
    this.closeDetail();
    this.voucher.set(null);
    if (value) this.load();
  }

  protected load(page = 1): void {
    const tenantId = this.tenantId();
    if (tenantId === null) return;
    this.loading.set(true);
    this.error.set(null);
    this.pageNumber.set(page);
    this.service.list(tenantId, { ...this.filters(), page }).subscribe({
      next: (result) => {
        this.page.set(result);
        this.loading.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(error, 'No se pudieron cargar las reservas.'));
      },
    });
  }

  protected setFilter(key: 'buscar' | 'estado' | 'desde' | 'hasta', event: Event): void {
    const value = (event.target as HTMLInputElement | HTMLSelectElement).value;
    this.filters.update((current) => ({ ...current, [key]: value, llegadas: '' }));
    if (key !== 'buscar') this.load();
  }

  protected arrivalsToday(): void {
    this.filters.set({ buscar: '', estado: '', desde: '', hasta: '', llegadas: 'hoy' });
    this.load();
  }

  protected clearFilters(): void {
    this.filters.set({ buscar: '', estado: '', desde: '', hasta: '', llegadas: '' });
    this.load();
  }

  // --- Validar voucher -------------------------------------------------------

  protected updateVoucher(event: Event): void {
    this.voucherCode.set((event.target as HTMLInputElement).value);
  }

  protected checkVoucher(): void {
    const tenantId = this.tenantId();
    const code = this.voucherCode().trim();
    if (tenantId === null || !code || this.checking()) return;
    this.checking.set(true);
    this.voucher.set(null);
    this.voucherError.set(null);
    this.service.check(tenantId, code).subscribe({
      next: (result) => {
        this.voucher.set(result);
        this.checking.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.checking.set(false);
        this.voucherError.set(apiErrorMessage(error, 'No se pudo validar el código.'));
      },
    });
  }

  protected checkIn(booking: CompanyBooking): void {
    const tenantId = this.tenantId();
    if (tenantId === null || this.working()) return;
    this.working.set(true);
    this.service.checkIn(tenantId, booking.id).subscribe({
      next: (updated) => {
        this.working.set(false);
        this.voucher.set(null);
        this.voucherCode.set('');
        this.selected.set(updated);
        this.message.set(`Llegada de ${updated.cliente.nombre} registrada.`);
        this.load(this.pageNumber());
      },
      error: (error: HttpErrorResponse) => {
        this.working.set(false);
        this.voucherError.set(apiErrorMessage(error, 'No se pudo marcar la llegada.'));
      },
    });
  }

  // --- Detalle ---------------------------------------------------------------

  protected open(booking: CompanyBooking): void {
    this.selected.set(booking);
    this.reporting.set(false);
    this.message.set(null);
    this.detailError.set(null);
  }

  protected closeDetail(): void {
    this.selected.set(null);
    this.reporting.set(false);
  }

  protected updateReason(event: Event): void {
    this.reportReason.set((event.target as HTMLTextAreaElement).value);
  }

  protected sendReport(): void {
    const tenantId = this.tenantId();
    const booking = this.selected();
    const reason = this.reportReason().trim();
    if (tenantId === null || !booking || this.working()) return;
    if (reason.length < 5) {
      this.detailError.set('Explica el problema (al menos 5 caracteres).');
      return;
    }
    this.working.set(true);
    this.service.report(tenantId, booking.id, reason).subscribe({
      next: ({ detail }) => {
        this.working.set(false);
        this.reporting.set(false);
        this.reportReason.set('');
        this.detailError.set(null);
        this.message.set(detail);
      },
      error: (error: HttpErrorResponse) => {
        this.working.set(false);
        this.detailError.set(apiErrorMessage(error, 'No se pudo enviar el reporte.'));
      },
    });
  }

  protected stateLabel(state: string): string {
    return STATES[state] ?? state;
  }

  protected place(booking: CompanyBooking): string {
    const product = booking.producto;
    if (!product) return booking.codigo;
    return product.establecimiento ? `${product.establecimiento} · ${product.nombre}` : product.nombre;
  }

  protected pages(): number {
    const result = this.page();
    return result ? Math.max(1, Math.ceil(result.count / 20)) : 1;
  }

  protected income(): string {
    const values = this.page()?.resumen.ingresos_mes ?? [];
    return values.length ? values.map((value) => `${value.moneda} ${value.total}`).join(' · ') : '—';
  }
}
