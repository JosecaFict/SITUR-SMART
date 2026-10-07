import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { LucideMap } from '@lucide/angular';
import { apiErrorMessage } from '../../core/http/api-error';
import { Itinerary } from '../../core/traveler/traveler.models';
import { TravelerService } from '../../core/traveler/traveler.service';

/** Viajes que planifica el turista, día por día. */
@Component({
  selector: 'situr-itinerarios',
  imports: [DatePipe, RouterLink, LucideMap],
  template: `
    <section class="mx-auto max-w-5xl space-y-6">
      <header class="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p class="text-accent-dark text-xs font-bold tracking-widest uppercase">Mi cuenta</p>
          <h1 class="font-heading text-title mt-1 text-3xl font-bold tracking-tight">Itinerarios</h1>
          <p class="text-text-secondary mt-2 text-sm">Planifica tu viaje día por día. Tus reservas pagadas aparecen solas en su día.</p>
        </div>
        <button type="button" class="primary-button" (click)="creating.set(!creating())">{{ creating() ? 'Cancelar' : 'Nuevo itinerario' }}</button>
      </header>

      @if (error(); as text) { <p class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{{ text }}</p> }

      @if (creating()) {
        <form class="border-input-border grid gap-3 rounded-2xl border bg-white p-5 sm:grid-cols-3" (submit)="$event.preventDefault(); create()">
          <label class="flex flex-col gap-1 text-xs font-semibold text-label sm:col-span-3">Nombre
            <input class="field-control" maxlength="120" placeholder="Viaje a Santa Cruz" [value]="name()" (input)="name.set($any($event.target).value)" />
          </label>
          <label class="flex flex-col gap-1 text-xs font-semibold text-label">Salida
            <input type="date" class="field-control" [value]="start()" (change)="start.set($any($event.target).value)" />
          </label>
          <label class="flex flex-col gap-1 text-xs font-semibold text-label">Regreso
            <input type="date" class="field-control" [min]="start()" [value]="end()" (change)="end.set($any($event.target).value)" />
          </label>
          <div class="flex items-end"><button type="submit" class="primary-button w-full" [disabled]="working()">Crear</button></div>
        </form>
      }

      @if (loading()) {
        <p class="text-text-secondary text-sm">Cargando…</p>
      } @else if (itineraries().length === 0 && !creating()) {
        <div class="border-input-border rounded-2xl border border-dashed bg-white px-6 py-16 text-center">
          <svg lucideMap class="text-text-secondary mx-auto h-10 w-10"></svg>
          <p class="text-title mt-3 font-semibold">Arma tu primer itinerario</p>
        </div>
      } @else {
        <div class="grid gap-3 sm:grid-cols-2">
          @for (itinerary of itineraries(); track itinerary.id) {
            <a [routerLink]="['/itinerarios', itinerary.id]" class="border-input-border rounded-2xl border bg-white p-4 transition hover:shadow-md">
              <p class="text-title font-semibold">{{ itinerary.nombre }}</p>
              <p class="text-text-secondary text-sm">{{ itinerary.inicio | date: 'dd/MM/yyyy' }} – {{ itinerary.fin | date: 'dd/MM/yyyy' }}</p>
              <p class="text-text-secondary text-xs">
                {{ itinerary.dias }} {{ itinerary.dias === 1 ? 'día' : 'días' }} · {{ itinerary.actividades }} {{ itinerary.actividades === 1 ? 'actividad' : 'actividades' }}
                @if (itinerary.ciudad) { · {{ itinerary.ciudad }} }
              </p>
            </a>
          }
        </div>
      }
    </section>
  `,
})
export class Itinerarios implements OnInit {
  private readonly traveler = inject(TravelerService);
  private readonly router = inject(Router);

  protected readonly itineraries = signal<Itinerary[]>([]);
  protected readonly loading = signal(true);
  protected readonly creating = signal(false);
  protected readonly working = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly name = signal('');
  protected readonly start = signal('');
  protected readonly end = signal('');

  ngOnInit(): void {
    this.traveler.itineraries().subscribe({
      next: (list) => {
        this.itineraries.set(list);
        this.loading.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(error, 'No se pudieron cargar tus itinerarios.'));
      },
    });
  }

  protected create(): void {
    if (!this.name().trim() || !this.start() || !this.end()) {
      this.error.set('Ponle un nombre y elige las fechas del viaje.');
      return;
    }
    this.working.set(true);
    this.error.set(null);
    this.traveler.createItinerary({ nombre: this.name().trim(), inicio: this.start(), fin: this.end() }).subscribe({
      next: (created) => this.router.navigate(['/itinerarios', created.id]),
      error: (error: HttpErrorResponse) => {
        this.working.set(false);
        this.error.set(apiErrorMessage(error, 'No se pudo crear el itinerario.'));
      },
    });
  }
}
