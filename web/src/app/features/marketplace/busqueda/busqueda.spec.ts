import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { AuthService } from '../../../core/auth/auth.service';
import { CompaniesService } from '../../../core/companies/companies.service';
import { LodgingEstablishment } from '../../../core/lodging/lodging.models';
import { LodgingService } from '../../../core/lodging/lodging.service';
import { TourismProduct } from '../../../core/products/products.models';
import { ProductsService } from '../../../core/products/products.service';
import { Promotion } from '../../../core/promotions/promotions.models';
import { PromotionsService } from '../../../core/promotions/promotions.service';
import { Busqueda } from './busqueda';

describe('Busqueda CU35', () => {
  let fixture: ComponentFixture<Busqueda>;
  let lodging: jasmine.SpyObj<LodgingService>;
  let promotions: jasmine.SpyObj<PromotionsService>;
  let products: jasmine.SpyObj<ProductsService>;
  const product = {
    id: 7, tipo_codigo: 'TOUR', tipo: 'Tour', nombre: 'Ruta local', descripcion: 'Recorrido',
    localidad: null, ciudad: 'La Paz', pais: 'Bolivia', empresa: 'Empresa local',
    imagen_url: null, moneda_simbolo: 'Bs', precio_base: '100.00', precio_desde: null,
    capacidad_maxima: 10, establecimiento: null, hospedaje_id: null,
    calificacion_promedio: 4.5, cantidad_resenas: 2,
  } as TourismProduct;

  beforeEach(async () => {
    products = jasmine.createSpyObj<ProductsService>('ProductsService', ['listTypes', 'listMarketplace', 'getPublic']);
    const companies = jasmine.createSpyObj<CompaniesService>('CompaniesService', ['listCountries', 'listCities']);
    lodging = jasmine.createSpyObj<LodgingService>('LodgingService', ['listPublicLodgings']);
    promotions = jasmine.createSpyObj<PromotionsService>('PromotionsService', ['listPublic']);
    promotions.listPublic.and.returnValue(of([]));
    products.getPublic.and.returnValue(of(product));
    products.listTypes.and.returnValue(of([{ id: 1, codigo: 'HOTEL', nombre: 'Hotel' }]));
    products.listMarketplace.and.returnValue(of({ count: 1, next: null, previous: null, results: [product] }));
    companies.listCountries.and.returnValue(of([]));
    companies.listCities.and.returnValue(of([]));
    lodging.listPublicLodgings.and.returnValue(of({
      count: 1, next: null, previous: null,
      results: [{
        id: 13, producto_id: 70, tipo_hospedaje: 'Hotel', nombre: 'Hotel local',
        localidad: null, ciudad: 'La Paz', pais: 'Bolivia', empresa: 'Empresa local',
        imagen_url: null, precio_desde: '200.00', moneda_simbolo: 'Bs', descripcion: null,
        categoria_estrellas: 3, calificacion_promedio: 4.5, cantidad_resenas: 2,
      } as LodgingEstablishment],
    }));
    await TestBed.configureTestingModule({
      imports: [Busqueda],
      providers: [
        provideRouter([]),
        { provide: ProductsService, useValue: products },
        { provide: CompaniesService, useValue: companies },
        { provide: LodgingService, useValue: lodging },
        { provide: PromotionsService, useValue: promotions },
        { provide: AuthService, useValue: { session: signal(null), isAuthenticated: signal(false) } },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(Busqueda);
    fixture.detectChanges();
  });

  it('muestra valoración y abre la ficha pública al elegir un tour', () => {
    const element = fixture.nativeElement as HTMLElement;
    const link = Array.from(element.querySelectorAll('article a'))
      .find((item) => item.textContent?.includes('Ruta local')) as HTMLAnchorElement;
    expect(link.getAttribute('href')).toBe('/marketplace/productos/7');
    expect(element.textContent).toContain('4.5');
    expect(element.textContent).toContain('2 reseñas');
    expect(element.querySelector('article button[aria-expanded]')).toBeNull();
  });

  it('distingue la categoría hotelera de la valoración de clientes', () => {
    const element = fixture.nativeElement as HTMLElement;
    (Array.from(element.querySelectorAll('button')).find((item) => item.textContent?.trim() === 'Hospedajes') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(lodging.listPublicLodgings).toHaveBeenCalled();
    expect(element.querySelector('[aria-label="Categoría hotelera: 3 estrellas"]')).not.toBeNull();
    expect(element.querySelector('[aria-label="Valoración de clientes: 4.5 de 5, 2 reseñas"]')).not.toBeNull();
    const link = Array.from(element.querySelectorAll('article a'))
      .find((item) => item.textContent?.includes('Hotel local')) as HTMLAnchorElement;
    expect(link.getAttribute('href')).toBe('/marketplace/hospedajes/13');
  });
  for (const code of ['RESTAURANTE', 'TOUR', 'EXPERIENCIA', 'ATRACCION', 'PAQUETE']) {
    it(`muestra el descuento real de ${code} y conserva su ficha de producto`, () => {
    const discounted = {
      ...product, tipo_codigo: code, nombre: `${code} local`, promocion: {
        id: 21, modalidad: 'EXISTENTE', nombre: 'Oferta', porcentaje_descuento: '20.00',
        precio_original: '100.00', precio_final: '80.00', monto_descuento: '20.00',
        total_original: '100.00', descuento_total: '20.00', total: '80.00',
        inicio: '2026-11-01T10:00:00-04:00', fin: '2026-11-30T10:00:00-04:00',
      },
    } as TourismProduct;
    products.listMarketplace.and.returnValue(of({ count: 1, next: null, previous: null, results: [discounted] }));
    products.getPublic.and.returnValue(of(discounted));
    (Array.from(fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>)
      .find((button) => button.textContent?.trim() === 'Limpiar filtros') as HTMLButtonElement).click();
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('Bs 80.00');
    expect(element.textContent).toContain('Bs 100.00');
    expect(element.querySelector('article a[href="/marketplace/productos/7"]')).not.toBeNull();
    promotions.listPublic.and.returnValue(of([{
      id: 21, modalidad: 'EXISTENTE', producto_id: 7,
    } as unknown as Promotion]));
    (Array.from(element.querySelectorAll('button')).find((button) => button.textContent?.trim() === 'Promociones') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(element.textContent).toContain('Bs 80.00');
    expect(element.querySelector('article a[href="/marketplace/productos/7"]')).not.toBeNull();
    });
  }

  it('muestra una oferta combinada en Promociones sin inventar calificaciones', () => {
    promotions.listPublic.and.returnValue(of([{
      id: 31, modalidad: 'COMBINADO', producto_id: null, nombre: 'Oferta combinada',
      descripcion: 'Dos servicios', empresa: 'Empresa local', componentes: [],
      precio_original: '200.00', precio_final: '160.00', monto_descuento: '40.00',
      porcentaje_descuento: '20.00', moneda_simbolo: 'Bs', imagen_url: null,
    } as unknown as Promotion]));
    const element = fixture.nativeElement as HTMLElement;
    (Array.from(element.querySelectorAll('button')).find((button) => button.textContent?.trim() === 'Promociones') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(promotions.listPublic).toHaveBeenCalled();
    expect(element.textContent).toContain('Oferta combinada');
    expect(element.textContent).toContain('Bs 160.00');
    expect(element.querySelector('article a[href="/marketplace/promociones/31"]')).not.toBeNull();
    expect(element.querySelector('article [aria-label^="Valoración de clientes"]')).toBeNull();
  });
});
