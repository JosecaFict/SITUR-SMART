import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { LucideShieldCheck } from '@lucide/angular';
import { AccountService, AccountSession } from '../../core/auth/account.service';
import { AuthService } from '../../core/auth/auth.service';
import { apiErrorMessage } from '../../core/http/api-error';
import { VerificarCorreo } from '../../shared/verificar-correo/verificar-correo';

type Panel = 'contrasena' | 'sesiones' | 'eliminar' | null;

/** Seguridad de la cuenta en Mi perfil: correo, contraseña, sesiones y baja. */
@Component({
  selector: 'situr-cuenta-seguridad',
  imports: [DatePipe, LucideShieldCheck, VerificarCorreo],
  template: `
    <div class="bg-surface rounded-2xl border border-input-border/60 p-6 shadow-sm space-y-4">
      <h3 class="text-title font-heading flex items-center gap-2 text-base font-bold">
        <svg lucideShieldCheck class="text-accent-dark h-5 w-5"></svg> Seguridad de la cuenta
      </h3>

      @if (needsVerification()) {
        <situr-verificar-correo [sendFirst]="false" (verified)="notice.set('Correo verificado. Ya puedes reservar.')" />
      }
      @if (notice(); as text) {
        <p class="border-accent/30 bg-demo-bg text-accent-dark rounded-xl border px-3 py-2 text-xs">{{ text }}</p>
      }

      <div class="flex flex-wrap gap-2">
        <button type="button" class="secondary-button" (click)="toggle('contrasena')">Cambiar contraseña</button>
        <button type="button" class="secondary-button" (click)="toggle('sesiones')">Sesiones abiertas</button>
        @if (canDelete()) {
          <button type="button" class="rounded-lg border border-red-200 px-3 py-2 text-xs font-semibold text-red-700 hover:bg-red-50" (click)="toggle('eliminar')">Eliminar mi cuenta</button>
        }
      </div>

      @if (error(); as text) { <p class="text-xs font-semibold text-red-700">{{ text }}</p> }

      @switch (panel()) {
        @case ('contrasena') {
          <form class="space-y-2" (submit)="$event.preventDefault(); changePassword()">
            <input type="password" class="field-control" placeholder="Contraseña actual" autocomplete="current-password"
              [value]="current()" (input)="current.set($any($event.target).value)" aria-label="Contraseña actual" />
            <input type="password" class="field-control" placeholder="Contraseña nueva (mínimo 8)" autocomplete="new-password"
              [value]="next()" (input)="next.set($any($event.target).value)" aria-label="Contraseña nueva" />
            <button type="submit" class="primary-button" [disabled]="working()">Guardar contraseña</button>
          </form>
        }
        @case ('sesiones') {
          <ul class="divide-input-border divide-y text-sm">
            @for (session of sessions(); track session.id) {
              <li class="flex items-center justify-between gap-3 py-2">
                <span class="min-w-0">
                  <span class="text-title block truncate font-medium">{{ session.actual ? 'Este navegador' : session.dispositivo }}</span>
                  <span class="text-text-secondary text-xs">Desde el {{ session.iniciada_en | date: 'dd/MM/yyyy HH:mm' }}</span>
                </span>
                @if (!session.actual) {
                  <button type="button" class="secondary-button" (click)="closeSession(session.id)">Cerrar</button>
                }
              </li>
            } @empty {
              <li class="text-text-secondary py-2 text-xs">Cargando…</li>
            }
          </ul>
          <button type="button" class="secondary-button" (click)="closeOthers()">Cerrar todas las demás</button>
        }
        @case ('eliminar') {
          <div class="rounded-xl border border-red-200 bg-red-50 p-3">
            <p class="text-xs leading-5 text-red-800">
              Se borran tu nombre, correo y teléfono, y tus reservas sin pagar se cancelan. Las reservas ya pagadas
              se mantienen para la empresa. No se puede deshacer.
            </p>
            <input type="password" class="field-control mt-2" placeholder="Tu contraseña" autocomplete="current-password"
              [value]="password()" (input)="password.set($any($event.target).value)" aria-label="Contraseña para eliminar la cuenta" />
            <button type="button" class="mt-2 rounded-lg bg-red-600 px-3 py-2 text-sm font-semibold text-white hover:bg-red-700"
              [disabled]="working()" (click)="deleteAccount()">Eliminar definitivamente</button>
          </div>
        }
      }
    </div>
  `,
})
export class CuentaSeguridad {
  private readonly account = inject(AccountService);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly needsVerification = computed(() => this.auth.session()?.user.correo_verificado === false);
  /** El personal de empresas y el SuperAdmin no se dan de baja aquí. */
  protected readonly canDelete = computed(() => {
    const user = this.auth.session()?.user;
    return !!user && !user.roles.includes('SUPER_ADMIN') && user.tenants.length === 0;
  });

  protected readonly panel = signal<Panel>(null);
  protected readonly sessions = signal<AccountSession[]>([]);
  protected readonly current = signal('');
  protected readonly next = signal('');
  protected readonly password = signal('');
  protected readonly working = signal(false);
  protected readonly notice = signal<string | null>(null);
  protected readonly error = signal<string | null>(null);

  protected toggle(panel: Panel): void {
    this.panel.set(this.panel() === panel ? null : panel);
    this.error.set(null);
    this.notice.set(null);
    if (this.panel() === 'sesiones') this.loadSessions();
  }

  private fail(error: HttpErrorResponse, fallback: string): void {
    this.working.set(false);
    this.error.set(apiErrorMessage(error, fallback));
  }

  protected changePassword(): void {
    if (this.next().length < 8) {
      this.error.set('La contraseña nueva debe tener al menos 8 caracteres.');
      return;
    }
    this.working.set(true);
    this.account.changePassword(this.current(), this.next()).subscribe({
      next: () => {
        this.working.set(false);
        this.panel.set(null);
        this.current.set('');
        this.next.set('');
        this.notice.set('Contraseña cambiada. Cerramos tus sesiones en los demás dispositivos.');
      },
      error: (error: HttpErrorResponse) => this.fail(error, 'No se pudo cambiar la contraseña.'),
    });
  }

  private loadSessions(): void {
    this.account.sessions().subscribe({
      next: (sessions) => this.sessions.set(sessions),
      error: (error: HttpErrorResponse) => this.fail(error, 'No se pudieron cargar las sesiones.'),
    });
  }

  protected closeSession(id: number): void {
    this.account.closeSession(id).subscribe({
      next: () => this.loadSessions(),
      error: (error: HttpErrorResponse) => this.fail(error, 'No se pudo cerrar la sesión.'),
    });
  }

  protected closeOthers(): void {
    this.account.closeOthers().subscribe({
      next: ({ cerradas }) => {
        this.notice.set(cerradas ? `Cerramos ${cerradas} ${cerradas === 1 ? 'sesión' : 'sesiones'}.` : 'No había otras sesiones.');
        this.loadSessions();
      },
      error: (error: HttpErrorResponse) => this.fail(error, 'No se pudieron cerrar las sesiones.'),
    });
  }

  protected deleteAccount(): void {
    this.working.set(true);
    this.account.deleteAccount(this.password()).subscribe({
      next: () => this.router.navigateByUrl('/login'),
      error: (error: HttpErrorResponse) => this.fail(error, 'No se pudo eliminar la cuenta.'),
    });
  }
}
