import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { LocationsService } from './locations.service';

describe('LocationsService', () => {
  let service: LocationsService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(LocationsService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('consulta las ciudades administrativas de un país', () => {
    service.listCities(1, 'santa').subscribe();
    const request = http.expectOne(
      `${environment.apiUrl}/admin/catalogos/ciudades/?pais=1&buscar=santa`,
    );
    expect(request.request.method).toBe('GET');
    request.flush([]);
  });

  it('cambia el estado de una ciudad mediante su acción específica', () => {
    service.changeCityStatus(4, false).subscribe();
    const request = http.expectOne(
      `${environment.apiUrl}/admin/catalogos/ciudades/4/estado/`,
    );
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ activo: false });
    request.flush({});
  });
});
