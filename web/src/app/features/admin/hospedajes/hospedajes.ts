import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import {
  LucideArrowLeft, LucideBedDouble, LucideBuilding2, LucideCheck, LucideCircleAlert,
  LucideClock, LucideEye, LucideEyeOff, LucideImage, LucideMapPin, LucidePencil,
  LucidePlus, LucideRefreshCw, LucideStar, LucideTrash2, LucideUpload, LucideUsers,
  LucideX,
} from '@lucide/angular';
import { forkJoin } from 'rxjs';
import { AuthService } from '../../../core/auth/auth.service';
import { City } from '../../../core/companies/companies.models';
import { CompaniesService } from '../../../core/companies/companies.service';
import { apiErrorMessage } from '../../../core/http/api-error';
import {
  LodgingEstablishment, LodgingPayload, LodgingType, Room, RoomPayload,
} from '../../../core/lodging/lodging.models';
import { LodgingService } from '../../../core/lodging/lodging.service';
import { MediaService } from '../../../core/media/media.service';
import { Currency, ProductStatus } from '../../../core/products/products.models';
import { ProductsService } from '../../../core/products/products.service';

interface CompanyChoice { id: number; name: string; }
type View = 'list' | 'create' | 'detail';
type Tab = 'general' | 'hospedaje' | 'habitaciones';

/** Servicios ofrecidos como casillas. Los que lleguen de la API y no estén acá
 *  se conservan igual, porque la lista se inicializa con lo que vino. */
const SERVICE_OPTIONS = [
  'Wi-Fi', 'Piscina', 'Desayuno incluido', 'Estacionamiento', 'Aire acondicionado',
  'Gimnasio', 'Restaurante', 'Spa', 'Recepción 24 h', 'Admite mascotas',
];

@Component({
  selector: 'situr-hospedajes',
  imports: [
    ReactiveFormsModule, LucideArrowLeft, LucideBedDouble, LucideBuilding2, LucideCheck,
    LucideCircleAlert, LucideClock, LucideEye, LucideEyeOff, LucideImage, LucideMapPin,
    LucidePencil, LucidePlus, LucideRefreshCw, LucideStar, LucideTrash2, LucideUpload,
    LucideUsers, LucideX,
  ],
  templateUrl: './hospedajes.html',
})
export class Hospedajes implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly companiesService = inject(CompaniesService);
  private readonly productsService = inject(ProductsService);
  private readonly lodgingService = inject(LodgingService);
  private readonly mediaService = inject(MediaService);
  private readonly fb = inject(FormBuilder);

  protected readonly serviceOptions = SERVICE_OPTIONS;

  protected readonly companies = signal<CompanyChoice[]>([]);
  protected readonly selectedCompanyId = signal<number | null>(null);
  protected readonly lodgings = signal<LodgingEstablishment[]>([]);
  protected readonly lodgingTypes = signal<LodgingType[]>([]);
  protected readonly currencies = signal<Currency[]>([]);
  protected readonly cities = signal<City[]>([]);

  protected readonly loading = signal(true);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly successMessage = signal<string | null>(null);

  protected readonly view = signal<View>('list');
  protected readonly activeTab = signal<Tab>('general');
  protected readonly selectedLodging = signal<LodgingEstablishment | null>(null);
  protected readonly savingLodging = signal(false);
  protected readonly lodgingFormError = signal<string | null>(null);
  protected readonly selectedServices = signal<string[]>([]);

  protected readonly rooms = signal<Room[]>([]);
  protected readonly roomsLoading = signal(false);
  protected readonly showRoomForm = signal(false);
  protected readonly editingRoom = signal<Room | null>(null);
  protected readonly savingRoom = signal(false);
  protected readonly roomFormError = signal<string | null>(null);

  protected readonly uploadingImage = signal(false);
  protected readonly imageUploadError = signal<string | null>(null);

  protected readonly isSuperAdmin = computed(
    () => this.auth.session()?.user.roles.includes('SUPER_ADMIN') ?? false,
  );
  protected readonly canManage = computed(() => {
    const user = this.auth.session()?.user;
    return !!user && (user.roles.includes('SUPER_ADMIN') || user.permisos.includes('PRODUCTOS_GESTIONAR'));
  });
  protected readonly selectedCompany = computed(
    () => this.companies().find((item) => item.id === this.selectedCompanyId()),
  );
  protected readonly publishedCount = computed(
    () => this.lodgings().filter((item) => item.estado === 'PUBLICADO').length,
  );
  protected readonly publishedRooms = computed(
    () => this.rooms().filter((room) => room.estado === 'PUBLICADO').length,
  );

  /** Todos los campos del hospedaje. Las pestañas solo deciden qué mostrar. */
  protected readonly lodgingForm = this.fb.nonNullable.group({
    nombre: ['', Validators.required],
    descripcion: [''],
    ciudad_id: [0, [Validators.required, Validators.min(1)]],
    localidad: [''],
    moneda_codigo: ['BOB', Validators.required],
    capacidad_maxima: [1, [Validators.required, Validators.min(1)]],
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
   * en la capacidad total, pero su suma no se valida acá. Una habitación de 4
   * plazas con hasta 4 adultos y hasta 3 niños es válida — son combinaciones que
   * nunca se dan al mismo tiempo. La suma se comprueba al reservar.
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

  /** Una habitación publicada no puede costar 0: fijaría el precio del hotel en 0. */
  protected readonly priceWarning = computed(() => {
    const { precio_base, estado } = this.roomForm.getRawValue();
    return estado === 'PUBLICADO' && Number(precio_base) <= 0
      ? 'Una habitación publicada debe tener un precio por noche mayor a 0.'
      : null;
  });

  /** Si no hay ninguna habitación publicada con precio, el hotel no se puede publicar. */
  protected readonly canPublishLodging = computed(() =>
    this.rooms().some((room) => room.estado === 'PUBLICADO' && Number(room.precio_noche) > 0),
  );

  ngOnInit(): void {
    const sessionCompanies = this.auth.session()?.user.tenants.map((item) => ({ id: item.id, name: item.name })) ?? [];
    forkJoin({
      types: this.lodgingService.listTypes(),
      currencies: this.productsService.listCurrencies(),
      cities: this.companiesService.listCities(),
    }).subscribe({
      next: ({ types, currencies, cities }) => {
        this.lodgingTypes.set(types);
        this.currencies.set(currencies);
        this.cities.set(cities);
        if (this.isSuperAdmin()) {
          this.companiesService.list('', 'ACTIVO').subscribe({
            next: (companies) => this.initializeCompanies(
              companies.map((item) => ({ id: item.id, name: item.nombre_comercial })),
            ),
            error: () => this.failLoading('No fue posible cargar las empresas.'),
          });
        } else this.initializeCompanies(sessionCompanies);
      },
      error: () => this.failLoading('No fue posible cargar los catálogos de hospedaje. Verifica que las migraciones estén aplicadas.'),
    });
  }

  private initializeCompanies(companies: CompanyChoice[]): void {
    this.companies.set(companies);
    if (!companies.length) return this.failLoading('Tu cuenta no tiene una empresa activa asignada.');
    this.selectedCompanyId.set(companies[0].id);
    this.loadLodgings();
  }

  private failLoading(message: string): void {
    this.loading.set(false);
    this.errorMessage.set(message);
  }

  protected changeCompany(event: Event): void {
    this.selectedCompanyId.set(Number((event.target as HTMLSelectElement).value));
    this.backToList();
    this.loadLodgings();
  }

  protected loadLodgings(): void {
    const companyId = this.selectedCompanyId();
    if (!companyId) return;
    this.loading.set(true);
    this.errorMessage.set(null);
    this.lodgingService.listCompanyLodgings(companyId).subscribe({
      next: (lodgings) => { this.lodgings.set(lodgings); this.loading.set(false); },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        this.errorMessage.set(apiErrorMessage(error, 'No fue posible cargar los hospedajes.'));
      },
    });
  }

  // --- Navegación ---------------------------------------------------------

  protected backToList(): void {
    this.view.set('list');
    this.selectedLodging.set(null);
    this.showRoomForm.set(false);
    this.editingRoom.set(null);
    this.rooms.set([]);
    this.lodgingFormError.set(null);
    this.imageUploadError.set(null);
  }

  protected startCreate(): void {
    this.selectedLodging.set(null);
    this.selectedServices.set([]);
    this.lodgingFormError.set(null);
    this.imageUploadError.set(null);
    this.lodgingForm.reset({
      ciudad_id: this.cities()[0]?.id ?? 0,
      moneda_codigo: this.currencies()[0]?.codigo ?? 'BOB',
      capacidad_maxima: 1,
      estado: 'BORRADOR',
      tipo_hospedaje_codigo: 'HOTEL',
    });
    this.view.set('create');
  }

  protected openLodging(lodging: LodgingEstablishment, tab: Tab = 'general'): void {
    this.selectedLodging.set(lodging);
    this.selectedServices.set([...lodging.servicios]);
    this.lodgingFormError.set(null);
    this.imageUploadError.set(null);
    this.lodgingForm.setValue({
      nombre: lodging.nombre,
      descripcion: lodging.descripcion ?? '',
      ciudad_id: lodging.ciudad_id,
      localidad: lodging.localidad ?? '',
      moneda_codigo: lodging.moneda_codigo,
      capacidad_maxima: lodging.capacidad_maxima,
      estado: lodging.estado,
      imagen_url: lodging.imagen_url ?? '',
      tipo_hospedaje_codigo: lodging.tipo_hospedaje_codigo,
      direccion: lodging.direccion ?? '',
      categoria_estrellas: lodging.categoria_estrellas?.toString() ?? '',
      hora_check_in: this.toTimeInput(lodging.hora_check_in),
      hora_check_out: this.toTimeInput(lodging.hora_check_out),
    });
    this.activeTab.set(tab);
    this.view.set('detail');
    this.loadRooms(lodging.id);
  }

  protected selectTab(tab: Tab): void {
    this.activeTab.set(tab);
  }

  // --- Hospedaje ----------------------------------------------------------

  protected toggleService(name: string): void {
    this.selectedServices.update((items) =>
      items.includes(name) ? items.filter((item) => item !== name) : [...items, name],
    );
  }

  protected hasService(name: string): boolean {
    return this.selectedServices().includes(name);
  }

  protected submitLodging(): void {
    const companyId = this.selectedCompanyId();
    if (!companyId || this.lodgingForm.invalid) { this.lodgingForm.markAllAsTouched(); return; }
    const raw = this.lodgingForm.getRawValue();
    const payload: LodgingPayload = {
      nombre: raw.nombre.trim(),
      descripcion: raw.descripcion.trim() || undefined,
      ciudad_id: Number(raw.ciudad_id),
      localidad: raw.localidad.trim() || undefined,
      moneda_codigo: raw.moneda_codigo,
      capacidad_maxima: Number(raw.capacidad_maxima),
      estado: raw.estado,
      imagen_url: raw.imagen_url.trim() || undefined,
      tipo_hospedaje_codigo: raw.tipo_hospedaje_codigo,
      direccion: raw.direccion.trim() || undefined,
      categoria_estrellas: raw.categoria_estrellas ? Number(raw.categoria_estrellas) : null,
      hora_check_in: raw.hora_check_in || null,
      hora_check_out: raw.hora_check_out || null,
      servicios: this.selectedServices(),
    };

    const editing = this.selectedLodging();
    this.savingLodging.set(true);
    this.lodgingFormError.set(null);
    const request = editing
      ? this.lodgingService.updateLodging(companyId, editing.id, payload)
      : this.lodgingService.createLodging(companyId, payload);

    request.subscribe({
      next: (lodging) => {
        this.lodgings.update((items) =>
          editing ? items.map((item) => (item.id === lodging.id ? lodging : item)) : [lodging, ...items],
        );
        this.savingLodging.set(false);
        this.successMessage.set(editing ? 'Hospedaje actualizado.' : 'Hospedaje creado. Ahora puedes registrar sus habitaciones.');
        if (editing) this.selectedLodging.set(lodging);
        else this.openLodging(lodging, 'habitaciones');
      },
      error: (error: HttpErrorResponse) => {
        this.savingLodging.set(false);
        this.lodgingFormError.set(apiErrorMessage(error, 'No fue posible guardar el hospedaje.'));
      },
    });
  }

  protected toggleLodgingPublication(lodging: LodgingEstablishment): void {
    const companyId = this.selectedCompanyId();
    if (!companyId) return;
    const estado: ProductStatus = lodging.estado === 'PUBLICADO' ? 'BORRADOR' : 'PUBLICADO';
    this.lodgingService.updateLodging(companyId, lodging.id, { estado }).subscribe({
      next: (updated) => {
        this.lodgings.update((items) => items.map((item) => (item.id === updated.id ? updated : item)));
        if (this.selectedLodging()?.id === updated.id) this.selectedLodging.set(updated);
      },
      error: (error: HttpErrorResponse) =>
        this.errorMessage.set(apiErrorMessage(error, 'No fue posible cambiar la publicación.')),
    });
  }

  protected deactivateLodging(lodging: LodgingEstablishment): void {
    const companyId = this.selectedCompanyId();
    if (!companyId) return;
    const confirmed = confirm(
      `¿Desactivar “${lodging.nombre}”?\n\nSus habitaciones dejarán de aparecer en el Marketplace mientras el hospedaje esté inactivo.`,
    );
    if (!confirmed) return;
    this.lodgingService.deactivateLodging(companyId, lodging.id).subscribe({
      next: (updated) => {
        this.lodgings.update((items) => items.map((item) => (item.id === updated.id ? updated : item)));
        if (this.selectedLodging()?.id === updated.id) this.selectedLodging.set(updated);
        this.successMessage.set('Hospedaje desactivado.');
      },
      error: (error: HttpErrorResponse) =>
        this.errorMessage.set(apiErrorMessage(error, 'No fue posible desactivar el hospedaje.')),
    });
  }

  // --- Habitaciones -------------------------------------------------------

  protected loadRooms(lodgingId: number): void {
    const companyId = this.selectedCompanyId();
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
    const companyId = this.selectedCompanyId();
    const lodging = this.selectedLodging();
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
        this.refreshSelectedLodging();
      },
      error: (error: HttpErrorResponse) => {
        this.savingRoom.set(false);
        this.roomFormError.set(apiErrorMessage(error, 'No fue posible guardar la habitación.'));
      },
    });
  }

  protected toggleRoomPublication(room: Room): void {
    const companyId = this.selectedCompanyId();
    if (!companyId) return;
    const estado: ProductStatus = room.estado === 'PUBLICADO' ? 'BORRADOR' : 'PUBLICADO';
    this.lodgingService.updateRoom(companyId, room.id, { estado }).subscribe({
      next: (updated) => {
        this.rooms.update((items) => items.map((item) => (item.id === updated.id ? updated : item)));
        this.refreshSelectedLodging();
      },
      error: (error: HttpErrorResponse) =>
        this.errorMessage.set(apiErrorMessage(error, 'No fue posible cambiar la publicación.')),
    });
  }

  protected deactivateRoom(room: Room): void {
    const companyId = this.selectedCompanyId();
    if (!companyId || !confirm(`¿Desactivar “${room.nombre}”?`)) return;
    this.lodgingService.deactivateRoom(companyId, room.id).subscribe({
      next: (updated) => {
        this.rooms.update((items) => items.map((item) => (item.id === updated.id ? updated : item)));
        this.refreshSelectedLodging();
        this.successMessage.set('Habitación desactivada.');
      },
      error: (error: HttpErrorResponse) =>
        this.errorMessage.set(apiErrorMessage(error, 'No fue posible desactivar la habitación.')),
    });
  }

  /** El precio "desde" y el conteo los calcula el backend: hay que releerlos. */
  private refreshSelectedLodging(): void {
    const companyId = this.selectedCompanyId();
    const lodging = this.selectedLodging();
    if (!companyId || !lodging) return;
    this.lodgingService.listCompanyLodgings(companyId).subscribe({
      next: (lodgings) => {
        this.lodgings.set(lodgings);
        const updated = lodgings.find((item) => item.id === lodging.id);
        if (updated) this.selectedLodging.set(updated);
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

  // --- Utilidades de presentación ----------------------------------------

  /** El backend devuelve "14:00:00"; <input type="time"> espera "14:00". */
  private toTimeInput(value: string | null): string {
    return value ? value.slice(0, 5) : '';
  }

  protected cityLabel(cityId: number): string {
    const city = this.cities().find((item) => item.id === cityId);
    return city ? `${city.nombre}, ${city.pais}` : '—';
  }

  protected stars(count: number | null): number[] {
    return count ? Array.from({ length: count }, (_, index) => index) : [];
  }
}
