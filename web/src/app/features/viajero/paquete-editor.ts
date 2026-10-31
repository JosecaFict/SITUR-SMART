import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import {
  LucideArrowLeft,
  LucideArrowRight,
  LucideCalendarDays,
  LucideCheckCircle2,
  LucideCircleAlert,
  LucideMapPin,
  LucidePackageOpen,
  LucidePencil,
  LucidePlus,
  LucideSave,
  LucideSearch,
  LucideStar,
  LucideTag,
  LucideTrash2,
  LucideUsers,
} from '@lucide/angular';
import { CompaniesService } from '../../core/companies/companies.service';
import { City } from '../../core/companies/companies.models';
import { apiErrorMessage } from '../../core/http/api-error';
import { ComponentPayload, CustomPackage, PackageComponent, PackageQuote } from '../../core/packages/packages.models';
import { PackagesService } from '../../core/packages/packages.service';
import { ProductDeparture, ProductType, TourismProduct } from '../../core/products/products.models';
import { ProductsService } from '../../core/products/products.service';

type Selection = TourismProduct | PackageComponent;
type CatalogSort = 'recientes' | 'precio_asc' | 'precio_desc' | 'nombre';
const CATEGORY_CODES = new Set(['TOUR', 'EXPERIENCIA', 'HABITACION', 'ATRACCION', 'RESTAURANTE']);

@Component({
  selector: 'situr-paquete-editor',
  imports: [
    DatePipe, RouterLink, LucideArrowLeft, LucideArrowRight, LucideCalendarDays,
    LucideCheckCircle2, LucideCircleAlert, LucideMapPin, LucidePackageOpen,
    LucidePencil, LucidePlus, LucideSave, LucideSearch, LucideStar,
    LucideTag, LucideTrash2, LucideUsers,
  ],
  templateUrl: './paquete-editor.html',
  styleUrl: './paquete-editor.css',
})
export class PaqueteEditor implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly service = inject(PackagesService);
  private readonly productsService = inject(ProductsService);
  private readonly companies = inject(CompaniesService);

  protected readonly package = signal<CustomPackage | null>(null);
  protected readonly products = signal<TourismProduct[]>([]);
  protected readonly cities = signal<City[]>([]);
  protected readonly types = signal<ProductType[]>([]);
  protected readonly loading = signal(false);
  protected readonly catalogLoading = signal(false);
  protected readonly working = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly success = signal<string | null>(null);
  protected readonly totalProducts = signal(0);
  protected readonly page = signal(1);
  protected readonly selected = signal<Selection | null>(null);
  protected readonly editingId = signal<number | null>(null);
  protected readonly departures = signal<ProductDeparture[]>([]);
  protected readonly departuresLoading = signal(false);
  protected readonly quote = signal<PackageQuote | null>(null);
  protected readonly step = signal(1);

  protected readonly name = signal('');
  protected readonly cityId = signal<number | null>(null);
  protected readonly start = signal('');
  protected readonly end = signal('');
  protected readonly travelers = signal(1);
  protected readonly category = signal('');
  protected readonly sortOrder = signal<CatalogSort>('recientes');
  protected readonly search = signal('');
  protected readonly categoryOptions = computed(() => this.types()
    .filter((type) => CATEGORY_CODES.has(type.codigo))
    .map((type) => ({ ...type, nombre: type.codigo === 'HABITACION' ? 'Hospedajes' : type.nombre })));
  protected readonly sortedProducts = computed(() => {
    const products = [...this.products()];
    switch (this.sortOrder()) {
      case 'precio_asc': return products.sort((a, b) => Number(a.precio_base) - Number(b.precio_base));
      case 'precio_desc': return products.sort((a, b) => Number(b.precio_base) - Number(a.precio_base));
      case 'nombre': return products.sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'));
      default: return products;
    }
  });
  protected readonly itemStart = signal('');
  protected readonly itemEnd = signal('');
  protected readonly quantity = signal(1);
  protected readonly guests = signal(1);
  protected readonly departureId = signal<number | null>(null);

  ngOnInit(): void {
    this.companies.listCities().subscribe({ next: (cities) => this.cities.set(cities) });
    this.productsService.listTypes().subscribe({ next: (types) => this.types.set(types) });
    const id = Number(this.route.snapshot.paramMap.get('id'));
    if (id) this.load(id);
    this.loadCatalog();
  }

  protected load(id: number): void {
    this.loading.set(true);
    this.service.get(id).subscribe({
      next: (item) => { this.accept(item); this.loading.set(false); },
      error: (error: HttpErrorResponse) => { this.error.set(apiErrorMessage(error)); this.loading.set(false); },
    });
  }

  private accept(item: CustomPackage): void {
    this.package.set(item);
    this.name.set(item.nombre);
    this.cityId.set(item.ciudad_id);
    this.start.set(item.fecha_inicio);
    this.end.set(item.fecha_fin);
    this.travelers.set(item.personas);
  }

  protected saveTrip(): void {
    this.error.set(null); this.success.set(null);
    if (!this.name().trim() || !this.start() || !this.end() || this.end() < this.start() || this.travelers() < 1) {
      this.error.set('Escribe un nombre, fechas válidas y la cantidad de personas.'); return;
    }
    const payload = { nombre: this.name().trim(), ciudad_id: this.cityId(), fecha_inicio: this.start(), fecha_fin: this.end(), personas: this.travelers() };
    this.working.set(true);
    const existing = this.package();
    const request = existing ? this.service.update(existing.id, payload) : this.service.create(payload);
    request.subscribe({
      next: (item) => {
        this.accept(item); this.working.set(false); this.step.set(1);
        this.success.set(existing ? 'Datos del viaje actualizados. Revisa los servicios antes de guardar.' : 'Borrador creado. Selecciona tus servicios.');
        if (!existing) this.router.navigate(['/paquetes', item.id, 'editar'], { replaceUrl: true });
        this.page.set(1); this.loadCatalog();
      },
      error: (error: HttpErrorResponse) => { this.error.set(apiErrorMessage(error)); this.working.set(false); },
    });
  }

  protected loadCatalog(): void {
    this.catalogLoading.set(true);
    this.service.catalog({ ciudad: this.cityId() || undefined, tipo: this.category() || undefined,
      buscar: this.search() || undefined, page: this.page(), page_size: 12 }).subscribe({
      next: (result) => { this.products.set(result.results); this.totalProducts.set(result.count); this.catalogLoading.set(false); },
      error: (error: HttpErrorResponse) => { this.error.set(apiErrorMessage(error)); this.catalogLoading.set(false); },
    });
  }

  protected searchCatalog(): void { this.page.set(1); this.loadCatalog(); }
  protected selectCategory(value: string): void { this.category.set(value); this.searchCatalog(); }
  protected setSort(value: string): void { this.sortOrder.set(value as CatalogSort); }
  protected inPackage(productId: number): boolean {
    return this.package()?.componentes?.some((part) => part.producto_id === productId) ?? false;
  }
  protected nights(start: string, end: string | null): number {
    return end ? Math.max(0, (Date.parse(`${end}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`)) / 86_400_000) : 0;
  }
  protected nextPage(): void { this.page.update((value) => value + 1); this.loadCatalog(); }
  protected previousPage(): void { this.page.update((value) => Math.max(1, value - 1)); this.loadCatalog(); }

  protected productId(item: Selection): number { return 'producto_id' in item ? item.producto_id : item.id; }
  protected productType(item: Selection): string { return item.tipo_codigo; }
  protected productName(item: Selection): string { return item.nombre; }
  protected productLink(item: TourismProduct): string {
    return item.tipo_codigo === 'HABITACION' && item.hospedaje_id
      ? `/marketplace/hospedajes/${item.hospedaje_id}` : `/marketplace/productos/${item.id}`;
  }

  protected choose(item: Selection, componentId: number | null = null): void {
    const packageValue = this.package();
    if (!packageValue) { this.error.set('Primero crea el borrador con las fechas del viaje.'); return; }
    this.selected.set(item); this.editingId.set(componentId); this.step.set(1);
    this.itemStart.set(componentId ? (item as PackageComponent).fecha_inicio : packageValue.fecha_inicio);
    this.itemEnd.set(componentId ? ((item as PackageComponent).fecha_fin || '') :
      item.tipo_codigo === 'HABITACION' ? (packageValue.fecha_fin > packageValue.fecha_inicio ? packageValue.fecha_fin : this.nextDay(packageValue.fecha_fin)) : '');
    this.quantity.set(componentId ? (item as PackageComponent).cantidad : 1);
    this.guests.set(componentId ? ((item as PackageComponent).huespedes || packageValue.personas) : packageValue.personas);
    this.departureId.set(componentId ? (item as PackageComponent).salida_id : null);
    this.quote.set(null); this.error.set(null); this.success.set(null);
    this.loadDepartures();
  }

  private nextDay(value: string): string {
    const date = new Date(`${value}T00:00:00Z`);
    date.setUTCDate(date.getUTCDate() + 1);
    return date.toISOString().slice(0, 10);
  }

  protected selectionChanged(): void { this.quote.set(null); this.error.set(null); }
  protected dateChanged(value: string): void {
    this.itemStart.set(value); this.departureId.set(null); this.selectionChanged(); this.loadDepartures();
  }

  protected loadDepartures(): void {
    const item = this.selected();
    this.departures.set([]);
    if (!item || !['TOUR', 'EXPERIENCIA'].includes(item.tipo_codigo) || !this.itemStart()) return;
    this.departuresLoading.set(true);
    this.productsService.publicDepartures(this.productId(item), this.itemStart()).subscribe({
      next: (items) => { this.departures.set(items); this.departuresLoading.set(false); },
      error: (error: HttpErrorResponse) => { this.error.set(apiErrorMessage(error)); this.departuresLoading.set(false); },
    });
  }

  private componentPayload(): ComponentPayload | null {
    const item = this.selected();
    if (!item) return null;
    return { producto_id: this.productId(item), fecha_inicio: this.itemStart(),
      fecha_fin: item.tipo_codigo === 'HABITACION' ? this.itemEnd() : null,
      cantidad: this.quantity(), huespedes: item.tipo_codigo === 'HABITACION' ? this.guests() : null,
      salida_id: this.departureId() };
  }

  protected check(): void {
    const packageValue = this.package(); const payload = this.componentPayload();
    if (!packageValue || !payload) return;
    this.quote.set(null); this.error.set(null); this.working.set(true);
    this.service.quote(packageValue.id, { ...payload, componente_id: this.editingId() || undefined }).subscribe({
      next: (quote) => { this.quote.set(quote); this.working.set(false); },
      error: (error: HttpErrorResponse) => { this.error.set(apiErrorMessage(error)); this.working.set(false); },
    });
  }

  protected addOrUpdate(): void {
    const packageValue = this.package(); const payload = this.componentPayload();
    if (!packageValue || !payload || !this.quote()) return;
    this.working.set(true); this.error.set(null);
    const id = this.editingId();
    const request = id ? this.service.change(packageValue.id, id, payload) : this.service.add(packageValue.id, payload);
    request.subscribe({
      next: (updated) => { this.accept(updated); this.selected.set(null); this.quote.set(null); this.working.set(false);
        this.success.set(id ? 'Servicio actualizado.' : 'Servicio agregado al paquete.'); },
      error: (error: HttpErrorResponse) => { this.error.set(apiErrorMessage(error)); this.quote.set(null); this.working.set(false); },
    });
  }

  protected remove(componentId: number): void {
    const item = this.package(); if (!item) return;
    this.working.set(true); this.error.set(null);
    this.service.remove(item.id, componentId).subscribe({
      next: (updated) => { this.accept(updated); this.working.set(false); this.success.set('Servicio quitado del paquete.'); },
      error: (error: HttpErrorResponse) => { this.error.set(apiErrorMessage(error)); this.working.set(false); },
    });
  }

  protected review(): void { this.step.set(2); this.selected.set(null); this.error.set(null); }
  protected revalidate(): void {
    const item = this.package(); if (!item) return;
    this.working.set(true); this.error.set(null);
    this.service.validate(item.id, false).subscribe({
      next: (updated) => { this.accept(updated); this.working.set(false); this.success.set('Precios y cupos comprobados de nuevo.'); },
      error: (error: HttpErrorResponse) => { this.error.set(apiErrorMessage(error)); this.working.set(false); this.load(item.id); },
    });
  }
  protected save(): void {
    const item = this.package(); if (!item) return;
    this.working.set(true); this.error.set(null); this.step.set(3);
    this.service.validate(item.id, true).subscribe({
      next: (saved) => { this.accept(saved); this.working.set(false); this.router.navigate(['/paquetes', saved.id]); },
      error: (error: HttpErrorResponse) => { this.error.set(apiErrorMessage(error)); this.working.set(false); this.step.set(2); this.load(item.id); },
    });
  }
}
