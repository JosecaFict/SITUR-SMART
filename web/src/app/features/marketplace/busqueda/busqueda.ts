import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
  LucideCalendarDays,
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

@Component({
  selector: 'situr-busqueda',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    LucideCalendarDays,
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

  protected readonly products = signal<TourismProduct[]>([]);
  protected readonly countries = signal<Country[]>([]);
  protected readonly cities = signal<City[]>([]);
  protected readonly types = signal<ProductType[]>([]);
  protected readonly loading = signal(true);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly selectedType = signal('');
  protected readonly selectedCountryId = signal(0);
  protected readonly expandedProductId = signal<number | null>(null);
  protected readonly today = this.localDate(new Date());

  protected readonly filterForm = this.formBuilder.nonNullable.group({
    pais: [''],
    ciudad: [''],
    localidad: [''],
    tipo: [''],
    fecha: [''],
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

  protected search(): void {
    this.loading.set(true);
    this.errorMessage.set(null);
    const raw = this.filterForm.getRawValue();
    this.selectedType.set(raw.tipo);
    this.productsService
      .listMarketplace({
        pais: raw.pais ? Number(raw.pais) : undefined,
        ciudad: raw.ciudad ? Number(raw.ciudad) : undefined,
        localidad: raw.localidad.trim() || undefined,
        tipo: raw.tipo || undefined,
        fecha: raw.fecha || undefined,
      })
      .subscribe({
        next: (products) => {
          this.products.set(products);
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
    this.filterForm.reset();
    this.selectedCountryId.set(0);
    this.search();
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

  private localDate(value: Date): string {
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, '0');
    const day = String(value.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }
}
