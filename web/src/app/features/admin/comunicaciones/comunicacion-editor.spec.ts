import { HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router';
import { Subject, of, throwError } from 'rxjs';
import { AuthService } from '../../../core/auth/auth.service';
import { AudiencePreview, Communication, CommunicationOptions } from '../../../core/communications/communications.models';
import { CommunicationsService } from '../../../core/communications/communications.service';
import { ComunicacionEditor } from './comunicacion-editor';

describe('ComunicacionEditor', () => {
  let fixture: ComponentFixture<ComunicacionEditor>;
  let service: jasmine.SpyObj<CommunicationsService>;
  let snapshot: { paramMap: ReturnType<typeof convertToParamMap>; queryParamMap: ReturnType<typeof convertToParamMap> };
  const item: Communication = {
    id: 8, titulo: 'Cambio de horario', mensaje: 'Encuentro a las 09:00.', tipo: 'OPERATIVA', estado: 'BORRADOR',
    audiencia: { grupo: 'PERSONAL', empresa_ids: [], rol_ids: [], usuario_ids: [] }, reserva_id: null,
    remitente: { nombre: 'Ana Paz' }, creado_en: '2026-11-21T12:00:00Z', publicado_en: null,
    total_destinatarios: 0, leidas: 0, push_pendientes: 0, push_aceptados: 0, push_fallidos: 0, sin_dispositivo: 0,
  };
  const options: CommunicationOptions = {
    empresas: [{ id: 3, nombre: 'Empresa' }], roles: [], usuarios: [{ id: 21, nombre: 'Ana', email: 'ana@example.test' }], es_global: false,
    reservas: [{ id: 17, nombre: 'RES-0017 · Ana Paz' }], salidas: [{ id: 5, nombre: 'Tour Titicaca · 2026-12-01' }],
  };
  const preview: AudiencePreview = { total: 1, destinatarios: [{ id: 21, nombre: 'Ana', email: 'ana@example.test' }], huella: 'huella-v1' };
  const element = () => fixture.nativeElement as HTMLElement;
  const editor = () => fixture.componentInstance;
  const render = () => { fixture = TestBed.createComponent(ComunicacionEditor); fixture.detectChanges(); };
  function click(text: string): void {
    fixture.detectChanges();
    const button = Array.from(element().querySelectorAll('button')).find((button) => button.textContent?.trim() === text);
    expect(button).withContext(text).toBeDefined();
    button!.click(); fixture.detectChanges();
  }

  beforeEach(async () => {
    service = jasmine.createSpyObj<CommunicationsService>('CommunicationsService', ['options', 'detail', 'create', 'update', 'preview', 'publish', 'cancel', 'emailPreview']);
    service.options.and.returnValue(of(options));
    service.detail.and.returnValue(of(item));
    service.emailPreview.and.returnValue(of({ asunto: 'Ejemplo', html: '<p>Hola Ana</p>', texto: 'Hola Ana' }));
    service.create.and.returnValue(of(item));
    service.update.and.callFake((_id, payload) => of({ ...item, ...payload }));
    service.preview.and.returnValue(of(preview));
    service.publish.and.returnValue(of({ ...item, estado: 'PUBLICADA', total_destinatarios: 1 }));
    snapshot = { paramMap: convertToParamMap({ id: '8' }), queryParamMap: convertToParamMap({ empresa: '3' }) };
    await TestBed.configureTestingModule({ imports: [ComunicacionEditor], providers: [
      provideRouter([]),
      { provide: ActivatedRoute, useValue: { snapshot } },
      { provide: AuthService, useValue: { session: signal({ user: { roles: ['TENANT_ADMIN'], permisos: [], tenants: [{ id: 3, name: 'Empresa' }] } }) } },
      { provide: CommunicationsService, useValue: service },
    ] }).compileComponents();
  });

  it('previsualiza solo el borrador guardado y exige confirmar el título y destinatarios', () => {
    render();
    click('Previsualizar destinatarios');
    expect(service.preview).toHaveBeenCalledWith({ titulo: item.titulo, mensaje: item.mensaje, tipo: item.tipo, audiencia: item.audiencia, reserva_id: null, programado_en: null, vence_en: null, promocion_id: null }, 3);
    expect(element().textContent).toContain('ana@example.test');
    expect(service.publish).not.toHaveBeenCalled();
    click('Continuar para publicar');
    const confirmation = element().querySelector('[aria-labelledby="publish-title"]');
    expect(confirmation?.textContent).toContain(item.titulo);
    expect(confirmation?.textContent).toContain('1 destinatarios');
    click('Publicar para 1 destinatarios');
    expect(service.publish).toHaveBeenCalledOnceWith(8, 'huella-v1', 3);
    expect(element().textContent).toContain('Comunicación publicada');
    expect(element().querySelector('fieldset')?.disabled).toBeTrue();
  });

  it('invalida la huella al cambiar contenido y exige guardar antes de previsualizar de nuevo', () => {
    render(); click('Previsualizar destinatarios'); click('Continuar para publicar');
    editor()['form'].controls.mensaje.setValue('Nuevo horario a las 10:00.'); fixture.detectChanges();
    expect(element().querySelector('[aria-labelledby="publish-title"]')).toBeNull();
    expect(editor()['preview']()).toBeNull();
    editor()['publish']();
    expect(service.publish).not.toHaveBeenCalled();
    editor()['previewAudience']();
    expect(service.preview).toHaveBeenCalledTimes(1);
    click('Guardar borrador'); click('Previsualizar destinatarios');
    expect(service.preview.calls.mostRecent().args[0].mensaje).toBe('Nuevo horario a las 10:00.');
  });

  it('descarta una previsualización tardía si cambia la audiencia', () => {
    const delayed = new Subject<AudiencePreview>();
    service.preview.and.returnValue(delayed);
    render(); click('Previsualizar destinatarios');
    editor()['form'].controls.rol_ids.setValue([4]);
    delayed.next(preview); fixture.detectChanges();
    expect(editor()['preview']()).toBeNull();
  });

  it('un 409 retira la huella e impide reintentos hasta recargar el borrador', () => {
    service.publish.and.returnValue(throwError(() => new HttpErrorResponse({ status: 409 })));
    render(); click('Previsualizar destinatarios'); click('Continuar para publicar'); click('Publicar para 1 destinatarios');
    expect(element().textContent).toContain('Recarga el borrador');
    expect(editor()['preview']()).toBeNull();
    editor()['publish'](); editor()['previewAudience']();
    expect(service.publish).toHaveBeenCalledTimes(1);
    expect(service.preview).toHaveBeenCalledTimes(1);
    click('Recargar detalle'); click('Previsualizar destinatarios');
    expect(service.preview).toHaveBeenCalledTimes(2);
  });

  it('no permite publicar una audiencia vacía', () => {
    service.preview.and.returnValue(of({ total: 0, destinatarios: [], huella: 'vacia' }));
    render(); click('Previsualizar destinatarios'); editor()['preparePublish'](); editor()['publish']();
    expect(service.publish).not.toHaveBeenCalled();
    expect(element().textContent).toContain('No hay destinatarios');
  });

  it('crea un borrador y conserva su empresa en la URL del editor', () => {
    snapshot.paramMap = convertToParamMap({});
    const navigate = spyOn(TestBed.inject(Router), 'navigate').and.resolveTo(true);
    render();
    editor()['form'].patchValue({ titulo: item.titulo, mensaje: item.mensaje, reserva_id: 17, salida_id: 5 });
    click('Guardar borrador');
    expect(service.create).toHaveBeenCalledWith(jasmine.objectContaining({ reserva_id: 17, audiencia: jasmine.objectContaining({ reserva_id: 17, salida_id: 5 }) }), 3);
    expect(navigate).toHaveBeenCalledWith(['/comunicaciones', 8], { queryParams: { empresa: 3 }, replaceUrl: true });
  });

  it('mantiene INTERNA limitada a grupos de personal y valida usuarios específicos', () => {
    render(); editor()['form'].patchValue({ grupo: 'CLIENTES' }); editor()['form'].controls.tipo.setValue('INTERNA');
    expect(editor()['form'].controls.grupo.value).toBe('PERSONAL');
    expect(editor()['groups']().some((group) => group.value === 'CLIENTES')).toBeFalse();
    editor()['form'].controls.grupo.setValue('USUARIOS'); editor()['save']();
    expect(service.update).not.toHaveBeenCalled();
    expect(editor()['error']()).toContain('Selecciona al menos un usuario');
  });

  it('busca usuarios fuera de las primeras opciones y conserva selecciones anteriores', fakeAsync(() => {
    render(); editor()['toggle']('usuario_ids', 21);
    service.options.and.returnValue(of({ ...options, usuarios: [{ id: 222, nombre: 'Bea', email: 'bea@example.test' }] }));
    const input = element().querySelector('[aria-label="Buscar usuarios"]') as HTMLInputElement;
    input.value = 'bea'; input.dispatchEvent(new Event('input')); tick(301); fixture.detectChanges();
    expect(service.options).toHaveBeenCalledWith(3, 'bea', jasmine.objectContaining({ grupo: 'PERSONAL', tipo: 'OPERATIVA' }));
    expect(element().textContent).toContain('bea@example.test');
    editor()['toggle']('usuario_ids', 222);
    expect(editor()['form'].controls.usuario_ids.value).toEqual([21, 222]);
    expect(editor()['selectedLabels']('usuarios', 'usuario_ids')).toContain('Ana');
  }));

  it('elige reserva y salida por etiquetas y conserva la selección durante búsquedas remotas', fakeAsync(() => {
    render();
    const selects = Array.from(element().querySelectorAll('select'));
    const reservation = selects.find((select) => select.textContent?.includes('Sin reserva vinculada'))!;
    const departure = selects.find((select) => select.textContent?.includes('Sin salida vinculada'))!;
    reservation.value = Array.from(reservation.options).find((option) => option.textContent?.includes('RES-0017 · Ana Paz'))!.value;
    reservation.dispatchEvent(new Event('change'));
    departure.value = Array.from(departure.options).find((option) => option.textContent?.includes('Tour Titicaca'))!.value;
    departure.dispatchEvent(new Event('change')); fixture.detectChanges();
    expect(editor()['payload']().reserva_id).toBe(17);
    expect(editor()['payload']().audiencia.salida_id).toBe(5);
    service.options.and.returnValue(of({ ...options, reservas: [{ id: 222, nombre: 'RES-0222 · Bea' }], salidas: [] }));
    const search = element().querySelector('[aria-label="Buscar reservas"]') as HTMLInputElement;
    search.value = 'Bea'; search.dispatchEvent(new Event('input')); tick(301); fixture.detectChanges();
    expect(service.options).toHaveBeenCalledWith(3, 'Bea', jasmine.objectContaining({ grupo: 'PERSONAL', tipo: 'OPERATIVA' }));
    expect(reservation.textContent).toContain('RES-0017 · Ana Paz');
    expect(reservation.textContent).toContain('RES-0222 · Bea');
    expect(editor()['payload']().reserva_id).toBe(17);
    expect(editor()['payload']().audiencia.salida_id).toBe(5);
  }));

  it('muestra un vínculo publicado fuera de las opciones con etiqueta segura', () => {
    service.detail.and.returnValue(of({ ...item, estado: 'PUBLICADA', reserva_id: 999, audiencia: { ...item.audiencia, salida_id: 888 } }));
    render();
    expect(element().textContent).toContain('Reserva vinculada (fuera de los resultados actuales)');
    expect(element().textContent).toContain('Salida vinculada (fuera de los resultados actuales)');
    expect(element().querySelector('input[type="number"]')).toBeNull();
    expect(element().querySelector('fieldset')?.disabled).toBeTrue();
    editor()['save'](); editor()['previewAudience'](); editor()['publish']();
    expect(service.update).not.toHaveBeenCalled();
    expect(service.publish).not.toHaveBeenCalled();
  });

  it('rechaza un ámbito ajeno sin hacer ninguna solicitud ni permitir reintentar como global', () => {
    snapshot.queryParamMap = convertToParamMap({ empresa: '99' }); render(); click('Reintentar');
    expect(service.options).not.toHaveBeenCalled();
    expect(service.detail).not.toHaveBeenCalled();
  });

  it('muestra errores de guardado y conserva el contenido del formulario', () => {
    service.update.and.returnValue(throwError(() => new HttpErrorResponse({ status: 403, error: { detail: 'No puedes gestionar esta empresa.' } })));
    render(); editor()['form'].controls.mensaje.setValue('Contenido conservado'); click('Guardar borrador');
    expect(element().textContent).toContain('No puedes gestionar esta empresa.');
    expect(editor()['form'].controls.mensaje.value).toBe('Contenido conservado');
  });
  it('confirma una programación con fechas ISO y conserva su contenido inmóvil', () => {
    render();
    editor()['form'].patchValue({ programado_en: '2026-12-01T09:30', vence_en: '2026-12-02T23:00', tipo: 'PROMOCIONAL' });
    const payload = editor()['payload']();
    expect(payload.programado_en).toBe(new Date('2026-12-01T09:30').toISOString());
    expect(payload.vence_en).toBe(new Date('2026-12-02T23:00').toISOString());
    service.detail.and.returnValue(of({ ...item, ...payload, estado: 'PROGRAMADA' }));
    editor()['load'](); fixture.detectChanges();
    expect(element().querySelector('fieldset')?.disabled).toBeTrue();
    service.cancel.and.returnValue(of({ ...item, estado: 'CANCELADA' }));
    click('Cancelar envío pendiente');
    expect(service.cancel).toHaveBeenCalledOnceWith(8, 3);
    expect(element().textContent).toContain('Envío cancelado');
  });

  it('una promoción conserva la oferta seleccionada y muestra exclusiones en su audiencia', () => {
    service.detail.and.returnValue(of({ ...item, tipo: 'PROMOCIONAL', promocion_id: 9, vence_en: '2026-12-02T23:00:00Z' }));
    service.options.and.returnValue(of({ ...options, promociones: [{ id: 9, nombre: 'Fin de semana 20%' }] }));
    service.preview.and.returnValue(of({ ...preview, excluidos_promociones: 3 }));
    render(); click('Previsualizar destinatarios');
    expect(editor()['payload']().promocion_id).toBe(9);
    expect(element().textContent).toContain('Fin de semana 20%');
    expect(element().textContent).toContain('3 personas excluidas');
  });

  it('SuperAdmin global ve la acción tras previsualizar y solo publica al confirmar', () => {
    TestBed.overrideProvider(AuthService, { useValue: { session: signal({ user: { roles: ['SUPER_ADMIN'], permisos: [], tenants: [] } }) } });
    snapshot.queryParamMap = convertToParamMap({});
    const owners = { ...item, remitente: 'SITUR-SMART', audiencia: { ...item.audiencia, grupo: 'PROPIETARIOS' as const } };
    service.detail.and.returnValue(of(owners));
    service.options.and.returnValue(of({ ...options, es_global: true }));
    service.preview.and.returnValue(of({ ...preview, total: 4 }));
    const scroll = spyOn(HTMLElement.prototype, 'scrollIntoView');
    render(); click('Previsualizar destinatarios');
    expect(service.preview.calls.mostRecent().args[1]).toBeUndefined();
    expect(element().querySelector('#audience-title')?.textContent).toContain('4 destinatarios');
    expect(document.activeElement?.id).toBe('audience-title');
    expect(scroll).toHaveBeenCalled();
    expect(service.publish).not.toHaveBeenCalled();
    click('Continuar para publicar');
    expect(document.activeElement?.id).toBe('publish-title');
    expect(element().querySelector('#publish-confirmation')?.textContent).toContain('Toda la plataforma');
    expect(service.publish).not.toHaveBeenCalled();
    click('Publicar para 4 destinatarios');
    expect(service.publish).toHaveBeenCalledOnceWith(8, 'huella-v1', undefined);
  });

  it('SuperAdmin no puede continuar si la audiencia está vacía', () => {
    TestBed.overrideProvider(AuthService, { useValue: { session: signal({ user: { roles: ['SUPER_ADMIN'], permisos: [], tenants: [] } }) } });
    snapshot.queryParamMap = convertToParamMap({});
    service.preview.and.returnValue(of({ total: 0, destinatarios: [], huella: 'vacia' }));
    render(); click('Previsualizar destinatarios');
    const next = Array.from(element().querySelectorAll('button')).find((button) => button.textContent?.trim() === 'Continuar para publicar')!;
    expect(next.disabled).toBeTrue();
    expect(element().textContent).toContain('No hay destinatarios');
    expect(element().querySelector('#publish-confirmation')).toBeNull();
    expect(service.publish).not.toHaveBeenCalled();
  });

  it('la programación tiene acción visible y volver conserva la revisión sin enviar', () => {
    service.detail.and.returnValue(of({ ...item, programado_en: '2026-12-01T09:30:00-04:00' }));
    render(); click('Previsualizar destinatarios'); click('Continuar para programar');
    expect(element().querySelector('#publish-title')?.textContent).toContain('Confirmar programación');
    click('Volver a destinatarios');
    expect(element().querySelector('#publish-confirmation')).toBeNull();
    expect(document.activeElement?.id).toBe('audience-title');
    expect(editor()['preview']()).not.toBeNull();
    expect(service.publish).not.toHaveBeenCalled();
    click('Continuar para programar');
    expect(element().querySelector('#publish-confirmation')).not.toBeNull();
  });

  it('incluye notificación y correo sin un selector adicional al publicar', () => {
    render();
    expect(element().querySelector('[formControlName="enviar_correo"]')).toBeNull();
    expect(element().textContent).toContain('Notificación + correo electrónico');
    expect(element().textContent).toContain('Ver correo de ejemplo');
    click('Previsualizar destinatarios'); click('Continuar para publicar');
    expect(element().querySelector('#publish-confirmation')?.textContent).toContain('Notificación y correo electrónico incluidos');
    click('Publicar para 1 destinatarios');
    expect(service.publish).toHaveBeenCalledWith(8, preview.huella, 3);
  });

  it('muestra el correo en un marco aislado sin publicar ni enviar', () => {
    service.detail.and.returnValue(of({ ...item, enviar_correo: true }));
    render(); editor()['previewEmail'](); fixture.detectChanges();
    expect(service.emailPreview).toHaveBeenCalledWith(8, 3);
    const frame = element().querySelector('iframe');
    expect(frame?.getAttribute('sandbox')).toBe('');
    expect(frame?.getAttribute('srcdoc')).toContain('Hola Ana');
    expect(service.publish).not.toHaveBeenCalled();
    editor()['form'].controls.mensaje.setValue('Cambió el contenido'); fixture.detectChanges();
    expect(element().querySelector('iframe')).toBeNull();
  });

  it('descarta correos tardíos si el contenido cambió durante la consulta', () => {
    service.detail.and.returnValue(of({ ...item, enviar_correo: true }));
    const response = new Subject<{ asunto: string; html: string; texto: string }>();
    service.emailPreview.and.returnValue(response);
    render(); editor()['previewEmail']();
    editor()['form'].controls.mensaje.setValue('Contenido nuevo');
    response.next({ asunto: 'Viejo', html: '<p>Mensaje viejo</p>', texto: 'Viejo' }); fixture.detectChanges();
    expect(editor()['emailHtml']()).toBeNull();
    expect(element().querySelector('iframe')).toBeNull();
  });

  it('al elegir empresas retira roles globales y personas de una selección anterior', () => {
    TestBed.overrideProvider(AuthService, { useValue: { session: signal({ user: { roles: ['SUPER_ADMIN'], permisos: [], tenants: [] } }) } });
    snapshot.queryParamMap = convertToParamMap({});
    service.options.and.returnValue(of({ ...options, es_global: true, roles: [{ id: 99, nombre: 'Cliente', ambito: 'GLOBAL' }] }));
    render(); editor()['form'].controls.rol_ids.setValue([99]); editor()['form'].controls.usuario_ids.setValue([21]);
    editor()['form'].controls.empresa_ids.setValue([3]);
    expect(editor()['form'].controls.rol_ids.value).toEqual([]);
    expect(editor()['form'].controls.usuario_ids.value).toEqual([]);
    expect(editor()['audienceNote']()).toContain('Vuelve a elegir las personas');
  });

  it('elegir empresas sin seleccionar ninguna bloquea el envío global de un borrador guardado', () => {
    TestBed.overrideProvider(AuthService, { useValue: { session: signal({ user: { roles: ['SUPER_ADMIN'], permisos: [], tenants: [] } }) } });
    snapshot.queryParamMap = convertToParamMap({});
    render(); click('Previsualizar destinatarios'); editor()['setCompanyMode'](true);
    expect(editor()['preview']()).toBeNull();
    editor()['save']();
    expect(editor()['error']()).toContain('Selecciona al menos una empresa');
    expect(service.update).not.toHaveBeenCalled();
    expect(service.publish).not.toHaveBeenCalled();
  });

});
