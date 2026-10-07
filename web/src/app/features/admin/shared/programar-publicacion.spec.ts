import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { TourismProduct } from '../../../core/products/products.models';
import { ProductsService } from '../../../core/products/products.service';
import { ProgramarPublicacion } from './programar-publicacion';

describe('ProgramarPublicacion', () => {
  let fixture: ComponentFixture<ProgramarPublicacion>;
  let products: jasmine.SpyObj<ProductsService>;
  const text = () => fixture.nativeElement.textContent as string;
  const button = (label: string) =>
    Array.from(fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>)
      .find((item) => item.textContent?.includes(label))!;

  function render(estado: string, publicarEn: string | null = null): void {
    fixture = TestBed.createComponent(ProgramarPublicacion);
    fixture.componentRef.setInput('tenantId', 5);
    fixture.componentRef.setInput('productId', 12);
    fixture.componentRef.setInput('estado', estado);
    fixture.componentRef.setInput('publicarEn', publicarEn);
    fixture.detectChanges();
  }

  beforeEach(async () => {
    products = jasmine.createSpyObj<ProductsService>('ProductsService', ['schedule', 'clearSchedule']);
    products.schedule.and.returnValue(of({ id: 12, publicar_en: '2026-10-15T12:00:00Z' } as TourismProduct));
    products.clearSchedule.and.returnValue(of({ id: 12, publicar_en: null } as TourismProduct));
    await TestBed.configureTestingModule({
      imports: [ProgramarPublicacion],
      providers: [{ provide: ProductsService, useValue: products }],
    }).compileComponents();
  });

  it('pide al menos una fecha', () => {
    render('BORRADOR');
    button('Guardar programación').click();
    fixture.detectChanges();
    expect(products.schedule).not.toHaveBeenCalled();
    expect(text()).toContain('Elige cuándo publicar o cuándo retirar');
  });

  it('manda la fecha de publicación en ISO', () => {
    render('BORRADOR');
    const input = fixture.nativeElement.querySelector('input[aria-label="Publicar el"]') as HTMLInputElement;
    input.value = '2026-10-15T08:00';
    input.dispatchEvent(new Event('input'));
    button('Guardar programación').click();
    const [tenant, product, fechas] = products.schedule.calls.mostRecent().args;
    expect([tenant, product]).toEqual([5, 12]);
    expect(fechas.publicar_en).toBe(new Date('2026-10-15T08:00').toISOString());
    expect(fechas.retirar_en).toBeNull();
  });

  it('un producto publicado solo programa su retiro y puede quitar la programación', () => {
    render('PUBLICADO', '2026-10-15T12:00:00Z');
    expect(fixture.nativeElement.querySelector('input[aria-label="Publicar el"]')).toBeNull();
    expect(text()).toContain('Se publica el');
    button('Quitar programación').click();
    expect(products.clearSchedule).toHaveBeenCalledWith(5, 12);
  });
});
