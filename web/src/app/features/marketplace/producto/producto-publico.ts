import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import {
  LucideArrowLeft, LucideBaby, LucideCheck, LucideClock, LucideImage, LucideLanguages, LucideMapPin,
  LucideMountain, LucideRoute, LucideStar, LucideUsers, LucideX,
} from '@lucide/angular';
import { AuthService } from '../../../core/auth/auth.service';
import { apiErrorMessage } from '../../../core/http/api-error';
import { TourismProduct } from '../../../core/products/products.models';
import { ProductsService } from '../../../core/products/products.service';
import { Tour } from '../../../core/tours/tours.models';
import { ToursService } from '../../../core/tours/tours.service';
import { LatLng } from '../../../core/geo/geo.models';
import { MapaUbicacion } from '../../../shared/mapa-ubicacion/mapa-ubicacion';
import { Itinerary } from '../../../core/traveler/traveler.models';
import { TravelerService } from '../../../core/traveler/traveler.service';
import { Favorito } from '../../../shared/favorito/favorito';
import { Reservar } from '../../../shared/reservar/reservar';
import { Resenas } from '../../../shared/resenas/resenas';

/** Lo que se reserva por día y persona desde su ficha (un hotel se reserva por habitación). */
const BOOKABLE = new Set(['TOUR', 'EXPERIENCIA', 'ATRACCION', 'RESTAURANTE', 'PAQUETE']);
const TOUR_CODES = new Set(['TOUR', 'EXPERIENCIA']);
const DIFFICULTY_LABELS: Record<string, string> = { BAJA: 'Baja', MEDIA: 'Media', ALTA: 'Alta' };

/**
 * Ficha pública de un tour, experiencia, atracción, restaurante o paquete:
 * reservar, guardar en favoritos y sumarlo a un itinerario.
 */
@Component({
  selector: 'situr-producto-publico',
  imports: [
    DatePipe, RouterLink, Favorito, Reservar, Resenas, MapaUbicacion, LucideArrowLeft, LucideBaby, LucideCheck,
    LucideClock, LucideImage, LucideLanguages, LucideMapPin, LucideMountain, LucideRoute, LucideStar, LucideUsers,
    LucideX,
  ],
  templateUrl: './producto-publico.html',
})
export class ProductoPublico implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly products = inject(ProductsService);
  private readonly traveler = inject(TravelerService);
  private readonly toursService = inject(ToursService);
  protected readonly auth = inject(AuthService);
  protected readonly inShell = this.route.snapshot.data['inShell'] === true;
  protected readonly imageFailed = signal(false);

  protected readonly product = signal<TourismProduct | null>(null);
  protected readonly loading = signal(true);
  /**
   * Ficha del tour (CU20): recorrido, punto de encuentro, incluye. Null si no
   * es un tour o si todavía no tiene ficha. Las salidas las muestra Reservar.
   */
  protected readonly tour = signal<Tour | null>(null);
  protected readonly meetingPoint = computed<LatLng | null>(() => {
    const detail = this.tour()?.detalle;
    if (!detail?.latitud || !detail.longitud) return null;
    const point = { lat: Number(detail.latitud), lng: Number(detail.longitud) };
    return Number.isFinite(point.lat) && Number.isFinite(point.lng) ? point : null;
  });
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
    const id = Number(this.route.snapshot.paramMap.get('id') ?? this.route.parent?.snapshot.paramMap.get('id'));
    this.products.getPublic(id).subscribe({
      next: (product) => {
        this.product.set(product);
        this.loading.set(false);
        if (TOUR_CODES.has(product.tipo_codigo)) this.loadTour(product.id);
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

  private loadTour(id: number): void {
    this.toursService.getPublic(id).subscribe({
      next: (tour) => this.tour.set(tour),
      // Sin ficha (404): la página muestra solo los datos del producto.
      error: () => this.tour.set(null),
    });
  }

  protected difficulty(code: string | null): string {
    return code ? DIFFICULTY_LABELS[code] ?? code : '';
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

  protected refreshRating(): void {
    const current = this.product();
    if (!current) return;
    this.products.getPublic(current.id).subscribe({
      next: (updated) => this.product.set(updated),
    });
  }
}
