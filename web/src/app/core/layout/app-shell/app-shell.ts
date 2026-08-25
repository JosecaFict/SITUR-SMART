import { Component, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import {
  LucideLayoutDashboard,
  LucideLogOut,
  LucideScrollText,
  LucideShieldCheck,
  LucideUsers,
} from '@lucide/angular';
import { AuthService } from '../../auth/auth.service';

interface NavItem {
  label: string;
  path: string;
  icon: 'dashboard' | 'roles' | 'users' | 'audit';
}

@Component({
  selector: 'situr-app-shell',
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    LucideLayoutDashboard,
    LucideLogOut,
    LucideScrollText,
    LucideShieldCheck,
    LucideUsers,
  ],
  templateUrl: './app-shell.html',
  styleUrl: './app-shell.css',
})
export class AppShell {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly session = this.auth.session;

  protected readonly navItems: NavItem[] = [
    { label: 'Dashboard', path: '/dashboard', icon: 'dashboard' },
    { label: 'Usuarios', path: '/usuarios', icon: 'users' },
    { label: 'Roles y permisos', path: '/roles', icon: 'roles' },
    { label: 'Bitácora', path: '/bitacora', icon: 'audit' },
  ];

  protected logout(): void {
    this.auth.logout();
    this.router.navigateByUrl('/login');
  }
}
