import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { AuthService } from '../../../core/auth/auth.service';
import { Promotion } from '../../../core/promotions/promotions.models';
import { PromotionsService } from '../../../core/promotions/promotions.service';
import { Promociones } from './promociones';

describe('Promociones empresariales', () => {
  let fixture: ComponentFixture<Promociones>;
  let service: jasmine.SpyObj<PromotionsService>;
  const permissions = signal(['PRODUCTOS_LEER', 'PRODUCTOS_GESTIONAR']);
  const item = {
    id: 12, nombre: 'Oferta real', descripcion: 'Paquete', empresa: 'Empresa',
    modalidad: 'EXISTENTE', estado: 'BORRADOR', estado_administrativo: 'BORRADOR',
    precio_original: '200.00', precio_final: '170.00', moneda_simbolo: 'Bs',
    porcentaje_descuento: '15.00', imagen_url: null,
    inicio: '2026-11-01T10:00:00-04:00', fin: '2026-11-30T10:00:00-04:00',
  } as unknown as Promotion;
  const element = () => fixture.nativeElement as HTMLElement;

  beforeEach(async () => {
    permissions.set(['PRODUCTOS_LEER', 'PRODUCTOS_GESTIONAR']);
    service = jasmine.createSpyObj<PromotionsService>('PromotionsService', ['listCompany', 'publish', 'deactivate']);
    service.listCompany.and.returnValue(of([item]));
    service.publish.and.returnValue(of({ ...item, estado: 'VIGENTE', estado_administrativo: 'HABILITADA' }));
    service.deactivate.and.returnValue(of({ ...item, estado: 'DESACTIVADA', estado_administrativo: 'DESACTIVADA' }));
    await TestBed.configureTestingModule({
      imports: [Promociones],
      providers: [
        provideRouter([]),
        { provide: PromotionsService, useValue: service },
        { provide: AuthService, useValue: { session: () => ({ user: { tenants: [{ id: 3, name: 'Empresa' }], permisos: permissions() } }) } },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(Promociones);
    fixture.detectChanges();
  });

  it('carga el listado con la empresa activa y permite publicar', () => {
    expect(service.listCompany).toHaveBeenCalledWith(3);
    expect(element().textContent).toContain('Oferta real');
    expect(element().querySelector('a[href="/promociones/12/editar?empresa=3"]')).not.toBeNull();
    const publish = Array.from(element().querySelectorAll('button')).find((button) => button.textContent?.trim() === 'Publicar') as HTMLButtonElement;
    publish.click(); fixture.detectChanges();
    expect(service.publish).toHaveBeenCalledWith(3, 12);
    expect(element().textContent).toContain('Promoción publicada');
  });

  it('ofrece aplicar un descuento a un producto existente', () => {
    (Array.from(element().querySelectorAll('button')).find((button) => button.textContent?.includes('Nueva promoción')) as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(element().textContent).toContain('Aplicar descuento a producto existente');
    expect(element().textContent).toContain('Producto existente');
    expect(element().textContent).not.toContain('Elige un PAQUETE publicado');
  });

  it('mantiene solo lectura sin PRODUCTOS_GESTIONAR', () => {
    permissions.set(['PRODUCTOS_LEER']);
    fixture.detectChanges();
    expect(element().textContent).toContain('Oferta real');
    expect(element().querySelector('a[href="/promociones/12/editar?empresa=3"]')).toBeNull();
    expect(Array.from(element().querySelectorAll('button')).some((button) => button.textContent?.trim() === 'Publicar')).toBeFalse();
  });

  it('exige confirmación antes de desactivar una oferta', () => {
    const publish = Array.from(element().querySelectorAll('button')).find((button) => button.textContent?.trim() === 'Publicar') as HTMLButtonElement;
    publish.click(); fixture.detectChanges();
    const deactivate = Array.from(element().querySelectorAll('button')).find((button) => button.textContent?.trim() === 'Desactivar') as HTMLButtonElement;
    const confirm = spyOn(window, 'confirm').and.returnValue(false);
    deactivate.click();
    expect(service.deactivate).not.toHaveBeenCalled();
    confirm.and.returnValue(true);
    deactivate.click(); fixture.detectChanges();
    expect(service.deactivate).toHaveBeenCalledWith(3, 12);
    expect(element().textContent).toContain('Desactivada');
  });
});
