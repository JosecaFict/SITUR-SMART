import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { LucideBadgePercent, LucideBell, LucideSparkles } from '@lucide/angular';
import { apiErrorMessage } from '../../core/http/api-error';
import { AppNotification, CustomerInterests } from '../../core/traveler/traveler.models';
import { TravelerService } from '../../core/traveler/traveler.service';

const OFFER_KIND = 'OFERTA_INTERES';

/**
 * Bandeja de avisos: reservas (confirmada, vencida, cancelada…) y ofertas que
 * encajan con los intereses del turista. Arriba se muestra qué intereses detectó
 * el sistema, para que sepa por qué le llegan esas ofertas.
 */
@Component({
  selector: 'situr-notificaciones',
  imports: [DatePipe, LucideBadgePercent, LucideBell, LucideSparkles],
  template: `
    <section class="mx-auto max-w-3xl space-y-5">
      <header class="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p class="text-accent-dark text-xs font-bold tracking-widest uppercase">Mi cuenta</p>
          <h1 class="font-heading text-title mt-1 text-3xl font-bold tracking-tight">Notificaciones</h1>
        </div>
        @if (traveler.unread() > 0) {
          <button type="button" class="secondary-button" (click)="markAll()">Marcar todas como leídas</button>
        }
      </header>

      <!-- Mis intereses -->
      <article class="border-input-border rounded-2xl border bg-white p-5 shadow-sm" aria-label="Mis intereses">
        <h2 class="text-title flex items-center gap-2 font-bold"><svg lucideSparkles class="text-accent-dark h-5 w-5"></svg>Mis intereses</h2>
        @if (interests(); as profile) {
          @if (hasInterests()) {
            <p class="text-text-secondary mt-1 text-sm">
              Te avisamos de ofertas que encajan con esto. Lo calculamos con
              {{ profile.basado_en.favoritos }} favoritos, {{ profile.basado_en.reservas }} reservas y {{ profile.basado_en.resenas }} reseñas.
            </p>
            <div class="mt-4 grid gap-4 sm:grid-cols-2">
              <div>
                <p class="text-label text-xs font-semibold">Destinos</p>
                <ul class="mt-2 space-y-2">
                  @for (city of profile.ciudades; track city.nombre) {
                    <li>
                      <div class="flex justify-between text-sm"><span class="text-title">{{ city.nombre }}</span><span class="text-text-secondary">{{ city.puntaje }}%</span></div>
                      <div class="bg-input-bg mt-1 h-1.5 overflow-hidden rounded-full"><div class="bg-accent h-full rounded-full" [style.width.%]="city.puntaje"></div></div>
                    </li>
                  }
                </ul>
              </div>
              <div>
                <p class="text-label text-xs font-semibold">Tipo de experiencia</p>
                <ul class="mt-2 space-y-2">
                  @for (type of profile.tipos; track type.nombre) {
                    <li>
                      <div class="flex justify-between text-sm"><span class="text-title">{{ type.nombre }}</span><span class="text-text-secondary">{{ type.puntaje }}%</span></div>
                      <div class="bg-input-bg mt-1 h-1.5 overflow-hidden rounded-full"><div class="bg-accent h-full rounded-full" [style.width.%]="type.puntaje"></div></div>
                    </li>
                  }
                </ul>
              </div>
            </div>
          } @else {
            <p class="text-text-secondary mt-1 text-sm">
              Todavía no sabemos qué te interesa. Guarda lugares en favoritos o haz una reserva y te avisaremos de ofertas que te encajen.
            </p>
          }
        } @else {
          <p class="text-text-secondary mt-1 text-sm">Cargando tus intereses…</p>
        }
      </article>

      @if (error(); as text) { <p class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{{ text }}</p> }
      @if (items().length === 0 && !loading()) {
        <div class="border-input-border rounded-2xl border border-dashed bg-white px-6 py-16 text-center">
          <svg lucideBell class="text-text-secondary mx-auto h-10 w-10"></svg>
          <p class="text-title mt-3 font-semibold">No tienes avisos</p>
        </div>
      }
      <ul class="space-y-2">
        @for (item of items(); track item.id) {
          <li>
            <button type="button" (click)="open(item)" class="border-input-border w-full rounded-2xl border bg-white px-4 py-3 text-left transition hover:shadow-sm"
              [class.border-l-4]="!item.leida" [class.border-l-accent]="!item.leida">
              @if (isOffer(item)) {
                <span class="bg-demo-bg text-accent-dark mb-1 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-bold">
                  <svg lucideBadgePercent class="h-3.5 w-3.5"></svg>Oferta para ti
                </span>
              }
              <p class="text-title font-semibold">{{ item.titulo }}</p>
              <p class="text-label text-sm">{{ item.mensaje }}</p>
              <p class="text-text-secondary mt-1 text-xs">{{ item.creado_en | date: 'dd/MM/yyyy HH:mm' }}</p>
            </button>
          </li>
        }
      </ul>
      @if (hasMore()) {
        <button type="button" class="secondary-button" (click)="load(page() + 1)">Ver más</button>
      }
    </section>
  `,
})
export class Notificaciones implements OnInit {
  protected readonly traveler = inject(TravelerService);
  private readonly router = inject(Router);

  protected readonly items = signal<AppNotification[]>([]);
  protected readonly loading = signal(true);
  protected readonly hasMore = signal(false);
  protected readonly page = signal(1);
  protected readonly error = signal<string | null>(null);
  protected readonly interests = signal<CustomerInterests | null>(null);
  protected readonly hasInterests = computed(() => {
    const profile = this.interests();
    return !!profile && (profile.ciudades.length > 0 || profile.tipos.length > 0);
  });

  ngOnInit(): void {
    this.load(1);
    this.traveler.interests().subscribe({
      next: (profile) => this.interests.set(profile),
      error: () => this.interests.set({ ciudades: [], tipos: [], basado_en: { favoritos: 0, reservas: 0, resenas: 0 } }),
    });
  }

  protected load(page: number): void {
    this.loading.set(true);
    this.traveler.notifications(page).subscribe({
      next: (result) => {
        this.items.update((list) => (page === 1 ? result.results : [...list, ...result.results]));
        this.hasMore.set(!!result.next);
        this.page.set(page);
        this.loading.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(error, 'No se pudieron cargar tus avisos.'));
      },
    });
  }

  protected isOffer(item: AppNotification): boolean {
    return item.tipo === OFFER_KIND;
  }

  protected open(item: AppNotification): void {
    if (!item.leida) {
      this.traveler.markRead(item.id).subscribe();
      this.items.update((list) => list.map((n) => (n.id === item.id ? { ...n, leida: true } : n)));
    }
    if (item.datos?.promocion_id) {
      this.router.navigate(['/marketplace/promociones', item.datos.promocion_id]);
    } else if (item.datos?.reserva_id) {
      this.router.navigate(['/mis-viajes', item.datos.reserva_id]);
    }
  }

  protected markAll(): void {
    this.traveler.markAllRead().subscribe(() => this.items.update((list) => list.map((n) => ({ ...n, leida: true }))));
  }
}