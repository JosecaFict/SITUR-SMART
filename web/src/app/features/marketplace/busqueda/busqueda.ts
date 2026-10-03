import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
  LucideArrowLeft,
  LucideArrowRight,
  LucideChevronDown,
  LucideCircleAlert,
  LucideMapPin,
  LucideSearch,
  LucideX,
} from '@lucide/angular';
import { forkJoin } from 'rxjs';
import { City, Country } from '../../../core/companies/companies.models';
import { CompaniesService } from '../../../core/companies/companies.service';
import { ProductType, TourismProduct } from '../../../core/products/products.models';
import { ProductsService } from '../../../core/products/products.service';
import { AuthService } from '../../../core/auth/auth.service';

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
    LucideX,
  ],
  templateUrl: './busqueda.html',
  styleUrl: './busqueda.css',
})
export class Busqueda implements OnInit {
  private readonly formBuilder = inject(FormBuilder);
  private readonly productsService = inject(ProductsService);
  private readonly companiesService = inject(CompaniesService);
  private readonly auth = inject(AuthService);

  protected readonly session = this.auth.session;
  protected readonly isAuthenticated = this.auth.isAuthenticated;

  protected readonly products = signal<TourismProduct[]>([]);
  protected readonly countries = signal<Country[]>([]);
  protected readonly cities = signal<City[]>([]);
  protected readonly types = signal<ProductType[]>([]);
  protected readonly loading = signal(true);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly validationMessage = signal<string | null>(null);
  protected readonly selectedType = signal('');
  protected readonly selectedCountryId = signal(0);
  protected readonly expandedProductId = signal<number | null>(null);
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
    orden: ['recientes' as 'recientes' | 'precio_asc' | 'precio_desc' | 'nombre'],
  });

  protected readonly filteredCities = computed(() => {
    const countryId = this.selectedCountryId();
    return countryId ? this.cities().filter((city) => city.pais_id === countryId) : this.cities();
  });

  ngOnInit(): void {
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
    this.productsService
      .listMarketplace({
        buscar: raw.buscar.trim() || undefined,
        pais: raw.pais ? Number(raw.pais) : undefined,
        ciudad: raw.ciudad ? Number(raw.ciudad) : undefined,
        localidad: raw.localidad.trim() || undefined,
        tipo: raw.tipo || undefined,
        precio_min: minimum,
        precio_max: maximum,
        orden: raw.orden,
        page: this.page(),
        page_size: this.pageSize,
      })
      .subscribe({
        next: (response) => {
          this.products.set(response.results);
          this.total.set(response.count);
          this.loading.set(false);
        },
        error: (error: HttpErrorResponse) => {
          this.loading.set(false);
          this.errorMessage.set(
            error.status === 0
              ? 'No se pudo conectar con el backend.'
              : 'No se pudieron obtener los productos. Revisa los filtros e inténtalo otra vez.',
          );
        },
      });
  }

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

  protected toggleDetails(productId: number): void {
    this.expandedProductId.update((current) => (current === productId ? null : productId));
  }

  protected productImage(product: TourismProduct): string {
    return product.imagen_url || '/images/auth-carousel/Hotel4.webp';
  }

  protected imageError(event: Event): void {
    (event.target as HTMLImageElement).src = '/images/auth-carousel/Hotel4.webp';
  }

  private parsePrice(value: string): number | undefined {
    if (!value.trim()) return undefined;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
}
