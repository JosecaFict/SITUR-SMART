import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import {
  LucideCalendarDays, LucideCircleAlert, LucideClock, LucideCompass, LucideEye, LucideEyeOff,
  LucideImage, LucideMapPin, LucidePencil, LucidePlus, LucideRefreshCw, LucideUserCheck, LucideX,
} from '@lucide/angular';
import { AuthService } from '../../../core/auth/auth.service';
import { CompaniesService } from '../../../core/companies/companies.service';
import { apiErrorMessage } from '../../../core/http/api-error';
import { ProductStatus } from '../../../core/products/products.models';
import { Tour, TourTypeCode } from '../../../core/tours/tours.models';
import { ToursService } from '../../../core/tours/tours.service';

interface CompanyChoice { id: number; name: string; }
type TypeFilter = 'TODOS' | TourTypeCode;

/**
 * Tours y experiencias de la empresa. La ficha, el alta y las salidas viven en
 * sus propias pantallas, cada una con su URL.
 */
@Component({
  selector: 'situr-tours-lista',
  imports: [
    DatePipe, LucideCalendarDays, LucideCircleAlert, LucideClock, LucideCompass, LucideEye, LucideEyeOff,
    LucideImage, LucideMapPin, LucidePencil, LucidePlus, LucideRefreshCw, LucideUserCheck, LucideX,
  ],
  templateUrl: './tours-lista.html',
})
export class ToursLista implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly companiesService = inject(CompaniesService);
  private readonly toursService = inject(ToursService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  protected readonly companies = signal<CompanyChoice[]>([]);
  protected readonly selectedCompanyId = signal<number | null>(null);
  protected readonly tours = signal<Tour[]>([]);
  protected readonly loading = signal(true);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly successMessage = signal<string | null>(null);
  protected readonly typeFilter = signal<TypeFilter>('TODOS');

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
  protected readonly visibleTours = computed(() => {
    const filter = this.typeFilter();
    return filter === 'TODOS' ? this.tours() : this.tours().filter((tour) => tour.tipo_codigo === filter);
  });
  protected readonly publishedCount = computed(() => this.tours().filter((tour) => tour.estado === 'PUBLICADO').length);
  protected readonly isEmpty = computed(() => !this.loading() && this.tours().length === 0);

  ngOnInit(): void {
    const fromQuery = Number(this.route.snapshot.queryParamMap.get('empresa')) || null;
    const sessionCompanies = this.auth.session()?.user.tenants.map((item) => ({ id: item.id, name: item.name })) ?? [];
    if (this.isSuperAdmin()) {
      this.companiesService.list('', 'ACTIVO').subscribe({
        next: (companies) =>
          this.initializeCompanies(companies.map((item) => ({ id: item.id, name: item.nombre_comercial })), fromQuery),
        error: () => this.failLoading('No fue posible cargar las empresas.'),
      });
    } else this.initializeCompanies(sessionCompanies, fromQuery);
  }

  private initializeCompanies(companies: CompanyChoice[], preferred: number | null): void {
    this.companies.set(companies);
    if (!companies.length) return this.failLoading('Tu cuenta no tiene una empresa activa asignada.');
    const chosen = companies.find((item) => item.id === preferred) ?? companies[0];
    this.selectedCompanyId.set(chosen.id);
    this.loadTours();
  }

  private failLoading(message: string): void {
    this.loading.set(false);
    this.errorMessage.set(message);
  }

  protected changeCompany(event: Event): void {
    this.selectedCompanyId.set(Number((event.target as HTMLSelectElement).value));
    this.loadTours();
  }

  protected loadTours(): void {
    const companyId = this.selectedCompanyId();
    if (!companyId) return;
    this.loading.set(true);
    this.errorMessage.set(null);
    this.toursService.list(companyId).subscribe({
      next: (tours) => { this.tours.set(tours); this.loading.set(false); },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        this.errorMessage.set(apiErrorMessage(error, 'No fue posible cargar los tours.'));
      },
    });
  }

  // --- Navegación ---------------------------------------------------------

  private companyParam(): { empresa: number } | undefined {
    const companyId = this.selectedCompanyId();
    return companyId ? { empresa: companyId } : undefined;
  }

  protected goToNew(): void {
    this.router.navigate(['/tours/nuevo'], { queryParams: this.companyParam() });
  }

  protected goToTour(tour: Tour): void {
    this.router.navigate(['/tours', tour.id], { queryParams: this.companyParam() });
  }

  protected goToDepartures(tour: Tour): void {
    this.router.navigate(['/tours', tour.id, 'salidas'], { queryParams: this.companyParam() });
  }

  protected goToGuides(): void {
    this.router.navigate(['/guias'], { queryParams: this.companyParam() });
  }

  // --- Publicación --------------------------------------------------------

  /**
   * Lo que le falta para publicarse, para avisarlo antes de intentarlo.
   * El backend vuelve a comprobarlo (y además mira el límite del plan).
   */
  protected missing(tour: Tour): string | null {
    if (!tour.detalle) return 'Completa su ficha: desde ahí se vende por salidas.';
    if (Number(tour.precio_base) <= 0) return 'Indica un precio por persona.';
    if (!tour.detalle.punto_encuentro) return 'Indica el punto de encuentro.';
    if (!tour.salidas_proximas) return 'Programa al menos una salida.';
    return null;
  }

  protected togglePublication(tour: Tour): void {
    const companyId = this.selectedCompanyId();
    if (!companyId) return;
    const estado: ProductStatus = tour.estado === 'PUBLICADO' ? 'BORRADOR' : 'PUBLICADO';
    this.errorMessage.set(null);
    this.successMessage.set(null);
    this.toursService.update(companyId, tour.id, { estado }).subscribe({
      next: (updated) => {
        this.tours.update((items) => items.map((item) => (item.id === updated.id ? updated : item)));
        this.successMessage.set(updated.estado === 'PUBLICADO' ? 'Tour publicado.' : 'Tour retirado del Marketplace.');
      },
      error: (error: HttpErrorResponse) =>
        this.errorMessage.set(apiErrorMessage(error, 'No fue posible cambiar la publicación.')),
    });
  }

  protected imageError(event: Event): void {
    (event.target as HTMLImageElement).style.display = 'none';
  }
}
