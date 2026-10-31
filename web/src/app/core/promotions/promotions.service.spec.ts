import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { PromotionPayload } from './promotions.models';
import { PromotionsService } from './promotions.service';

describe('PromotionsService', () => {
  let service: PromotionsService;
  let http: HttpTestingController;
  const api = environment.apiUrl;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(PromotionsService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('envía el tenant en consultas y operaciones de empresa', () => {
    service.listCompany(8).subscribe();
    const listing = http.expectOne((request) => request.url === `${api}/promociones/` && request.method === 'GET');
    expect(listing.request.headers.get('X-Tenant-ID')).toBe('8');
    expect(listing.request.params.get('page_size')).toBe('50');
    listing.flush({ count: 0, next: null, previous: null, results: [] });

    const payload: PromotionPayload = {
      modalidad: 'EXISTENTE', producto_id: 12, nombre: 'Oferta', porcentaje_descuento: '15',
      inicio: '2026-11-01T10:00:00-04:00', fin: '2026-11-30T10:00:00-04:00',
    };
    service.create(8, payload).subscribe();
    const creation = http.expectOne(`${api}/promociones/`);
    expect(creation.request.method).toBe('POST');
    expect(creation.request.headers.get('X-Tenant-ID')).toBe('8');
    expect(creation.request.body).toEqual(payload);
    creation.flush({ id: 1 });
  });

  it('consulta todas las páginas públicas sin cabecera de empresa', () => {
    let result: unknown[] = [];
    service.listPublic().subscribe((items) => result = items);
    const first = http.expectOne((request) => request.url === `${api}/marketplace/promociones/` && request.params.get('page') === '1');
    expect(first.request.headers.has('X-Tenant-ID')).toBeFalse();
    first.flush({ count: 51, next: '?page=2', previous: null, results: [{ id: 1 }] });
    const second = http.expectOne((request) => request.url === `${api}/marketplace/promociones/` && request.params.get('page') === '2');
    expect(second.request.headers.has('X-Tenant-ID')).toBeFalse();
    second.flush({ count: 51, next: null, previous: '?page=1', results: [{ id: 2 }] });
    expect(result).toEqual([{ id: 1 }, { id: 2 }]);
  });

  it('separa detalle público y filtros de fecha de operaciones empresariales', () => {
    service.getPublic(9, { fecha: '2026-11-12', cantidad: 3 }).subscribe();
    const request = http.expectOne((item) => item.url === `${api}/marketplace/promociones/9/`);
    expect(request.request.params.get('fecha')).toBe('2026-11-12');
    expect(request.request.params.get('cantidad')).toBe('3');
    expect(request.request.headers.has('X-Tenant-ID')).toBeFalse();
    request.flush({ id: 9 });
  });
});
