import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import {
  LucideArrowLeft, LucideCalendarDays, LucideCheck, LucideChevronLeft, LucideChevronRight, LucideCircleAlert,
  LucideLock, LucideLockOpen, LucidePlus, LucideRepeat, LucideTrash2, LucideUserCheck, LucideUsers, LucideX,
} from '@lucide/angular';
import { forkJoin } from 'rxjs';
import { AuthService } from '../../../core/auth/auth.service';
import { apiErrorMessage } from '../../../core/http/api-error';
import { Guide, Tour, TourDeparture } from '../../../core/tours/tours.models';
import { DeparturesService, GuidesService, ToursService } from '../../../core/tours/tours.service';

/** Cuántos días muestra cada página del calendario. */
const RANGE_DAYS = 28;

export const WEEKDAYS = [
  { value: 0, short: 'Lun' }, { value: 1, short: 'Mar' }, { value: 2, short: 'Mié' }, { value: 3, short: 'Jue' },
  { value: 4, short: 'Vie' }, { value: 5, short: 'Sáb' }, { value: 6, short: 'Dom' },
];

export function isoDay(date: Date): string {
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function addDays(day: string, days: number): string {
  const date = new Date(`${day}T00:00:00`);
  date.setDate(date.getDate() + days);
  return isoDay(date);
}

interface DayGroup { day: string; label: string; departures: TourDeparture[]; }

/** "sábado, 8 de noviembre". Sin locale de Angular registrado, el DatePipe lo daría en inglés. */
function dayLabel(day: string): string {
  return new Date(`${day}T00:00:00`).toLocaleDateString('es-BO', { weekday: 'long', day: 'numeric', month: 'long' });
}

/**
 * Salidas de un tour: fecha, hora, cupo y guía. El turista reserva una de
 * estas. Cancelar una salida con reservas (y reembolsar) se hace en Pagos.
 */
@Component({
  selector: 'situr-tour-salidas',
  imports: [
    DatePipe, LucideArrowLeft, LucideCalendarDays, LucideCheck, LucideChevronLeft, LucideChevronRight,
    LucideCircleAlert, LucideLock, LucideLockOpen, LucidePlus, LucideRepeat, LucideTrash2, LucideUserCheck,
    LucideUsers, LucideX,
  ],
  templateUrl: './tour-salidas.html',
})
export class TourSalidas implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly toursService = inject(ToursService);
  private readonly departuresService = inject(DeparturesService);
  private readonly guidesService = inject(GuidesService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  protected readonly weekdays = WEEKDAYS;
  protected readonly today = isoDay(new Date());

  protected readonly companyId = signal<number | null>(null);
  protected readonly tour = signal<Tour | null>(null);
  protected readonly guides = signal<Guide[]>([]);
  protected readonly departures = signal<TourDeparture[]>([]);
  protected readonly loading = signal(true);
  protected readonly listLoading = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly successMessage = signal<string | null>(null);
  protected readonly justCreated = signal(false);
  protected readonly rangeStart = signal(isoDay(new Date()));

  // Formulario de alta.
  protected readonly mode = signal<'una' | 'repetidas'>('repetidas');
  protected readonly day = signal('');
  protected readonly startTime = signal('08:00');
  protected readonly endTime = signal('');
  protected readonly capacity = signal<number | null>(null);
  protected readonly guideId = signal<number | null>(null);
  protected readonly selectedWeekdays = signal<number[]>([]);
  protected readonly from = signal(isoDay(new Date()));
  protected readonly to = signal(addDays(isoDay(new Date()), 27));
  protected readonly creating = signal(false);
  protected readonly createError = signal<string | null>(null);

  /** Cupo que se está editando, por salida. */
  protected readonly capacityDrafts = signal<Record<number, number>>({});

  protected readonly canManage = computed(() => {
    const user = this.auth.session()?.user;
    return !!user && (user.roles.includes('SUPER_ADMIN') || user.permisos.includes('DISPONIBILIDAD_GESTIONAR'));
  });
  protected readonly activeGuides = computed(() => this.guides().filter((guide) => guide.estado === 'ACTIVO'));
  protected readonly rangeEnd = computed(() => addDays(this.rangeStart(), RANGE_DAYS - 1));
  protected readonly groups = computed<DayGroup[]>(() => {
    const byDay = new Map<string, TourDeparture[]>();
    for (const departure of this.departures()) {
      const day = isoDay(new Date(departure.inicio));
      byDay.set(day, [...(byDay.get(day) ?? []), departure]);
    }
    return [...byDay.entries()].map(([day, departures]) => ({ day, label: dayLabel(day), departures }));
  });
  protected readonly canGoBack = computed(() => this.rangeStart() > this.today);

  ngOnInit(): void {
    const tourId = Number(this.route.snapshot.paramMap.get('id'));
    const query = this.route.snapshot.queryParamMap;
    this.companyId.set(Number(query.get('empresa')) || this.auth.session()?.user.tenants[0]?.id || null);
    this.justCreated.set(query.get('creado') === '1');
    const companyId = this.companyId();
    if (!companyId) {
      this.loading.set(false);
      this.errorMessage.set('No fue posible determinar la empresa de este tour.');
      return;
    }
    forkJoin({ tour: this.toursService.get(companyId, tourId), guides: this.guidesService.list(companyId) }).subscribe({
      next: ({ tour, guides }) => {
        this.tour.set(tour);
        this.guides.set(guides);
        this.capacity.set(tour.capacidad_maxima);
        this.loading.set(false);
        this.loadDepartures();
      },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        this.errorMessage.set(apiErrorMessage(error, 'No fue posible cargar el tour.'));
      },
    });
  }

  protected loadDepartures(): void {
    const companyId = this.companyId();
    const tour = this.tour();
    if (!companyId || !tour) return;
    this.listLoading.set(true);
    this.departuresService.list(companyId, tour.id, this.rangeStart(), this.rangeEnd()).subscribe({
      next: (departures) => {
        this.departures.set(departures);
        this.capacityDrafts.set({});
        this.listLoading.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.listLoading.set(false);
        this.errorMessage.set(apiErrorMessage(error, 'No fue posible cargar las salidas.'));
      },
    });
  }

  protected moveRange(direction: -1 | 1): void {
    const next = addDays(this.rangeStart(), direction * RANGE_DAYS);
    this.rangeStart.set(next < this.today ? this.today : next);
    this.loadDepartures();
  }

  // --- Alta -------------------------------------------------------------------

  protected toggleWeekday(value: number): void {
    this.selectedWeekdays.update((days) => (days.includes(value) ? days.filter((day) => day !== value) : [...days, value].sort()));
  }

  protected create(): void {
    const companyId = this.companyId();
    const tour = this.tour();
    if (!companyId || !tour || this.creating()) return;
    this.createError.set(null);
    this.successMessage.set(null);
    const common = {
      cupo: this.capacity() ?? undefined,
      guia_id: this.guideId(),
    };

    if (this.mode() === 'una') {
      if (!this.day() || !this.startTime()) { this.createError.set('Elige la fecha y la hora de inicio.'); return; }
      this.creating.set(true);
      this.departuresService.create(companyId, tour.id, {
        ...common,
        inicio: `${this.day()}T${this.startTime()}`,
        fin: this.endTime() ? `${this.day()}T${this.endTime()}` : null,
      }).subscribe({
        next: () => this.created('Salida creada.'),
        error: (error: HttpErrorResponse) => this.failCreate(error),
      });
      return;
    }

    if (!this.selectedWeekdays().length) { this.createError.set('Elige al menos un día de la semana.'); return; }
    this.creating.set(true);
    this.departuresService.createRecurring(companyId, tour.id, {
      ...common,
      dias_semana: this.selectedWeekdays(),
      hora_inicio: this.startTime(),
      hora_fin: this.endTime() || null,
      desde: this.from(),
      hasta: this.to(),
    }).subscribe({
      next: (result) => this.created(
        `Se crearon ${result.creadas.length} salidas` + (result.omitidas ? ` (${result.omitidas} omitidas porque ya existían o ya pasaron).` : '.'),
      ),
      error: (error: HttpErrorResponse) => this.failCreate(error),
    });
  }

  private created(message: string): void {
    this.creating.set(false);
    this.justCreated.set(false);
    this.successMessage.set(message);
    this.loadDepartures();
    this.refreshTour();
  }

  private failCreate(error: HttpErrorResponse): void {
    this.creating.set(false);
    this.createError.set(apiErrorMessage(error, 'No fue posible crear las salidas.'));
  }

  /** El resumen del tour (salidas próximas) cambia al crear o cerrar salidas. */
  private refreshTour(): void {
    const companyId = this.companyId();
    const tour = this.tour();
    if (companyId && tour) this.toursService.get(companyId, tour.id).subscribe({ next: (fresh) => this.tour.set(fresh) });
  }

  // --- Cambios sobre una salida --------------------------------------------------

  private replace(updated: TourDeparture): void {
    this.departures.update((items) => items.map((item) => (item.id === updated.id ? updated : item)));
  }

  private act(request: ReturnType<DeparturesService['update']>, message: string): void {
    this.errorMessage.set(null);
    this.successMessage.set(null);
    request.subscribe({
      next: (updated) => { this.replace(updated); this.successMessage.set(message); this.refreshTour(); },
      error: (error: HttpErrorResponse) => this.errorMessage.set(apiErrorMessage(error, 'No fue posible actualizar la salida.')),
    });
  }

  protected changeGuide(departure: TourDeparture, event: Event): void {
    const companyId = this.companyId();
    if (!companyId) return;
    const value = Number((event.target as HTMLSelectElement).value) || null;
    this.act(this.departuresService.update(companyId, departure.id, { guia_id: value }), value ? 'Guía asignado.' : 'Guía quitado.');
  }

  protected draftCapacity(departure: TourDeparture, value: string): void {
    this.capacityDrafts.update((drafts) => ({ ...drafts, [departure.id]: Number(value) }));
  }

  protected capacityChanged(departure: TourDeparture): boolean {
    const draft = this.capacityDrafts()[departure.id];
    return draft !== undefined && draft !== departure.cupo;
  }

  protected saveCapacity(departure: TourDeparture): void {
    const companyId = this.companyId();
    const draft = this.capacityDrafts()[departure.id];
    if (!companyId || !draft) return;
    this.act(this.departuresService.update(companyId, departure.id, { cupo: draft }), 'Cupo actualizado.');
  }

  protected toggleClosed(departure: TourDeparture): void {
    const companyId = this.companyId();
    if (!companyId) return;
    if (departure.cerrada) {
      this.act(this.departuresService.update(companyId, departure.id, { cerrada: false }), 'Salida reabierta.');
      return;
    }
    const message = departure.reservados
      ? `Cerrar la salida la quita de la venta. Sus ${departure.reservados} lugares reservados se mantienen.\n\n¿Cerrarla?`
      : '¿Cerrar la salida? Deja de venderse.';
    if (!confirm(message)) return;
    this.act(this.departuresService.close(companyId, departure.id), 'Salida cerrada.');
  }

  protected remove(departure: TourDeparture): void {
    const companyId = this.companyId();
    if (!companyId || !confirm('¿Eliminar esta salida?')) return;
    this.errorMessage.set(null);
    this.departuresService.remove(companyId, departure.id).subscribe({
      next: () => {
        this.departures.update((items) => items.filter((item) => item.id !== departure.id));
        this.successMessage.set('Salida eliminada.');
        this.refreshTour();
      },
      error: (error: HttpErrorResponse) => this.errorMessage.set(apiErrorMessage(error, 'No fue posible eliminar la salida.')),
    });
  }

  // --- Navegación -------------------------------------------------------------------

  private companyParam() {
    return this.companyId() ? { empresa: this.companyId() } : undefined;
  }

  protected backToTour(): void {
    const tour = this.tour();
    this.router.navigate(tour ? ['/tours', tour.id] : ['/tours'], { queryParams: this.companyParam() });
  }

  protected goToGuides(): void {
    this.router.navigate(['/guias'], { queryParams: this.companyParam() });
  }

  protected goToPayments(): void {
    this.router.navigate(['/pagos']);
  }
}
