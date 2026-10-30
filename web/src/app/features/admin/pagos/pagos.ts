import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { AuthService } from '../../../core/auth/auth.service';
import { CompaniesService } from '../../../core/companies/companies.service';
import { apiErrorMessage } from '../../../core/http/api-error';
import { PaymentPage, PaymentsService } from '../../../core/payments/payments.service';

@Component({
  selector: 'situr-pagos', imports: [DatePipe],
  template: `
    <section class="space-y-6">
      <header><p class="text-accent-dark text-xs font-bold tracking-widest uppercase">Finanzas</p><h1 class="font-heading text-title mt-1 text-3xl font-bold">Pagos de la empresa</h1><p class="text-text-secondary mt-2 text-sm">Cobros, devoluciones y monto neto registrado.</p></header>
      @if (isSuperAdmin()) { <select class="field-control max-w-sm" [value]="tenantId() ?? ''" (change)="chooseCompany($event)"><option value="">Selecciona una empresa</option>@for (company of companies(); track company.id) { <option [value]="company.id">{{ company.name }}</option> }</select> }
      @if (error(); as text) { <p class="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{{ text }}</p> }
      @if (page()?.resumen; as summaries) { <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">@for (summary of summaries; track summary.moneda) { <div class="border-input-border rounded-2xl border bg-white p-4"><p class="text-text-secondary text-xs">Cobrado ({{ summary.moneda }})</p><p class="text-title text-2xl font-bold">{{ summary.simbolo }} {{ summary.cobrado }}</p><p class="text-text-secondary mt-2 text-xs">Reembolsado: {{ summary.simbolo }} {{ summary.reembolsado }}</p><p class="text-accent-dark text-sm font-bold">Neto: {{ summary.simbolo }} {{ summary.neto }}</p></div> }</div> }
      @if (tenantId()) {
        <div class="border-input-border grid gap-3 rounded-2xl border bg-white p-4 sm:grid-cols-5"><input class="field-control sm:col-span-2" placeholder="Reserva, cliente o correo" [value]="filters().buscar" (input)="setFilter('buscar', $event)" (keyup.enter)="load()"><select class="field-control" [value]="filters().estado" (change)="setFilter('estado', $event); load()"><option value="">Todos los estados</option><option value="APROBADO">Aprobados</option><option value="PENDIENTE">Pendientes</option><option value="ANULADO">Anulados</option></select><input type="date" class="field-control" [value]="filters().desde" (change)="setFilter('desde', $event); load()"><input type="date" class="field-control" [value]="filters().hasta" (change)="setFilter('hasta', $event); load()"></div>
      }
      @if (loading()) { <p class="text-text-secondary">Cargando movimientos…</p> }
      @else if (page(); as current) { <div class="border-input-border overflow-x-auto rounded-2xl border bg-white"><table class="w-full min-w-[850px] text-left text-sm"><thead class="bg-gray-50 text-xs uppercase text-text-secondary"><tr><th class="p-4">Fecha</th><th class="p-4">Cliente</th><th class="p-4">Reserva / producto</th><th class="p-4">Método</th><th class="p-4">Estado</th><th class="p-4 text-right">Cobrado</th><th class="p-4 text-right">Reembolsado</th></tr></thead><tbody>@for (payment of current.results; track payment.id) { <tr class="border-input-border border-t"><td class="p-4">{{ payment.processed_at ?? payment.created_at | date: 'dd/MM/yyyy HH:mm' }}</td><td class="p-4"><p class="font-semibold">{{ payment.cliente.nombre }}</p><p class="text-text-secondary text-xs">{{ payment.cliente.email }}</p></td><td class="p-4"><p class="font-semibold">{{ payment.reserva }}</p><p class="text-text-secondary text-xs">{{ payment.producto?.nombre ?? '—' }}</p></td><td class="p-4">{{ payment.method }}</td><td class="p-4">{{ payment.status }}</td><td class="p-4 text-right font-semibold">{{ payment.simbolo }} {{ payment.amount }}</td><td class="p-4 text-right">{{ payment.simbolo }} {{ refunded(payment.reembolsos) }}</td></tr> } @empty { <tr><td colspan="7" class="p-12 text-center text-text-secondary">No hay movimientos con estos filtros.</td></tr> }</tbody></table></div> }
    </section>
  `,
})
export class Pagos implements OnInit {
  private readonly auth = inject(AuthService); private readonly companiesService = inject(CompaniesService); private readonly service = inject(PaymentsService);
  protected readonly isSuperAdmin = computed(() => this.auth.session()?.user.roles.includes('SUPER_ADMIN') ?? false);
  protected readonly companies = signal<{ id: number; name: string }[]>([]); protected readonly tenantId = signal<number | null>(null); protected readonly page = signal<PaymentPage | null>(null); protected readonly loading = signal(false); protected readonly error = signal<string | null>(null); protected readonly filters = signal({ buscar: '', estado: '', desde: '', hasta: '' });
  ngOnInit(): void { if (this.isSuperAdmin()) { this.companiesService.list().subscribe({ next: (items) => this.companies.set(items.map((item) => ({ id: item.id, name: item.nombre_comercial }))), error: () => this.companies.set([]) }); } else { const tenant = this.auth.session()?.user.tenants[0]; if (tenant) { this.tenantId.set(tenant.id); this.load(); } else this.error.set('Tu cuenta no tiene una empresa asignada.'); } }
  protected chooseCompany(event: Event): void { const value = (event.target as HTMLSelectElement).value; this.tenantId.set(value ? Number(value) : null); this.page.set(null); if (value) this.load(); }
  protected setFilter(key: 'buscar' | 'estado' | 'desde' | 'hasta', event: Event): void { const value = (event.target as HTMLInputElement | HTMLSelectElement).value; this.filters.update((current) => ({ ...current, [key]: value })); }
  protected load(): void { const tenant = this.tenantId(); if (!tenant) return; this.loading.set(true); this.service.company(tenant, this.filters()).subscribe({ next: (page) => { this.page.set(page); this.loading.set(false); }, error: (error: HttpErrorResponse) => { this.loading.set(false); this.error.set(apiErrorMessage(error, 'No se pudieron cargar los pagos.')); } }); }
  protected refunded(items: PaymentPage['results'][number]['reembolsos']): string { return items.filter((item) => item.estado === 'COMPLETADO').reduce((sum, item) => sum + Number(item.monto), 0).toFixed(2); }
}
