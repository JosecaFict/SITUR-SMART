import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { ProductsService } from './products.service';

describe('ProductsService salidas', () => {
  let service: ProductsService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(ProductsService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('consulta el día público sin enviar X-Tenant-ID', () => {
    service.publicDepartures(7, '2026-11-12').subscribe();
    const request = http.expectOne(`${environment.apiUrl}/marketplace/productos/7/salidas/?fecha=2026-11-12`);
    expect(request.request.method).toBe('GET');
    expect(request.request.headers.has('X-Tenant-ID')).toBeFalse();
    request.flush([]);
  });

  it('usa el tenant en listado, alta, edición y cierre', () => {
    const payload = { fecha: '2026-11-12', hora_inicio: '09:00', hora_fin: '11:00', cupo_total: 8 };
    service.companyDepartures(3, 7).subscribe();
    service.createDeparture(3, 7, payload).subscribe();
    service.updateDeparture(3, 7, 42, payload).subscribe();
    service.closeDeparture(3, 7, 42).subscribe();
    const base = `${environment.apiUrl}/productos/7/salidas/`;
    for (const [url, method] of [
      [base, 'GET'], [base, 'POST'], [`${base}42/`, 'PATCH'], [`${base}42/cerrar/`, 'POST'],
    ]) {
      const request = http.expectOne((item) => item.url === url && item.method === method);
      expect(request.request.headers.get('X-Tenant-ID')).toBe('3');
      if (method === 'PATCH' || method === 'POST' && url === base) expect(request.request.body).toEqual(payload);
      request.flush(method === 'GET' ? [] : {});
    }
  });
});
