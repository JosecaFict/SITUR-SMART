import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { AuthService } from '../../../core/auth/auth.service';
import { TourismProduct } from '../../../core/products/products.models';
import { ProductsService } from '../../../core/products/products.service';
import { Promotion } from '../../../core/promotions/promotions.models';
import { PromotionsService } from '../../../core/promotions/promotions.service';
import { PromocionEditor } from './promocion-editor';

describe('PromocionEditor', () => {
  let fixture: ComponentFixture<PromocionEditor>;
  let service: jasmine.SpyObj<PromotionsService>;
  let products: jasmine.SpyObj<ProductsService>;
  let routeSnapshot: {
    url: { path: string }[];
    paramMap: ReturnType<typeof convertToParamMap>;
    queryParamMap: ReturnType<typeof convertToParamMap>;
  };
  const offer = {
    id: 15, modalidad: 'COMBINADO', producto_id: null, nombre: 'Oferta nueva', descripcion: '',
    porcentaje_descuento: '20.00', inicio: '2026-11-02T10:00:00-04:00', fin: '2026-11-30T10:00:00-04:00',
    empresa: 'Empresa', estado: 'BORRADOR', estado_administrativo: 'BORRADOR', componentes: [],
    precio_original: null, precio_final: null, monto_descuento: null, moneda_simbolo: null,
    advertencias: [], valida: false, requiere_revalidacion: false,
  } as unknown as Promotion;
  const tour = {
    id: 7, nombre: 'Tour local', tipo_codigo: 'TOUR', tipo: 'Tour', precio_base: '100.00',
    moneda_simbolo: 'Bs', ciudad: 'La Paz', localidad: null, imagen_url: null,
  } as TourismProduct;
  const element = () => fixture.nativeElement as HTMLElement;

  function input(label: string, value: string, event = 'input'): void {
    const node = Array.from(element().querySelectorAll('label')).find((item) => item.textContent?.includes(label))?.querySelector('input, textarea') as HTMLInputElement;
    node.value = value;
    node.dispatchEvent(new Event(event));
    fixture.detectChanges();
  }

  function render(mode: 'EXISTENTE' | 'COMBINADO'): void {
    routeSnapshot.queryParamMap = convertToParamMap({ empresa: '3', modalidad: mode });
    fixture = TestBed.createComponent(PromocionEditor);
    fixture.detectChanges();
  }

  beforeEach(async () => {
    service = jasmine.createSpyObj<PromotionsService>('PromotionsService', ['eligible', 'preview', 'create', 'addComponent', 'publish']);
    products = jasmine.createSpyObj<ProductsService>('ProductsService', ['publicDepartures']);
    service.eligible.and.returnValue(of([tour]));
    service.create.and.returnValue(of(offer));
    service.preview.and.returnValue(of({ ...offer }));
    service.addComponent.and.returnValue(of({ ...offer, componentes: [{
      id: 2, producto_id: 7, nombre: 'Tour local', fecha_inicio: '2026-11-02', cantidad: 1,
      disponible: true, precio_unitario: '100.00', total: '100.00', motivo: null, precio_cambio: false,
    }] }));
    products.publicDepartures.and.returnValue(of([]));
    routeSnapshot = {
      url: [{ path: 'nueva' }], paramMap: convertToParamMap({}),
      queryParamMap: convertToParamMap({ empresa: '3', modalidad: 'COMBINADO' }),
    };
    await TestBed.configureTestingModule({
      imports: [PromocionEditor],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { snapshot: routeSnapshot } },
        { provide: PromotionsService, useValue: service },
        { provide: ProductsService, useValue: products },
        { provide: AuthService, useValue: { session: signal({ user: {
          tenants: [{ id: 3, name: 'Empresa' }], permisos: ['PRODUCTOS_LEER', 'PRODUCTOS_GESTIONAR'],
        } }) } },
      ],
    }).compileComponents();
  });

  it('crea un borrador combinado y después agrega un servicio con el tenant correcto', () => {
    render('COMBINADO');
    expect(service.eligible).toHaveBeenCalledWith(3, 'COMBINADO');
    input('Nombre de la promoción', 'Oferta nueva');
    input('Descuento (%)', '20');
    input('Inicio de vigencia', '2026-11-02T10:00', 'change');
    input('Fin de vigencia', '2026-11-30T10:00', 'change');
    const form = element().querySelector('form') as HTMLFormElement;
    form.dispatchEvent(new Event('submit', { cancelable: true }));
    fixture.detectChanges();
    expect(service.create).toHaveBeenCalledWith(3, jasmine.objectContaining({
      modalidad: 'COMBINADO', producto_id: null, inicio: '2026-11-02T10:00:00-04:00', componentes: [],
    }));
    (Array.from(element().querySelectorAll('button')).find((button) => button.textContent?.trim() === 'Agregar') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(products.publicDepartures).toHaveBeenCalledWith(7, '2026-11-02');
    (Array.from(element().querySelectorAll('button')).find((button) => button.textContent?.trim() === 'Agregar servicio') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(service.addComponent).toHaveBeenCalledWith(3, 15, { producto_id: 7, fecha_inicio: '2026-11-02', cantidad: 1 });
  });

  it('permite seleccionar un restaurante publicado para una promoción existente', () => {
    const restaurant = { ...tour, id: 8, tipo_codigo: 'RESTAURANTE', tipo: 'Restaurante', nombre: 'Mesa local' };
    service.eligible.and.returnValue(of([restaurant]));
    service.create.and.returnValue(of({ ...offer, modalidad: 'EXISTENTE', producto_id: 8 }));
    render('EXISTENTE');
    expect(service.eligible).toHaveBeenCalledWith(3, 'EXISTENTE');
    expect(element().textContent).toContain('Producto publicado de tu empresa');
    const select = Array.from(element().querySelectorAll('label')).find((label) => label.textContent?.includes('Producto publicado de tu empresa'))?.querySelector('select') as HTMLSelectElement;
    expect(select.textContent).toContain('Restaurante · Mesa local');
    select.value = '8'; select.dispatchEvent(new Event('change')); fixture.detectChanges();
    input('Nombre de la promoción', 'Oferta restaurante');
    input('Descuento (%)', '20');
    input('Inicio de vigencia', '2026-11-02T10:00', 'change');
    input('Fin de vigencia', '2026-11-30T10:00', 'change');
    (element().querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit', { cancelable: true }));
    fixture.detectChanges();
    expect(service.create).toHaveBeenCalledWith(3, jasmine.objectContaining({
      modalidad: 'EXISTENTE', producto_id: 8, porcentaje_descuento: '20',
    }));
  });
});
