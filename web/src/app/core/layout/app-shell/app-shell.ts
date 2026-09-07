import { Component, HostListener, computed, inject, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import {
  LucideBuilding2,
  LucideCompass,
  LucideLayoutDashboard,
  LucideLogOut,
  LucideMenu,
  LucidePackageOpen,
  LucideScrollText,
  LucideShieldCheck,
  LucideUser,
  LucideUsers,
  LucideX,
} from '@lucide/angular';
import { AuthService } from '../../auth/auth.service';

interface NavItem {
  label: string;
  path: string;
  icon: 'dashboard' | 'companies' | 'products' | 'roles' | 'users' | 'audit' | 'profile' | 'explore';
  superAdminOnly?: boolean;
  hideForSuperAdmin?: boolean;
  hideForCustomer?: boolean;
  customerOnly?: boolean;
  permission?: string;
}

@Component({
  selector: 'situr-app-shell',
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    LucideBuilding2,
    LucideCompass,
    LucideLayoutDashboard,
    LucideLogOut,
    LucideMenu,
    LucidePackageOpen,
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

  protected readonly session = this.auth.session;
  protected readonly menuOpen = signal(false);

  private readonly allNavItems: NavItem[] = [
    { label: 'Dashboard', path: '/dashboard', icon: 'dashboard' },
    { label: 'Explorar', path: '/', icon: 'explore' },
    { label: 'Mi Perfil', path: '/perfil', icon: 'profile' },
    {
      label: 'Empresas',
      path: '/empresas',
      icon: 'companies',
      superAdminOnly: true,
      hideForCustomer: true,
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
      if (item.hideForCustomer && isCustomer) return false;
      if (item.superAdminOnly && !isSuperAdmin) return false;
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
