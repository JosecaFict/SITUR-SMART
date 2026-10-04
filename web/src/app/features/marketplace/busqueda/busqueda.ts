import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import {
  LucideArrowLeft,
  LucideArrowRight,
  LucideChevronDown,
  LucideCircleAlert,
  LucideMapPin,
  LucideSearch,
  LucideStar,
  LucideX,
} from '@lucide/angular';
import { Observable, forkJoin, map } from 'rxjs';
import { City, Country } from '../../../core/companies/companies.models';
import { CompaniesService } from '../../../core/companies/companies.service';
import { LodgingEstablishment } from '../../../core/lodging/lodging.models';
import { LodgingService } from '../../../core/lodging/lodging.service';
import { ProductType, TourismProduct } from '../../../core/products/products.models';
import { ProductsService } from '../../../core/products/products.service';
import { AuthService } from '../../../core/auth/auth.service';

type SortOrder = 'recientes' | 'precio_asc' | 'precio_desc' | 'nombre';

/**
 * De cara al viajero el sector se llama Hospedajes, no Hotel: en el Marketplace
 * agrupa lo que después serán también hostales y cabañas. El código sigue
 * siendo HOTEL, así que solo cambia la etiqueta del filtro.
 */
const PUBLIC_TYPE_LABELS: Record<string, string> = { HOTEL: 'Hospedajes' };

/**
 * Habitación se oculta del filtro público: una habitación no se oferta por
 * separado, se llega a ella abriendo su hospedaje. El endpoint sigue existiendo
 * para el móvil y para las búsquedas por huéspedes y disponibilidad.
 */
const HIDDEN_PUBLIC_TYPES = ['HABITACION'];

/** Imagen que se muestra cuando la del producto no carga. */
const FALLBACK_IMAGE = '/images/auth-carousel/Hotel4.webp';

/**
 * Las tres consultas públicas (productos, hospedajes y habitaciones) devuelven
 * formas distintas. Se normalizan a esta tarjeta para que la grilla sea una
 * sola, y cada origen decide qué significa su precio.
 */
interface MarketplaceCard {
  id: number;
  tipo: string;
  nombre: string;
  descripcion: string | null;
  localidad: string | null;
  ciudad: string;
  pais: string;
  empresa: string;
  imagen: string;
  /** "Desde", "Por noche" o "Habitaciones desde". */
  precioEtiqueta: string;
  /** Ya formateado con símbolo. Nulo cuando no hay precio que mostrar. */
  precio: string | null;
  /** Nula en un hospedaje: su capacidad la dan las habitaciones, no el producto. */
  capacidad: number | null;
  /** El botón dice "Ver habitaciones" si abre un hospedaje. */
  esHospedaje: boolean;
  /** Solo en habitaciones: el hotel del que dependen. */
  establecimiento: string | null;
  /** Hospedaje a abrir al expandir: el propio hotel o el de la habitación. */
  hospedajeId: number | null;
  estrellas: number | null;
}

@Component({
  selector: 'situr-busqueda',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    LucideArrowLeft,
    LucideArrowRight,
    LucideChevronDown,
    LucideCircleAlert,
    LucideMapPin,
    LucideSearch,
    LucideStar,
    LucideX,
  ],
  templateUrl: './busqueda.html',
  styleUrl: './busqueda.css',
})
export class Busqueda implements OnInit {
  private readonly formBuilder = inject(FormBuilder);
  private readonly productsService = inject(ProductsService);
  private readonly companiesService = inject(CompaniesService);
  private readonly lodgingService = inject(LodgingService);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  protected readonly session = this.auth.session;
  protected readonly isAuthenticated = this.auth.isAuthenticated;

  protected readonly cards = signal<MarketplaceCard[]>([]);
  protected readonly countries = signal<Country[]>([]);
  protected readonly cities = signal<City[]>([]);
  protected readonly types = signal<ProductType[]>([]);
  protected readonly loading = signal(true);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly validationMessage = signal<string | null>(null);
  protected readonly selectedType = signal('');
  protected readonly selectedCountryId = signal(0);
  /**
   * Producto no hospedaje con su descripción desplegada.
   *
   * Solo aplica a tours, experiencias, atracciones, restaurantes y paquetes: un
   * hospedaje no se despliega, navega a su página. La descripción ya viene en la
   * tarjeta, así que desplegar no consulta nada.
   */
  protected readonly expandedCardId = signal<number | null>(null);
  protected readonly total = signal(0);
  protected readonly page = signal(1);
  protected readonly pageSize = 9;

  protected readonly totalPages = computed(() => Math.max(1, Math.ceil(this.total() / this.pageSize)));
  protected readonly hasPreviousPage = computed(() => this.page() > 1);
  protected readonly hasNextPage = computed(() => this.page() < this.totalPages());

  protected readonly filterForm = this.formBuilder.nonNullable.group({
    buscar: [''],
    pais: [''],
    ciudad: [''],
    localidad: [''],
    tipo: [''],
    precio_min: [''],
    precio_max: [''],
    orden: ['recientes' as SortOrder],
  });

  protected readonly filteredCities = computed(() => {
    const countryId = this.selectedCountryId();
    return countryId ? this.cities().filter((city) => city.pais_id === countryId) : this.cities();
  });

  /** Categorías que se ofrecen al viajero, con el nombre público del sector. */
  protected readonly visibleTypes = computed(() =>
    this.types()
      .filter((type) => !HIDDEN_PUBLIC_TYPES.includes(type.codigo))
      .map((type) => ({ ...type, nombre: PUBLIC_TYPE_LABELS[type.codigo] ?? type.nombre })),
  );

  ngOnInit(): void {
    this.restoreFiltersFromUrl();
    forkJoin({
      countries: this.companiesService.listCountries(),
      cities: this.companiesService.listCities(),
      types: this.productsService.listTypes(),
    }).subscribe({
      next: ({ countries, cities, types }) => {
        this.countries.set(countries);
        this.cities.set(cities);
        this.types.set(types);
        this.search();
      },
      error: () => {
        this.loading.set(false);
        this.errorMessage.set('No se pudieron cargar los filtros del Marketplace.');
      },
    });
  }

  protected countryChanged(): void {
    this.selectedCountryId.set(Number(this.filterForm.controls.pais.value));
    const cityId = Number(this.filterForm.controls.ciudad.value);
    if (cityId && !this.filteredCities().some((city) => city.id === cityId)) {
      this.filterForm.controls.ciudad.setValue('');
    }
  }

  protected search(resetPage = true): void {
    const raw = this.filterForm.getRawValue();
    const minimum = this.parsePrice(raw.precio_min);
    const maximum = this.parsePrice(raw.precio_max);

    this.validationMessage.set(null);
    if (minimum !== undefined && maximum !== undefined && minimum > maximum) {
      this.validationMessage.set('El precio máximo debe ser mayor o igual que el precio mínimo.');
      return;
    }
    if (resetPage) this.page.set(1);
    this.loading.set(true);
    this.errorMessage.set(null);
    this.selectedType.set(raw.tipo);
    this.expandedCardId.set(null);
    this.syncUrl();

    const common = {
      buscar: raw.buscar.trim() || undefined,
      pais: raw.pais ? Number(raw.pais) : undefined,
      ciudad: raw.ciudad ? Number(raw.ciudad) : undefined,
      localidad: raw.localidad.trim() || undefined,
      precio_min: minimum,
      precio_max: maximum,
      orden: raw.orden,
      page: this.page(),
      page_size: this.pageSize,
    };

    // Hoteles y habitaciones tienen endpoints propios: solo ellos saben el
    // precio "desde" de un hotel y a qué establecimiento pertenece una
    // habitación. El resto del catálogo sigue por la consulta genérica.
    let request: Observable<{ count: number; results: MarketplaceCard[] }>;
    if (raw.tipo === 'HOTEL') {
      request = this.lodgingService
        .listPublicLodgings(common)
        .pipe(map((page) => ({ count: page.count, results: page.results.map((item) => this.lodgingCard(item)) })));
    } else {
      request = this.productsService
        .listMarketplace({ ...common, tipo: raw.tipo || undefined })
        .pipe(map((page) => ({ count: page.count, results: page.results.map((item) => this.productCard(item)) })));
    }

    request.subscribe({
      next: (response) => {
        this.cards.set(response.results);
        this.total.set(response.count);
        this.loading.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        this.errorMessage.set(
          error.status === 0
            ? 'No se pudo conectar con el backend.'
            : 'No se pudieron obtener los resultados. Revisa los filtros e inténtalo otra vez.',
        );
      },
    });
  }

  /**
   * Siembra el formulario con los filtros de la URL.
   *
   * Es lo que hace que el botón atrás desde la página de un hospedaje devuelva
   * la búsqueda tal como estaba, y que una búsqueda se pueda compartir.
   */
  private restoreFiltersFromUrl(): void {
    const query = this.route.snapshot.queryParamMap;
    const valor = (clave: string) => query.get(clave) ?? '';
    // Un enlace guardado puede traer una categoría que ya no se ofrece. Se
    // ignora en lugar de dejar el filtro en un valor que el desplegable no
    // tiene y que devolvería cero resultados sin explicación.
    const tipo = valor('tipo');
    this.filterForm.patchValue({
      buscar: valor('buscar'),
      pais: valor('pais'),
      ciudad: valor('ciudad'),
      localidad: valor('localidad'),
      tipo: HIDDEN_PUBLIC_TYPES.includes(tipo) ? '' : tipo,
      precio_min: valor('precio_min'),
      precio_max: valor('precio_max'),
      orden: (query.get('orden') as SortOrder) ?? 'recientes',
    });
    this.selectedCountryId.set(Number(valor('pais')));
    const pagina = Number(query.get('page'));
    if (pagina > 0) this.page.set(pagina);
  }

  /** Refleja los filtros activos en la URL, sin apilar entradas de historial. */
  private syncUrl(): void {
    const raw = this.filterForm.getRawValue();
    const queryParams: Record<string, string | number> = {};
    for (const [clave, valor] of Object.entries(raw)) {
      if (valor !== '' && valor !== 'recientes') queryParams[clave] = valor as string;
    }
    if (this.page() > 1) queryParams['page'] = this.page();
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams,
      replaceUrl: true,
    });
  }

  // --- Normalización de cada origen ---------------------------------------

  private productCard(product: TourismProduct): MarketplaceCard {
    const isHotel = product.tipo_codigo === 'HOTEL';
    const isRoom = product.tipo_codigo === 'HABITACION';

    // Un hotel muestra el precio "desde" calculado de sus habitaciones: su
    // precio_base es 0 y no significa nada para el viajero. Una habitación sí
    // cobra su precio_base, que es el de la noche.
    let precioEtiqueta = 'Desde';
    let precio: string | null = `${product.moneda_simbolo} ${product.precio_base}`;
    if (isHotel) {
      precioEtiqueta = 'Habitaciones desde';
      precio = product.precio_desde ? `${product.moneda_simbolo} ${product.precio_desde}` : null;
    } else if (isRoom) {
      precioEtiqueta = 'Por noche';
    }

    return {
      id: product.id,
      tipo: product.tipo,
      nombre: product.nombre,
      descripcion: product.descripcion,
      localidad: product.localidad,
      ciudad: product.ciudad,
      pais: product.pais,
      empresa: product.empresa,
      imagen: product.imagen_url || FALLBACK_IMAGE,
      precioEtiqueta,
      precio,
      // Un hospedaje no muestra la capacidad de su producto: en los heredados es
      // un número viejo y en los nuevos un centinela. La real la dan sus
      // habitaciones y se ve al abrirlo.
      capacidad: isHotel ? null : product.capacidad_maxima,
      establecimiento: product.establecimiento,
      // El backend ya resuelve cuál establecimiento abrir: su propia ficha si es
      // un hotel, la del hotel que la aloja si es una habitación. Es el id de
      // establecimiento_hospedaje, no el del producto.
      hospedajeId: product.hospedaje_id,
      estrellas: null,
      esHospedaje: isHotel,
    };
  }

  private lodgingCard(lodging: LodgingEstablishment): MarketplaceCard {
    return {
      id: lodging.id,
      tipo: lodging.tipo_hospedaje,
      nombre: lodging.nombre,
      descripcion: lodging.descripcion,
      localidad: lodging.localidad,
      ciudad: lodging.ciudad,
      pais: lodging.pais,
      empresa: lodging.empresa,
      imagen: lodging.imagen_url || FALLBACK_IMAGE,
      precioEtiqueta: 'Habitaciones desde',
      precio: lodging.precio_desde ? `${lodging.moneda_simbolo} ${lodging.precio_desde}` : null,
      capacidad: null,
      establecimiento: null,
      hospedajeId: lodging.id,
      estrellas: lodging.categoria_estrellas,
      esHospedaje: true,
    };
  }

  // --- Interacción ---------------------------------------------------------

  protected selectType(code = ''): void {
    this.filterForm.controls.tipo.setValue(code);
    this.search();
  }

  protected clearFilters(): void {
    this.filterForm.reset({
      buscar: '', pais: '', ciudad: '', localidad: '', tipo: '',
      precio_min: '', precio_max: '', orden: 'recientes',
    });
    this.selectedCountryId.set(0);
    this.search();
  }

  protected previousPage(): void {
    if (!this.hasPreviousPage() || this.loading()) return;
    this.page.update((value) => value - 1);
    this.search(false);
  }

  protected nextPage(): void {
    if (!this.hasNextPage() || this.loading()) return;
    this.page.update((value) => value + 1);
    this.search(false);
  }

  protected toggleDetails(card: MarketplaceCard): void {
    this.expandedCardId.update((actual) => (actual === card.id ? null : card.id));
  }

  /**
   * Cae a la imagen por defecto del proyecto una sola vez.
   *
   * El guardado importa: si la imagen por defecto tambien falla, reasignar el
   * `src` vuelve a disparar `error` y el ciclo no termina.
   */
  protected imageError(event: Event): void {
    const img = event.target as HTMLImageElement;
    if (img.dataset['fallback'] === 'done') return;
    img.dataset['fallback'] = 'done';
    img.src = FALLBACK_IMAGE;
  }

  protected stars(count: number | null): number[] {
    return count ? Array.from({ length: count }, (_, index) => index) : [];
  }

  private parsePrice(value: string): number | undefined {
    if (!value.trim()) return undefined;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
}
