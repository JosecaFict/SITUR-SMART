import { Component, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { LucideCompass, LucideLogOut } from '@lucide/angular';
import { AuthService } from '../../auth/auth.service';

interface NavItem {
  label: string;
  path: string;
}

@Component({
  selector: 'situr-app-shell',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, LucideCompass, LucideLogOut],
  templateUrl: './app-shell.html',
  styleUrl: './app-shell.css',
})
export class AppShell {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly session = this.auth.session;

  protected readonly navItems: NavItem[] = [
    { label: 'Dashboard', path: '/dashboard' },
    { label: 'Roles', path: '/roles' },
    { label: 'Usuarios', path: '/usuarios' },
    { label: 'Bitácora', path: '/bitacora' },
  ];

  protected logout(): void {
    this.auth.logout();
    this.router.navigateByUrl('/login');
  }
}
