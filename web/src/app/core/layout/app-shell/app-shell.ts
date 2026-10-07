import { Component, HostListener, computed, inject, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import {
  LucideBedDouble,
  LucideBuilding2,
  LucideCompass,
  LucideCreditCard,
  LucideDatabaseBackup,
  LucideLayoutDashboard,
  LucideLogOut,
  LucideMenu,
  LucideMapPinned,
  LucidePackageOpen,
  LucideChartNoAxesCombined,
  LucideScrollText,
  LucideShieldCheck,
  LucideUser,
  LucideUsers,
  LucideX,
} from '@lucide/angular';
import { AuthService } from '../../auth/auth.service';
import { MyPlanService } from '../../subscription/my-plan.service';

interface NavItem {
  label: string;
  path: string;
  icon: 'dashboard' | 'companies' | 'locations' | 'backups' | 'products' | 'lodging' | 'roles' | 'users' | 'audit' | 'reports' | 'profile' | 'explore' | 'plan';
  superAdminOnly?: boolean;
  anyPermission?: string[];
  anyRole?: string[];
  hideForSuperAdmin?: boolean;
  hideForCustomer?: boolean;
  customerOnly?: boolean;
  /** Solo para quien pertenece a una empresa. */
  tenantOnly?: boolean;
  permission?: string;
}

@Component({
  selector: 'situr-app-shell',
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    LucideBedDouble,
    LucideBuilding2,
    LucideCompass,
  LucideCreditCard,
    LucideDatabaseBackup,
    LucideLayoutDashboard,
    LucideLogOut,
    LucideMenu,
    LucideMapPinned,
    LucidePackageOpen,
    LucideChartNoAxesCombined,
    LucideScrollText,
    LucideShieldCheck,
    LucideUser,
    LucideUsers,
    LucideX,
  ],
  templateUrl: './app-shell.html',
  styleUrl: './app-shell.css',
})
export class AppShell {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  private readonly myPlan = inject(MyPlanService);

  protected readonly session = this.auth.session;
  protected readonly menuOpen = signal(false);

  /** Aviso arriba de todo cuando el plan de la empresa vence pronto o ya venció. */
  protected readonly planAlert = signal<{ message: string; restricted: boolean } | null>(null);

  constructor() {
    const user = this.session()?.user;
    const tenantId = user && !user.roles.includes('SUPER_ADMIN') ? user.tenants[0]?.id : undefined;
    if (tenantId === undefined) return;
    this.myPlan.get(tenantId).subscribe({
      next: (plan) => {
        if (plan.restringida) {
          this.planAlert.set({
            restricted: true,
            message: 'El plan de tu empresa venció: tus productos no se muestran y no puedes crear ni publicar oferta.',
          });
        } else if (plan.estado === 'POR_VENCER' && plan.dias_restantes !== null) {
          const when = plan.dias_restantes <= 1 ? 'mañana' : `en ${plan.dias_restantes} días`;
          this.planAlert.set({ restricted: false, message: `Tu plan vence ${when}.` });
        }
      },
      // Sin aviso si no se pudo consultar: no tiene que romper el panel.
      error: () => this.planAlert.set(null),
    });
  }

  private readonly allNavItems: NavItem[] = [
    { label: 'Dashboard', path: '/dashboard', icon: 'dashboard' },
    { label: 'Explorar', path: '/', icon: 'explore' },
    { label: 'Mi Perfil', path: '/perfil', icon: 'profile' },
    {
      label: 'Empresas',
      path: '/empresas',
      icon: 'companies',
      anyPermission: ['TENANTS_LEER', 'TENANTS_GESTIONAR'],
      anyRole: ['TENANT_ADMIN'],
      hideForCustomer: true,
    },
    {
      label: 'Clientes',
      path: '/clientes',
      icon: 'users',
      hideForCustomer: true,
      permission: 'CLIENTES_GESTIONAR',
    },
    {
      label: 'Países y ciudades',
      path: '/ubicaciones',
      icon: 'locations',
      superAdminOnly: true,
      hideForCustomer: true,
    },
    {
      label: 'Copias de seguridad',
      path: '/copias-seguridad',
      icon: 'backups',
      superAdminOnly: true,
      hideForCustomer: true,
    },
    {
      label: 'Mi plan',
      path: '/mi-plan',
      icon: 'plan',
      hideForSuperAdmin: true,
      hideForCustomer: true,
      tenantOnly: true,
    },
    {
      label: 'Empleados',
      path: '/usuarios',
      icon: 'users',
      hideForSuperAdmin: true,
      hideForCustomer: true,
      permission: 'USUARIOS_GESTIONAR',
    },
    {
      label: 'Roles y permisos',
      path: '/roles',
      icon: 'roles',
      hideForCustomer: true,
      permission: 'ROLES_GESTIONAR',
    },
    {
      label: 'Catálogo',
      path: '/productos',
      icon: 'products',
      hideForCustomer: true,
      permission: 'PRODUCTOS_LEER',
    },
    {
      label: 'Hospedajes',
      path: '/hospedajes',
      icon: 'lodging',
      hideForCustomer: true,
      permission: 'PRODUCTOS_LEER',
    },
    {
      label: 'Reportes',
      path: '/reportes',
      icon: 'reports',
      hideForCustomer: true,
      anyPermission: ['REPORTES_GLOBALES', 'REPORTES_TENANT'],
    },
    {
      label: 'Bitácora',
      path: '/bitacora',
      icon: 'audit',
      hideForCustomer: true,
      permission: 'BITACORA_LEER',
    },
  ];

  protected readonly navItems = computed(() => {
    const roles = this.session()?.user.roles ?? [];
    const isSuperAdmin = roles.includes('SUPER_ADMIN');
    const isCustomer = roles.includes('CLIENTE') && !isSuperAdmin && (this.session()?.user.tenants.length ?? 0) === 0;
    const permissions = this.session()?.user.permisos ?? [];

    return this.allNavItems.filter((item) => {
      if (item.customerOnly && !isCustomer) return false;
      if (item.tenantOnly && (this.session()?.user.tenants.length ?? 0) === 0) return false;
      if (item.hideForCustomer && isCustomer) return false;
      if (item.superAdminOnly && !isSuperAdmin) return false;
      if (item.anyPermission && !isSuperAdmin) {
        const hasPermission = item.anyPermission.some((permission) =>
          permissions.includes(permission),
        );
        const hasRole = item.anyRole?.some((role) => roles.includes(role)) ?? false;
        if (!hasPermission && !hasRole) return false;
      }
      if (item.hideForSuperAdmin && isSuperAdmin) return false;
      if (item.permission && !isSuperAdmin && !permissions.includes(item.permission)) return false;
      return true;
    });
  });

  @HostListener('document:keydown.escape')
  protected closeMenu(): void {
    this.menuOpen.set(false);
  }

  protected toggleMenu(): void {
    this.menuOpen.update((open) => !open);
  }

  protected logout(): void {
    this.closeMenu();
    this.auth.logout();
    this.router.navigateByUrl('/login');
  }
}
