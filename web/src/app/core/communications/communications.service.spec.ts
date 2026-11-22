import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { CommunicationPayload } from './communications.models';
import { CommunicationsService } from './communications.service';

describe('CommunicationsService: contrato HTTP', () => {
  let service: CommunicationsService;
  let http: HttpTestingController;
  const base = `${environment.apiUrl}/comunicaciones/`;
  const payload: CommunicationPayload = {
    titulo: 'Cambio de horario', mensaje: 'Nos encontramos a las 09:00.', tipo: 'OPERATIVA',
    audiencia: { grupo: 'USUARIOS', empresa_ids: [], rol_ids: [], usuario_ids: [21], salida_id: 7 },
    reserva_id: null,
  };
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(CommunicationsService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('pagina en el ámbito de empresa y admite un listado sin paginar', () => {
    service.list(3, 2).subscribe((result) => expect(result.results).toEqual([]));
    const request = http.expectOne(`${base}?page=2`);
    expect(request.request.headers.get('X-Tenant-ID')).toBe('3');
    request.flush([]);
  });

  it('omite la cabecera en el ámbito global', () => {
    service.list().subscribe();
    const request = http.expectOne(`${base}?page=1`);
    expect(request.request.headers.has('X-Tenant-ID')).toBeFalse();
    request.flush({ count: 0, next: null, previous: null, results: [] });
  });

  it('crea, consulta y actualiza el borrador con la empresa elegida', () => {
    service.create(payload, 3).subscribe();
    const create = http.expectOne(base);
    expect(create.request.method).toBe('POST');
    expect(create.request.body).toEqual(payload);
    expect(create.request.headers.get('X-Tenant-ID')).toBe('3');
    create.flush({ id: 8 });
    service.detail(8, 3).subscribe();
    const detail = http.expectOne(`${base}8/`);
    expect(detail.request.method).toBe('GET');
    expect(detail.request.headers.get('X-Tenant-ID')).toBe('3');
    detail.flush({ id: 8 });
    service.update(8, payload, 3).subscribe();
    const update = http.expectOne(`${base}8/`);
    expect(update.request.method).toBe('PATCH');
    expect(update.request.body).toEqual(payload);
    expect(update.request.headers.get('X-Tenant-ID')).toBe('3');
    update.flush({ id: 8 });
  });

  it('previsualiza el contenido completo con reserva nula y publica exclusivamente la huella', () => {
    service.preview(payload, 3).subscribe();
    const preview = http.expectOne(`${base}audiencia/`);
    expect(preview.request.method).toBe('POST');
    expect(preview.request.body).toEqual(payload);
    expect(preview.request.body.reserva_id).toBeNull();
    expect(preview.request.headers.get('X-Tenant-ID')).toBe('3');
    preview.flush({ total: 1, destinatarios: [], huella: 'contenido-y-audiencia' });
    service.publish(8, 'contenido-y-audiencia', 3).subscribe();
    const publish = http.expectOne(`${base}8/publicar/`);
    expect(publish.request.method).toBe('POST');
    expect(publish.request.body).toEqual({ huella: 'contenido-y-audiencia' });
    expect(publish.request.headers.get('X-Tenant-ID')).toBe('3');
    publish.flush({ id: 8 });
  });

  it('busca usuarios remotamente mediante buscar', () => {
    service.options(3, '  ana@example.test  ').subscribe();
    const request = http.expectOne(`${base}opciones/?buscar=ana@example.test`);
    expect(request.request.headers.get('X-Tenant-ID')).toBe('3');
    request.flush({ empresas: [], roles: [], usuarios: [], es_global: false });
  });
  it('filtra opciones por empresas, roles y grupo dentro de la cabecera autorizada', () => {
    service.options(3, '', { empresa_ids: [3], rol_ids: [4], grupo: 'PERSONAL', tipo: 'INTERNA' }).subscribe();
    const request = http.expectOne((request) => request.url === `${base}opciones/`);
    expect(request.request.params.get('empresa_ids')).toBe('3');
    expect(request.request.params.get('rol_ids')).toBe('4');
    expect(request.request.params.get('grupo')).toBe('PERSONAL');
    expect(request.request.headers.get('X-Tenant-ID')).toBe('3');
    request.flush({ empresas: [], roles: [], usuarios: [], es_global: false });
  });

  it('consulta el correo guardado con GET sin ejecutar publicación', () => {
    service.emailPreview(8, 3).subscribe();
    const request = http.expectOne(`${base}8/correo/`);
    expect(request.request.method).toBe('GET');
    expect(request.request.headers.get('X-Tenant-ID')).toBe('3');
    request.flush({ asunto: 'Viaje', html: '<p>Hola</p>', texto: 'Hola' });
  });
});
