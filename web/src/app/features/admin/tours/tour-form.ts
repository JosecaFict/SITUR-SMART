import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import {
  LucideArrowDown, LucideArrowLeft, LucideArrowUp, LucideCalendarClock, LucideCalendarDays, LucideCheck,
  LucideCircleAlert, LucideCompass, LucideEye, LucideEyeOff, LucideImage, LucideMapPin, LucidePlus,
  LucideRoute, LucideTrash2, LucideUpload, LucideX,
} from '@lucide/angular';
import { forkJoin } from 'rxjs';
import { AuthService } from '../../../core/auth/auth.service';
import { City, Country } from '../../../core/companies/companies.models';
import { CompaniesService } from '../../../core/companies/companies.service';
import { LatLng } from '../../../core/geo/geo.models';
import { apiErrorMessage } from '../../../core/http/api-error';
import { MediaService } from '../../../core/media/media.service';
import { Currency, ProductStatus, TourismProduct } from '../../../core/products/products.models';
import { ProductsService } from '../../../core/products/products.service';
import { Tour, TourDifficulty, TourPayload, TourTypeCode } from '../../../core/tours/tours.models';
import { ToursService } from '../../../core/tours/tours.service';
import { MapaUbicacion } from '../../../shared/mapa-ubicacion/mapa-ubicacion';
import { ProgramarPublicacion } from '../shared/programar-publicacion';

/** Decimales que guarda el backend. */
const COORDINATE_DECIMALS = 6;

/** Una parada mientras se edita: la clave solo sirve para el `track` de la lista. */
interface StopDraft {
  key: number;
  nombre: string;
  descripcion: string;
  duracion_minutos: number | null;
}

function parseLatLng(lat: string | null | undefined, lng: string | null | undefined): LatLng | null {
  if (!lat || !lng) return null;
  const parsed = { lat: Number(lat), lng: Number(lng) };
  return Number.isFinite(parsed.lat) && Number.isFinite(parsed.lng) ? parsed : null;
}

/**
 * Alta y ficha de un tour o experiencia:
 *
 *   /tours/nuevo   -> alta (queda en borrador)
 *   /tours/:id     -> ficha
 *
 * La empresa llega como `?empresa=`, igual que en Hospedajes.
 */
@Component({
  selector: 'situr-tour-form',
  imports: [
    DatePipe, ReactiveFormsModule, MapaUbicacion, ProgramarPublicacion,
    LucideArrowDown, LucideArrowLeft, LucideArrowUp, LucideCalendarClock, LucideCalendarDays, LucideCheck,
    LucideCircleAlert, LucideCompass, LucideEye, LucideEyeOff, LucideImage, LucideMapPin, LucidePlus,
    LucideRoute, LucideTrash2, LucideUpload, LucideX,
  ],
  templateUrl: './tour-form.html',
})
export class TourForm implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly companiesService = inject(CompaniesService);
  private readonly productsService = inject(ProductsService);
  private readonly toursService = inject(ToursService);
  private readonly mediaService = inject(MediaService);
  private readonly fb = inject(FormBuilder);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  protected readonly difficulties: { value: TourDifficulty; label: string }[] = [
    { value: 'BAJA', label: 'Baja' }, { value: 'MEDIA', label: 'Media' }, { value: 'ALTA', label: 'Alta' },
  ];

  protected readonly companyId = signal<number | null>(null);
  protected readonly currencies = signal<Currency[]>([]);
  protected readonly cities = signal<City[]>([]);
  protected readonly countries = signal<Country[]>([]);
  protected readonly tour = signal<Tour | null>(null);
  protected readonly isNew = signal(false);
  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly formErrors = signal<string[]>([]);
  protected readonly successMessage = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);
  protected readonly scheduleOpen = signal(false);
  protected readonly uploadingImage = signal(false);
  protected readonly imageError = signal<string | null>(null);

  protected readonly coordinates = signal<LatLng | null>(null);
  protected readonly includes = signal<string[]>([]);
  protected readonly excludes = signal<string[]>([]);
  protected readonly stops = signal<StopDraft[]>([]);
  private nextStopKey = 1;

  private readonly selectedCountryId = signal(0);
  private readonly selectedCityId = signal(0);

  protected readonly canManage = computed(() => {
    const user = this.auth.session()?.user;
    return !!user && (user.roles.includes('SUPER_ADMIN') || user.permisos.includes('PRODUCTOS_GESTIONAR'));
  });
  protected readonly filteredCities = computed(() => {
    const countryId = this.selectedCountryId();
    return countryId ? this.cities().filter((city) => city.pais_id === countryId) : [];
  });
  protected readonly cityCenter = computed<LatLng | null>(() => {
    const city = this.cities().find((item) => item.id === this.selectedCityId());
    return city ? parseLatLng(city.latitud, city.longitud) : null;
  });
  /** Un tour del Catálogo genérico que todavía no tiene ficha. */
  protected readonly withoutDetail = computed(() => !!this.tour() && !this.tour()?.detalle);

  protected readonly form = this.fb.nonNullable.group({
    tipo_codigo: ['TOUR' as TourTypeCode, Validators.required],
    nombre: ['', [Validators.required, Validators.maxLength(180)]],
    descripcion: [''],
    pais: ['', Validators.required],
    ciudad_id: [0, [Validators.required, Validators.min(1)]],
    localidad: [''],
    moneda_codigo: ['BOB', Validators.required],
    precio_base: [0, [Validators.required, Validators.min(0)]],
    capacidad_maxima: [10, [Validators.required, Validators.min(1), Validators.max(500)]],
    imagen_url: [''],
    duracion_horas: [0, [Validators.min(0), Validators.max(168)]],
    duracion_min: [0, [Validators.min(0), Validators.max(59)]],
    idioma: [''],
    dificultad: ['' as TourDifficulty | ''],
    edad_minima: [null as number | null, [Validators.min(0), Validators.max(120)]],
    punto_encuentro: ['', Validators.maxLength(250)],
    requisitos: [''],
  });

  protected readonly newInclude = this.fb.nonNullable.control('');
  protected readonly newExclude = this.fb.nonNullable.control('');

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    this.isNew.set(id === null);
    const fromQuery = Number(this.route.snapshot.queryParamMap.get('empresa'));
    this.companyId.set(fromQuery || this.auth.session()?.user.tenants[0]?.id || null);

    forkJoin({
      currencies: this.productsService.listCurrencies(),
      cities: this.companiesService.listCities(),
      countries: this.companiesService.listCountries(),
    }).subscribe({
      next: ({ currencies, cities, countries }) => {
        this.currencies.set(currencies);
        this.cities.set(cities);
        this.countries.set(countries);
        if (id) this.loadTour(Number(id));
        else this.prepareNew();
      },
      error: () => {
        this.loading.set(false);
        this.errorMessage.set('No fue posible cargar los catálogos.');
      },
    });
  }

  private prepareNew(): void {
    const onlyCountry = this.countries().length === 1 ? this.countries()[0] : null;
    this.selectedCountryId.set(onlyCountry?.id ?? 0);
    this.form.patchValue({ pais: onlyCountry ? String(onlyCountry.id) : '', moneda_codigo: this.currencies()[0]?.codigo ?? 'BOB' });
    this.loading.set(false);
  }

  private loadTour(tourId: number): void {
    const companyId = this.companyId();
    if (!companyId) {
      this.loading.set(false);
      this.errorMessage.set('No fue posible determinar la empresa de este tour.');
      return;
    }
    this.toursService.get(companyId, tourId).subscribe({
      next: (tour) => { this.applyTour(tour); this.loading.set(false); },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        this.errorMessage.set(apiErrorMessage(error, 'No fue posible cargar el tour.'));
      },
    });
  }

  private applyTour(tour: Tour): void {
    this.tour.set(tour);
    const city = this.cities().find((item) => item.id === tour.ciudad_id);
    this.selectedCountryId.set(city?.pais_id ?? 0);
    this.selectedCityId.set(tour.ciudad_id);
    const detail = tour.detalle;
    const minutes = detail?.duracion_minutos ?? 0;
    this.form.setValue({
      tipo_codigo: tour.tipo_codigo,
      nombre: tour.nombre,
      descripcion: tour.descripcion ?? '',
      pais: city ? String(city.pais_id) : '',
      ciudad_id: tour.ciudad_id,
      localidad: tour.localidad ?? '',
      moneda_codigo: tour.moneda_codigo,
      precio_base: Number(tour.precio_base),
      capacidad_maxima: tour.capacidad_maxima,
      imagen_url: tour.imagen_url ?? '',
      duracion_horas: Math.floor(minutes / 60),
      duracion_min: minutes % 60,
      idioma: detail?.idioma ?? '',
      dificultad: detail?.dificultad ?? '',
      edad_minima: detail?.edad_minima ?? null,
      punto_encuentro: detail?.punto_encuentro ?? '',
      requisitos: detail?.requisitos ?? '',
    });
    this.coordinates.set(parseLatLng(detail?.latitud, detail?.longitud));
    this.includes.set([...(detail?.incluye ?? [])]);
    this.excludes.set([...(detail?.no_incluye ?? [])]);
    this.stops.set(
      tour.paradas.map((stop) => ({
        key: this.nextStopKey++,
        nombre: stop.nombre,
        descripcion: stop.descripcion ?? '',
        duracion_minutos: stop.duracion_minutos,
      })),
    );
    this.notice.set(tour.aviso);
  }

  // --- Ubicación ------------------------------------------------------------

  protected countryChanged(): void {
    this.selectedCountryId.set(Number(this.form.controls.pais.value));
    const cityId = Number(this.form.controls.ciudad_id.value);
    if (cityId && !this.filteredCities().some((city) => city.id === cityId)) {
      this.form.controls.ciudad_id.setValue(0);
      this.selectedCityId.set(0);
    }
  }

  protected cityChanged(): void {
    this.selectedCityId.set(Number(this.form.controls.ciudad_id.value));
  }

  protected pinPicked(point: LatLng): void {
    this.coordinates.set(point);
  }

  protected clearPin(): void {
    this.coordinates.set(null);
  }

  // --- Incluye / no incluye ------------------------------------------------

  protected addItem(list: 'includes' | 'excludes'): void {
    const control = list === 'includes' ? this.newInclude : this.newExclude;
    const value = control.value.trim();
    if (!value) return;
    const target = list === 'includes' ? this.includes : this.excludes;
    if (!target().some((item) => item.toLowerCase() === value.toLowerCase())) target.update((items) => [...items, value]);
    control.setValue('');
  }

  protected removeItem(list: 'includes' | 'excludes', index: number): void {
    const target = list === 'includes' ? this.includes : this.excludes;
    target.update((items) => items.filter((_, i) => i !== index));
  }

  protected addOnEnter(event: KeyboardEvent, list: 'includes' | 'excludes'): void {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    this.addItem(list);
  }

  // --- Recorrido -------------------------------------------------------------

  protected addStop(): void {
    this.stops.update((items) => [...items, { key: this.nextStopKey++, nombre: '', descripcion: '', duracion_minutos: null }]);
  }

  protected removeStop(index: number): void {
    this.stops.update((items) => items.filter((_, i) => i !== index));
  }

  protected moveStop(index: number, delta: -1 | 1): void {
    this.stops.update((items) => {
      const target = index + delta;
      if (target < 0 || target >= items.length) return items;
      const copy = [...items];
      [copy[index], copy[target]] = [copy[target], copy[index]];
      return copy;
    });
  }

  protected updateStop(index: number, field: 'nombre' | 'descripcion' | 'duracion_minutos', value: string): void {
    this.stops.update((items) =>
      items.map((stop, i) => {
        if (i !== index) return stop;
        if (field === 'duracion_minutos') return { ...stop, duracion_minutos: value ? Number(value) : null };
        return { ...stop, [field]: value };
      }),
    );
  }

  // --- Guardar ---------------------------------------------------------------

  /** El cuerpo del pedido. Extraído para poder probar qué viaja. */
  buildPayload(): TourPayload {
    const raw = this.form.getRawValue();
    const point = this.coordinates();
    const minutes = Number(raw.duracion_horas) * 60 + Number(raw.duracion_min);
    return {
      tipo_codigo: raw.tipo_codigo,
      nombre: raw.nombre.trim(),
      descripcion: raw.descripcion.trim() || null,
      ciudad_id: Number(raw.ciudad_id),
      localidad: raw.localidad.trim() || null,
      moneda_codigo: raw.moneda_codigo,
      precio_base: Number(raw.precio_base),
      capacidad_maxima: Number(raw.capacidad_maxima),
      imagen_url: raw.imagen_url.trim() || null,
      duracion_minutos: minutes > 0 ? minutes : null,
      idioma: raw.idioma.trim() || null,
      dificultad: raw.dificultad || null,
      edad_minima: raw.edad_minima === null || (raw.edad_minima as unknown) === '' ? null : Number(raw.edad_minima),
      punto_encuentro: raw.punto_encuentro.trim() || null,
      // Las dos coordenadas viajan juntas, como exige el backend.
      latitud: point ? point.lat.toFixed(COORDINATE_DECIMALS) : null,
      longitud: point ? point.lng.toFixed(COORDINATE_DECIMALS) : null,
      incluye: this.includes(),
      no_incluye: this.excludes(),
      requisitos: raw.requisitos.trim() || null,
      paradas: this.stops()
        .filter((stop) => stop.nombre.trim())
        .map((stop) => ({
          nombre: stop.nombre.trim(),
          descripcion: stop.descripcion.trim() || null,
          duracion_minutos: stop.duracion_minutos,
        })),
    };
  }

  protected save(): void {
    const companyId = this.companyId();
    if (!companyId || this.form.invalid) {
      this.form.markAllAsTouched();
      this.formErrors.set(['Revisa los campos marcados.']);
      return;
    }
    if (this.stops().some((stop) => !stop.nombre.trim())) {
      this.formErrors.set(['Cada parada del recorrido necesita un nombre (o quítala).']);
      return;
    }
    const existing = this.tour();
    this.saving.set(true);
    this.formErrors.set([]);
    this.successMessage.set(null);
    const request = existing
      ? this.toursService.update(companyId, existing.id, this.buildPayload())
      : this.toursService.create(companyId, this.buildPayload());
    request.subscribe({
      next: (tour) => {
        this.saving.set(false);
        if (existing) {
          this.applyTour(tour);
          this.successMessage.set('Tour actualizado.');
          return;
        }
        // Recién creado: el paso siguiente son sus salidas.
        this.router.navigate(['/tours', tour.id, 'salidas'], { queryParams: { empresa: companyId, creado: 1 }, replaceUrl: true });
      },
      error: (error: HttpErrorResponse) => {
        this.saving.set(false);
        this.formErrors.set(this.errorList(error, 'No fue posible guardar el tour.'));
      },
    });
  }

  protected togglePublication(): void {
    const companyId = this.companyId();
    const tour = this.tour();
    if (!companyId || !tour) return;
    const estado: ProductStatus = tour.estado === 'PUBLICADO' ? 'BORRADOR' : 'PUBLICADO';
    this.formErrors.set([]);
    this.successMessage.set(null);
    this.toursService.update(companyId, tour.id, { estado }).subscribe({
      next: (updated) => {
        this.applyTour(updated);
        this.successMessage.set(updated.estado === 'PUBLICADO' ? 'Tour publicado. Ya aparece en el Marketplace.' : 'Tour retirado del Marketplace.');
      },
      error: (error: HttpErrorResponse) =>
        this.formErrors.set(this.errorList(error, 'No fue posible cambiar la publicación.')),
    });
  }

  protected deactivate(): void {
    const companyId = this.companyId();
    const tour = this.tour();
    if (!companyId || !tour) return;
    if (!confirm(`¿Desactivar “${tour.nombre}”?\n\nSale del Marketplace. Las reservas ya pagadas se mantienen.`)) return;
    this.toursService.deactivate(companyId, tour.id).subscribe({
      next: (updated) => { this.applyTour(updated); this.successMessage.set('Tour desactivado.'); },
      error: (error: HttpErrorResponse) => this.formErrors.set(this.errorList(error, 'No fue posible desactivarlo.')),
    });
  }

  protected scheduled(product: TourismProduct): void {
    const current = this.tour();
    if (current) this.tour.set({ ...current, publicar_en: product.publicar_en ?? null, retirar_en: product.retirar_en ?? null });
    this.scheduleOpen.set(false);
  }

  /**
   * Los errores del backend como lista: al publicar llegan varios a la vez
   * ("falta el punto de encuentro", "programa una salida"…) y conviene verlos todos.
   */
  private errorList(error: HttpErrorResponse, fallback: string): string[] {
    const details = error.error?.error?.details as Record<string, unknown> | undefined;
    const messages: string[] = [];
    if (details && typeof details === 'object') {
      for (const value of Object.values(details)) {
        if (Array.isArray(value)) messages.push(...value.filter((item): item is string => typeof item === 'string'));
        else if (typeof value === 'string') messages.push(value);
      }
    }
    return messages.length ? messages : [apiErrorMessage(error, fallback)];
  }

  // --- Navegación e imagen ------------------------------------------------------

  protected backToList(): void {
    this.router.navigate(['/tours'], { queryParams: this.companyId() ? { empresa: this.companyId() } : undefined });
  }

  protected goToDepartures(): void {
    const tour = this.tour();
    if (tour) this.router.navigate(['/tours', tour.id, 'salidas'], { queryParams: { empresa: this.companyId() } });
  }

  protected uploadImage(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    this.imageError.set(null);
    if (!['image/jpeg', 'image/png', 'image/webp', 'image/avif', 'image/gif'].includes(file.type)) {
      this.imageError.set('Formato no admitido. Selecciona un archivo JPG, PNG, WEBP o AVIF.');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      this.imageError.set('La imagen supera el límite de 10 MB.');
      return;
    }
    this.uploadingImage.set(true);
    this.mediaService.uploadImage(file, 'tours').subscribe({
      next: (res) => { this.form.patchValue({ imagen_url: res.url }); this.uploadingImage.set(false); },
      error: (error: HttpErrorResponse) => {
        this.uploadingImage.set(false);
        this.imageError.set(apiErrorMessage(error, 'No fue posible subir la imagen.'));
      },
    });
  }

  protected removeImage(): void {
    this.form.patchValue({ imagen_url: '' });
  }
}
