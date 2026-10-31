import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { AuthService } from '../../../core/auth/auth.service';
import { CompaniesService } from '../../../core/companies/companies.service';
import { addCalendarDays, boliviaToday } from '../../../core/products/departure-dates';
import { ProductDeparture, TourismProduct } from '../../../core/products/products.models';
import { ProductsService } from '../../../core/products/products.service';
import { MediaService } from '../../../core/media/media.service';
import { Productos } from './productos';

describe('Productos: salidas', () => {
  let fixture: ComponentFixture<Productos>;
  let products: jasmine.SpyObj<ProductsService>;
  const permissions = signal<string[]>(['PRODUCTOS_LEER', 'DISPONIBILIDAD_GESTIONAR']);
  const day = addCalendarDays(boliviaToday(), 1);
  const product = {
    id: 7, tipo_codigo: 'TOUR', tipo: 'Tour', nombre: 'Tour de prueba', empresa_id: 3,
    ciudad: 'La Paz', pais: 'Bolivia', capacidad_maxima: 10, estado: 'PUBLICADO',
    precio_base: '100.00', moneda_simbolo: 'Bs', imagen_url: null, descripcion: null,
    localidad: null, codigo: 'TOUR-7', hospedaje_id: null, establecimiento: null,
  } as TourismProduct;
  const departure: ProductDeparture = {
    id: 42, producto_id: 7, fecha: day, hora_inicio: '09:00', hora_fin: '11:00',
    inicio: `${day}T09:00:00-04:00`, fin: `${day}T11:00:00-04:00`,
    cupo_total: 8, cupos_restantes: 6, cerrado: false,
  };
  const el = () => fixture.nativeElement as HTMLElement;
  const clickManage = () => {
    (Array.from(el().querySelectorAll('button')).find((button) => button.textContent?.includes('Gestionar salidas')) as HTMLButtonElement).click();
    fixture.detectChanges();
  };

  beforeEach(async () => {
    permissions.set(['PRODUCTOS_LEER', 'DISPONIBILIDAD_GESTIONAR']);
    products = jasmine.createSpyObj<ProductsService>('ProductsService', [
      'listTypes', 'listCurrencies', 'listCompanyProducts', 'companyDepartures',
      'createDeparture', 'updateDeparture', 'closeDeparture',
    ]);
    products.listTypes.and.returnValue(of([]));
    products.listCurrencies.and.returnValue(of([]));
    products.listCompanyProducts.and.returnValue(of([product]));
    products.companyDepartures.and.returnValue(of([departure]));
    products.createDeparture.and.returnValue(of(departure));
    products.closeDeparture.and.returnValue(of({ ...departure, cerrado: true, cupos_restantes: 0 }));
    const companies = jasmine.createSpyObj<CompaniesService>('CompaniesService', ['listCities']);
    companies.listCities.and.returnValue(of([]));
    await TestBed.configureTestingModule({
      imports: [Productos],
      providers: [
        provideRouter([]),
        { provide: ProductsService, useValue: products },
        { provide: CompaniesService, useValue: companies },
        { provide: MediaService, useValue: {} },
        { provide: AuthService, useValue: { session: () => ({ user: {
          roles: [], permisos: permissions(), tenants: [{ id: 3, name: 'Empresa' }],
        } }) } },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(Productos);
    fixture.detectChanges();
  });

  it('lista salidas y permite crear con tenant y cupo del producto', () => {
    clickManage();
    expect(products.companyDepartures).toHaveBeenCalledWith(3, 7);
    expect(el().textContent).toContain('6 de 8 cupos restantes');
    const form = Array.from(el().querySelectorAll('form')).find((item) => item.textContent?.includes('Nueva salida')) as HTMLFormElement;
    for (const [name, value] of [
      ['fecha', day], ['hora_inicio', '12:00'], ['hora_fin', '14:00'], ['cupo_total', '7'],
    ]) {
      const input = form.querySelector(`[formcontrolname="${name}"]`) as HTMLInputElement;
      input.value = value;
      input.dispatchEvent(new Event('input'));
    }
    form.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    expect(products.createDeparture).toHaveBeenCalledWith(3, 7, {
      fecha: day, hora_inicio: '12:00', hora_fin: '14:00', cupo_total: 7,
    });
  });

  it('muestra solo consulta sin permiso de gestión de disponibilidad', () => {
    permissions.set(['PRODUCTOS_LEER']);
    fixture.detectChanges();
    clickManage();
    expect(el().textContent).toContain('Necesitas el permiso');
    expect(el().textContent).not.toContain('Crear salida');
    expect(products.companyDepartures).toHaveBeenCalledWith(3, 7);
  });

  it('edita una salida y exige confirmación antes de cerrarla', () => {
    products.updateDeparture.and.returnValue(of(departure));
    clickManage();
    (Array.from(el().querySelectorAll('button')).find((button) => button.textContent?.trim() === 'Editar') as HTMLButtonElement).click();
    fixture.detectChanges();
    const form = Array.from(el().querySelectorAll('form')).find((item) => item.textContent?.includes('Editar salida')) as HTMLFormElement;
    const capacity = form.querySelector('[formcontrolname="cupo_total"]') as HTMLInputElement;
    capacity.value = '9'; capacity.dispatchEvent(new Event('input'));
    form.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    expect(products.updateDeparture).toHaveBeenCalledWith(3, 7, 42, {
      fecha: day, hora_inicio: '09:00', hora_fin: '11:00', cupo_total: 9,
    });
    const confirmation = spyOn(window, 'confirm').and.returnValue(false);
    (Array.from(el().querySelectorAll('button')).find((button) => button.textContent?.includes('Cerrar salida')) as HTMLButtonElement).click();
    expect(products.closeDeparture).not.toHaveBeenCalled();
    confirmation.and.returnValue(true);
    (Array.from(el().querySelectorAll('button')).find((button) => button.textContent?.includes('Cerrar salida')) as HTMLButtonElement).click();
    expect(products.closeDeparture).toHaveBeenCalledWith(3, 7, 42);
  });
});
