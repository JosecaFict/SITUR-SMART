import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { LucideArrowLeft, LucideBadgePercent, LucideCircleAlert, LucidePackageOpen, LucidePencil, LucidePlus, LucideTrash2 } from '@lucide/angular';
import { AuthService } from '../../../core/auth/auth.service';
import { boliviaToday } from '../../../core/products/departure-dates';
import { ProductDeparture, TourismProduct } from '../../../core/products/products.models';
import { ProductsService } from '../../../core/products/products.service';
import { fromBoliviaInput, toBoliviaInput } from '../../../core/promotions/promotion-dates';
import { Promotion, PromotionComponent, PromotionComponentInput, PromotionEvaluation, PromotionMode, PromotionPayload } from '../../../core/promotions/promotions.models';
import { promotionApiError, PromotionsService } from '../../../core/promotions/promotions.service';

const CATALOG_PAGE_SIZE = 9;

@Component({
  selector: 'situr-promocion-editor',
  imports: [DatePipe, RouterLink, LucideArrowLeft, LucideBadgePercent, LucideCircleAlert, LucidePackageOpen, LucidePencil, LucidePlus, LucideTrash2],
  templateUrl: './promocion-editor.html',
  styleUrls: ['../../viajero/paquete-editor.css', './promocion-editor.css'],
})
export class PromocionEditor implements OnInit, OnDestroy {
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly service = inject(PromotionsService);
  private readonly productsService = inject(ProductsService);
  private previewTimer: ReturnType<typeof setTimeout> | null = null;
  private previewVersion = 0;
  private departureVersion = 0;

  protected readonly today = boliviaToday();
  protected readonly tenantId = signal<number | null>(null);
  protected readonly mode = signal<PromotionMode>('EXISTENTE');
  protected readonly current = signal<Promotion | null>(null);
  protected readonly products = signal<TourismProduct[]>([]);
  protected readonly loading = signal(false);
  protected readonly catalogLoading = signal(false);
  protected readonly working = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly success = signal<string | null>(null);
  protected readonly previewError = signal<string | null>(null);
  protected readonly previewLoading = signal(false);
  protected readonly preview = signal<PromotionEvaluation | null>(null);
  protected readonly isNew = this.route.snapshot.paramMap.get('id') === null;
  protected readonly editing = this.isNew || this.route.snapshot.url.some((part) => part.path === 'editar');
  protected readonly canManage = computed(() => this.auth.session()?.user.permisos.includes('PRODUCTOS_GESTIONAR') ?? false);

  protected readonly name = signal('');
  protected readonly description = signal('');
  protected readonly productId = signal<number | null>(null);
  protected readonly percentage = signal('');
  protected readonly startsAt = signal('');
  protected readonly endsAt = signal('');
  protected readonly selectedProduct = computed(() => this.products().find((item) => item.id === this.productId()) ?? null);
  protected readonly changed = computed(() => {
    const item = this.current();
    return !item || this.name().trim() !== item.nombre || this.description().trim() !== item.descripcion ||
      Number(this.percentage()) !== Number(item.porcentaje_descuento) ||
      this.startsAt() !== toBoliviaInput(item.inicio) || this.endsAt() !== toBoliviaInput(item.fin);
  });
  protected readonly evaluation = computed(() => this.changed() ? this.preview() : (this.preview() ?? this.current()));

  protected readonly search = signal('');
  protected readonly category = signal('');
  protected readonly catalogPage = signal(1);
  protected readonly categoryOptions = computed(() => Array.from(new Set(this.products().map((item) => item.tipo_codigo)))
    .map((code) => ({ code, label: code === 'HABITACION' ? 'Hospedajes' : this.products().find((item) => item.tipo_codigo === code)?.tipo ?? code })));
  protected readonly filteredProducts = computed(() => {
    const query = this.search().trim().toLocaleLowerCase('es');
    return this.products().filter((item) => (!this.category() || item.tipo_codigo === this.category()) &&
      (!query || [item.nombre, item.ciudad, item.localidad].join(' ').toLocaleLowerCase('es').includes(query)));
  });
  protected readonly catalogPages = computed(() => Math.max(1, Math.ceil(this.filteredProducts().length / CATALOG_PAGE_SIZE)));
  protected readonly visibleProducts = computed(() => this.filteredProducts().slice((this.catalogPage() - 1) * CATALOG_PAGE_SIZE, this.catalogPage() * CATALOG_PAGE_SIZE));

  protected readonly chosenProduct = signal<TourismProduct | null>(null);
  protected readonly editingComponentId = signal<number | null>(null);
  protected readonly serviceDate = signal('');
  protected readonly serviceEnd = signal('');
  protected readonly quantity = signal(1);
  protected readonly guests = signal(1);
  protected readonly departureId = signal<number | null>(null);
  protected readonly departures = signal<ProductDeparture[]>([]);
  protected readonly departuresLoading = signal(false);
  protected readonly componentError = signal<string | null>(null);
  protected readonly minServiceDate = computed(() => {
    const start = this.startsAt().slice(0, 10);
    return start > this.today ? start : this.today;
  });

  ngOnInit(): void {
    const tenants = this.auth.session()?.user.tenants ?? [];
    const requested = Number(this.route.snapshot.queryParamMap.get('empresa'));
    const tenant = tenants.some((item) => item.id === requested) ? requested : tenants[0]?.id;
    if (!tenant) { this.error.set('No tienes una empresa activa asignada.'); return; }
    this.tenantId.set(tenant);
    const mode = this.route.snapshot.queryParamMap.get('modalidad');
    if (mode === 'COMBINADO') this.mode.set(mode);
    const id = Number(this.route.snapshot.paramMap.get('id'));
    if (id) this.load(id);
    else this.loadEligible();
  }

  ngOnDestroy(): void {
    if (this.previewTimer) clearTimeout(this.previewTimer);
    ++this.previewVersion;
    ++this.departureVersion;
  }

  protected load(id: number): void {
    const tenant = this.tenantId();
    if (!tenant) return;
    this.loading.set(true); this.error.set(null);
    this.service.getCompany(tenant, id).subscribe({
      next: (item) => { this.accept(item, true); this.loading.set(false); this.loadEligible(); },
      error: (error: HttpErrorResponse) => { this.loading.set(false); this.error.set(promotionApiError(error)); },
    });
  }

  private accept(item: Promotion, fillForm: boolean): void {
    this.current.set(item);
    this.preview.set(item);
    this.previewError.set(null);
    if (fillForm) {
      this.mode.set(item.modalidad);
      this.name.set(item.nombre);
      this.description.set(item.descripcion);
      this.productId.set(item.producto_id);
      this.percentage.set(item.porcentaje_descuento);
      this.startsAt.set(toBoliviaInput(item.inicio));
      this.endsAt.set(toBoliviaInput(item.fin));
    }
  }

  protected loadEligible(): void {
    const tenant = this.tenantId();
    if (!tenant) return;
    this.catalogLoading.set(true);
    this.service.eligible(tenant, this.mode()).subscribe({
      next: (items) => { this.products.set(items); this.catalogLoading.set(false); },
      error: (error: HttpErrorResponse) => { this.catalogLoading.set(false); this.error.set(promotionApiError(error, 'No se pudo cargar el catálogo elegible.')); },
    });
  }

  protected changeField(field: 'name' | 'description' | 'percentage' | 'startsAt' | 'endsAt', value: string): void {
    this[field].set(value);
    this.schedulePreview();
  }

  protected chooseProduct(value: string): void {
    this.productId.set(Number(value) || null);
    this.schedulePreview();
  }

  private payload(): PromotionPayload | null {
    const start = this.startsAt(), end = this.endsAt();
    if (!this.name().trim() || !start || !end || !Number.isFinite(Date.parse(fromBoliviaInput(start))) ||
      !Number.isFinite(Date.parse(fromBoliviaInput(end))) || Date.parse(fromBoliviaInput(end)) <= Date.parse(fromBoliviaInput(start)) ||
      Date.parse(fromBoliviaInput(end)) <= Date.now() || !(Number(this.percentage()) > 0 && Number(this.percentage()) < 100) ||
      (this.mode() === 'EXISTENTE' && !this.productId())) return null;
    const components: PromotionComponentInput[] = this.mode() === 'COMBINADO'
      ? (this.current()?.componentes ?? []).map((item) => ({ producto_id: item.producto_id, fecha_inicio: item.fecha_inicio,
          fecha_fin: item.fecha_fin ?? null, cantidad: item.cantidad, huespedes: item.huespedes ?? null, salida_id: item.salida_id ?? null }))
      : [];
    return { modalidad: this.mode(), producto_id: this.mode() === 'EXISTENTE' ? this.productId() : null,
      nombre: this.name().trim(), descripcion: this.description().trim(), porcentaje_descuento: this.percentage(),
      inicio: fromBoliviaInput(start), fin: fromBoliviaInput(end), componentes: components };
  }

  protected schedulePreview(): void {
    ++this.previewVersion;
    if (this.previewTimer) clearTimeout(this.previewTimer);
    this.preview.set(null); this.previewError.set(null);
    const payload = this.payload(), tenant = this.tenantId();
    if (!payload || !tenant) { this.previewLoading.set(false); return; }
    const version = this.previewVersion;
    this.previewLoading.set(true);
    this.previewTimer = setTimeout(() => this.service.preview(tenant, payload).subscribe({
      next: (result) => { if (version !== this.previewVersion) return; this.preview.set(result); this.previewLoading.set(false); },
      error: (error: HttpErrorResponse) => { if (version !== this.previewVersion) return; this.previewLoading.set(false); this.previewError.set(promotionApiError(error, 'No se pudo cotizar la oferta.')); },
    }), 350);
  }

  protected save(): void {
    const tenant = this.tenantId(), payload = this.payload();
    if (!tenant || !this.canManage() || !this.editing || this.working()) return;
    if (!payload) { this.error.set('Completa nombre, paquete si corresponde, porcentaje entre 0 y 100 y fechas de vigencia válidas.'); return; }
    this.working.set(true); this.error.set(null); this.success.set(null);
    const existing = this.current();
    const request = existing
      ? this.service.update(tenant, existing.id, { nombre: payload.nombre, descripcion: payload.descripcion,
          porcentaje_descuento: payload.porcentaje_descuento, inicio: payload.inicio, fin: payload.fin })
      : this.service.create(tenant, { ...payload, componentes: [] });
    request.subscribe({
      next: (item) => {
        this.accept(item, true); this.working.set(false);
        this.success.set(existing ? 'Promoción actualizada.' : 'Borrador guardado. Ya puedes agregar servicios o publicarlo.');
        if (!existing) this.router.navigate(['/promociones', item.id, 'editar'], { replaceUrl: true, queryParams: { empresa: tenant } });
      },
      error: (error: HttpErrorResponse) => { this.working.set(false); this.error.set(promotionApiError(error, 'No se pudo guardar la promoción.')); },
    });
  }

  protected publish(): void {
    const item = this.current(), tenant = this.tenantId();
    if (!tenant || !item || !this.canManage() || this.changed() || this.working()) return;
    this.working.set(true); this.error.set(null); this.success.set(null);
    this.service.publish(tenant, item.id).subscribe({
      next: (updated) => { this.accept(updated, false); this.working.set(false); this.success.set('Promoción publicada.'); },
      error: (error: HttpErrorResponse) => { this.working.set(false); this.error.set(promotionApiError(error, 'No se pudo publicar.')); },
    });
  }

  protected deactivate(): void {
    const item = this.current(), tenant = this.tenantId();
    if (!tenant || !item || !this.canManage() || this.working() || !confirm('¿Desactivar esta promoción? Dejará de mostrarse públicamente.')) return;
    this.working.set(true); this.error.set(null); this.success.set(null);
    this.service.deactivate(tenant, item.id).subscribe({
      next: (updated) => { this.accept(updated, false); this.working.set(false); this.success.set('Promoción desactivada.'); },
      error: (error: HttpErrorResponse) => { this.working.set(false); this.error.set(promotionApiError(error, 'No se pudo desactivar.')); },
    });
  }

  protected recalculate(): void {
    const item = this.current(), tenant = this.tenantId();
    if (!tenant || !item) return;
    this.previewLoading.set(true);
    this.service.recalculate(tenant, item.id).subscribe({
      next: (updated) => { this.current.set(updated); this.preview.set(updated); this.previewLoading.set(false); },
      error: (error: HttpErrorResponse) => { this.previewLoading.set(false); this.previewError.set(promotionApiError(error)); },
    });
  }

  protected setSearch(value: string): void { this.search.set(value); this.catalogPage.set(1); }
  protected setCategory(value: string): void { this.category.set(value); this.catalogPage.set(1); }
  protected nextCatalogPage(): void { this.catalogPage.update((value) => Math.min(this.catalogPages(), value + 1)); }
  protected previousCatalogPage(): void { this.catalogPage.update((value) => Math.max(1, value - 1)); }

  protected choose(product: TourismProduct, component?: PromotionComponent): void {
    if (this.current()?.estado_administrativo === 'HABILITADA') return;
    this.chosenProduct.set(product);
    this.editingComponentId.set(component?.id ?? null);
    this.serviceDate.set(component?.fecha_inicio ?? this.minServiceDate());
    this.serviceEnd.set(component?.fecha_fin ?? '');
    this.quantity.set(component?.cantidad ?? 1);
    this.guests.set(component?.huespedes ?? 1);
    this.departureId.set(component?.salida_id ?? null);
    this.componentError.set(null);
    this.loadDepartures();
  }

  protected editComponent(component: PromotionComponent): void {
    const product = this.products().find((item) => item.id === component.producto_id);
    if (!product) { this.componentError.set('Este producto ya no es elegible. Puedes quitarlo y seleccionar otro.'); return; }
    this.choose(product, component);
  }

  protected cancelSelection(): void { ++this.departureVersion; this.chosenProduct.set(null); this.departures.set([]); this.componentError.set(null); }
  protected changeServiceDate(value: string): void { this.serviceDate.set(value); this.departureId.set(null); this.loadDepartures(); }
  protected changeQuantity(value: number): void { this.quantity.set(value); if (this.guests() < value) this.guests.set(value); }

  private loadDepartures(): void {
    const item = this.chosenProduct(), day = this.serviceDate(), version = ++this.departureVersion;
    this.departures.set([]); this.departuresLoading.set(false);
    if (!item || !['TOUR', 'EXPERIENCIA'].includes(item.tipo_codigo) || !day) return;
    this.departuresLoading.set(true);
    this.productsService.publicDepartures(item.id, day).subscribe({
      next: (slots) => { if (version !== this.departureVersion) return; this.departures.set(slots); this.departuresLoading.set(false); },
      error: (error: HttpErrorResponse) => { if (version !== this.departureVersion) return; this.departuresLoading.set(false); this.componentError.set(promotionApiError(error, 'No se pudieron cargar las salidas.')); },
    });
  }

  protected slotAllowed(slot: ProductDeparture): boolean {
    return !slot.cerrado && slot.cupos_restantes >= this.quantity() && Date.parse(slot.inicio) > Date.now();
  }

  protected saveComponent(): void {
    const offer = this.current(), tenant = this.tenantId(), product = this.chosenProduct();
    if (!tenant || !offer || !product || !this.canManage() || offer.estado_administrativo === 'HABILITADA' || this.working()) return;
    if (!this.serviceDate() || this.serviceDate() < this.minServiceDate() || this.quantity() < 1 || this.quantity() > 500) {
      this.componentError.set('Revisa la fecha y la cantidad del servicio.'); return;
    }
    const room = product.tipo_codigo === 'HABITACION';
    if (room && (!this.serviceEnd() || this.serviceEnd() <= this.serviceDate() || this.guests() < this.quantity())) {
      this.componentError.set('Indica salida posterior a la llegada y huéspedes suficientes.'); return;
    }
    const slot = this.departureId() === null ? null : this.departures().find((item) => item.id === this.departureId());
    if (slot && !this.slotAllowed(slot)) { this.componentError.set('La salida está cerrada o sin cupos suficientes.'); return; }
    const payload: PromotionComponentInput = { producto_id: product.id, fecha_inicio: this.serviceDate(), cantidad: this.quantity(),
      ...(room ? { fecha_fin: this.serviceEnd(), huespedes: this.guests() } : {}),
      ...(['TOUR', 'EXPERIENCIA'].includes(product.tipo_codigo) && this.departureId() ? { salida_id: this.departureId()! } : {}) };
    this.working.set(true); this.componentError.set(null); this.error.set(null);
    const componentId = this.editingComponentId();
    const request = componentId === null ? this.service.addComponent(tenant, offer.id, payload)
      : this.service.updateComponent(tenant, offer.id, componentId, payload);
    request.subscribe({
      next: (updated) => { this.accept(updated, false); this.working.set(false); this.cancelSelection(); this.success.set(componentId === null ? 'Servicio agregado.' : 'Servicio actualizado.'); },
      error: (error: HttpErrorResponse) => { this.working.set(false); this.componentError.set(promotionApiError(error, 'No se pudo guardar el servicio.')); },
    });
  }

  protected removeComponent(component: PromotionComponent): void {
    const offer = this.current(), tenant = this.tenantId();
    if (!offer || !tenant || !this.canManage() || offer.estado_administrativo === 'HABILITADA' || this.working() ||
      !confirm(`¿Quitar «${component.nombre ?? 'este servicio'}» de la oferta?`)) return;
    this.working.set(true); this.error.set(null);
    this.service.removeComponent(tenant, offer.id, component.id).subscribe({
      next: (updated) => { this.accept(updated, false); this.working.set(false); this.success.set('Servicio eliminado.'); },
      error: (error: HttpErrorResponse) => { this.working.set(false); this.error.set(promotionApiError(error, 'No se pudo quitar el servicio.')); },
    });
  }
}
