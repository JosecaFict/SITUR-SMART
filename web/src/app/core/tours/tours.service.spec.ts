import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { DeparturesService, GuidesService, ToursService } from './tours.service';

describe('Servicios de tours', () => {
  let tours: ToursService;
  let departures: DeparturesService;
  let guides: GuidesService;
  let http: HttpTestingController;
  const api = environment.apiUrl;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    tours = TestBed.inject(ToursService);
    departures = TestBed.inject(DeparturesService);
    guides = TestBed.inject(GuidesService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('lista los tours de la empresa con su X-Tenant-ID', () => {
    tours.list(7).subscribe();
    const request = http.expectOne(`${api}/tours/`);
    expect(request.request.headers.get('X-Tenant-ID')).toBe('7');
    request.flush([]);
  });

  it('guarda el recorrido completo con PUT', () => {
    tours.saveStops(7, 3, [{ nombre: 'Isla Incahuasi' }]).subscribe();
    const request = http.expectOne(`${api}/tours/3/paradas/`);
    expect(request.request.method).toBe('PUT');
    expect(request.request.body).toEqual({ paradas: [{ nombre: 'Isla Incahuasi' }] });
    request.flush([]);
  });

  it('la ficha pública no manda la empresa', () => {
    tours.getPublic(3).subscribe();
    const request = http.expectOne(`${api}/marketplace/tours/3/`);
    expect(request.request.headers.has('X-Tenant-ID')).toBeFalse();
    request.flush({});
  });

  it('pide las salidas de un rango de fechas', () => {
    departures.list(7, 3, '2026-11-01', '2026-11-28').subscribe();
    const request = http.expectOne(`${api}/tours/3/salidas/?desde=2026-11-01&hasta=2026-11-28`);
    expect(request.request.headers.get('X-Tenant-ID')).toBe('7');
    request.flush([]);
  });

  it('las salidas repetidas van al mismo endpoint que una salida', () => {
    departures.createRecurring(7, 3, {
      dias_semana: [0, 3], hora_inicio: '08:00', desde: '2026-11-01', hasta: '2026-11-28',
    }).subscribe();
    const request = http.expectOne(`${api}/tours/3/salidas/`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body.dias_semana).toEqual([0, 3]);
    request.flush({ creadas: [], omitidas: 0 });
  });

  it('cerrar una salida es un POST a cerrar/', () => {
    departures.close(7, 11).subscribe();
    const request = http.expectOne(`${api}/salidas/11/cerrar/`);
    expect(request.request.method).toBe('POST');
    request.flush({});
  });

  it('desactivar un guía es un DELETE', () => {
    guides.deactivate(7, 5).subscribe();
    const request = http.expectOne(`${api}/guias/5/`);
    expect(request.request.method).toBe('DELETE');
    request.flush({});
  });
});
