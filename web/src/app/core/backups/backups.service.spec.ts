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
