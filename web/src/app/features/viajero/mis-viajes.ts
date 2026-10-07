import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { LucideLuggage } from '@lucide/angular';
import { apiErrorMessage } from '../../core/http/api-error';
import { TravelerBooking } from '../../core/traveler/traveler.models';
import { TravelerService } from '../../core/traveler/traveler.service';

/** Reservas del turista: pendientes de pago, próximas y anteriores. */
@Component({
  selector: 'situr-mis-viajes',
  imports: [DatePipe, RouterLink, LucideLuggage],
  template: `
    <section class="mx-auto max-w-5xl space-y-6">
      <header>
        <p class="text-accent-dark text-xs font-bold tracking-widest uppercase">Mi cuenta</p>
        <h1 class="font-heading text-title mt-1 text-3xl font-bold tracking-tight">Mis viajes</h1>
        <p class="text-text-secondary mt-2 text-sm">Tus reservas, su voucher y el comprobante.</p>
      </header>

      @if (error(); as text) { <p class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{{ text }}</p> }

      @if (loading()) {
        <p class="text-text-secondary text-sm">Cargando tus viajes…</p>
      } @else if (bookings().length === 0) {
        <div class="border-input-border rounded-2xl border border-dashed bg-white px-6 py-16 text-center">
          <svg lucideLuggage class="text-text-secondary mx-auto h-10 w-10"></svg>
          <p class="text-title mt-3 font-semibold">Todavía no tienes viajes</p>
          <p class="text-text-secondary mt-1 text-sm">Reserva una habitación o un tour y aquí verás tu voucher.</p>
          <a routerLink="/" class="btn-accent mt-5 inline-flex min-h-11 items-center rounded-xl px-5 text-sm font-semibold text-white">Explorar</a>
        </div>
      } @else {
        @for (group of groups(); track group.title) {
          @if (group.items.length) {
            <div>
              <h2 class="text-title mb-3 text-lg font-bold">{{ group.title }}</h2>
              <div class="grid gap-3 sm:grid-cols-2">
                @for (booking of group.items; track booking.id) {
                  <a [routerLink]="['/mis-viajes', booking.id]" class="border-input-border flex gap-3 overflow-hidden rounded-2xl border bg-white transition hover:shadow-md">
                    <div class="h-28 w-28 shrink-0 bg-gray-100">
                      @if (booking.producto?.imagen_url; as image) { <img [src]="image" alt="" class="h-full w-full object-cover" /> }
                    </div>
                    <div class="min-w-0 py-3 pr-3">
                      <span class="rounded-full px-2 py-0.5 text-[11px] font-bold" [class]="badge(booking)">{{ booking.estado_nombre }}</span>
                      <p class="text-title mt-1 truncate font-semibold">{{ title(booking) }}</p>
                      <p class="text-text-secondary text-xs">
                        {{ booking.fechas?.inicio | date: 'dd/MM/yyyy' }}@if (booking.fechas?.noches) { → {{ booking.fechas?.fin | date: 'dd/MM/yyyy' }} }
                      </p>
                      <p class="text-text-secondary text-xs font-semibold">{{ booking.codigo }} · {{ booking.moneda_simbolo }} {{ booking.importe.total }}</p>
                    </div>
                  </a>
                }
              </div>
            </div>
          }
        }
      }
    </section>
  `,
})
export class MisViajes implements OnInit {
  private readonly traveler = inject(TravelerService);

  protected readonly bookings = signal<TravelerBooking[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  protected readonly groups = computed(() => {
    const all = this.bookings();
    return [
      { title: 'Pendientes de pago', items: all.filter((b) => b.estado === 'CREADA') },
      {
        title: 'Próximos',
        items: all
          .filter((b) => b.estado === 'CONFIRMADA' || b.estado === 'PAGO_PARCIAL')
          .sort((a, b) => (a.fechas?.inicio ?? '').localeCompare(b.fechas?.inicio ?? '')),
      },
      { title: 'Anteriores', items: all.filter((b) => ['COMPLETADA', 'CANCELADA', 'EXPIRADA_LIBERADA'].includes(b.estado)) },
    ];
  });

  ngOnInit(): void {
    this.traveler.bookings().subscribe({
      next: (bookings) => {
        this.bookings.set(bookings);
        this.loading.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(error, 'No se pudieron cargar tus viajes.'));
      },
    });
  }

  protected title(booking: TravelerBooking): string {
    return booking.producto?.establecimiento ?? booking.producto?.nombre ?? booking.codigo;
  }

  protected badge(booking: TravelerBooking): string {
    if (booking.estado === 'CONFIRMADA' || booking.estado === 'COMPLETADA') return 'bg-demo-bg text-accent-dark';
    if (booking.estado === 'CREADA') return 'bg-amber-100 text-amber-800';
    return 'bg-gray-100 text-text-secondary';
  }
}
