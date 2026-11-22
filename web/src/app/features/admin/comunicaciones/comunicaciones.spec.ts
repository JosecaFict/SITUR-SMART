import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { Subject, of } from 'rxjs';
import { AuthService } from '../../../core/auth/auth.service';
import { Communication } from '../../../core/communications/communications.models';
import { CommunicationsService } from '../../../core/communications/communications.service';
import { Paged } from '../../../core/traveler/traveler.models';
import { Comunicaciones } from './comunicaciones';

describe('Comunicaciones: listado', () => {
  let fixture: ComponentFixture<Comunicaciones>;
  let service: jasmine.SpyObj<CommunicationsService>;
  const session = signal({ user: { roles: ['EMPLEADO'], tenants: [{ id: 3, name: 'Empresa A' }, { id: 4, name: 'Empresa B' }] } });
  const empty: Paged<Communication> = { count: 0, results: [], next: null, previous: null };
  beforeEach(async () => {
    session.set({ user: { roles: ['EMPLEADO'], tenants: [{ id: 3, name: 'Empresa A' }, { id: 4, name: 'Empresa B' }] } });
    service = jasmine.createSpyObj('CommunicationsService', ['list', 'options']);
    service.list.and.returnValue(of(empty));
    service.options.and.returnValue(of({ empresas: [{ id: 7, nombre: 'Empresa global' }], roles: [], usuarios: [], reservas: [], salidas: [], es_global: true }));
    await TestBed.configureTestingModule({ imports: [Comunicaciones], providers: [
      provideRouter([]), { provide: ActivatedRoute, useValue: { snapshot: { queryParamMap: convertToParamMap({}) } } },
      { provide: AuthService, useValue: { session } }, { provide: CommunicationsService, useValue: service },
    ] }).compileComponents();
  });
  const render = () => { fixture = TestBed.createComponent(Comunicaciones); fixture.detectChanges(); };

  it('lista en la empresa de la sesión y conserva ese ámbito al crear', () => {
    render();
    expect(service.list).toHaveBeenCalledWith(3, 1);
    const link = (fixture.nativeElement as HTMLElement).querySelector('a')!;
    expect(link.getAttribute('href')).toBe('/comunicaciones/nueva?empresa=3');
    expect(service.options).not.toHaveBeenCalled();
  });

  it('cancela respuestas anteriores al cambiar de empresa', () => {
    const pending = new Subject<Paged<Communication>>(); service.list.and.returnValue(pending);
    render(); service.list.and.returnValue(of({ ...empty, count: 12 }));
    const select = (fixture.nativeElement as HTMLElement).querySelector('select')!;
    select.value = '4'; select.dispatchEvent(new Event('change')); fixture.detectChanges();
    pending.next({ ...empty, count: 99 }); fixture.detectChanges();
    expect(service.list).toHaveBeenCalledWith(4, 1);
    expect(fixture.componentInstance['result']()?.count).toBe(12);
  });

  it('permite al SuperAdmin seleccionar una empresa desde el ámbito global', () => {
    session.set({ user: { roles: ['SUPER_ADMIN'], tenants: [] } }); render();
    expect(service.list).toHaveBeenCalledWith(undefined, 1);
    expect(service.options).toHaveBeenCalledWith();
    const select = (fixture.nativeElement as HTMLElement).querySelector('select')!;
    expect(select.textContent).toContain('Mensajes de la plataforma');
    expect(select.textContent).toContain('Empresa global');
    select.value = '7'; select.dispatchEvent(new Event('change'));
    expect(service.list).toHaveBeenCalledWith(7, 1);
  });
});
