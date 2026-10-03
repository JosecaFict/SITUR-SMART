import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import {
  LucideBedDouble, LucideBuilding2, LucideCircleAlert, LucideEye, LucideEyeOff,
  LucideImage, LucideMapPin, LucidePencil, LucidePlus, LucideRefreshCw, LucideStar,
  LucideX,
} from '@lucide/angular';
import { AuthService } from '../../../core/auth/auth.service';
import { CompaniesService } from '../../../core/companies/companies.service';
import { apiErrorMessage } from '../../../core/http/api-error';
import { LodgingEstablishment } from '../../../core/lodging/lodging.models';
import { LodgingService } from '../../../core/lodging/lodging.service';
import { ProductStatus } from '../../../core/products/products.models';

interface CompanyChoice { id: number; name: string; }

/**
 * Lista de hospedajes de la empresa, o el estado vacío que empuja a registrar
 * el primero. La ficha y el alta viven en HospedajeDetalle, cada una con su
 * propia URL.
 */
@Component({
  selector: 'situr-hospedajes-lista',
  imports: [
    LucideBedDouble, LucideBuilding2, LucideCircleAlert, LucideEye, LucideEyeOff,
    LucideImage, LucideMapPin, LucidePencil, LucidePlus, LucideRefreshCw, LucideStar,
    LucideX,
  ],
  templateUrl: './hospedajes-lista.html',
})
export class HospedajesLista implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly companiesService = inject(CompaniesService);
  private readonly lodgingService = inject(LodgingService);
  private readonly router = inject(Router);

  protected readonly companies = signal<CompanyChoice[]>([]);
  protected readonly selectedCompanyId = signal<number | null>(null);
  protected readonly lodgings = signal<LodgingEstablishment[]>([]);
  protected readonly loading = signal(true);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly successMessage = signal<string | null>(null);

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
  /** Distingue "no hay hoteles" de "todavía estoy cargando". */
  protected readonly isEmpty = computed(() => !this.loading() && this.lodgings().length === 0);

  ngOnInit(): void {
    const sessionCompanies = this.auth.session()?.user.tenants.map((item) => ({ id: item.id, name: item.name })) ?? [];
    if (this.isSuperAdmin()) {
      this.companiesService.list('', 'ACTIVO').subscribe({
        next: (companies) => this.initializeCompanies(
          companies.map((item) => ({ id: item.id, name: item.nombre_comercial })),
        ),
        error: () => this.failLoading('No fue posible cargar las empresas.'),
      });
    } else this.initializeCompanies(sessionCompanies);
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
  // La empresa viaja en la URL para que la ficha funcione con enlace directo y
  // sobreviva a un recargado, sin depender de estado compartido en memoria.

  private companyParam(): { empresa: number } | undefined {
    const companyId = this.selectedCompanyId();
    return companyId ? { empresa: companyId } : undefined;
  }

  protected goToNew(): void {
    this.router.navigate(['/hospedajes/nuevo'], { queryParams: this.companyParam() });
  }

  protected goToLodging(lodging: LodgingEstablishment): void {
    this.router.navigate(['/hospedajes', lodging.id], { queryParams: this.companyParam() });
  }

  protected goToRooms(lodging: LodgingEstablishment): void {
    this.router.navigate(['/hospedajes', lodging.id, 'habitaciones'], {
      queryParams: this.companyParam(),
    });
  }

  // --- Publicación --------------------------------------------------------

  /** Un hotel sin habitación publicada con precio no se puede publicar. */
  protected canPublish(lodging: LodgingEstablishment): boolean {
    return lodging.precio_desde !== null;
  }

  protected togglePublication(lodging: LodgingEstablishment): void {
    const companyId = this.selectedCompanyId();
    if (!companyId) return;
    const estado: ProductStatus = lodging.estado === 'PUBLICADO' ? 'BORRADOR' : 'PUBLICADO';
    this.errorMessage.set(null);
    this.lodgingService.updateLodging(companyId, lodging.id, { estado }).subscribe({
      next: (updated) => {
        this.lodgings.update((items) => items.map((item) => (item.id === updated.id ? updated : item)));
        this.successMessage.set(
          updated.estado === 'PUBLICADO' ? 'Hospedaje publicado.' : 'Hospedaje retirado del Marketplace.',
        );
      },
      error: (error: HttpErrorResponse) =>
        this.errorMessage.set(apiErrorMessage(error, 'No fue posible cambiar la publicación.')),
    });
  }

  protected imageError(event: Event): void {
    (event.target as HTMLImageElement).style.display = 'none';
  }

  protected stars(count: number | null): number[] {
    return count ? Array.from({ length: count }, (_, index) => index) : [];
  }
}
