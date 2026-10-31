import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, inject, input, signal, untracked } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { apiErrorMessage } from '../../core/http/api-error';
import { addCalendarDays, boliviaToday, calendarLabel } from '../../core/products/departure-dates';
import { ProductDeparture } from '../../core/products/products.models';
import { ProductsService } from '../../core/products/products.service';
import { BookingQuote, BookingRequest } from '../../core/traveler/traveler.models';
import { TravelerService, newIdempotencyKey } from '../../core/traveler/traveler.service';
import { VerificarCorreo } from '../verificar-correo/verificar-correo';

/**
 * Reservar desde la web: una habitación (llegada, salida, habitaciones y
 * huéspedes) o un tour/experiencia (día y personas). Cotiza con el backend en
 * cada cambio y abre el pago en Stripe, que vuelve a Mis viajes.
 */
@Component({
  selector: 'situr-reservar',
  imports: [VerificarCorreo],
  styles: [`
    .field-control {
      min-height: 2.75rem;
      width: 100%;
      border: 1px solid var(--color-input-border);
      border-radius: 0.75rem;
      background: white;
      padding: 0.65rem 0.8rem;
      color: var(--color-label);
      font-size: 0.875rem;
      outline: none;
      transition: border-color 180ms ease, box-shadow 180ms ease;
    }
    .field-control:focus-visible {
      border-color: var(--color-accent-dark);
      box-shadow: 0 0 0 3px rgba(45, 212, 191, 0.2);
    }
  `],
  template: `
    <div class="border-input-border rounded-2xl border bg-white p-4 shadow-sm">
      <p class="text-title font-heading text-base font-bold">Reservar</p>
      @if (isScheduledProduct()) {
        <div class="mt-4">
          <p class="text-xs font-semibold text-label">Elige una fecha</p>
          <div class="mt-2 flex gap-2 overflow-x-auto pb-2" aria-label="Fechas disponibles">
            @for (day of dateCards(); track day) {
              <button type="button" (click)="selectDate(day)" [attr.aria-pressed]="start() === day"
                class="min-h-16 min-w-16 shrink-0 rounded-xl border px-2 py-1 text-center text-xs font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-dark"
                [class]="start() === day ? 'border-accent-dark bg-demo-bg text-accent-dark shadow-sm' : 'border-input-border bg-white text-label hover:border-accent hover:bg-demo-bg'">
                <span class="block capitalize">{{ dayLabel(day, 'weekday') }}</span>
                <span class="block text-lg font-bold">{{ dayLabel(day, 'day') }}</span>
                <span class="block capitalize">{{ dayLabel(day, 'month') }}</span>
              </button>
            }
          </div>
          <label class="mt-2 flex items-center gap-2 text-xs font-semibold text-label">Más fechas
            <input type="date" class="field-control min-w-0 flex-1" [min]="today" [max]="lastBookableDay" [value]="start()"
              (change)="selectDate($any($event.target).value)" aria-label="Elegir otra fecha" />
          </label>
          @if (start()) {
            <div class="mt-3" aria-live="polite">
              <p class="text-xs font-semibold text-label">{{ dateHeading() }}</p>
              @if (loadingDepartures() || checkingDaily()) {
                <p class="mt-2 text-sm text-text-secondary">Consultando disponibilidad…</p>
              } @else if (departures().length) {
                <div class="mt-2 flex flex-wrap gap-2" aria-label="Horarios disponibles">
                  @for (departure of departures(); track departure.id) {
                    <button type="button" (click)="selectDeparture(departure)" [disabled]="!departureAvailable(departure)"
                      [attr.aria-pressed]="selectedDeparture()?.id === departure.id"
                      class="rounded-full border px-3 py-2 text-xs font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-dark disabled:cursor-not-allowed disabled:opacity-50"
                      [class]="selectedDeparture()?.id === departure.id ? 'border-accent-dark bg-accent-dark text-white' : 'border-input-border bg-white text-label hover:border-accent hover:bg-demo-bg'">
                      {{ departure.hora_inicio }}–{{ departure.hora_fin }}
                      <span class="block text-[11px]">{{ departure.cerrado ? 'Cerrada' : departure.cupos_restantes === 0 ? 'Agotada' : departure.cupos_restantes < quantity() ? 'Cupos insuficientes' : departure.cupos_restantes + ' cupos' }}</span>
                    </button>
                  }
                </div>
                @if (!selectedDeparture()) { <p class="mt-2 text-xs text-text-secondary">Selecciona un horario para continuar.</p> }
              } @else if (dailyAvailable()) {
                <p class="bg-demo-bg mt-2 rounded-xl px-3 py-2 text-sm text-accent-dark">Disponibilidad por día, sin horario específico. La reserva será para {{ dateHeading() }}.</p>
              } @else if (!error()) {
                <p class="mt-2 text-sm text-text-secondary">{{ auth.isAuthenticated() ? 'No hay salidas disponibles para esta fecha y cantidad. Prueba otra fecha.' : 'Inicia sesión para comprobar la disponibilidad por día.' }}</p>
              }
            </div>
          }
        </div>
      }
      @if (!auth.isAuthenticated()) {
        <p class="text-text-secondary mt-1 text-sm">Inicia sesión o crea tu cuenta para reservar.</p>
        <button type="button" class="btn-accent mt-3 min-h-11 w-full rounded-xl px-4 text-sm font-semibold text-white" (click)="goLogin()">
          Iniciar sesión para reservar
        </button>
      } @else {
        <div class="mt-3 grid gap-3" [class]="isRoom() ? 'sm:grid-cols-2' : ''">
          @if (!isScheduledProduct()) {
          <label class="flex flex-col gap-1 text-xs font-semibold text-label">{{ isRoom() ? 'Llegada' : 'Fecha' }}
            <input type="date" class="field-control" [min]="today" [value]="start()" (change)="start.set($any($event.target).value); requote()" aria-label="Fecha de inicio" />
          </label>
          }
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
            @if (current.promocion; as discount) { <div class="mt-1 text-xs text-label"><span class="line-through">Original: {{ current.moneda_simbolo }} {{ discount.total_original }}</span><span class="ml-2 font-semibold text-accent-dark">{{ discount.porcentaje_descuento }} % de descuento · Ahorro {{ current.moneda_simbolo }} {{ discount.descuento_total }}</span></div> }
            <p class="text-accent-dark text-xl font-bold">{{ current.moneda_simbolo }} {{ current.total }}</p>
            @if (!current.disponible) { <p class="text-xs font-semibold text-red-700">No hay cupo para esa fecha y cantidad.</p> }
          </div>
        }
        @if (error(); as text) { <p class="mt-3 text-sm font-semibold text-red-700">{{ text }}</p> }
        @if (pendingBookingId(); as id) { <button type="button" class="mt-2 text-sm font-semibold text-accent-dark underline" (click)="openPendingBooking(id)">Revisar la reserva {{ id }} antes de pagar</button> }
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
  private readonly products = inject(ProductsService);
  private readonly router = inject(Router);

  readonly productId = input.required<number>();
  readonly promotionId = input<number | null>(null);
  readonly isRoom = input(false);
  readonly isScheduledProduct = input(false);
  readonly maxQuantity = input(1);
  /** Huéspedes por habitación (solo habitaciones). */
  readonly capacityPerUnit = input(1);

  protected readonly today = boliviaToday();
  protected readonly lastBookableDay = addCalendarDays(this.today, 365);
  protected readonly cardStart = signal(this.today);
  protected readonly dateCards = computed(() => Array.from({ length: 7 }, (_, i) => addCalendarDays(this.cardStart(), i)));
  protected readonly departures = signal<ProductDeparture[]>([]);
  protected readonly selectedDeparture = signal<ProductDeparture | null>(null);
  protected readonly loadingDepartures = signal(false);
  protected readonly checkingDaily = signal(false);
  protected readonly dailyAvailable = signal(false);
  protected readonly start = signal('');
  protected readonly end = signal('');
  protected readonly quantity = signal(1);
  protected readonly guests = signal(1);
  protected readonly quote = signal<BookingQuote | null>(null);
  protected readonly quoting = signal(false);
  protected readonly booking = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly needsVerification = signal(false);
  protected readonly pendingBookingId = signal<number | null>(null);
  private idempotencyKey = newIdempotencyKey();
  private departureVersion = 0;
  private quoteVersion = 0;

  constructor() {
    effect(() => {
      this.promotionId();
      untracked(() => { if (this.start()) this.requote(); });
    });
  }

  protected readonly quantities = computed(() => Array.from({ length: Math.max(1, Math.min(this.maxQuantity(), 20)) }, (_, i) => i + 1));
  protected readonly guestOptions = computed(() => {
    const max = Math.max(this.quantity(), this.quantity() * this.capacityPerUnit());
    return Array.from({ length: max - this.quantity() + 1 }, (_, i) => this.quantity() + i);
  });
  protected readonly canBook = computed(() => {
    const quote = this.quote();
    if (!quote?.disponible || this.quoting() || this.loadingDepartures() || this.checkingDaily()) return false;
    if (this.promotionId() !== null && quote.promocion?.id !== this.promotionId()) return false;
    if (!this.isScheduledProduct()) return true;
    const selected = this.selectedDeparture();
    return selected
      ? quote.salida_id === selected.id && this.departureAvailable(selected)
      : this.dailyAvailable() && quote.salida_id === null;
  });

  protected dayLabel(day: string, part: 'weekday' | 'day' | 'month'): string {
    return calendarLabel(day, { [part]: part === 'day' ? 'numeric' : 'short' });
  }

  protected dateHeading(): string {
    return calendarLabel(this.start(), { weekday: 'long', day: 'numeric', month: 'long' });
  }

  protected departureAvailable(departure: ProductDeparture): boolean {
    return !departure.cerrado && departure.cupos_restantes >= this.quantity() && Date.parse(departure.inicio) > Date.now();
  }

  protected selectDate(day: string): void {
    if (this.booking()) return;
    if (!day || day < this.today || day > this.lastBookableDay) {
      this.error.set('Elige una fecha válida desde hoy hasta un año adelante.');
      return;
    }
    this.start.set(day);
    this.cardStart.set(day);
    this.selectedDeparture.set(null);
    this.loadDepartures();
  }

  protected selectDeparture(departure: ProductDeparture): void {
    if (this.booking()) return;
    if (!this.departureAvailable(departure)) return;
    this.selectedDeparture.set(departure);
    this.dailyAvailable.set(false);
    if (this.auth.isAuthenticated()) this.requote();
  }

  private loadDepartures(keepError = false): void {
    const day = this.start();
    if (!day) return;
    const version = ++this.departureVersion;
    ++this.quoteVersion;
    this.quote.set(null);
    this.quoting.set(false);
    this.dailyAvailable.set(false);
    this.checkingDaily.set(false);
    this.loadingDepartures.set(true);
    if (!keepError) this.error.set(null);
    this.idempotencyKey = newIdempotencyKey();
    this.products.publicDepartures(this.productId(), day).subscribe({
      next: (items) => {
        if (version !== this.departureVersion) return;
        this.loadingDepartures.set(false);
        this.departures.set(items);
        const previous = this.selectedDeparture();
        const current = items.find((item) => item.id === previous?.id);
        if (current && this.departureAvailable(current)) {
          this.selectedDeparture.set(current);
          this.requote(keepError);
        } else {
          this.selectedDeparture.set(null);
          if (!items.length && this.auth.isAuthenticated()) this.checkDaily(version);
          else if (previous && !keepError) this.error.set('El horario dejó de estar disponible. Elige otro.');
        }
      },
      error: (error: HttpErrorResponse) => {
        if (version !== this.departureVersion) return;
        this.loadingDepartures.set(false);
        this.departures.set([]);
        this.selectedDeparture.set(null);
        this.error.set(apiErrorMessage(error, 'No se pudieron consultar los horarios.'));
      },
    });
  }

  private checkDaily(version: number): void {
    const request = this.baseRequest();
    if (!request) return;
    this.checkingDaily.set(true);
    this.traveler.quote(request).subscribe({
      next: (quote) => {
        if (version !== this.departureVersion) return;
        this.checkingDaily.set(false);
        // El endpoint público omite salidas cerradas/agotadas. Nunca tratarlas como día libre.
        if (quote.salida_id === null) {
          this.dailyAvailable.set(true);
          this.quote.set(quote);
        }
      },
      error: (error: HttpErrorResponse) => {
        if (version !== this.departureVersion) return;
        this.checkingDaily.set(false);
        this.error.set(apiErrorMessage(error, 'No se pudo confirmar la disponibilidad del día.'));
      },
    });
  }

  protected goLogin(): void {
    this.router.navigate(['/login'], { queryParams: { returnUrl: this.router.url } });
  }

  protected setQuantity(value: number): void {
    if (this.booking()) return;
    this.quantity.set(value);
    if (this.isRoom()) this.guests.set(Math.min(Math.max(this.guests(), value), value * this.capacityPerUnit()));
    if (this.isScheduledProduct()) this.loadDepartures();
    else this.requote();
  }

  private baseRequest(): BookingRequest | null {
    if (!this.start() || (this.isRoom() && !this.end())) return null;
    const promotionId = this.promotionId() ?? this.quote()?.promocion?.id;
    return {
      producto_id: this.productId(),
      fecha_inicio: this.start(),
      ...(this.isRoom() ? { fecha_fin: this.end(), huespedes: this.guests() } : {}),
      cantidad: this.quantity(),
      ...(promotionId ? { promocion_id: promotionId } : {}),
    };
  }

  private request(): BookingRequest | null {
    const request = this.baseRequest();
    if (!request || !this.isScheduledProduct()) return request;
    const selected = this.selectedDeparture();
    if (selected) return { ...request, salida_id: selected.id };
    return this.dailyAvailable() ? request : null;
  }

  protected requote(keepError = false): void {
    const request = this.request();
    const version = ++this.quoteVersion;
    this.quote.set(null);
    this.pendingBookingId.set(null);
    if (!keepError) this.error.set(null);
    // Cambió el pedido: es otra reserva para el control de duplicados.
    this.idempotencyKey = newIdempotencyKey();
    if (!request) { this.quoting.set(false); return; }
    this.quoting.set(true);
    this.traveler.quote(request).subscribe({
      next: (quote) => {
        if (version !== this.quoteVersion) return;
        if (this.promotionId() !== null && quote.promocion?.id !== this.promotionId()) {
          this.quoting.set(false);
          this.error.set('La promoción ya no está disponible. Actualiza la ficha y solicita una nueva cotización.');
          return;
        }
        if (this.isScheduledProduct() && quote.salida_id !== this.selectedDeparture()?.id) {
          this.quoting.set(false);
          this.selectedDeparture.set(null);
          this.error.set('El horario cambió. Elige uno disponible de nuevo.');
          this.loadDepartures(true);
          return;
        }
        this.quote.set(quote);
        this.quoting.set(false);
        if (this.isScheduledProduct() && !quote.disponible) {
          this.error.set('El horario ya no tiene cupos suficientes. Elige otro.');
          this.selectedDeparture.set(null);
          this.loadDepartures(true);
        }
      },
      error: (error: HttpErrorResponse) => {
        if (version !== this.quoteVersion) return;
        this.quoting.set(false);
        this.error.set(apiErrorMessage(error, 'No se pudo calcular el precio.'));
      },
    });
  }

  protected book(): void {
    const request = this.request();
    if (!request || !this.canBook() || this.booking()) return;
    this.booking.set(true);
    this.error.set(null);
    if (this.isScheduledProduct() || request.promocion_id) {
      const selectionVersion = this.departureVersion;
      const shownTotal = this.quote()?.total;
      this.traveler.quote(request).subscribe({
        next: (quote) => {
          const current = this.request();
          if (selectionVersion !== this.departureVersion || !current ||
              current.fecha_inicio !== request.fecha_inicio || current.cantidad !== request.cantidad ||
              current.salida_id !== request.salida_id) {
            this.booking.set(false);
            return;
          }
          if (!quote.disponible || (this.isScheduledProduct() && (quote.salida_id !== (request.salida_id ?? null) ||
              (this.selectedDeparture() && !this.departureAvailable(this.selectedDeparture()!))))) {
            this.booking.set(false);
            this.error.set('La fecha o el cupo dejó de estar disponible. Elige otra opción.');
            if (this.isScheduledProduct()) this.loadDepartures(true);
            else this.quote.set(null);
            return;
          }
          if (request.promocion_id && (quote.promocion?.id !== request.promocion_id || quote.total !== shownTotal)) {
            this.booking.set(false);
            this.quote.set(quote.promocion?.id === request.promocion_id ? quote : null);
            this.error.set('La promoción o el precio cambió. Revisa la nueva cotización antes de reservar.');
            return;
          }
          this.submitBooking(request, request.promocion_id ? quote.total : undefined);
        },
        error: (error: HttpErrorResponse) => {
          this.booking.set(false);
          this.error.set(apiErrorMessage(error, 'No se pudo validar el horario.'));
          if (this.isScheduledProduct()) this.loadDepartures(true);
          else this.quote.set(null);
        },
      });
      return;
    }
    this.submitBooking(request);
  }

  private submitBooking(request: BookingRequest, expectedTotal?: string): void {
    this.traveler.book(request, this.idempotencyKey).subscribe({
      next: (booking) => {
        if (expectedTotal !== undefined && (booking.promocion?.id !== request.promocion_id || booking.importe?.total !== expectedTotal)) {
          this.booking.set(false);
          this.quote.set(null);
          this.pendingBookingId.set(booking.id);
          this.error.set('El importe cambió al crear la reserva. Revisa el nuevo total antes de pagar.');
          return;
        }
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
        if (request.promocion_id) this.quote.set(null);
        if (this.isScheduledProduct()) this.loadDepartures(true);
      },
    });
  }

  protected onVerified(): void {
    this.needsVerification.set(false);
    this.book();
  }

  protected openPendingBooking(id: number): void {
    this.router.navigate(['/mis-viajes', id]);
  }
}
