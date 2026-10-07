import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { LucideArrowLeft, LucideImage, LucideMapPin, LucideUsers } from '@lucide/angular';
import { AuthService } from '../../../core/auth/auth.service';
import { apiErrorMessage } from '../../../core/http/api-error';
import { TourismProduct } from '../../../core/products/products.models';
import { ProductsService } from '../../../core/products/products.service';
import { Itinerary } from '../../../core/traveler/traveler.models';
import { TravelerService } from '../../../core/traveler/traveler.service';
import { Favorito } from '../../../shared/favorito/favorito';
import { Reservar } from '../../../shared/reservar/reservar';

/** Lo que se reserva por día y persona desde su ficha (un hotel se reserva por habitación). */
const BOOKABLE = new Set(['TOUR', 'EXPERIENCIA', 'ATRACCION', 'RESTAURANTE', 'PAQUETE']);

/**
 * Ficha pública de un tour, experiencia, atracción, restaurante o paquete:
 * reservar, guardar en favoritos y sumarlo a un itinerario.
 */
@Component({
  selector: 'situr-producto-publico',
  imports: [RouterLink, Favorito, Reservar, LucideArrowLeft, LucideImage, LucideMapPin, LucideUsers],
  templateUrl: './producto-publico.html',
})
export class ProductoPublico implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly products = inject(ProductsService);
  private readonly traveler = inject(TravelerService);
  protected readonly auth = inject(AuthService);

  protected readonly product = signal<TourismProduct | null>(null);
  protected readonly loading = signal(true);
  protected readonly notFound = signal(false);
  protected readonly bookable = computed(() => {
    const product = this.product();
    return (
      !!product &&
      BOOKABLE.has(product.tipo_codigo) &&
      Number(product.precio_base) > 0 &&
      product.capacidad_maxima > 0
    );
  });

  // Agregar a un itinerario.
  protected readonly itineraries = signal<Itinerary[]>([]);
  protected readonly itineraryId = signal<number | null>(null);
  protected readonly itineraryDay = signal('');
  protected readonly itineraryMessage = signal<string | null>(null);
  protected readonly itineraryError = signal<string | null>(null);
  protected readonly selectedItinerary = computed(
    () => this.itineraries().find((item) => item.id === this.itineraryId()) ?? null,
  );

  ngOnInit(): void {
    const id = Number(this.route.snapshot.paramMap.get('id'));
    this.products.getPublic(id).subscribe({
      next: (product) => {
        this.product.set(product);
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.notFound.set(true);
      },
    });
    if (this.auth.isAuthenticated()) {
      const today = new Date().toISOString().slice(0, 10);
      this.traveler.itineraries().subscribe({
        next: (list) => this.itineraries.set(list.filter((item) => item.fin >= today)),
        error: () => this.itineraries.set([]),
      });
    }
  }

  protected chooseItinerary(event: Event): void {
    const value = Number((event.target as HTMLSelectElement).value);
    this.itineraryId.set(value || null);
    this.itineraryDay.set(this.selectedItinerary()?.inicio ?? '');
    this.itineraryMessage.set(null);
  }

  protected addToItinerary(): void {
    const product = this.product();
    const itinerary = this.selectedItinerary();
    if (!product || !itinerary || !this.itineraryDay()) return;
    this.itineraryError.set(null);
    this.traveler.addActivity(itinerary.id, { fecha: this.itineraryDay(), producto_id: product.id }).subscribe({
      next: () => this.itineraryMessage.set(`Agregado a "${itinerary.nombre}".`),
      error: (error: HttpErrorResponse) => this.itineraryError.set(apiErrorMessage(error, 'No se pudo agregar.')),
    });
  }
}
