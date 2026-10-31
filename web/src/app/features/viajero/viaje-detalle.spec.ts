import { ComponentFixture, TestBed, fakeAsync, flush } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { CancellationQuote, PaidCancellationResult, TravelerBooking } from '../../core/traveler/traveler.models';
import { TravelerService } from '../../core/traveler/traveler.service';
import { ViajeDetalle } from './viaje-detalle';

const BOOKING: TravelerBooking = {
  datos_facturacion: null,
  politica_cancelacion: null,
  politica_aceptada_en: null,
  id: 5, codigo: 'RES-1A2B3C4D', orden: 'ORD-1', estado: 'CONFIRMADA', estado_nombre: 'Confirmada',
  empresa: 'Hotel Cortez',
  producto: {
    id: 40, nombre: 'Habitación Simple', tipo_codigo: 'HABITACION', tipo: 'Habitación', ciudad: 'Santa Cruz',
    localidad: null, imagen_url: null, es_hospedaje: true, hospedaje_id: 3, establecimiento: 'Hotel Cortez',
  },
  fechas: { inicio: '2026-10-20', fin: '2026-10-22', noches: 2 },
  importe: {
    cantidad: 1, unidad: 'habitación', precio_unitario: '350.00',
    precio_original: '700.00', descuento: '0.00', total: '700.00',
  },
  huespedes: 1, moneda_codigo: 'BOB', moneda_simbolo: 'Bs', pago: null, vence_en: null,
  qr: 'token-firmado', creado_en: '2026-10-06T22:00:00-04:00',
};

describe('ViajeDetalle', () => {
  let fixture: ComponentFixture<ViajeDetalle>;
  let traveler: jasmine.SpyObj<TravelerService>;

  async function render(booking: TravelerBooking, pago: string | null = null): Promise<void> {
    traveler = jasmine.createSpyObj<TravelerService>('TravelerService', [
      'booking', 'pay', 'cancel', 'receiptUrl', 'cancellationQuote', 'cancelPaid',
    ]);
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

  it('una reserva pagada cotiza antes de confirmar y muestra el reembolso', async () => {
    const quote: CancellationQuote = {
      reserva_id: 5, politica_id: 2, politica: 'Flexible', regla_id: 7, dias_anticipacion: 10,
      monto_pagado: '700.00', porcentaje_penalizacion: '25.00', monto_penalizacion: '175.00',
      monto_reembolso: '525.00',
    };
    const result: PaidCancellationResult = {
      cancelacion_id: 9, reserva_id: 5, estado_reserva: 'CANCELADA', dias_anticipacion: 10,
      porcentaje_penalizacion: '25.00', monto_penalizacion: '175.00', monto_reembolso: '525.00',
      reembolso: {
        id: 3, estado: 'COMPLETADO', monto: '525.00', moneda_id: 1, referencia: 're_1',
        solicitado_en: '2026-10-30T10:00:00-04:00', procesado_en: '2026-10-30T10:00:01-04:00', motivo_fallo: null,
      },
    };
    await render(BOOKING);
    traveler.cancellationQuote.and.returnValue(of(quote));
    traveler.cancelPaid.and.returnValue(of(result));

    const buttons = Array.from(fixture.nativeElement.querySelectorAll('button')) as HTMLButtonElement[];
    buttons.find((button) => button.textContent?.includes('Consultar cancelación'))!.click();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Recibirás');
    expect(fixture.nativeElement.textContent).toContain('525.00');

    const updatedButtons = Array.from(fixture.nativeElement.querySelectorAll('button')) as HTMLButtonElement[];
    updatedButtons.find((button) => button.textContent?.includes('Confirmar cancelación'))!.click();
    fixture.detectChanges();
    expect(traveler.cancelPaid).toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('Cancelación y devolución completadas');
  });
});
