import { Component, HostListener, computed, inject, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import {
  LucideLayoutDashboard,
  LucideBuilding2,
  LucideLogOut,
  LucideMenu,
  LucidePackageOpen,
  LucideScrollText,
  LucideShieldCheck,
  LucideUsers,
  LucideX,
} from '@lucide/angular';
import { AuthService } from '../../auth/auth.service';

interface NavItem {
  label: string;
  path: string;
  icon: 'dashboard' | 'companies' | 'products' | 'roles' | 'users' | 'audit';
  superAdminOnly?: boolean;
  hideForSuperAdmin?: boolean;
  permission?: string;
}

@Component({
  selector: 'situr-app-shell',
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    LucideBuilding2,
    LucideLayoutDashboard,
    LucideLogOut,
    LucideMenu,
    LucidePackageOpen,
    LucideScrollText,
    LucideShieldCheck,
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
    {
      label: 'Empresas',
      path: '/empresas',
      icon: 'companies',
      superAdminOnly: true,
    },
    {
      label: 'Empleados',
      path: '/usuarios',
      icon: 'users',
      hideForSuperAdmin: true,
      permission: 'USUARIOS_GESTIONAR',
    },
    { label: 'Roles y permisos', path: '/roles', icon: 'roles', permission: 'ROLES_GESTIONAR' },
    { label: 'Catálogo', path: '/productos', icon: 'products', permission: 'PRODUCTOS_LEER' },
    { label: 'Bitácora', path: '/bitacora', icon: 'audit', permission: 'BITACORA_LEER' },
  ];

  protected readonly navItems = computed(() => {
    const isSuperAdmin = this.session()?.user.roles.includes('SUPER_ADMIN') ?? false;
    const permissions = this.session()?.user.permisos ?? [];
    return this.allNavItems.filter(
      (item) =>
        (!item.superAdminOnly || isSuperAdmin) &&
        (!item.hideForSuperAdmin || !isSuperAdmin) &&
        (!item.permission || isSuperAdmin || permissions.includes(item.permission)),
    );
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
