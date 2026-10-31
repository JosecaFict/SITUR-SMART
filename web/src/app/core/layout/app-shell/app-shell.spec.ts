import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { AuthService } from '../../auth/auth.service';
import { AuthSession } from '../../auth/auth.models';
import { MyPlanService } from '../../subscription/my-plan.service';
import { TravelerService } from '../../traveler/traveler.service';
import { AppShell } from './app-shell';

describe('AppShell: menú de promociones', () => {
  it('solo lo muestra a miembros de empresa con PRODUCTOS_LEER', async () => {
    const user = { id: 1, email: 'empresa@example.test', nombres: 'Representante', apellidos: 'Local', estado: 'ACTIVO' };
    const session = signal<AuthSession | null>({ access: 'test', refresh: 'test', user: {
      ...user, roles: ['TENANT_ADMIN'], permisos: ['PRODUCTOS_LEER'],
      tenants: [{ id: 3, name: 'Empresa', subdomain: 'empresa' }],
    } });
    await TestBed.configureTestingModule({
      imports: [AppShell],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: { session, logout: () => undefined } },
        { provide: TravelerService, useValue: { unread: signal(0), refreshUnread: () => of(0) } },
        { provide: MyPlanService, useValue: { get: () => of({ restringida: false, estado: 'ACTIVO', dias_restantes: null }) } },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(AppShell);
    fixture.detectChanges();
    const links = () => Array.from((fixture.nativeElement as HTMLElement).querySelectorAll('a')).map((link) => link.textContent?.trim());
    expect(links()).toContain('Paquetes con descuento');

    session.set({ access: 'test', refresh: 'test', user: { ...user, roles: ['CLIENTE'], permisos: [], tenants: [] } });
    fixture.detectChanges();
    expect(links()).not.toContain('Paquetes con descuento');

    session.set({ access: 'test', refresh: 'test', user: { ...user, roles: ['SUPER_ADMIN'], permisos: ['PRODUCTOS_LEER'], tenants: [{ id: 3, name: 'Empresa', subdomain: 'empresa' }] } });
    fixture.detectChanges();
    expect(links()).not.toContain('Paquetes con descuento');
  });
});
