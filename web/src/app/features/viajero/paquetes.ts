import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { LucideEye, LucidePackageOpen, LucidePencil, LucidePlus } from '@lucide/angular';
import { apiErrorMessage } from '../../core/http/api-error';
import { CustomPackage } from '../../core/packages/packages.models';
import { PackagesService } from '../../core/packages/packages.service';

@Component({
  selector: 'situr-paquetes',
  imports: [DatePipe, RouterLink, LucideEye, LucidePackageOpen, LucidePencil, LucidePlus],
  template: `
    <section class="mx-auto max-w-6xl space-y-6">
      <header class="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p class="text-accent-dark text-xs font-bold tracking-widest uppercase">Mi cuenta</p>
          <h1 class="font-heading text-title mt-1 text-3xl font-bold">Mis paquetes personalizados</h1>
          <p class="text-text-secondary mt-2 text-sm">Organiza servicios para tu viaje. Guardarlos no realiza una reserva ni un pago.</p>
        </div>
        <a routerLink="/paquetes/nuevo" class="btn-accent inline-flex min-h-11 items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold text-white">
          <svg lucidePlus class="h-4 w-4"></svg>Crear paquete
        </a>
      </header>
      @if (loading()) { <p class="text-text-secondary text-sm">Cargando paquetes…</p> }
      @else if (error(); as message) {
        <div class="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{{ message }}
          <button type="button" class="ml-3 font-semibold underline" (click)="load()">Reintentar</button>
        </div>
      } @else if (packages().length === 0) {
        <div class="border-input-border rounded-2xl border border-dashed bg-white px-6 py-16 text-center">
          <svg lucidePackageOpen class="mx-auto h-11 w-11 text-accent-dark"></svg>
          <h2 class="font-heading text-title mt-3 text-xl font-bold">Todavía no tienes paquetes</h2>
          <p class="text-text-secondary mt-2 text-sm">Combina los servicios reales del catálogo y guarda tu selección.</p>
          <a routerLink="/paquetes/nuevo" class="btn-accent mt-5 inline-flex min-h-11 items-center rounded-xl px-5 text-sm font-semibold text-white">Crear mi primer paquete</a>
        </div>
      } @else {
        <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          @for (package of packages(); track package.id) {
            <article class="border-input-border flex flex-col rounded-2xl border bg-white p-5 shadow-sm">
              <span class="w-fit rounded-full bg-demo-bg px-3 py-1 text-xs font-bold text-accent-dark">{{ package.estado === 'GUARDADO' ? 'Guardado' : 'Borrador' }}</span>
              <h2 class="font-heading text-title mt-3 text-lg font-bold">{{ package.nombre }}</h2>
              @if (package.ciudad) { <p class="text-text-secondary mt-1 text-sm">{{ package.ciudad }}</p> }
              <p class="text-text-secondary mt-3 text-sm">{{ package.fecha_inicio | date: 'dd/MM/yyyy' }} – {{ package.fecha_fin | date: 'dd/MM/yyyy' }}</p>
              <p class="text-text-secondary text-sm">{{ package.personas }} personas · {{ package.cantidad_servicios }} servicios</p>
              <p class="font-heading text-accent-dark mt-3 text-xl font-bold">Bs {{ package.total }}</p><p class="text-text-secondary text-xs">Último total calculado</p>
              <div class="mt-auto flex flex-wrap gap-2 pt-5">
                <a [routerLink]="['/paquetes', package.id]" class="inline-flex min-h-10 flex-1 items-center justify-center gap-1.5 rounded-xl border border-input-border bg-white px-3 py-2 text-sm font-semibold text-label shadow-sm transition hover:border-accent hover:bg-demo-bg hover:text-accent-dark focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-dark"><svg lucideEye class="h-4 w-4"></svg>Ver detalles</a>
                <a [routerLink]="['/paquetes', package.id, 'editar']" class="inline-flex min-h-10 flex-1 items-center justify-center gap-1.5 rounded-xl border border-accent-dark bg-demo-bg px-3 py-2 text-sm font-semibold text-accent-dark shadow-sm transition hover:bg-accent-dark hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-dark"><svg lucidePencil class="h-4 w-4"></svg>{{ package.estado === 'BORRADOR' ? 'Continuar' : 'Editar' }}</a>
              </div>
            </article>
          }
        </div>
      }
    </section>
  `,
})
export class Paquetes implements OnInit {
  private readonly service = inject(PackagesService);
  protected readonly packages = signal<CustomPackage[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  ngOnInit(): void { this.load(); }
  protected load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.service.list().subscribe({
      next: (packages) => { this.packages.set(packages); this.loading.set(false); },
      error: (error: HttpErrorResponse) => { this.error.set(apiErrorMessage(error)); this.loading.set(false); },
    });
  }
}
