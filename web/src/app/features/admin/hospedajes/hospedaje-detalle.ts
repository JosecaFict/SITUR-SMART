import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import {
  LucideArrowLeft, LucideBedDouble, LucideBuilding2, LucideCheck, LucideCircleAlert,
  LucideClock, LucideEye, LucideEyeOff, LucideImage, LucideMapPin, LucidePencil,
  LucidePlus, LucideRefreshCw, LucideTrash2, LucideUpload, LucideUsers, LucideX,
} from '@lucide/angular';
import { forkJoin } from 'rxjs';
import { AuthService } from '../../../core/auth/auth.service';
import { City, Country } from '../../../core/companies/companies.models';
import { CompaniesService } from '../../../core/companies/companies.service';
import { apiErrorMessage } from '../../../core/http/api-error';
import {
  LodgingEstablishment, LodgingPayload, LodgingType, Room, RoomPayload,
} from '../../../core/lodging/lodging.models';
import { LodgingService } from '../../../core/lodging/lodging.service';
import { MediaService } from '../../../core/media/media.service';
import { Currency, ProductStatus } from '../../../core/products/products.models';
import { ProductsService } from '../../../core/products/products.service';

type Tab = 'general' | 'hospedaje' | 'habitaciones';

/** Los que no estén acá se conservan si vinieron de la API. */
const SERVICE_OPTIONS = [
  'Wi-Fi', 'Piscina', 'Desayuno incluido', 'Estacionamiento', 'Aire acondicionado',
  'Gimnasio', 'Restaurante', 'Spa', 'Recepción 24 h', 'Admite mascotas',
];

/**
 * Alta y ficha de un hospedaje. Sirve a cuatro rutas:
 *
 *   /hospedajes/nuevo                 -> alta
 *   /hospedajes/:id                   -> ficha, pestaña Información general
 *   /hospedajes/:id/habitaciones      -> ficha, pestaña Habitaciones
 *
 * La empresa llega como `?empresa=`, para que la ficha funcione con enlace
 * directo y tras un recargado sin depender de estado en memoria.
 */
@Component({
  selector: 'situr-hospedaje-detalle',
  imports: [
    ReactiveFormsModule, LucideArrowLeft, LucideBedDouble, LucideBuilding2, LucideCheck,
    LucideCircleAlert, LucideClock, LucideEye, LucideEyeOff, LucideImage, LucideMapPin,
    LucidePencil, LucidePlus, LucideRefreshCw, LucideTrash2, LucideUpload, LucideUsers,
    LucideX,
  ],
  templateUrl: './hospedaje-detalle.html',
})
export class HospedajeDetalle implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly companiesService = inject(CompaniesService);
  private readonly productsService = inject(ProductsService);
  private readonly lodgingService = inject(LodgingService);
  private readonly mediaService = inject(MediaService);
  private readonly fb = inject(FormBuilder);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  protected readonly serviceOptions = SERVICE_OPTIONS;

  private readonly companyId = signal<number | null>(null);
  protected readonly lodgingTypes = signal<LodgingType[]>([]);
  protected readonly currencies = signal<Currency[]>([]);
  protected readonly cities = signal<City[]>([]);
  protected readonly countries = signal<Country[]>([]);

  protected readonly loading = signal(true);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly successMessage = signal<string | null>(null);

  /** Nulo mientras se carga, y en el alta hasta que se guarda. */
  protected readonly lodging = signal<LodgingEstablishment | null>(null);
  protected readonly isNew = signal(false);
  protected readonly activeTab = signal<Tab>('general');
  protected readonly savingLodging = signal(false);
  protected readonly lodgingFormError = signal<string | null>(null);
  protected readonly selectedServices = signal<string[]>([]);
  /** Llega como ?creado=1 tras el alta, para guiar al paso siguiente. */
  protected readonly justCreated = signal(false);

  protected readonly rooms = signal<Room[]>([]);
  protected readonly roomsLoading = signal(false);
  protected readonly showRoomForm = signal(false);
  protected readonly editingRoom = signal<Room | null>(null);
  protected readonly savingRoom = signal(false);
  protected readonly roomFormError = signal<string | null>(null);

  protected readonly uploadingImage = signal(false);
  protected readonly imageUploadError = signal<string | null>(null);

  protected readonly canManage = computed(() => {
    const user = this.auth.session()?.user;
    return !!user && (user.roles.includes('SUPER_ADMIN') || user.permisos.includes('PRODUCTOS_GESTIONAR'));
  });
  protected readonly publishedRooms = computed(
    () => this.rooms().filter((room) => room.estado === 'PUBLICADO').length,
  );
  protected readonly canPublishLodging = computed(() =>
    this.rooms().some((room) => room.estado === 'PUBLICADO' && Number(room.precio_noche) > 0),
  );
  protected readonly hasNoRooms = computed(() => !this.roomsLoading() && this.rooms().length === 0);

  private readonly selectedCountryId = signal(0);

  /**
   * Ciudades del país elegido. Vacío mientras no haya país.
   *
   * Devolver todas sería peor que devolver nada: dejaría elegir una ciudad que
   * el filtro va a descartar en cuanto se elija el país.
   */
  protected readonly filteredCities = computed(() => {
    const countryId = this.selectedCountryId();
    return countryId ? this.cities().filter((city) => city.pais_id === countryId) : [];
  });

  protected readonly lodgingForm = this.fb.nonNullable.group({
    nombre: ['', Validators.required],
    descripcion: [''],
    // No se envía: el backend deriva el país de la ciudad. Es obligatorio para
    // forzar el orden país → ciudad, no porque el API lo pida.
    pais: ['', Validators.required],
    ciudad_id: [0, [Validators.required, Validators.min(1)]],
    localidad: [''],
    moneda_codigo: ['BOB', Validators.required],
    estado: ['BORRADOR' as ProductStatus, Validators.required],
    imagen_url: [''],
    tipo_hospedaje_codigo: ['HOTEL', Validators.required],
    direccion: [''],
    categoria_estrellas: [''],
    hora_check_in: [''],
    hora_check_out: [''],
  });

  protected readonly roomForm = this.fb.nonNullable.group({
    nombre: ['', Validators.required],
    descripcion: [''],
    precio_base: [0, [Validators.required, Validators.min(0)]],
    capacidad_maxima: [2, [Validators.required, Validators.min(1)]],
    capacidad_adultos: [2, [Validators.required, Validators.min(1)]],
    capacidad_ninos: [0, [Validators.required, Validators.min(0)]],
    cantidad_habitaciones: [1, [Validators.required, Validators.min(1)]],
    tipo_cama: [''],
    incluye_desayuno: [false],
    estado: ['BORRADOR' as ProductStatus, Validators.required],
    imagen_url: [''],
  });

  /**
   * Los tres campos son topes alternativos, no un desglose: cada uno debe caber
   * en el total, pero su suma no se valida acá. Una habitación de 4 plazas con
   * hasta 4 adultos y hasta 3 niños es válida — nunca se ocupan a la vez.
   */
  protected readonly capacityWarning = computed(() => {
    const { capacidad_maxima, capacidad_adultos, capacidad_ninos } = this.roomForm.getRawValue();
    const total = Number(capacidad_maxima);
    if (Number(capacidad_adultos) > total) {
      return `El máximo de adultos (${capacidad_adultos}) no puede superar la capacidad total de la habitación (${total}).`;
    }
    if (Number(capacidad_ninos) > total) {
      return `El máximo de niños (${capacidad_ninos}) no puede superar la capacidad total de la habitación (${total}).`;
    }
    return null;
  });

  protected readonly priceWarning = computed(() => {
    const { precio_base, estado } = this.roomForm.getRawValue();
    return estado === 'PUBLICADO' && Number(precio_base) <= 0
      ? 'Una habitación publicada debe tener un precio por noche mayor a 0.'
      : null;
  });

  ngOnInit(): void {
    const params = this.route.snapshot.paramMap;
    const query = this.route.snapshot.queryParamMap;
    const lodgingId = params.get('id');
    this.isNew.set(lodgingId === null);
    this.activeTab.set((this.route.snapshot.data['tab'] as Tab) ?? 'general');
    this.justCreated.set(query.get('creado') === '1');

    const fromQuery = Number(query.get('empresa'));
    const sessionCompany = this.auth.session()?.user.tenants[0]?.id ?? null;
    this.companyId.set(fromQuery || sessionCompany);

    forkJoin({
      types: this.lodgingService.listTypes(),
      currencies: this.productsService.listCurrencies(),
      cities: this.companiesService.listCities(),
      countries: this.companiesService.listCountries(),
    }).subscribe({
      next: ({ types, currencies, cities, countries }) => {
        this.lodgingTypes.set(types);
        this.currencies.set(currencies);
        this.cities.set(cities);
        this.countries.set(countries);
        if (lodgingId) this.loadLodging(Number(lodgingId));
        else this.prepareNew();
      },
      error: () => {
        this.loading.set(false);
        this.errorMessage.set('No fue posible cargar los catálogos de hospedaje.');
      },
    });
  }

  private prepareNew(): void {
    this.selectedCountryId.set(0);
    this.lodgingForm.reset({
      // Sin país no puede haber ciudad válida elegida.
      pais: '',
      ciudad_id: 0,
      moneda_codigo: this.currencies()[0]?.codigo ?? 'BOB',
      estado: 'BORRADOR',
      tipo_hospedaje_codigo: 'HOTEL',
    });
    this.selectedServices.set([]);
    this.loading.set(false);
  }

  private loadLodging(lodgingId: number): void {
    const companyId = this.companyId();
    if (!companyId) {
      this.loading.set(false);
      this.errorMessage.set('No fue posible determinar la empresa de este hospedaje.');
      return;
    }
    this.lodgingService.getCompanyLodging(companyId, lodgingId).subscribe({
      next: (lodging) => {
        this.applyLodging(lodging);
        this.loading.set(false);
        this.loadRooms(lodging.id);
      },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        this.errorMessage.set(apiErrorMessage(error, 'No fue posible cargar el hospedaje.'));
      },
    });
  }

  private applyLodging(lodging: LodgingEstablishment): void {
    this.lodging.set(lodging);
    this.selectedServices.set([...lodging.servicios]);
    this.selectedCountryId.set(lodging.pais_id);
    this.lodgingForm.setValue({
      nombre: lodging.nombre,
      descripcion: lodging.descripcion ?? '',
      pais: String(lodging.pais_id),
      ciudad_id: lodging.ciudad_id,
      localidad: lodging.localidad ?? '',
      moneda_codigo: lodging.moneda_codigo,
      estado: lodging.estado,
      imagen_url: lodging.imagen_url ?? '',
      tipo_hospedaje_codigo: lodging.tipo_hospedaje_codigo,
      direccion: lodging.direccion ?? '',
      categoria_estrellas: lodging.categoria_estrellas?.toString() ?? '',
      hora_check_in: this.toTimeInput(lodging.hora_check_in),
      hora_check_out: this.toTimeInput(lodging.hora_check_out),
    });
  }

  // --- Navegación ---------------------------------------------------------

  protected backToList(): void {
    this.router.navigate(['/hospedajes']);
  }

  /** Cambiar de pestaña cambia la URL, así el botón atrás del navegador sirve. */
  protected selectTab(tab: Tab): void {
    const lodging = this.lodging();
    if (!lodging) return;
    const path = tab === 'habitaciones'
      ? ['/hospedajes', lodging.id, 'habitaciones']
      : ['/hospedajes', lodging.id];
    this.router.navigate(path, {
      queryParams: { empresa: this.companyId() },
      replaceUrl: true,
    });
    this.activeTab.set(tab);
  }

  // --- Hospedaje ----------------------------------------------------------

  /**
   * Acota las ciudades al país elegido y limpia la ciudad si quedó fuera.
   *
   * El país es obligatorio pero **no se envía**: el backend lo deriva de la
   * ciudad. Existe para imponer el orden país → ciudad y para que el
   * desplegable no liste ciudades de todo el mundo.
   */
  protected countryChanged(): void {
    this.selectedCountryId.set(Number(this.lodgingForm.controls.pais.value));
    const cityId = Number(this.lodgingForm.controls.ciudad_id.value);
    if (cityId && !this.filteredCities().some((city) => city.id === cityId)) {
      this.lodgingForm.controls.ciudad_id.setValue(0);
    }
  }

  protected toggleService(name: string): void {
    this.selectedServices.update((items) =>
      items.includes(name) ? items.filter((item) => item !== name) : [...items, name],
    );
  }

  protected hasService(name: string): boolean {
    return this.selectedServices().includes(name);
  }

  /**
   * Arma el cuerpo del pedido desde el formulario.
   *
   * Extraído para poder afirmar en una prueba qué viaja y qué no. Tres campos
   * del formulario quedan deliberadamente fuera:
   *
   * * `pais` — el backend lo deriva de la ciudad;
   * * precio — es el de la habitación más económica publicada;
   * * capacidad — se deriva de las habitaciones.
   */
  private buildLodgingPayload(): LodgingPayload {
    const raw = this.lodgingForm.getRawValue();
    return {
      nombre: raw.nombre.trim(),
      descripcion: raw.descripcion.trim() || undefined,
      ciudad_id: Number(raw.ciudad_id),
      localidad: raw.localidad.trim() || undefined,
      moneda_codigo: raw.moneda_codigo,
      estado: raw.estado,
      imagen_url: raw.imagen_url.trim() || undefined,
      tipo_hospedaje_codigo: raw.tipo_hospedaje_codigo,
      direccion: raw.direccion.trim() || undefined,
      categoria_estrellas: raw.categoria_estrellas ? Number(raw.categoria_estrellas) : null,
      hora_check_in: raw.hora_check_in || null,
      hora_check_out: raw.hora_check_out || null,
      servicios: this.selectedServices(),
    };
  }

  protected submitLodging(): void {
    const companyId = this.companyId();
    if (!companyId || this.lodgingForm.invalid) { this.lodgingForm.markAllAsTouched(); return; }
    const payload = this.buildLodgingPayload();
    const existing = this.lodging();
    this.savingLodging.set(true);
    this.lodgingFormError.set(null);
    const request = existing
      ? this.lodgingService.updateLodging(companyId, existing.id, payload)
      : this.lodgingService.createLodging(companyId, payload);

    request.subscribe({
      next: (lodging) => {
        this.savingLodging.set(false);
        if (existing) {
          this.applyLodging(lodging);
          this.successMessage.set('Hospedaje actualizado.');
          return;
        }
        // Recién creado: la URL pasa a ser la de su ficha, en Habitaciones.
        this.router.navigate(['/hospedajes', lodging.id, 'habitaciones'], {
          queryParams: { empresa: companyId, creado: 1 },
          replaceUrl: true,
        });
      },
      error: (error: HttpErrorResponse) => {
        this.savingLodging.set(false);
        this.lodgingFormError.set(apiErrorMessage(error, 'No fue posible guardar el hospedaje.'));
      },
    });
  }

  protected deactivateLodging(): void {
    const companyId = this.companyId();
    const lodging = this.lodging();
    if (!companyId || !lodging) return;
    const confirmed = confirm(
      `¿Desactivar “${lodging.nombre}”?\n\nSus habitaciones dejarán de aparecer en el Marketplace mientras el hospedaje esté inactivo.`,
    );
    if (!confirmed) return;
    this.lodgingService.deactivateLodging(companyId, lodging.id).subscribe({
      next: (updated) => {
        this.applyLodging(updated);
        this.successMessage.set('Hospedaje desactivado.');
      },
      error: (error: HttpErrorResponse) =>
        this.errorMessage.set(apiErrorMessage(error, 'No fue posible desactivar el hospedaje.')),
    });
  }

  // --- Habitaciones -------------------------------------------------------

  protected loadRooms(lodgingId: number): void {
    const companyId = this.companyId();
    if (!companyId) return;
    this.roomsLoading.set(true);
    this.lodgingService.listRooms(companyId, lodgingId).subscribe({
      next: (rooms) => { this.rooms.set(rooms); this.roomsLoading.set(false); },
      error: (error: HttpErrorResponse) => {
        this.roomsLoading.set(false);
        this.errorMessage.set(apiErrorMessage(error, 'No fue posible cargar las habitaciones.'));
      },
    });
  }

  protected startCreateRoom(): void {
    this.editingRoom.set(null);
    this.roomFormError.set(null);
    this.imageUploadError.set(null);
    this.roomForm.reset({
      precio_base: 0, capacidad_maxima: 2, capacidad_adultos: 2, capacidad_ninos: 0,
      cantidad_habitaciones: 1, incluye_desayuno: false, estado: 'BORRADOR',
    });
    this.showRoomForm.set(true);
    this.justCreated.set(false);
  }

  protected startEditRoom(room: Room): void {
    this.editingRoom.set(room);
    this.roomFormError.set(null);
    this.imageUploadError.set(null);
    this.roomForm.setValue({
      nombre: room.nombre,
      descripcion: room.descripcion ?? '',
      precio_base: Number(room.precio_noche),
      capacidad_maxima: room.capacidad_maxima,
      capacidad_adultos: room.capacidad_adultos,
      capacidad_ninos: room.capacidad_ninos,
      cantidad_habitaciones: room.cantidad_habitaciones,
      tipo_cama: room.tipo_cama ?? '',
      incluye_desayuno: room.incluye_desayuno,
      estado: room.estado,
      imagen_url: room.imagen_url ?? '',
    });
    this.showRoomForm.set(true);
  }

  protected cancelRoomForm(): void {
    this.showRoomForm.set(false);
    this.editingRoom.set(null);
    this.roomFormError.set(null);
    this.roomForm.reset();
  }

  protected submitRoom(): void {
    const companyId = this.companyId();
    const lodging = this.lodging();
    if (!companyId || !lodging || this.roomForm.invalid) { this.roomForm.markAllAsTouched(); return; }
    const raw = this.roomForm.getRawValue();
    const payload: RoomPayload = {
      nombre: raw.nombre.trim(),
      descripcion: raw.descripcion.trim() || undefined,
      precio_base: Number(raw.precio_base),
      capacidad_maxima: Number(raw.capacidad_maxima),
      capacidad_adultos: Number(raw.capacidad_adultos),
      capacidad_ninos: Number(raw.capacidad_ninos),
      cantidad_habitaciones: Number(raw.cantidad_habitaciones),
      tipo_cama: raw.tipo_cama.trim() || undefined,
      incluye_desayuno: raw.incluye_desayuno,
      estado: raw.estado,
      imagen_url: raw.imagen_url.trim() || undefined,
    };

    const editing = this.editingRoom();
    this.savingRoom.set(true);
    this.roomFormError.set(null);
    const request = editing
      ? this.lodgingService.updateRoom(companyId, editing.id, payload)
      : this.lodgingService.createRoom(companyId, lodging.id, payload);

    request.subscribe({
      next: (room) => {
        this.rooms.update((items) =>
          editing ? items.map((item) => (item.id === room.id ? room : item)) : [...items, room],
        );
        this.savingRoom.set(false);
        this.successMessage.set(editing ? 'Habitación actualizada.' : 'Habitación registrada.');
        this.cancelRoomForm();
        this.refreshLodging();
      },
      error: (error: HttpErrorResponse) => {
        this.savingRoom.set(false);
        this.roomFormError.set(apiErrorMessage(error, 'No fue posible guardar la habitación.'));
      },
    });
  }

  protected toggleRoomPublication(room: Room): void {
    const companyId = this.companyId();
    if (!companyId) return;
    const estado: ProductStatus = room.estado === 'PUBLICADO' ? 'BORRADOR' : 'PUBLICADO';
    this.errorMessage.set(null);
    this.lodgingService.updateRoom(companyId, room.id, { estado }).subscribe({
      next: (updated) => {
        this.rooms.update((items) => items.map((item) => (item.id === updated.id ? updated : item)));
        this.refreshLodging();
      },
      error: (error: HttpErrorResponse) =>
        this.errorMessage.set(apiErrorMessage(error, 'No fue posible cambiar la publicación.')),
    });
  }

  protected deactivateRoom(room: Room): void {
    const companyId = this.companyId();
    if (!companyId || !confirm(`¿Desactivar “${room.nombre}”?`)) return;
    this.lodgingService.deactivateRoom(companyId, room.id).subscribe({
      next: (updated) => {
        this.rooms.update((items) => items.map((item) => (item.id === updated.id ? updated : item)));
        this.refreshLodging();
        this.successMessage.set('Habitación desactivada.');
      },
      error: (error: HttpErrorResponse) =>
        this.errorMessage.set(apiErrorMessage(error, 'No fue posible desactivar la habitación.')),
    });
  }

  /**
   * Relee el hotel: el precio "desde", la capacidad y el conteo los calcula el
   * backend, y el estado puede haber cambiado solo.
   *
   * Si el backend lo bajó a borrador —porque la operación dejó al hotel sin
   * ninguna habitación publicada con precio— se avisa con el motivo. La señal es
   * el cambio de estado, no un campo extra en la respuesta de la habitación.
   */
  private refreshLodging(): void {
    const companyId = this.companyId();
    const lodging = this.lodging();
    if (!companyId || !lodging) return;
    const estadoAnterior = lodging.estado;
    this.lodgingService.getCompanyLodging(companyId, lodging.id).subscribe({
      next: (updated) => {
        this.lodging.set(updated);
        this.applyLodging(updated);
        if (estadoAnterior === 'PUBLICADO' && updated.estado === 'BORRADOR') {
          this.successMessage.set(
            'El hospedaje volvió a borrador porque ya no tiene ninguna habitación ' +
              'publicada con precio mayor a 0. No aparece en el Marketplace hasta ' +
              'que publiques una y lo publiques de nuevo.',
          );
        }
      },
      error: () => undefined,
    });
  }

  // --- Imágenes -----------------------------------------------------------

  protected uploadLodgingImage(event: Event): void {
    this.uploadImage(event, (url) => this.lodgingForm.patchValue({ imagen_url: url }));
  }

  protected uploadRoomImage(event: Event): void {
    this.uploadImage(event, (url) => this.roomForm.patchValue({ imagen_url: url }));
  }

  private uploadImage(event: Event, assign: (url: string) => void): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;

    this.imageUploadError.set(null);
    const validTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/avif', 'image/gif'];
    if (!validTypes.includes(file.type)) {
      this.imageUploadError.set('Formato no admitido. Selecciona un archivo JPG, PNG, WEBP o AVIF.');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      this.imageUploadError.set('La imagen supera el límite de 10 MB.');
      return;
    }

    this.uploadingImage.set(true);
    this.mediaService.uploadImage(file, 'hospedajes').subscribe({
      next: (res) => { assign(res.url); this.uploadingImage.set(false); },
      error: (error: HttpErrorResponse) => {
        this.uploadingImage.set(false);
        this.imageUploadError.set(apiErrorMessage(error, 'No fue posible subir la imagen.'));
      },
    });
  }

  protected removeLodgingImage(): void {
    this.lodgingForm.patchValue({ imagen_url: '' });
  }

  protected removeRoomImage(): void {
    this.roomForm.patchValue({ imagen_url: '' });
  }

  protected imageError(event: Event): void {
    (event.target as HTMLImageElement).style.display = 'none';
  }

  /** El backend devuelve "14:00:00"; <input type="time"> espera "14:00". */
  private toTimeInput(value: string | null): string {
    return value ? value.slice(0, 5) : '';
  }

  protected stars(count: number | null): number[] {
    return count ? Array.from({ length: count }, (_, index) => index) : [];
  }
}
