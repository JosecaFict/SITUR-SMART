import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { PackagesService } from './packages.service';

describe('PackagesService CU39', () => {
  let service: PackagesService;
  let http: HttpTestingController;
  const base = `${environment.apiUrl}/me/paquetes/`;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(PackagesService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('crea un borrador y agrega una salida exacta sin llamar a reservas ni pagos', () => {
    const trip = { nombre: 'Mi ruta', ciudad_id: 5, fecha_inicio: '2026-11-12', fecha_fin: '2026-11-14', personas: 2 };
    const component = { producto_id: 7, fecha_inicio: '2026-11-12', cantidad: 2, salida_id: 42 };
    service.create(trip).subscribe();
    service.quote(9, component).subscribe();
    service.add(9, component).subscribe();
    const create = http.expectOne(base);
    expect(create.request.method).toBe('POST');
    expect(create.request.body).toEqual(trip);
    create.flush({});
    const quote = http.expectOne(`${base}9/cotizar/`);
    expect(quote.request.body).toEqual(component);
    quote.flush({});
    const add = http.expectOne(`${base}9/componentes/`);
    expect(add.request.body.salida_id).toBe(42);
    add.flush({});
  });

  it('actualiza, quita y revalida antes de guardar', () => {
    service.change(9, 3, { cantidad: 1 }).subscribe();
    service.remove(9, 3).subscribe();
    service.validate(9, false).subscribe();
    service.validate(9, true).subscribe();
    const changes = http.match(`${base}9/componentes/3/`);
    expect(changes.map((item) => item.request.method)).toEqual(['PATCH', 'DELETE']);
    changes.forEach((request) => request.flush({}));
    const checks = http.match(`${base}9/validar/`);
    expect(checks.map((item) => item.request.body.guardar)).toEqual([false, true]);
    checks.forEach((request) => request.flush({}));
  });
});
