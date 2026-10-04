import { HttpErrorResponse } from '@angular/common/http';
import { Location } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import {
  LucideArrowLeft, LucideBedDouble, LucideBuilding2, LucideCircleAlert, LucideClock,
  LucideImage, LucideMapPin, LucideRefreshCw, LucideStar, LucideUsers,
} from '@lucide/angular';
import { LodgingEstablishment, Room } from '../../../core/lodging/lodging.models';
import { LodgingService } from '../../../core/lodging/lodging.service';

/** Tamaño de página del endpoint paginado de habitaciones. */
const PAGE_SIZE = 12;

/**
 * Página pública de un hospedaje: su ficha y la cuadrícula de tipos de
 * habitación para comparar. Reemplaza al detalle que antes se expandía dentro
 * de la cuadrícula del Marketplace.
 *
 * Las habitaciones llegan por /marketplace/habitaciones/?hospedaje=:id, que es
 * el endpoint paginado; /marketplace/hospedajes/:id/habitaciones/ devuelve una
 * lista plana y no escala a veinte tipos.
 */
@Component({
  selector: 'situr-hospedaje-publico',
  imports: [
    RouterLink, LucideArrowLeft, LucideBedDouble, LucideBuilding2, LucideCircleAlert,
    LucideClock, LucideImage, LucideMapPin, LucideRefreshCw, LucideStar, LucideUsers,
  ],
  templateUrl: './hospedaje-publico.html',
})
export class HospedajePublico implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly location = inject(Location);
  private readonly lodgingService = inject(LodgingService);

  private lodgingId = 0;

  protected readonly lodging = signal<LodgingEstablishment | null>(null);
  protected readonly loading = signal(true);
  /** Diferencia "no existe o no es público" de "falló la red". */
  protected readonly notFound = signal(false);
  protected readonly errorMessage = signal<string | null>(null);

  // Las habitaciones tienen sus propios estados: que falle la cuadrícula no
  // debe borrar la ficha del hotel que ya se cargó.
  protected readonly rooms = signal<Room[]>([]);
  protected readonly roomsLoading = signal(true);
  protected readonly roomsError = signal<string | null>(null);
  protected readonly totalRooms = signal(0);
  protected readonly hasMore = signal(false);
  protected readonly loadingMore = signal(false);
  private nextPage = 1;

  protected readonly hasRooms = computed(() => this.rooms().length > 0);
  /** Vacío real: terminó de cargar, sin error, y no hay ninguna. */
  protected readonly roomsEmpty = computed(
    () => !this.roomsLoading() && !this.roomsError() && !this.hasRooms(),
  );

  ngOnInit(): void {
    this.lodgingId = Number(this.route.snapshot.paramMap.get('id'));
    if (!this.lodgingId) {
      this.loading.set(false);
      this.notFound.set(true);
      return;
    }
    this.loadLodging();
    this.loadRooms();
  }

  protected loadLodging(): void {
    this.loading.set(true);
    this.errorMessage.set(null);
    this.notFound.set(false);
    this.lodgingService.getPublicLodging(this.lodgingId).subscribe({
      next: (lodging) => {
        this.lodging.set(lodging);
        this.loading.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        if (error.status === 404) this.notFound.set(true);
        else this.errorMessage.set('No pudimos cargar este hospedaje. Inténtalo de nuevo.');
      },
    });
  }

  protected loadRooms(): void {
    this.nextPage = 1;
    this.rooms.set([]);
    this.roomsLoading.set(true);
    this.roomsError.set(null);
    this.fetchRooms();
  }

  protected loadMore(): void {
    if (this.loadingMore() || !this.hasMore()) return;
    this.loadingMore.set(true);
    this.fetchRooms();
  }

  private fetchRooms(): void {
    this.lodgingService
      .listPublicRooms({
        hospedaje: this.lodgingId,
        orden: 'precio_asc',
        page: this.nextPage,
        page_size: PAGE_SIZE,
      })
      .subscribe({
        next: (page) => {
          // Se apilan: "Cargar más" agrega, no reemplaza.
          this.rooms.update((items) => [...items, ...page.results]);
          this.totalRooms.set(page.count);
          this.hasMore.set(page.next !== null);
          this.nextPage += 1;
          this.roomsLoading.set(false);
          this.loadingMore.set(false);
        },
        error: () => {
          this.roomsLoading.set(false);
          this.loadingMore.set(false);
          this.roomsError.set('No pudimos cargar los tipos de habitación.');
        },
      });
  }

  /**
   * Vuelve por el historial para conservar los filtros, que el Marketplace
   * ahora lleva en su URL. Si se entró por un enlace compartido no hay
   * historial propio de la app, así que se va al inicio.
   */
  protected backToMarketplace(): void {
    if (this.router.lastSuccessfulNavigation?.previousNavigation) this.location.back();
    else this.router.navigate(['/']);
  }

  /** El backend envía "12:00:00"; al viajero se le muestra "12:00". */
  protected shortTime(value: string | null): string | null {
    return value ? value.slice(0, 5) : null;
  }

  protected stars(count: number | null): number[] {
    return count ? Array.from({ length: count }, (_, index) => index) : [];
  }

  /**
   * Imágenes cuya URL falló al cargar.
   *
   * Se registran por clave en vez de reemplazar el `src` por una imagen por
   * defecto: cambiar el `src` puede volver a fallar y disparar `error` otra vez,
   * en bucle. Marcándolas, la plantilla cae al mismo bloque de icono que usa
   * cuando no hay imagen, y el `<img>` deja de existir.
   */
  private readonly failedImages = signal<ReadonlySet<string>>(new Set());

  protected imageFailed(key: string): boolean {
    return this.failedImages().has(key);
  }

  protected imageError(key: string): void {
    this.failedImages.update((keys) => new Set(keys).add(key));
  }
}
