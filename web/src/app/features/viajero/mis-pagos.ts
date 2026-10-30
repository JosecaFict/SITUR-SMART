import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { apiErrorMessage } from '../../core/http/api-error';
import { PaymentMovement, PaymentsService } from '../../core/payments/payments.service';

@Component({
  selector: 'situr-mis-pagos',
  imports: [DatePipe, RouterLink],
  template: `
    <section class="mx-auto max-w-5xl space-y-6">
      <header><p class="text-accent-dark text-xs font-bold tracking-widest uppercase">Mi cuenta</p><h1 class="font-heading text-title mt-1 text-3xl font-bold">Mis pagos</h1><p class="text-text-secondary mt-2 text-sm">Cobros y devoluciones de tus reservas.</p></header>
      @if (error(); as text) { <p class="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{{ text }}</p> }
      @if (loading()) { <p class="text-text-secondary">Cargando movimientos…</p> }
      @else if (!payments().length) { <div class="border-input-border rounded-2xl border border-dashed bg-white p-12 text-center"><p class="text-title font-semibold">Todavía no tienes pagos</p><p class="text-text-secondary mt-1 text-sm">Cuando pagues una reserva aparecerá aquí.</p></div> }
      @else {
        <div class="space-y-3">
          @for (payment of payments(); track payment.id) {
            <article class="border-input-border rounded-2xl border bg-white p-5 shadow-sm">
              <div class="flex flex-wrap items-start justify-between gap-3">
                <div><p class="text-text-secondary text-xs">{{ payment.processed_at ?? payment.created_at | date: 'dd/MM/yyyy HH:mm' }} · {{ payment.reserva }}</p><h2 class="text-title font-bold">{{ payment.producto?.nombre ?? 'Reserva turística' }}</h2><p class="text-text-secondary text-sm">{{ payment.empresa }} · {{ method(payment.method) }}</p></div>
                <div class="text-right"><p class="text-accent-dark text-xl font-bold">{{ payment.simbolo }} {{ payment.amount }}</p><span class="rounded-full px-2 py-1 text-xs font-bold" [class]="badge(payment.status)">{{ state(payment.status) }}</span></div>
              </div>
              @if (payment.reembolsos.length) {
                <div class="border-input-border mt-4 border-t pt-3">
                  @for (refund of payment.reembolsos; track refund.id) { <p class="text-sm"><span class="font-semibold">Reembolso {{ state(refund.estado) }}:</span> {{ payment.simbolo }} {{ refund.monto }} <span class="text-text-secondary">· {{ refund.procesado_en ?? refund.solicitado_en | date: 'dd/MM/yyyy HH:mm' }}</span></p> }
                </div>
              }
              <a [routerLink]="['/mis-viajes', payment.reserva_id]" class="text-accent-dark mt-4 inline-flex text-sm font-semibold hover:underline">Ver reserva →</a>
            </article>
          }
        </div>
      }
    </section>
  `,
})
export class MisPagos implements OnInit {
  private readonly service = inject(PaymentsService);
  protected readonly payments = signal<PaymentMovement[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.service.mine().subscribe({
      next: (page) => { this.payments.set(page.results); this.loading.set(false); },
      error: (error: HttpErrorResponse) => { this.loading.set(false); this.error.set(apiErrorMessage(error, 'No se pudieron cargar tus pagos.')); },
    });
  }
  protected state(value: string): string { return ({ APROBADO: 'Aprobado', PENDIENTE: 'Pendiente', ANULADO: 'Anulado', RECHAZADO: 'Rechazado', COMPLETADO: 'completado', PROCESANDO: 'procesando', SOLICITADO: 'solicitado', FALLIDO: 'fallido' } as Record<string, string>)[value] ?? value; }
  protected method(value: string): string { return ({ TARJETA: 'Tarjeta', EFECTIVO: 'Efectivo', QR: 'QR', TRANSFERENCIA: 'Transferencia' } as Record<string, string>)[value] ?? value; }
  protected badge(value: string): string { return value === 'APROBADO' ? 'bg-emerald-100 text-emerald-800' : value === 'PENDIENTE' ? 'bg-amber-100 text-amber-800' : 'bg-gray-100 text-text-secondary'; }
}
