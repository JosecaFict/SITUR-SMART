import { ComponentFixture, TestBed, fakeAsync, flush } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { TravelerBooking } from '../../core/traveler/traveler.models';
import { TravelerService } from '../../core/traveler/traveler.service';
import { ViajeDetalle } from './viaje-detalle';

const BOOKING: TravelerBooking = {
  id: 5, codigo: 'RES-1A2B3C4D', orden: 'ORD-1', estado: 'CONFIRMADA', estado_nombre: 'Confirmada',
  empresa: 'Hotel Cortez',
  producto: {
    id: 40, nombre: 'Habitación Simple', tipo_codigo: 'HABITACION', tipo: 'Habitación', ciudad: 'Santa Cruz',
    localidad: null, imagen_url: null, es_hospedaje: true, hospedaje_id: 3, establecimiento: 'Hotel Cortez',
  },
  fechas: { inicio: '2026-10-20', fin: '2026-10-22', noches: 2 },
  importe: { cantidad: 1, unidad: 'habitación', precio_unitario: '350.00', total: '700.00' },
  huespedes: 1, moneda_codigo: 'BOB', moneda_simbolo: 'Bs', pago: null, vence_en: null,
  qr: 'token-firmado', creado_en: '2026-10-06T22:00:00-04:00',
};

describe('ViajeDetalle', () => {
  let fixture: ComponentFixture<ViajeDetalle>;
  let traveler: jasmine.SpyObj<TravelerService>;

  async function render(booking: TravelerBooking, pago: string | null = null): Promise<void> {
    traveler = jasmine.createSpyObj<TravelerService>('TravelerService', ['booking', 'pay', 'cancel', 'receiptUrl']);
    traveler.booking.and.returnValue(of(booking));
    await TestBed.configureTestingModule({
      imports: [ViajeDetalle],
      providers: [
        provideRouter([]),
        { provide: TravelerService, useValue: traveler },
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: convertToParamMap({ id: '5' }), queryParamMap: convertToParamMap(pago ? { pago } : {}) } },
        },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(ViajeDetalle);
    fixture.detectChanges();
  }

  it('al volver del pago confirmado muestra el aviso, el QR y el comprobante', fakeAsync(async () => {
    await render(BOOKING, 'exito');
    flush();
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Pago realizado. Tu reserva fue confirmada');
    expect(text).toContain('Descargar comprobante');
    expect(fixture.nativeElement.querySelector('img[alt="Código QR de la reserva"]')).not.toBeNull();
  }));

  it('una reserva pendiente ofrece pagar o cancelar', async () => {
    await render({ ...BOOKING, estado: 'CREADA', estado_nombre: 'Pendiente de pago', qr: null });
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Pagar ahora');
    expect(text).toContain('Cancelar reserva');
    fixture.destroy();
  });
});
