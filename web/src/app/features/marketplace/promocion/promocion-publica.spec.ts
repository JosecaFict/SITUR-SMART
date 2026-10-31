import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { of } from 'rxjs';
import { Promotion } from '../../../core/promotions/promotions.models';
import { PromotionsService } from '../../../core/promotions/promotions.service';
import { PromocionPublica } from './promocion-publica';

describe('PromocionPublica combinada', () => {
  it('muestra servicios y precio reales, sin ofrecer reserva ni Stripe', async () => {
    const service = jasmine.createSpyObj<PromotionsService>('PromotionsService', ['getPublic']);
    service.getPublic.and.returnValue(of({
      id: 31, modalidad: 'COMBINADO', producto_id: null, nombre: 'Paquete combinado',
      empresa: 'Empresa local', descripcion: 'Dos servicios', porcentaje_descuento: '15.00',
      precio_original: '200.00', precio_final: '170.00', monto_descuento: '30.00',
      moneda_simbolo: 'Bs', imagen_url: null, motivo_no_reservable: 'Consulta esta oferta con la empresa.',
      inicio: '2026-11-01T10:00:00-04:00', fin: '2026-11-30T10:00:00-04:00',
      componentes: [{ id: 4, nombre: 'Tour local', tipo_codigo: 'TOUR', producto_id: 7,
        fecha_inicio: '2026-11-12', cantidad: 2, total: '100.00', imagen_url: null }],
    } as unknown as Promotion));
    await TestBed.configureTestingModule({
      providers: [
        provideRouter([{ path: 'marketplace/promociones/:id', component: PromocionPublica }]),
        { provide: PromotionsService, useValue: service },
      ],
    }).compileComponents();
    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl('/marketplace/promociones/31');
    const element = harness.routeNativeElement as HTMLElement;
    expect(service.getPublic).toHaveBeenCalledWith(31);
    expect(element.textContent).toContain('Paquete combinado');
    expect(element.textContent).toContain('Bs 170.00');
    expect(element.textContent).toContain('Tour local');
    expect(element.textContent).toContain('Consulta esta oferta con la empresa.');
    expect(element.textContent).not.toContain('Reservar y pagar');
  });
});
