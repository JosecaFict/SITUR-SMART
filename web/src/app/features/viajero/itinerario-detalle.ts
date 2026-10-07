import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { LucideArrowLeft } from '@lucide/angular';
import { apiErrorMessage } from '../../core/http/api-error';
import { ItineraryActivity, ItineraryDetail } from '../../core/traveler/traveler.models';
import { TravelerService } from '../../core/traveler/traveler.service';

/** Un viaje día por día: sus reservas pagadas y las actividades del turista. */
@Component({
  selector: 'situr-itinerario-detalle',
  imports: [DatePipe, RouterLink, LucideArrowLeft],
  template: `
    <section class="mx-auto max-w-3xl space-y-5">
      <a routerLink="/itinerarios" class="text-label inline-flex items-center gap-2 text-sm font-semibold hover:text-title">
        <svg lucideArrowLeft class="h-4 w-4"></svg>Itinerarios
      </a>
      @if (error(); as text) { <p class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{{ text }}</p> }

      @if (itinerary(); as trip) {
        <header class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 class="font-heading text-title text-3xl font-bold tracking-tight">{{ trip.nombre }}</h1>
            <p class="text-text-secondary text-sm">{{ trip.inicio | date: 'dd/MM/yyyy' }} – {{ trip.fin | date: 'dd/MM/yyyy' }}@if (trip.ciudad) { · {{ trip.ciudad }} }</p>
          </div>
          <button type="button" class="rounded-lg border border-red-200 px-3 py-2 text-xs font-semibold text-red-700 hover:bg-red-50" (click)="remove()">Eliminar</button>
        </header>

        @for (day of trip.agenda; track day.fecha) {
          <div class="border-input-border rounded-2xl border bg-white p-4">
            <div class="flex items-center justify-between gap-3">
              <h2 class="text-title font-bold capitalize">{{ dayLabel(day.fecha) }}</h2>
              <button type="button" class="text-accent-dark text-sm font-semibold hover:underline" (click)="openAdd(day.fecha)">+ Agregar</button>
            </div>
            @if (day.reservas.length === 0 && day.actividades.length === 0) {
              <p class="text-text-secondary mt-1 text-sm">Día libre</p>
            }
            <ul class="mt-2 space-y-2">
              @for (entry of day.reservas; track entry.reserva_id + (entry.momento ?? '')) {
                <li>
                  <a [routerLink]="['/mis-viajes', entry.reserva_id]" class="bg-demo-bg border-demo-border block rounded-xl border px-3 py-2 text-sm">
                    <span class="text-title font-semibold">{{ entry.titulo }}</span>
                    <span class="text-text-secondary block text-xs">{{ moment(entry.momento) }} · {{ entry.codigo }} · Pagada</span>
                  </a>
                </li>
              }
              @for (activity of day.actividades; track activity.id) {
                <li class="border-input-border flex items-start justify-between gap-3 rounded-xl border px-3 py-2 text-sm">
                  <span>
                    @if (activity.hora) { <span class="text-accent-dark mr-2 font-bold">{{ activity.hora }}</span> }
                    <span class="text-title font-semibold">{{ activity.titulo }}</span>
                    @if (activity.nota) { <span class="text-text-secondary block text-xs">{{ activity.nota }}</span> }
                  </span>
                  <button type="button" class="text-text-secondary text-xs hover:text-red-700" (click)="removeActivity(activity)" aria-label="Quitar actividad">Quitar</button>
                </li>
              }
            </ul>
            @if (addingDay() === day.fecha) {
              <form class="mt-3 flex flex-wrap gap-2" (submit)="$event.preventDefault(); addActivity(day.fecha)">
                <input type="time" class="field-control w-32" [value]="time()" (input)="time.set($any($event.target).value)" aria-label="Hora" />
                <input class="field-control min-w-48 flex-1" maxlength="150" placeholder="Qué vas a hacer" [value]="title()" (input)="title.set($any($event.target).value)" aria-label="Actividad" />
                <button type="submit" class="primary-button">Agregar</button>
              </form>
            }
          </div>
        }
        <p class="text-text-secondary text-xs">Para sumar un tour o un hospedaje, ábrelo en Explorar y usa "Agregar a un itinerario".</p>
      }
    </section>
  `,
})
export class ItinerarioDetalle implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly traveler = inject(TravelerService);

  protected readonly itinerary = signal<ItineraryDetail | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly addingDay = signal<string | null>(null);
  protected readonly time = signal('');
  protected readonly title = signal('');
  private id = 0;

  ngOnInit(): void {
    this.id = Number(this.route.snapshot.paramMap.get('id'));
    this.load();
  }

  private load(): void {
    this.traveler.itinerary(this.id).subscribe({
      next: (itinerary) => this.itinerary.set(itinerary),
      error: (error: HttpErrorResponse) => this.error.set(apiErrorMessage(error, 'No se pudo cargar el itinerario.')),
    });
  }

  /** "sábado 10 oct" sin depender del locale registrado en Angular. */
  protected dayLabel(day: string): string {
    return new Intl.DateTimeFormat('es-BO', { weekday: 'long', day: 'numeric', month: 'short' }).format(
      new Date(`${day}T12:00:00`),
    );
  }

  protected moment(value: string | null): string {
    return value === 'LLEGADA' ? 'Llegada' : value === 'SALIDA' ? 'Salida' : 'Reserva';
  }

  protected openAdd(day: string): void {
    this.addingDay.set(this.addingDay() === day ? null : day);
    this.time.set('');
    this.title.set('');
  }

  protected addActivity(day: string): void {
    if (!this.title().trim()) {
      this.error.set('Escribe qué vas a hacer.');
      return;
    }
    this.traveler.addActivity(this.id, { fecha: day, hora: this.time() || null, titulo: this.title().trim() }).subscribe({
      next: () => {
        this.addingDay.set(null);
        this.error.set(null);
        this.load();
      },
      error: (error: HttpErrorResponse) => this.error.set(apiErrorMessage(error, 'No se pudo agregar la actividad.')),
    });
  }

  protected removeActivity(activity: ItineraryActivity): void {
    this.traveler.deleteActivity(this.id, activity.id).subscribe({
      next: () => this.load(),
      error: (error: HttpErrorResponse) => this.error.set(apiErrorMessage(error, 'No se pudo quitar la actividad.')),
    });
  }

  protected remove(): void {
    if (!confirm('¿Eliminar el itinerario? Tus reservas no se tocan.')) return;
    this.traveler.deleteItinerary(this.id).subscribe({
      next: () => this.router.navigateByUrl('/itinerarios'),
      error: (error: HttpErrorResponse) => this.error.set(apiErrorMessage(error, 'No se pudo eliminar.')),
    });
  }
}
