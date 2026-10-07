import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { LucideBell } from '@lucide/angular';
import { apiErrorMessage } from '../../core/http/api-error';
import { AppNotification } from '../../core/traveler/traveler.models';
import { TravelerService } from '../../core/traveler/traveler.service';

/** Bandeja de avisos: reserva confirmada, vencida, cancelada… Al tocarlos abre la reserva. */
@Component({
  selector: 'situr-notificaciones',
  imports: [DatePipe, LucideBell],
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

  ngOnInit(): void {
    this.load(1);
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

  protected open(item: AppNotification): void {
    if (!item.leida) {
      this.traveler.markRead(item.id).subscribe();
      this.items.update((list) => list.map((n) => (n.id === item.id ? { ...n, leida: true } : n)));
    }
    if (item.datos?.reserva_id) this.router.navigate(['/mis-viajes', item.datos.reserva_id]);
  }

  protected markAll(): void {
    this.traveler.markAllRead().subscribe(() => this.items.update((list) => list.map((n) => ({ ...n, leida: true }))));
  }
}
