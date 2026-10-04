import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { CompaniesService } from './companies.service';

describe('CompaniesService', () => {
  let service: CompaniesService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(CompaniesService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('consulta una empresa por su identificador', () => {
    service.get(7).subscribe();

    const request = http.expectOne(`${environment.apiUrl}/empresas/7/`);
    expect(request.request.method).toBe('GET');
    request.flush({});
  });

  it('cambia el estado mediante la acción de la máquina de estados', () => {
    service.updateStatus(7, 'SUSPENDIDO').subscribe();

    const request = http.expectOne(`${environment.apiUrl}/empresas/7/estado/`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ estado: 'SUSPENDIDO' });
    request.flush({});
  });

  it('cambia el plan y envía la preferencia de renovación', () => {
    service.changeSubscription(7, 'PRO', true).subscribe();

    const request = http.expectOne(`${environment.apiUrl}/empresas/7/suscripcion/`);
    expect(request.request.method).toBe('PUT');
    expect(request.request.body).toEqual({
      plan_codigo: 'PRO',
      renovacion_automatica: true,
    });
    request.flush({});
  });
});
