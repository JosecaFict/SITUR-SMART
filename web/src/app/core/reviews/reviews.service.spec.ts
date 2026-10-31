import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { ReviewsService } from './reviews.service';

describe('ReviewsService', () => {
  let service: ReviewsService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(ReviewsService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('consulta la página pública y la reseña propia por ID de producto', () => {
    service.list(7, 2).subscribe();
    service.own(7).subscribe((review) => expect(review).toBeNull());
    const publicRequest = http.expectOne(`${environment.apiUrl}/marketplace/productos/7/resenas/?page=2`);
    expect(publicRequest.request.method).toBe('GET');
    expect(publicRequest.request.headers.has('X-Tenant-ID')).toBeFalse();
    publicRequest.flush({
      count: 0, next: null, previous: null, results: [],
      distribucion_calificaciones: { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 },
    });
    const ownRequest = http.expectOne(`${environment.apiUrl}/me/productos/7/resena/`);
    expect(ownRequest.request.method).toBe('GET');
    ownRequest.flush({ resena: null });
  });

  it('usa las rutas de publicación, edición y eliminación existentes', () => {
    const payload = { calificacion: 5, comentario: 'Excelente' };
    service.create(7, payload).subscribe();
    service.update(31, payload).subscribe();
    service.delete(31).subscribe();
    const create = http.expectOne(`${environment.apiUrl}/marketplace/productos/7/resenas/`);
    expect(create.request.method).toBe('POST');
    expect(create.request.body).toEqual(payload);
    create.flush({});
    const update = http.expectOne((request) => request.url === `${environment.apiUrl}/me/resenas/31/` && request.method === 'PATCH');
    expect(update.request.method).toBe('PATCH');
    expect(update.request.body).toEqual(payload);
    update.flush({});
    const remove = http.expectOne((request) => request.url === `${environment.apiUrl}/me/resenas/31/` && request.method === 'DELETE');
    expect(remove.request.method).toBe('DELETE');
    remove.flush(null);
  });
});
