import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { BackupsService } from './backups.service';

describe('BackupsService', () => {
  let service: BackupsService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(BackupsService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('requests the database dump as a blob', () => {
    service.download().subscribe();
    const request = http.expectOne(`${environment.apiUrl}/admin/copias-seguridad/descargar/`);
    expect(request.request.method).toBe('POST');
    expect(request.request.responseType).toBe('blob');
    request.flush(new Blob(['PGDMP']));
  });
});

describe('BackupsService schedule', () => {
  let service: BackupsService;
  let http: HttpTestingController;
  const base = `${environment.apiUrl}/admin/copias-seguridad`;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(BackupsService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('reads and updates the schedule', () => {
    service.schedule().subscribe();
    http.expectOne(`${base}/programacion/`).flush({});

    service.updateSchedule('CADA_3_DIAS').subscribe();
    const update = http.expectOne(`${base}/programacion/`);
    expect(update.request.method).toBe('PUT');
    expect(update.request.body).toEqual({ frecuencia: 'CADA_3_DIAS' });
    update.flush({});
  });

  it('asks for a signed link to a stored copy', () => {
    service.link(4).subscribe();
    const request = http.expectOne(`${base}/guardadas/4/enlace/`);
    expect(request.request.method).toBe('POST');
    request.flush({ url: 'https://firmado.test' });
  });
});
