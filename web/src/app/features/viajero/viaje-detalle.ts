import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import QRCode from 'qrcode';
import { LucideArrowLeft, LucideFileText } from '@lucide/angular';
import { apiErrorMessage } from '../../core/http/api-error';
import { CancellationQuote, PaidCancellationResult, TravelerBooking } from '../../core/traveler/traveler.models';
import { TravelerService, newIdempotencyKey } from '../../core/traveler/traveler.service';

/**
 * Una reserva del turista: estado, voucher con QR, comprobante PDF, y pagar o
 * cancelar mientras está pendiente. Stripe vuelve aquí con ?pago=exito|cancelado;
 * mientras el webhook confirma, se consulta sola cada pocos segundos.
 */
@Component({
  selector: 'situr-viaje-detalle',
  imports: [DatePipe, RouterLink, LucideArrowLeft, LucideFileText],
  template: `
    <section class="mx-auto max-w-3xl space-y-5">
      <a routerLink="/mis-viajes" class="text-label inline-flex items-center gap-2 text-sm font-semibold hover:text-title">
        <svg lucideArrowLeft class="h-4 w-4"></svg>Mis viajes
      </a>

      @if (paymentResult() === 'exito' && booking()?.estado !== 'CREADA') {
        <p class="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          Pago realizado. Tu reserva fue confirmada. Te enviamos el comprobante por correo.
        </p>
      } @else if (paymentResult() === 'exito') {
        <p class="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800">Recibimos tu pago. Estamos confirmando tu reserva…</p>
      } @else if (paymentResult() === 'cancelado') {
        <p class="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">El pago no se completó. No se cobró nada.</p>
      }
      @if (error(); as text) { <p class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{{ text }}</p> }

      @if (booking(); as item) {
        <article class="border-input-border rounded-2xl border bg-white p-6 shadow-sm">
          <p class="text-text-secondary font-mono text-xs">{{ item.codigo }} · {{ item.estado_nombre }}</p>
          <h1 class="font-heading text-title mt-1 text-2xl font-bold">{{ item.producto?.establecimiento ?? item.producto?.nombre }}</h1>
          @if (item.producto?.establecimiento) { <p class="text-text-secondary text-sm">{{ item.producto?.nombre }}</p> }
          <dl class="border-input-border mt-4 grid grid-cols-2 gap-3 border-y py-4 text-sm">
            <div><dt class="text-text-secondary text-xs">Fechas</dt><dd class="text-title font-semibold">
              {{ item.fechas?.inicio | date: 'dd/MM/yyyy' }}@if (item.fechas?.noches) { → {{ item.fechas?.fin | date: 'dd/MM/yyyy' }} ({{ item.fechas?.noches }} noches) }
            </dd></div>
            <div><dt class="text-text-secondary text-xs">Cantidad</dt><dd class="text-title font-semibold">{{ item.importe.cantidad }} {{ item.importe.unidad }}</dd></div>
            <div><dt class="text-text-secondary text-xs">Lugar</dt><dd class="text-title font-semibold">{{ item.producto?.localidad ? item.producto?.localidad + ', ' : '' }}{{ item.producto?.ciudad }}</dd></div>
            <div><dt class="text-text-secondary text-xs">Ofrecido por</dt><dd class="text-title font-semibold">{{ item.empresa }}</dd></div>
            <div class="col-span-2"><dt class="text-text-secondary text-xs">{{ item.estado === 'CREADA' ? 'Total' : 'Total pagado' }}</dt>
              <dd class="text-accent-dark text-xl font-bold">{{ item.moneda_simbolo }} {{ item.importe.total }}</dd></div>
          </dl>

          @if (item.estado === 'CREADA') {
            @if (item.vence_en) {
              <p class="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                Tu cupo está apartado hasta las {{ item.vence_en | date: 'HH:mm' }}. Si no pagas antes, se libera.
              </p>
            }
            <div class="mt-4 flex flex-wrap gap-2">
              <button type="button" class="primary-button" [disabled]="working()" (click)="pay()">Pagar ahora</button>
              <button type="button" class="secondary-button" [disabled]="working()" (click)="cancel()">Cancelar reserva</button>
            </div>
          } @else if (item.estado === 'CONFIRMADA' || item.estado === 'PAGO_PARCIAL') {
            <div class="mt-4">
              <button type="button" class="secondary-button" [disabled]="working()" (click)="openPaidCancellation()">
                Consultar cancelación
              </button>
            </div>
          }

          @if (cancellationQuote(); as quote) {
            <section class="mt-5 rounded-2xl border border-amber-200 bg-amber-50/70 p-5" aria-label="Resumen de cancelación">
              <h2 class="text-title font-heading text-lg font-bold">Antes de cancelar</h2>
              <p class="text-text-secondary mt-1 text-sm">Se aplicará la política “{{ quote.politica }}” que aceptaste al reservar.</p>
              <dl class="mt-4 grid gap-3 text-sm sm:grid-cols-3">
                <div><dt class="text-text-secondary">Total pagado</dt><dd class="text-title font-semibold">{{ item.moneda_simbolo }} {{ quote.monto_pagado }}</dd></div>
                <div><dt class="text-text-secondary">Penalización ({{ quote.porcentaje_penalizacion }}%)</dt><dd class="text-title font-semibold">{{ item.moneda_simbolo }} {{ quote.monto_penalizacion }}</dd></div>
                <div><dt class="text-text-secondary">Recibirás</dt><dd class="text-accent-dark text-lg font-bold">{{ item.moneda_simbolo }} {{ quote.monto_reembolso }}</dd></div>
              </dl>
              <label class="text-title mt-4 block text-sm font-semibold" for="cancellation-reason">Motivo <span class="text-text-secondary font-normal">(opcional)</span></label>
              <textarea id="cancellation-reason" rows="2" maxlength="1000" class="field-control mt-1 w-full" [value]="cancellationReason()" (input)="setCancellationReason($event)" placeholder="Cuéntanos por qué cancelas"></textarea>
              <p class="mt-3 text-xs text-amber-900">La reserva se cancelará y el cupo se liberará cuando Stripe confirme la devolución.</p>
              <div class="mt-4 flex flex-wrap gap-2">
                <button type="button" class="primary-button" [disabled]="working()" (click)="confirmPaidCancellation()">Confirmar cancelación</button>
                <button type="button" class="secondary-button" [disabled]="working()" (click)="closePaidCancellation()">Conservar reserva</button>
              </div>
            </section>
          }

          @if (cancellationResult(); as result) {
            <section class="mt-5 rounded-2xl border p-4 text-sm" [class.border-emerald-200]="result.reembolso?.estado === 'COMPLETADO' || !result.reembolso" [class.bg-emerald-50]="result.reembolso?.estado === 'COMPLETADO' || !result.reembolso" [class.border-sky-200]="result.reembolso?.estado === 'PROCESANDO' || result.reembolso?.estado === 'SOLICITADO'" [class.bg-sky-50]="result.reembolso?.estado === 'PROCESANDO' || result.reembolso?.estado === 'SOLICITADO'" [class.border-red-200]="result.reembolso?.estado === 'FALLIDO'" [class.bg-red-50]="result.reembolso?.estado === 'FALLIDO'">
              <p class="text-title font-bold">{{ cancellationStatus(result) }}</p>
              <p class="text-text-secondary mt-1">Monto previsto: {{ item.moneda_simbolo }} {{ result.monto_reembolso }}.</p>
              @if (result.reembolso?.motivo_fallo; as failure) { <p class="mt-2 text-red-700">{{ failure }}</p> }
            </section>
          }

          @if (qrImage(); as image) {
            <div class="bg-demo-bg mt-5 flex flex-col items-center rounded-2xl p-5 text-center">
              <p class="text-title font-semibold">Tu voucher</p>
              <p class="text-text-secondary text-xs">Muéstralo al llegar.</p>
              <img [src]="image" alt="Código QR de la reserva" class="mt-3 h-52 w-52 rounded-lg bg-white p-2" />
              <p class="text-title mt-2 font-mono text-lg font-bold tracking-widest">{{ item.codigo }}</p>
            </div>
            <div class="mt-4 flex flex-wrap gap-2">
              <button type="button" class="secondary-button" [disabled]="working()" (click)="openReceipt()">
                <svg lucideFileText class="h-4 w-4"></svg> Descargar comprobante
              </button>
              <button type="button" class="secondary-button" (click)="print()">Imprimir</button>
            </div>
          }
        </article>
      } @else if (!error()) {
        <p class="text-text-secondary text-sm">Cargando la reserva…</p>
      }
    </section>
  `,
})
export class ViajeDetalle implements OnInit, OnDestroy {
  private readonly route = inject(ActivatedRoute);
  private readonly traveler = inject(TravelerService);

  protected readonly booking = signal<TravelerBooking | null>(null);
  protected readonly qrImage = signal<string | null>(null);
  protected readonly working = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly paymentResult = signal<string | null>(null);
  protected readonly cancellationQuote = signal<CancellationQuote | null>(null);
  protected readonly cancellationResult = signal<PaidCancellationResult | null>(null);
  protected readonly cancellationReason = signal('');
  private cancellationKey: string | null = null;
  private poll: ReturnType<typeof setTimeout> | null = null;
  private id = 0;

  ngOnInit(): void {
    this.id = Number(this.route.snapshot.paramMap.get('id'));
    this.paymentResult.set(this.route.snapshot.queryParamMap.get('pago'));
    this.load();
  }

  ngOnDestroy(): void {
    if (this.poll) clearTimeout(this.poll);
  }

  private load(): void {
    this.traveler.booking(this.id).subscribe({
      next: (booking) => {
        this.booking.set(booking);
        this.error.set(null);
        if (booking.qr) {
          QRCode.toDataURL(booking.qr, { margin: 1, width: 416 }).then((image) => this.qrImage.set(image));
        }
        // Mientras espera el pago, el backend concilia con Stripe en cada consulta.
        if (booking.estado === 'CREADA') {
          this.poll = setTimeout(() => this.load(), this.paymentResult() === 'exito' ? 2000 : 5000);
        }
      },
      error: (error: HttpErrorResponse) => this.error.set(apiErrorMessage(error, 'No se pudo cargar la reserva.')),
    });
  }

  protected pay(): void {
    this.working.set(true);
    this.traveler.pay(this.id).subscribe({
      next: ({ checkout_url }) => window.location.assign(checkout_url),
      error: (error: HttpErrorResponse) => {
        this.working.set(false);
        this.error.set(apiErrorMessage(error, 'No se pudo abrir el pago.'));
      },
    });
  }

  protected cancel(): void {
    if (!confirm('Todavía no pagaste, así que no se cobra nada. ¿Liberar el cupo?')) return;
    this.working.set(true);
    this.traveler.cancel(this.id).subscribe({
      next: (booking) => {
        this.working.set(false);
        this.booking.set(booking);
        if (this.poll) clearTimeout(this.poll);
      },
      error: (error: HttpErrorResponse) => {
        this.working.set(false);
        this.error.set(apiErrorMessage(error, 'No se pudo cancelar.'));
      },
    });
  }

  protected openPaidCancellation(): void {
    this.working.set(true);
    this.error.set(null);
    this.traveler.cancellationQuote(this.id).subscribe({
      next: (quote) => {
        this.working.set(false);
        this.cancellationQuote.set(quote);
      },
      error: (error: HttpErrorResponse) => {
        this.working.set(false);
        this.error.set(apiErrorMessage(error, 'No se pudo calcular la cancelación.'));
      },
    });
  }

  protected closePaidCancellation(): void {
    this.cancellationQuote.set(null);
    this.cancellationReason.set('');
  }

  protected setCancellationReason(event: Event): void {
    this.cancellationReason.set((event.target as HTMLTextAreaElement).value);
  }

  protected confirmPaidCancellation(): void {
    if (!this.cancellationQuote()) return;
    this.cancellationKey ??= newIdempotencyKey();
    this.working.set(true);
    this.error.set(null);
    this.traveler.cancelPaid(this.id, this.cancellationReason().trim(), this.cancellationKey).subscribe({
      next: (result) => {
        this.working.set(false);
        this.cancellationQuote.set(null);
        this.cancellationResult.set(result);
        this.scheduleCancellationPoll(result);
        this.load();
      },
      error: (error: HttpErrorResponse) => {
        this.working.set(false);
        this.error.set(apiErrorMessage(error, 'No se pudo solicitar la cancelación. Puedes reintentar sin duplicar el reembolso.'));
      },
    });
  }

  protected cancellationStatus(result: PaidCancellationResult): string {
    return result.reembolso === null || result.reembolso.estado === 'COMPLETADO'
      ? 'Cancelación y devolución completadas'
      : result.reembolso.estado === 'FALLIDO'
        ? 'La devolución requiere revisión'
        : 'Estamos procesando tu devolución';
  }

  private scheduleCancellationPoll(result: PaidCancellationResult): void {
    if (this.poll) clearTimeout(this.poll);
    if (!result.reembolso || !['SOLICITADO', 'PROCESANDO'].includes(result.reembolso.estado)) return;
    this.poll = setTimeout(() => this.refreshCancellation(), 5000);
  }

  private refreshCancellation(): void {
    if (!this.cancellationKey) return;
    this.traveler.cancelPaid(this.id, this.cancellationReason().trim(), this.cancellationKey).subscribe({
      next: (result) => {
        this.cancellationResult.set(result);
        this.scheduleCancellationPoll(result);
        if (result.reembolso === null || result.reembolso.estado === 'COMPLETADO') this.load();
      },
      error: () => {
        this.poll = setTimeout(() => this.refreshCancellation(), 10000);
      },
    });
  }

  protected openReceipt(): void {
    this.working.set(true);
    this.traveler.receiptUrl(this.id).subscribe({
      next: ({ url }) => {
        this.working.set(false);
        window.open(url, '_blank', 'noopener');
      },
      error: (error: HttpErrorResponse) => {
        this.working.set(false);
        this.error.set(apiErrorMessage(error, 'No se pudo obtener el comprobante.'));
      },
    });
  }

  protected print(): void {
    window.print();
  }
}
