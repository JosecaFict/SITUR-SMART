import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { Subject, of } from 'rxjs';
import { AuthService } from '../../auth/auth.service';
import { AuthSession } from '../../auth/auth.models';
import { MyPlanService } from '../../subscription/my-plan.service';
import { TravelerService } from '../../traveler/traveler.service';
import { WebPushService } from '../../notifications/web-push.service';
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
        { provide: WebPushService, useValue: { foregroundMessages$: new Subject(), deactivate: () => Promise.resolve(true), restore: () => Promise.resolve(false) } },
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

describe('AppShell: comunicaciones y notificaciones', () => {
  const user = { id: 1, email: 'empresa@example.test', nombres: 'Ana', apellidos: 'Paz', estado: 'ACTIVO' };
  const session = signal<AuthSession | null>(null);
  const foreground = new Subject<unknown>();
  let deactivate: jasmine.Spy;
  let logout: jasmine.Spy;
  let refresh: jasmine.Spy;

  beforeEach(async () => {
    session.set({ access: 'test', refresh: 'test', user: { ...user, roles: ['EMPLEADO'], permisos: [], tenants: [{ id: 3, name: 'Empresa', subdomain: 'empresa' }] } });
    deactivate = jasmine.createSpy().and.resolveTo(true);
    logout = jasmine.createSpy();
    refresh = jasmine.createSpy().and.returnValue(of({ no_leidas: 2 }));
    await TestBed.configureTestingModule({ imports: [AppShell], providers: [
      provideRouter([]), { provide: AuthService, useValue: { session, logout } },
      { provide: TravelerService, useValue: { unread: signal(2), refreshUnread: refresh } },
      { provide: MyPlanService, useValue: { get: () => of({ restringida: false }) } },
      { provide: WebPushService, useValue: { foregroundMessages$: foreground.asObservable(), deactivate, restore: () => Promise.resolve(false) } },
    ] }).compileComponents();
  });

  it('ofrece bandeja al personal y gestión solo con permiso, como propietario o SuperAdmin', () => {
    const fixture = TestBed.createComponent(AppShell); fixture.detectChanges();
    const hasLink = (path: string) => !!(fixture.nativeElement as HTMLElement).querySelector(`a[href="${path}"]`);
    expect(hasLink('/notificaciones')).toBeTrue(); expect(hasLink('/comunicaciones')).toBeFalse();
    for (const values of [{ roles: ['EMPLEADO'], permisos: ['COMUNICACIONES_GESTIONAR'] }, { roles: ['TENANT_ADMIN'], permisos: [] }, { roles: ['SUPER_ADMIN'], permisos: [] }]) {
      session.update((value) => value ? { ...value, user: { ...value.user, ...values } } : value);
      fixture.detectChanges(); expect(hasLink('/comunicaciones')).toBeTrue();
    }
    foreground.next({}); expect(refresh).toHaveBeenCalledTimes(2);
  });

  it('retira el dispositivo antes de cerrar sesión y evita doble logout', async () => {
    let complete!: (value: boolean) => void;
    deactivate.and.returnValue(new Promise<boolean>((resolve) => { complete = resolve; }));
    const navigate = spyOn(TestBed.inject(Router), 'navigateByUrl').and.resolveTo(true);
    const fixture = TestBed.createComponent(AppShell); fixture.detectChanges();
    const pending = fixture.componentInstance['logout']();
    void fixture.componentInstance['logout']();
    expect(deactivate).toHaveBeenCalledTimes(1);
    expect(logout).not.toHaveBeenCalled(); expect(navigate).not.toHaveBeenCalled();
    complete(true); await pending;
    expect(logout).toHaveBeenCalledTimes(1); expect(navigate).toHaveBeenCalledWith('/login');
  });
});
