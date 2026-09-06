import { DatePipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import {
  LucideArrowRight,
  LucideBuilding2,
  LucideCalendarClock,
  LucideCheck,
  LucideCheckCircle2,
  LucideCircleAlert,
  LucideClock3,
  LucideExternalLink,
  LucideFilePenLine,
  LucideHotel,
  LucideImage,
  LucideLayers,
  LucideMapPin,
  LucidePackageOpen,
  LucidePencil,
  LucidePlus,
  LucideRefreshCw,
  LucideScrollText,
  LucideShieldAlert,
  LucideShieldCheck,
  LucideSparkles,
  LucideTrendingUp,
  LucideUsers,
} from '@lucide/angular';
import { catchError, forkJoin, of } from 'rxjs';
import { AuthService } from '../../../core/auth/auth.service';
import { Company, CompanyStatus } from '../../../core/companies/companies.models';
import { CompaniesService } from '../../../core/companies/companies.service';
import { ProductType, TourismProduct } from '../../../core/products/products.models';
import { ProductsService } from '../../../core/products/products.service';
import { Role } from '../../../core/rbac/rbac.models';
import { RbacService } from '../../../core/rbac/rbac.service';
import { TenantUser } from '../../../core/users/users.models';
import { UsersService } from '../../../core/users/users.service';

export interface CompanyChoice {
  id: number;
  name: string;
}

export interface AttentionItem {
  product: TourismProduct;
  issues: string[];
  severity: 'high' | 'medium';
}

export interface CategorySummary {
  code: string;
  name: string;
  count: number;
  percentage: number;
  publishedCount: number;
}

@Component({
  selector: 'situr-dashboard',
  imports: [
    DatePipe,
    RouterLink,
    LucideArrowRight,
    LucideBuilding2,
    LucideCalendarClock,
    LucideCheck,
    LucideCheckCircle2,
    LucideCircleAlert,
    LucideClock3,
    LucideExternalLink,
    LucideFilePenLine,
    LucideHotel,
    LucideImage,
    LucideLayers,
    LucideMapPin,
    LucidePackageOpen,
    LucidePencil,
    LucidePlus,
    LucideRefreshCw,
    LucideScrollText,
    LucideShieldAlert,
    LucideShieldCheck,
    LucideSparkles,
    LucideTrendingUp,
    LucideUsers,
  ],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class Dashboard implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly companiesService = inject(CompaniesService);
  private readonly productsService = inject(ProductsService);
  private readonly usersService = inject(UsersService);
  private readonly rbacService = inject(RbacService);

  protected readonly session = this.auth.session;
  protected readonly loading = signal(true);
  protected readonly errorMessage = signal<string | null>(null);

  // Raw data signals
  protected readonly companies = signal<Company[]>([]);
  protected readonly companyChoices = signal<CompanyChoice[]>([]);
  protected readonly selectedCompanyId = signal<number | null>(null);
  protected readonly products = signal<TourismProduct[]>([]);
  protected readonly users = signal<TenantUser[]>([]);
  protected readonly roles = signal<Role[]>([]);
  protected readonly productTypes = signal<ProductType[]>([]);

  // Permissions & user computed properties
  protected readonly isSuperAdmin = computed(
    () => this.session()?.user.roles.includes('SUPER_ADMIN') ?? false,
  );
  protected readonly selectedCompany = computed(() =>
    this.companyChoices().find((company) => company.id === this.selectedCompanyId()),
  );
  protected readonly canManageProducts = computed(
    () => this.session()?.user.permisos.includes('PRODUCTOS_GESTIONAR') ?? false,
  );
  protected readonly canManageUsers = computed(
    () => this.session()?.user.permisos.includes('USUARIOS_GESTIONAR') ?? false,
  );
  protected readonly canManageRoles = computed(
    () => this.session()?.user.permisos.includes('ROLES_GESTIONAR') ?? false,
  );
  protected readonly canReadAudit = computed(
    () => this.session()?.user.permisos.includes('BITACORA_LEER') ?? false,
  );

  // Tenant metrics
  protected readonly publishedCount = computed(
    () => this.products().filter((product) => product.estado === 'PUBLICADO').length,
  );
  protected readonly draftCount = computed(
    () => this.products().filter((product) => product.estado === 'BORRADOR').length,
  );
  protected readonly inactiveCount = computed(
    () => this.products().filter((product) => product.estado === 'INACTIVO').length,
  );
  protected readonly employeeCount = computed(
    () => this.users().filter((user) => !user.roles.includes('TENANT_ADMIN')).length,
  );
  protected readonly customRoleCount = computed(
    () => this.roles().filter((role) => role.tenant_id === this.selectedCompanyId()).length,
  );

  protected readonly attentionItems = computed<AttentionItem[]>(() =>
    this.products()
      .map((product) => {
        const issues = this.productIssues(product);
        const hasMissingMedia = !product.imagen_url?.trim();
        return {
          product,
          issues,
          severity: hasMissingMedia ? ('high' as const) : ('medium' as const),
        };
      })
      .filter((item) => item.issues.length > 0)
      .sort((a, b) => {
        if (a.severity === 'high' && b.severity !== 'high') return -1;
        if (a.severity !== 'high' && b.severity === 'high') return 1;
        return b.issues.length - a.issues.length;
      })
      .slice(0, 4),
  );

  protected readonly recentProducts = computed(() =>
    [...this.products()]
      .sort(
        (a, b) =>
          new Date(b.actualizado_en).getTime() - new Date(a.actualizado_en).getTime(),
      )
      .slice(0, 5),
  );

  protected readonly categories = computed<CategorySummary[]>(() => {
    const products = this.products();
    const totalProducts = products.length;
    const maxCount = Math.max(
      1,
      ...this.productTypes().map(
        (type) => products.filter((product) => product.tipo_codigo === type.codigo).length,
      ),
    );

    return this.productTypes()
      .map((type) => {
        const categoryProducts = products.filter((product) => product.tipo_codigo === type.codigo);
        const count = categoryProducts.length;
        const publishedCount = categoryProducts.filter((p) => p.estado === 'PUBLICADO').length;
        return {
          code: type.codigo,
          name: type.nombre,
          count,
          percentage: totalProducts > 0 ? Math.round((count / totalProducts) * 100) : 0,
          publishedCount,
        };
      })
      .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, 'es'));
  });

  protected readonly categoriesWithProductsCount = computed(
    () => this.categories().filter((c) => c.count > 0).length,
  );

  // SuperAdmin metrics
  protected readonly activeCompanies = computed(
    () => this.companies().filter((company) => company.estado === 'ACTIVO').length,
  );
  protected readonly pendingCompanies = computed(
    () => this.companies().filter((company) => company.estado === 'PENDIENTE').length,
  );
  protected readonly pausedCompanies = computed(
    () =>
      this.companies().filter(
        (company) => company.estado === 'SUSPENDIDO' || company.estado === 'INACTIVO',
      ).length,
  );
  protected readonly activationRate = computed(() => {
    const total = this.companies().length;
    return total > 0 ? Math.round((this.activeCompanies() / total) * 100) : 0;
  });

  protected readonly pendingCompaniesList = computed(() =>
    this.companies()
      .filter((company) => company.estado === 'PENDIENTE')
      .sort(
        (a, b) => new Date(b.creado_en).getTime() - new Date(a.creado_en).getTime(),
      ),
  );

  protected readonly recentCompanies = computed(() =>
    [...this.companies()]
      .sort(
        (a, b) => new Date(b.creado_en).getTime() - new Date(a.creado_en).getTime(),
      )
      .slice(0, 6),
  );

  ngOnInit(): void {
    if (this.isSuperAdmin()) {
      this.loadPlatformSummary();
      return;
    }

    const choices =
      this.session()?.user.tenants.map((tenant) => ({ id: tenant.id, name: tenant.name })) ?? [];
    this.companyChoices.set(choices);
    if (!choices.length) {
      this.loading.set(false);
      this.errorMessage.set('Tu cuenta no tiene una empresa asignada todavía.');
      return;
    }
    this.selectedCompanyId.set(choices[0].id);
    this.loadCompanySummary();
  }

  protected changeCompany(event: Event): void {
    const companyId = Number((event.target as HTMLSelectElement).value);
    this.selectedCompanyId.set(companyId);
    this.loadCompanySummary();
  }

  protected reload(): void {
    if (this.isSuperAdmin()) {
      this.loadPlatformSummary();
    } else {
      this.loadCompanySummary();
    }
  }

  protected statusLabel(status: TourismProduct['estado']): string {
    return { PUBLICADO: 'Publicado', BORRADOR: 'Borrador', INACTIVO: 'Inactivo' }[status] ?? status;
  }

  protected statusClass(status: TourismProduct['estado']): string {
    return {
      PUBLICADO: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-600/20',
      BORRADOR: 'bg-amber-50 text-amber-700 ring-1 ring-amber-600/20',
      INACTIVO: 'bg-gray-100 text-gray-600 ring-1 ring-gray-400/20',
    }[status] ?? 'bg-gray-100 text-gray-600';
  }

  protected companyStatusLabel(status: CompanyStatus): string {
    return {
      ACTIVO: 'Activa',
      PENDIENTE: 'Pendiente',
      SUSPENDIDO: 'Suspendida',
      INACTIVO: 'Inactiva',
    }[status] ?? status;
  }

  protected companyStatusBadgeClass(status: CompanyStatus): string {
    return {
      ACTIVO: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-600/20',
      PENDIENTE: 'bg-amber-50 text-amber-700 ring-1 ring-amber-600/20',
      SUSPENDIDO: 'bg-rose-50 text-rose-700 ring-1 ring-rose-600/20',
      INACTIVO: 'bg-gray-100 text-gray-600 ring-1 ring-gray-400/20',
    }[status] ?? 'bg-gray-100 text-gray-600';
  }

  private loadPlatformSummary(): void {
    this.loading.set(true);
    this.errorMessage.set(null);
    this.companiesService.list().subscribe({
      next: (companies) => {
        this.companies.set(companies);
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.errorMessage.set('No fue posible cargar el resumen de empresas de la plataforma.');
      },
    });
  }

  private loadCompanySummary(): void {
    const companyId = this.selectedCompanyId();
    if (!companyId) return;

    const permissions = this.session()?.user.permisos ?? [];
    const canReadProducts = permissions.includes('PRODUCTOS_LEER');
    const canReadUsers = permissions.includes('USUARIOS_GESTIONAR');
    const canReadRoles = permissions.includes('ROLES_GESTIONAR');

    this.loading.set(true);
    this.errorMessage.set(null);
    forkJoin({
      products: canReadProducts
        ? this.productsService.listCompanyProducts(companyId).pipe(catchError(() => of(null)))
        : of(null),
      users: canReadUsers
        ? this.usersService.listUsers(companyId).pipe(catchError(() => of(null)))
        : of(null),
      roles: canReadRoles
        ? this.rbacService.listRoles(companyId).pipe(catchError(() => of(null)))
        : of(null),
      types: this.productsService.listTypes().pipe(catchError(() => of(null))),
    }).subscribe(({ products, users, roles, types }) => {
      this.products.set(products ?? []);
      this.users.set(users ?? []);
      this.roles.set(roles ?? []);
      this.productTypes.set(types ?? []);
      this.loading.set(false);

      const requestedSources = [
        canReadProducts && products,
        canReadUsers && users,
        canReadRoles && roles,
      ];
      if (requestedSources.some((source) => source === null)) {
        this.errorMessage.set(
          'Algunos datos no pudieron actualizarse. Puedes reintentar sin perder la información visible.',
        );
      }
    });
  }

  private productIssues(product: TourismProduct): string[] {
    const issues: string[] = [];
    if (!product.imagen_url?.trim()) issues.push('Sin fotografía de portada');
    if (product.estado === 'BORRADOR') issues.push('En borrador');
    if (!product.descripcion?.trim()) issues.push('Sin descripción');
    if (!product.localidad?.trim()) issues.push('Sin localidad');
    if (Number(product.precio_base) <= 0) issues.push('Sin precio base establecido');
    return issues;
  }
}
