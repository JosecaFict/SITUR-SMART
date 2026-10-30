import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { PaymentsService } from './payments.service';

describe('PaymentsService', () => {
  let service: PaymentsService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(PaymentsService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('consulta únicamente los pagos del turista autenticado', () => {
    service.mine({ estado: 'APROBADO' }).subscribe();
    const request = http.expectOne(`${environment.apiUrl}/me/pagos/?estado=APROBADO`);
    expect(request.request.method).toBe('GET');
    request.flush({ count: 0, next: null, previous: null, results: [] });
  });

  it('envía el tenant al consultar los pagos empresariales', () => {
    service.company(7, { desde: '2026-10-01' }).subscribe();
    const request = http.expectOne(`${environment.apiUrl}/empresa/pagos/?desde=2026-10-01`);
    expect(request.request.headers.get('X-Tenant-ID')).toBe('7');
    request.flush({ count: 0, next: null, previous: null, results: [], resumen: [] });
  });
});
