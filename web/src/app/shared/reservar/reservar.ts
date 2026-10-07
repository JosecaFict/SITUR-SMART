import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, input, signal } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { apiErrorMessage } from '../../core/http/api-error';
import { BookingQuote, BookingRequest } from '../../core/traveler/traveler.models';
import { TravelerService, newIdempotencyKey } from '../../core/traveler/traveler.service';
import { VerificarCorreo } from '../verificar-correo/verificar-correo';

function isoDay(date: Date): string {
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/**
 * Reservar desde la web: una habitación (llegada, salida, habitaciones y
 * huéspedes) o un tour/experiencia (día y personas). Cotiza con el backend en
 * cada cambio y abre el pago en Stripe, que vuelve a Mis viajes.
 */
@Component({
  selector: 'situr-reservar',
  imports: [VerificarCorreo],
  template: `
    <div class="border-input-border rounded-2xl border bg-white p-4 shadow-sm">
      <p class="text-title font-heading text-base font-bold">Reservar</p>
      @if (!auth.isAuthenticated()) {
        <p class="text-text-secondary mt-1 text-sm">Inicia sesión o crea tu cuenta para reservar.</p>
        <button type="button" class="btn-accent mt-3 min-h-11 w-full rounded-xl px-4 text-sm font-semibold text-white" (click)="goLogin()">
          Iniciar sesión para reservar
        </button>
      } @else {
        <div class="mt-3 grid gap-3" [class]="isRoom() ? 'sm:grid-cols-2' : ''">
          <label class="flex flex-col gap-1 text-xs font-semibold text-label">{{ isRoom() ? 'Llegada' : 'Fecha' }}
            <input type="date" class="field-control" [min]="today" [value]="start()" (change)="start.set($any($event.target).value); requote()" aria-label="Fecha de inicio" />
          </label>
          @if (isRoom()) {
            <label class="flex flex-col gap-1 text-xs font-semibold text-label">Salida
              <input type="date" class="field-control" [min]="start() || today" [value]="end()" (change)="end.set($any($event.target).value); requote()" aria-label="Fecha de salida" />
            </label>
          }
          <label class="flex flex-col gap-1 text-xs font-semibold text-label">{{ isRoom() ? 'Habitaciones' : 'Personas' }}
            <select class="field-control" [value]="quantity()" (change)="setQuantity(+$any($event.target).value)" aria-label="Cantidad">
              @for (n of quantities(); track n) { <option [value]="n">{{ n }}</option> }
            </select>
          </label>
          @if (isRoom()) {
            <label class="flex flex-col gap-1 text-xs font-semibold text-label">Huéspedes
              <select class="field-control" [value]="guests()" (change)="guests.set(+$any($event.target).value); requote()" aria-label="Huéspedes">
                @for (n of guestOptions(); track n) { <option [value]="n">{{ n }}</option> }
              </select>
            </label>
          }
        </div>

        @if (quoting()) {
          <p class="text-text-secondary mt-3 text-sm">Calculando el precio…</p>
        } @else if (quote(); as current) {
          <div class="bg-demo-bg mt-3 rounded-xl px-3 py-2">
            <p class="text-text-secondary text-xs">Total{{ current.noches ? ' por ' + current.noches + (current.noches === 1 ? ' noche' : ' noches') : '' }}</p>
            <p class="text-accent-dark text-xl font-bold">{{ current.moneda_simbolo }} {{ current.total }}</p>
            @if (!current.disponible) { <p class="text-xs font-semibold text-red-700">No hay cupo para esa fecha y cantidad.</p> }
          </div>
        }
        @if (error(); as text) { <p class="mt-3 text-sm font-semibold text-red-700">{{ text }}</p> }
        @if (needsVerification()) {
          <div class="mt-3"><situr-verificar-correo [sendFirst]="true" (verified)="onVerified()" /></div>
        }
        <button type="button" class="btn-accent mt-3 min-h-11 w-full rounded-xl px-4 text-sm font-semibold text-white disabled:opacity-60"
          [disabled]="!canBook() || booking()" (click)="book()">
          {{ booking() ? 'Abriendo el pago…' : 'Reservar y pagar' }}
        </button>
        <p class="text-text-secondary mt-2 text-xs">Pago seguro con tarjeta en Stripe. Tu cupo queda apartado unos minutos mientras pagas.</p>
      }
    </div>
  `,
})
export class Reservar {
  protected readonly auth = inject(AuthService);
  private readonly traveler = inject(TravelerService);
  private readonly router = inject(Router);

  readonly productId = input.required<number>();
  readonly isRoom = input(false);
  readonly maxQuantity = input(1);
  /** Huéspedes por habitación (solo habitaciones). */
  readonly capacityPerUnit = input(1);

  protected readonly today = isoDay(new Date());
  protected readonly start = signal('');
  protected readonly end = signal('');
  protected readonly quantity = signal(1);
  protected readonly guests = signal(1);
  protected readonly quote = signal<BookingQuote | null>(null);
  protected readonly quoting = signal(false);
  protected readonly booking = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly needsVerification = signal(false);
  private idempotencyKey = newIdempotencyKey();

  protected readonly quantities = computed(() => Array.from({ length: Math.max(1, Math.min(this.maxQuantity(), 20)) }, (_, i) => i + 1));
  protected readonly guestOptions = computed(() => {
    const max = Math.max(this.quantity(), this.quantity() * this.capacityPerUnit());
    return Array.from({ length: max - this.quantity() + 1 }, (_, i) => this.quantity() + i);
  });
  protected readonly canBook = computed(() => !!this.quote()?.disponible && !this.quoting());

  protected goLogin(): void {
    this.router.navigate(['/login'], { queryParams: { returnUrl: this.router.url } });
  }

  protected setQuantity(value: number): void {
    this.quantity.set(value);
    if (this.isRoom()) this.guests.set(Math.min(Math.max(this.guests(), value), value * this.capacityPerUnit()));
    this.requote();
  }

  private request(): BookingRequest | null {
    if (!this.start() || (this.isRoom() && !this.end())) return null;
    return {
      producto_id: this.productId(),
      fecha_inicio: this.start(),
      ...(this.isRoom() ? { fecha_fin: this.end(), huespedes: this.guests() } : {}),
      cantidad: this.quantity(),
    };
  }

  protected requote(): void {
    const request = this.request();
    this.quote.set(null);
    this.error.set(null);
    // Cambió el pedido: es otra reserva para el control de duplicados.
    this.idempotencyKey = newIdempotencyKey();
    if (!request) return;
    this.quoting.set(true);
    this.traveler.quote(request).subscribe({
      next: (quote) => {
        this.quote.set(quote);
        this.quoting.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.quoting.set(false);
        this.error.set(apiErrorMessage(error, 'No se pudo calcular el precio.'));
      },
    });
  }

  protected book(): void {
    const request = this.request();
    if (!request || this.booking()) return;
    this.booking.set(true);
    this.error.set(null);
    this.traveler.book(request, this.idempotencyKey).subscribe({
      next: (booking) => {
        if (booking.checkout_url) {
          window.location.assign(booking.checkout_url);
        } else {
          this.router.navigate(['/mis-viajes', booking.id]);
        }
      },
      error: (error: HttpErrorResponse) => {
        this.booking.set(false);
        if (error.error?.error?.code === 'correo_no_verificado') {
          this.needsVerification.set(true);
          return;
        }
        this.error.set(apiErrorMessage(error, 'No se pudo completar la reserva.'));
      },
    });
  }

  protected onVerified(): void {
    this.needsVerification.set(false);
    this.book();
  }
}
