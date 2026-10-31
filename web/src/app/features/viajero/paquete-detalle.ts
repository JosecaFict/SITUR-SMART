import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { LucideArrowLeft, LucideCircleAlert, LucideCreditCard, LucidePencil } from '@lucide/angular';
import { apiErrorMessage } from '../../core/http/api-error';
import { CustomPackage, PackageCancellationQuote } from '../../core/packages/packages.models';
import { PackagesService } from '../../core/packages/packages.service';

@Component({
  selector: 'situr-paquete-detalle',
  imports: [DatePipe, RouterLink, LucideArrowLeft, LucideCircleAlert, LucideCreditCard, LucidePencil],
  template: `
    <section class="mx-auto max-w-5xl space-y-6">
      <a routerLink="/paquetes" class="inline-flex items-center gap-2 text-sm font-semibold text-accent-dark hover:underline"><svg lucideArrowLeft class="h-4 w-4"></svg>Mis paquetes</a>
      @if (loading()) { <p class="text-text-secondary">Cargando paquete…</p> }
      @else if (error(); as message) { <p class="rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">{{ message }}</p> }
      @else if (package(); as item) {
        <header class="border-input-border rounded-2xl border bg-white p-6 shadow-sm">
          <span class="rounded-full bg-demo-bg px-3 py-1 text-xs font-bold text-accent-dark">{{ item.estado === 'GUARDADO' ? 'Guardado' : 'Borrador' }}</span>
          <h1 class="font-heading text-title mt-3 text-3xl font-bold">{{ item.nombre }}</h1>
          <p class="text-text-secondary mt-2 text-sm">{{ item.ciudad || 'Varios destinos' }} · {{ item.fecha_inicio | date: 'dd/MM/yyyy' }} – {{ item.fecha_fin | date: 'dd/MM/yyyy' }} · {{ item.personas }} personas</p>
          <div class="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-gray-100 pt-4">
            <p class="font-heading text-accent-dark text-2xl font-bold">{{ item.requiere_revalidacion ? 'Último total calculado' : 'Total estimado' }}: Bs {{ item.total }}</p>
            <a [routerLink]="['/paquetes', item.id, 'editar']" class="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-accent-dark bg-demo-bg px-4 py-2.5 text-sm font-semibold text-accent-dark shadow-sm transition hover:bg-accent-dark hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-dark"><svg lucidePencil class="h-4 w-4"></svg>Editar paquete</a>
          </div>
          <p class="text-text-secondary mt-3 text-xs">Los precios y cupos pueden cambiar. Este paquete no aparta inventario ni genera un pago.</p>
          @if (item.compra) {
            <p class="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm font-semibold text-emerald-800">Compra {{ item.compra.estado.toLowerCase() }} · Bs {{ item.compra.total }} · {{ item.compra.reservas.length }} reservas asociadas.</p>
            @if (item.compra.estado === 'CONFIRMADA' || item.compra.estado === 'REEMBOLSADA') { <button type="button" class="secondary-button mt-3 inline-flex" (click)="downloadReceipt(item.compra.id)">Descargar comprobante PDF</button> }
            @if (item.compra.estado === 'CONFIRMADA') { <button type="button" class="mt-3 ml-2 rounded-xl border border-red-200 px-4 py-2 text-sm font-bold text-red-700" [disabled]="cancelling()" (click)="quoteCancellation(item.compra.id)">Cancelar paquete</button> }
          } @else if (item.estado === 'GUARDADO' && !item.requiere_revalidacion) {
            <section class="mt-5 rounded-xl border border-demo-border bg-demo-bg p-4">
              <label class="flex items-start gap-3 text-sm text-label"><input type="checkbox" class="mt-1" [checked]="accepted()" (change)="accepted.set($any($event.target).checked)" /><span>Acepto las políticas de cancelación de todos los servicios y el total definitivo mostrado antes de pagar.</span></label>
              <div class="mt-3 grid gap-3 sm:grid-cols-2"><input class="field-control" maxlength="180" placeholder="Razón social (opcional)" [value]="billingName()" (input)="billingName.set($any($event.target).value)" /><input class="field-control" maxlength="40" placeholder="NIT (opcional)" [value]="billingTaxId()" (input)="billingTaxId.set($any($event.target).value)" /></div>
              <button type="button" class="btn-accent mt-4 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl px-5 font-bold text-white disabled:opacity-50" [disabled]="!accepted() || purchasing()" (click)="purchase()"><svg lucideCreditCard class="h-5 w-5"></svg>{{ purchasing() ? 'Preparando pago…' : 'Reservar y pagar paquete' }}</button>
            </section>
          }
        </header>
        @if (item.requiere_revalidacion) {
          <div class="flex gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            <svg lucideCircleAlert class="h-5 w-5 shrink-0"></svg><span>Hay servicios que requieren nueva validación de precio o disponibilidad. Abre el editor para revisarlos.</span>
          </div>
        }
        @if (cancellation(); as quote) {
          <section class="rounded-2xl border border-amber-200 bg-amber-50 p-5"><h2 class="font-heading text-lg font-bold">Reembolso del paquete</h2><p class="mt-2 text-sm">Pagado: Bs {{ quote.pagado }} · Penalización: Bs {{ quote.penalizacion }} · Recibirás: <strong>Bs {{ quote.reembolso }}</strong></p>@for (part of quote.componentes; track part.reserva_id) { <p class="mt-2 text-xs">{{ part.empresa }} · {{ part.politica }} · reembolso Bs {{ part.reembolso }}</p> }<textarea class="field-control mt-4" maxlength="1000" placeholder="Motivo de cancelación" [value]="cancelReason()" (input)="cancelReason.set($any($event.target).value)"></textarea><div class="mt-3 flex gap-2"><button class="rounded-xl bg-red-700 px-4 py-2 text-sm font-bold text-white" [disabled]="cancelReason().trim().length < 5 || cancelling()" (click)="confirmCancellation(quote.compra_id)">Confirmar cancelación</button><button class="secondary-button" (click)="cancellation.set(null)">Volver</button></div></section>
        }
        <div class="space-y-3">
          @for (part of item.componentes || []; track part.id) {
            <article class="border-input-border flex flex-col gap-4 rounded-2xl border bg-white p-4 shadow-sm sm:flex-row">
              @if (part.imagen_url) { <img [src]="part.imagen_url" [alt]="part.nombre" class="h-32 w-full rounded-xl object-cover sm:w-40" /> }
              <div class="min-w-0 flex-1">
                <span class="text-accent-dark text-xs font-bold uppercase">{{ part.tipo }}</span>
                <h2 class="font-heading text-title mt-1 font-bold">{{ part.nombre }}</h2>
                <p class="text-text-secondary mt-1 text-sm">{{ part.empresa }} · {{ part.ciudad }}</p>
                <p class="text-text-secondary mt-2 text-sm">{{ part.fecha_inicio | date: 'dd/MM/yyyy' }}@if (part.fecha_fin) { – {{ part.fecha_fin | date: 'dd/MM/yyyy' }} } · {{ part.cantidad }} {{ part.tipo_codigo === 'HABITACION' ? 'habitaciones' : 'personas' }}</p>
                @if (part.hora_inicio) { <p class="text-text-secondary text-sm">Horario: {{ part.hora_inicio }}</p> }
                @if (part.motivo) { <p class="mt-2 text-sm text-red-700">{{ part.motivo }}</p> }
              </div>
              <p class="font-heading text-accent-dark text-lg font-bold">Bs {{ part.total }}</p>
            </article>
          }
        </div>
      }
    </section>
  `,
})
export class PaqueteDetalle implements OnInit {
  private readonly route = inject(ActivatedRoute);
  protected readonly service = inject(PackagesService);
  protected readonly package = signal<CustomPackage | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly accepted = signal(false);
  protected readonly billingName = signal('');
  protected readonly billingTaxId = signal('');
  protected readonly purchasing = signal(false);
  private purchaseKey: string | null = null;
  protected readonly cancellation = signal<PackageCancellationQuote | null>(null);
  protected readonly cancelReason = signal('');
  protected readonly cancelling = signal(false);
  private cancelKey: string | null = null;

  ngOnInit(): void {
    const id = Number(this.route.snapshot.paramMap.get('id'));
    this.service.get(id).subscribe({
      next: (item) => { this.package.set(item); this.loading.set(false); },
      error: (error: HttpErrorResponse) => { this.error.set(apiErrorMessage(error)); this.loading.set(false); },
    });
  }

  protected purchase(): void {
    const item = this.package();
    if (!item || !this.accepted() || this.purchasing()) return;
    this.purchaseKey ??= crypto.randomUUID();
    this.purchasing.set(true);
    const returnUrl = `${location.origin}/paquetes/${item.id}`;
    this.service.purchase(item.id, {
      acepta_politicas: true,
      razon_social_facturacion: this.billingName().trim(),
      nit_facturacion: this.billingTaxId().trim(),
      success_url: `${returnUrl}?pago=exito&compra={ID}`,
      cancel_url: `${returnUrl}?pago=cancelado&compra={ID}`,
    }, this.purchaseKey).subscribe({
      next: (result) => {
        if (result.checkout_url) location.assign(result.checkout_url);
        else { this.purchasing.set(false); this.error.set('No se recibió el enlace seguro de pago.'); }
      },
      error: (error: HttpErrorResponse) => {
        this.purchasing.set(false);
        this.error.set(apiErrorMessage(error, 'No se pudo iniciar el pago del paquete.'));
      },
    });
  }

  protected quoteCancellation(id: number): void {
    this.cancelling.set(true);
    this.service.cancellationQuote(id).subscribe({ next: (quote) => { this.cancellation.set(quote); this.cancelling.set(false); }, error: (error: HttpErrorResponse) => { this.error.set(apiErrorMessage(error)); this.cancelling.set(false); } });
  }

  protected confirmCancellation(id: number): void {
    this.cancelKey ??= crypto.randomUUID(); this.cancelling.set(true);
    this.service.cancelPurchase(id, this.cancelReason().trim(), this.cancelKey).subscribe({ next: () => { this.cancelling.set(false); this.cancellation.set(null); this.ngOnInit(); }, error: (error: HttpErrorResponse) => { this.error.set(apiErrorMessage(error)); this.cancelling.set(false); } });
  }

  protected downloadReceipt(id: number): void {
    this.service.receipt(id).subscribe({ next: (blob) => { const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = `paquete-${id}.pdf`; link.click(); URL.revokeObjectURL(url); }, error: (error: HttpErrorResponse) => this.error.set(apiErrorMessage(error, 'No se pudo descargar el comprobante.')) });
  }
}
