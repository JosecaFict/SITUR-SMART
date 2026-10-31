import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { LucideArrowLeft, LucideCircleAlert, LucideCreditCard, LucidePencil } from '@lucide/angular';
import { apiErrorMessage } from '../../core/http/api-error';
import { CustomPackage } from '../../core/packages/packages.models';
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
  private readonly service = inject(PackagesService);
  protected readonly package = signal<CustomPackage | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly accepted = signal(false);
  protected readonly billingName = signal('');
  protected readonly billingTaxId = signal('');
  protected readonly purchasing = signal(false);
  private purchaseKey: string | null = null;

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
}
