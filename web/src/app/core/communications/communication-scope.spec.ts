import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, Router, RouterStateSnapshot, provideRouter } from '@angular/router';
import { AuthUser } from '../auth/auth.models';
import { AuthService } from '../auth/auth.service';
import { communicationsGuard } from '../auth/auth.guard';
import { communicationScope } from './communication-scope';

describe('Comunicaciones: permisos y ámbito', () => {
  const user: AuthUser = {
    id: 1, email: 'personal@example.test', nombres: 'Ana', apellidos: 'Paz', estado: 'ACTIVO',
    roles: ['EMPLEADO'], permisos: [], tenants: [{ id: 3, name: 'Empresa', subdomain: 'empresa' }],
  };

  it('nunca convierte una empresa ajena o ausente de personal en ámbito global', () => {
    expect(communicationScope(user, null)).toBe(3);
    expect(() => communicationScope(user, '9')).toThrowError();
    expect(() => communicationScope({ ...user, tenants: [] }, null)).toThrowError();
    expect(() => communicationScope(user, '')).toThrowError();
    expect(() => communicationScope(user, '1.5')).toThrowError();
    expect(() => communicationScope(undefined, null)).toThrowError();
  });

  it('permite al SuperAdmin actuar globalmente o en una empresa concreta', () => {
    const admin = { ...user, roles: ['SUPER_ADMIN'], tenants: [] };
    expect(communicationScope(admin, null)).toBeUndefined();
    expect(communicationScope(admin, '9')).toBe(9);
  });

  it('admite permiso de gestión, propietario o SuperAdmin; deniega personal sin permiso y clientes', () => {
    let current = user;
    TestBed.configureTestingModule({ providers: [provideRouter([]), { provide: AuthService, useValue: { session: () => ({ user: current }) } }] });
    const allowed = () => TestBed.runInInjectionContext(() => communicationsGuard({} as ActivatedRouteSnapshot, {} as RouterStateSnapshot));
    expect(TestBed.inject(Router).serializeUrl(allowed() as ReturnType<Router['createUrlTree']>)).toBe('/dashboard');
    current = { ...user, permisos: ['COMUNICACIONES_GESTIONAR'] };
    expect(allowed()).toBeTrue();
    current = { ...user, roles: ['TENANT_ADMIN'] };
    expect(allowed()).toBeTrue();
    current = { ...user, roles: ['SUPER_ADMIN'], tenants: [] };
    expect(allowed()).toBeTrue();
    current = { ...user, roles: ['CLIENTE'], tenants: [] };
    expect(allowed()).not.toBeTrue();
  });
});
