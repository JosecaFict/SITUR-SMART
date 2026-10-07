import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { LucideHeart } from '@lucide/angular';
import { apiErrorMessage } from '../../core/http/api-error';
import { TourismProduct } from '../../core/products/products.models';
import { TravelerService } from '../../core/traveler/traveler.service';

/** Productos y hospedajes que el turista guardó con el corazón. */
@Component({
  selector: 'situr-favoritos',
  imports: [RouterLink, LucideHeart],
  template: `
    <section class="mx-auto max-w-5xl space-y-6">
      <header>
        <p class="text-accent-dark text-xs font-bold tracking-widest uppercase">Mi cuenta</p>
        <h1 class="font-heading text-title mt-1 text-3xl font-bold tracking-tight">Favoritos</h1>
      </header>
      @if (error(); as text) { <p class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{{ text }}</p> }
      @if (loading()) {
        <p class="text-text-secondary text-sm">Cargando…</p>
      } @else if (products().length === 0) {
        <div class="border-input-border rounded-2xl border border-dashed bg-white px-6 py-16 text-center">
          <svg lucideHeart class="text-text-secondary mx-auto h-10 w-10"></svg>
          <p class="text-title mt-3 font-semibold">Todavía no guardaste nada</p>
          <p class="text-text-secondary mt-1 text-sm">Toca "Guardar" en un hospedaje o un tour para encontrarlo aquí.</p>
          <a routerLink="/" class="btn-accent mt-5 inline-flex min-h-11 items-center rounded-xl px-5 text-sm font-semibold text-white">Explorar</a>
        </div>
      } @else {
        <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          @for (product of products(); track product.id) {
            <article class="border-input-border overflow-hidden rounded-2xl border bg-white">
              <a [routerLink]="link(product)" class="block">
                <div class="h-40 bg-gray-100">
                  @if (product.imagen_url) { <img [src]="product.imagen_url" [alt]="product.nombre" class="h-full w-full object-cover" /> }
                </div>
                <div class="p-4">
                  <p class="text-accent-dark text-[11px] font-bold uppercase">{{ product.tipo }}</p>
                  <p class="text-title font-semibold">{{ product.nombre }}</p>
                  <p class="text-text-secondary text-xs">{{ product.ciudad }} · {{ product.empresa }}</p>
                </div>
              </a>
              <div class="border-input-border flex justify-end border-t px-4 py-2">
                <button type="button" class="text-xs font-semibold text-rose-700 hover:underline" (click)="remove(product)">Quitar</button>
              </div>
            </article>
          }
        </div>
      }
    </section>
  `,
})
export class Favoritos implements OnInit {
  private readonly traveler = inject(TravelerService);

  protected readonly products = signal<TourismProduct[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.traveler.favorites().subscribe({
      next: (products) => {
        this.products.set(products);
        this.loading.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(error, 'No se pudieron cargar tus favoritos.'));
      },
    });
  }

  protected link(product: TourismProduct): (string | number)[] {
    return product.hospedaje_id ? ['/marketplace/hospedajes', product.hospedaje_id] : ['/marketplace/productos', product.id];
  }

  protected remove(product: TourismProduct): void {
    this.products.update((list) => list.filter((item) => item.id !== product.id));
    this.traveler.removeFavorite(product.id).subscribe({
      error: () => this.products.update((list) => [...list, product]),
    });
  }
}
