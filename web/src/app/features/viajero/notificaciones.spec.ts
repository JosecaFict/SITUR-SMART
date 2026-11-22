import { HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { ComponentFixture, TestBed, fakeAsync, flushMicrotasks } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { Subject, of, throwError } from 'rxjs';
import { AuthService } from '../../core/auth/auth.service';
import { WebPushService } from '../../core/notifications/web-push.service';
import { AppNotification } from '../../core/traveler/traveler.models';
import { TravelerService } from '../../core/traveler/traveler.service';
import { Notificaciones } from './notificaciones';
import { CommunicationsService } from '../../core/communications/communications.service';

describe('Notificaciones: recepción web', () => {
  let fixture: ComponentFixture<Notificaciones>;
  let traveler: jasmine.SpyObj<TravelerService>;
  let serverUnread: number;
  const foreground = new Subject<unknown>();
  const session = signal({ user: { id: 1, roles: ['EMPLEADO'], tenants: [{ id: 3 }] } });
  const push = {
    foregroundMessages$: foreground.asObservable(), loadConfig: jasmine.createSpy().and.resolveTo(null),
    activate: jasmine.createSpy().and.resolveTo(true), deactivate: jasmine.createSpy().and.resolveTo(true),
    restore: jasmine.createSpy().and.resolveTo(false),
    enabled: signal(false), supported: signal(true), busy: signal(false), status: signal('inactive'),
    permission: signal('default'), config: signal({ habilitado: true }), error: signal<string | null>(null),
  };
  const item: AppNotification = {
    id: 8, tipo: 'SISTEMA', titulo: 'Cambio de horario', mensaje: 'Nos encontramos a las 09:00.',
    datos: { motivo: 'COMUNICACION', remitente: { nombre: 'Ana Paz' }, reserva_id: 17 }, leida: false, creado_en: '2026-11-21T12:00:00Z',
  };
  const element = () => fixture.nativeElement as HTMLElement;
  const render = () => { fixture = TestBed.createComponent(Notificaciones); fixture.detectChanges(); };
  const notice = () => element().querySelector('ul button') as HTMLButtonElement;
  beforeEach(async () => {
    session.set({ user: { id: 1, roles: ['EMPLEADO'], tenants: [{ id: 3 }] } });
    push.enabled.set(false); push.permission.set('default'); push.activate.calls.reset(); push.loadConfig.calls.reset(); push.restore.calls.reset();
    traveler = jasmine.createSpyObj<TravelerService>('TravelerService', ['notifications', 'interests', 'markRead', 'markAllRead', 'refreshUnread'], { unread: signal(1) });
    serverUnread = 1;
    traveler.notifications.and.returnValue(of({ count: 1, next: null, previous: null, results: [item] }));
    traveler.interests.and.returnValue(of({ ciudades: [], tipos: [], basado_en: { favoritos: 0, reservas: 0, resenas: 0 } }));
    traveler.markRead.and.returnValue(of({ ...item, leida: true }));
    traveler.markAllRead.and.returnValue(of(undefined));
    traveler.refreshUnread.and.callFake(() => { traveler.unread.set(serverUnread); return of({ no_leidas: serverUnread }); });
    await TestBed.configureTestingModule({ imports: [Notificaciones], providers: [
      provideRouter([]), { provide: CommunicationsService, useValue: { preferences: () => of({ preferencias: [], limites: { por_empresa_24h: 1, total_24h: 3 } }) } }, { provide: AuthService, useValue: { session } },
      { provide: TravelerService, useValue: traveler }, { provide: WebPushService, useValue: push },
    ] }).compileComponents();
  });

  it('muestra comunicaciones, remitente y lectura para personal sin consultar intereses', () => {
    render();
    expect(element().textContent).toContain('Comunicación');
    expect(element().textContent).toContain('De: Ana Paz');
    expect(element().textContent).toContain('Sin leer');
    expect(traveler.interests).not.toHaveBeenCalled();
    expect(element().textContent).not.toContain('Mis intereses');
    expect(element().querySelector('a')).toBeNull();
  });

  it('solo marca leída después de la confirmación del servidor y sincroniza el contador', () => {
    const read = new Subject<AppNotification>(); traveler.markRead.and.returnValue(read);
    const navigate = spyOn(TestBed.inject(Router), 'navigate');
    render(); notice().click(); fixture.detectChanges();
    expect(notice().disabled).toBeTrue();
    expect(notice().textContent).toContain('Sin leer');
    serverUnread = 0; read.next({ ...item, leida: true }); fixture.detectChanges();
    expect(notice().textContent).not.toContain('Sin leer');
    expect(traveler.unread()).toBe(0);
    expect(navigate).not.toHaveBeenCalled();
  });

  it('conserva sin leer y muestra error si falla la lectura', () => {
    traveler.markRead.and.returnValue(throwError(() => new HttpErrorResponse({ status: 500 })));
    render(); notice().click(); fixture.detectChanges();
    expect(notice().textContent).toContain('Sin leer');
    expect(traveler.unread()).toBe(1);
    expect(element().querySelector('[role="alert"]')).not.toBeNull();
  });

  it('ofrece al cliente Ver reserva fuera del botón de lectura y no navega al leer', () => {
    session.set({ user: { id: 1, roles: ['CLIENTE'], tenants: [] } });
    const navigate = spyOn(TestBed.inject(Router), 'navigate');
    render(); notice().click(); fixture.detectChanges();
    const link = element().querySelector('li a') as HTMLAnchorElement;
    expect(link.textContent).toContain('Ver reserva');
    expect(link.getAttribute('href')).toBe('/mis-viajes/17');
    expect(notice().querySelector('a')).toBeNull();
    expect(navigate).not.toHaveBeenCalled();
    expect(traveler.interests).toHaveBeenCalled();
  });

  it('actualiza bandeja y contador al recibir un mensaje foreground', () => {
    render(); serverUnread = 2;
    traveler.notifications.and.returnValue(of({ count: 2, next: null, previous: null, results: [item, { ...item, id: 9, titulo: 'Nuevo aviso' }] }));
    foreground.next({}); fixture.detectChanges();
    expect(element().textContent).toContain('Nuevo aviso');
    expect(traveler.notifications).toHaveBeenCalledTimes(2);
    expect(traveler.unread()).toBe(2);
  });

  it('marca todas y actualiza el contador del menú', () => {
    render(); serverUnread = 0;
    fixture.componentInstance['markAll'](); fixture.detectChanges();
    expect(traveler.markAllRead).toHaveBeenCalledTimes(1);
    expect(traveler.unread()).toBe(0);
    expect(notice().textContent).not.toContain('Sin leer');
  });

  it('consulta configuración y usa restauración segura sin activar desde init', fakeAsync(() => {
    render(); flushMicrotasks();
    expect(push.loadConfig).toHaveBeenCalled();
    expect(push.restore).toHaveBeenCalledTimes(1);
    expect(push.activate).not.toHaveBeenCalled();
    fixture.destroy(); push.enabled.set(true);
    render(); flushMicrotasks();
    expect(push.restore).toHaveBeenCalledTimes(2);
    expect(push.activate).not.toHaveBeenCalled();
  }));

  it('explica un permiso bloqueado y permite activar mediante un clic explícito', () => {
    render(); push.permission.set('denied'); fixture.detectChanges();
    expect(element().textContent).toContain('Los avisos están bloqueados');
    expect(Array.from(element().querySelectorAll('button')).some((button) => button.textContent?.trim() === 'Activar avisos del navegador')).toBeFalse();
    push.permission.set('default'); fixture.detectChanges();
    const activate = Array.from(element().querySelectorAll('button')).find((button) => button.textContent?.trim() === 'Activar avisos del navegador')!;
    activate.click(); expect(push.activate).toHaveBeenCalledTimes(1);
  });
});
