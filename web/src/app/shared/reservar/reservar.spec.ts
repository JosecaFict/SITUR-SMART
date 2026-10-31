import { HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { AccountService } from '../../core/auth/account.service';
import { AuthService } from '../../core/auth/auth.service';
import { addCalendarDays, boliviaToday } from '../../core/products/departure-dates';
import { ProductDeparture } from '../../core/products/products.models';
import { ProductsService } from '../../core/products/products.service';
import { TravelerBooking } from '../../core/traveler/traveler.models';
import { TravelerService } from '../../core/traveler/traveler.service';
import { Reservar } from './reservar';

describe('Reservar', () => {
  let fixture: ComponentFixture<Reservar>;
  let traveler: jasmine.SpyObj<TravelerService>;
  let products: jasmine.SpyObj<ProductsService>;
  const logged = signal(true);
  const el = () => fixture.nativeElement as HTMLElement;

  function render(isRoom = false, scheduled = false, promotionId: number | null = null): void {
    fixture = TestBed.createComponent(Reservar);
    fixture.componentRef.setInput('productId', 7);
    fixture.componentRef.setInput('isRoom', isRoom);
    fixture.componentRef.setInput('isScheduledProduct', scheduled);
    fixture.componentRef.setInput('maxQuantity', 4);
    fixture.componentRef.setInput('capacityPerUnit', 2);
    fixture.componentRef.setInput('promotionId', promotionId);
    fixture.detectChanges();
  }

  function pickDate(label: string, value: string): void {
    const input = el().querySelector(`input[aria-label="${label}"]`) as HTMLInputElement;
    input.value = value;
    input.dispatchEvent(new Event('change'));
    fixture.detectChanges();
  }

  beforeEach(async () => {
    logged.set(true);
    traveler = jasmine.createSpyObj<TravelerService>('TravelerService', ['quote', 'book']);
    products = jasmine.createSpyObj<ProductsService>('ProductsService', ['publicDepartures']);
    products.publicDepartures.and.returnValue(of([]));
    traveler.quote.and.returnValue(of({ total: '450.00', precio_unitario: '450.00', moneda_simbolo: 'Bs', disponible: true, disponibles: 10 }));
    await TestBed.configureTestingModule({
      imports: [Reservar],
      providers: [
        provideRouter([]),
        { provide: TravelerService, useValue: traveler },
        { provide: ProductsService, useValue: products },
        { provide: AuthService, useValue: { isAuthenticated: logged } },
        { provide: AccountService, useValue: { sendEmailCode: () => of(undefined), confirmEmail: () => of({}) } },
      ],
    }).compileComponents();
  });

  it('sin sesión invita a iniciar sesión', () => {
    logged.set(false);
    render();
    expect(el().textContent).toContain('Iniciar sesión para reservar');
  });

  it('cotiza al elegir la fecha y muestra el total', () => {
    render();
    pickDate('Fecha de inicio', '2026-10-20');
    expect(traveler.quote).toHaveBeenCalledWith({ producto_id: 7, fecha_inicio: '2026-10-20', cantidad: 1 });
    expect(el().textContent).toContain('Bs 450.00');
  });

  it('una habitación pide llegada y salida y manda los huéspedes', () => {
    render(true);
    pickDate('Fecha de inicio', '2026-10-20');
    expect(traveler.quote).not.toHaveBeenCalled();
    pickDate('Fecha de salida', '2026-10-22');
    expect(traveler.quote).toHaveBeenCalledWith(jasmine.objectContaining({ fecha_fin: '2026-10-22', huespedes: 1 }));
  });

  it('si falta verificar el correo, lo pide en vez de fallar', () => {
    traveler.book.and.returnValue(throwError(() => new HttpErrorResponse({
      status: 403, error: { error: { code: 'correo_no_verificado', message: 'Verifica tu correo' } },
    })));
    render();
    pickDate('Fecha de inicio', '2026-10-20');
    (Array.from(el().querySelectorAll('button')).find((b) => b.textContent?.includes('Reservar y pagar')) as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(el().querySelector('situr-verificar-correo')).not.toBeNull();
  });

  it('con todo listo abre el pago', () => {
    traveler.book.and.returnValue(of({ id: 3, checkout_url: null } as TravelerBooking));
    render();
    pickDate('Fecha de inicio', '2026-10-20');
    (Array.from(el().querySelectorAll('button')).find((b) => b.textContent?.includes('Reservar y pagar')) as HTMLButtonElement).click();
    expect(traveler.book).toHaveBeenCalledWith({ producto_id: 7, fecha_inicio: '2026-10-20', cantidad: 1 }, jasmine.any(String));
  });

  const tomorrow = () => addCalendarDays(boliviaToday(), 1);
  const departure = (day: string, remaining = 4): ProductDeparture => ({
    id: 41, producto_id: 7, fecha: day, hora_inicio: '10:00', hora_fin: '12:00',
    inicio: `${day}T10:00:00-04:00`, fin: `${day}T12:00:00-04:00`,
    cupo_total: 5, cupos_restantes: remaining, cerrado: false,
  });

  function chooseScheduleDay(day: string): void {
    pickDate('Elegir otra fecha', day);
  }

  it('muestra horarios reales y solo cotiza y reserva el horario elegido', () => {
    const day = tomorrow();
    products.publicDepartures.and.returnValue(of([departure(day)]));
    traveler.quote.and.returnValue(of({
      total: '450.00', precio_unitario: '450.00', moneda_simbolo: 'Bs', disponible: true,
      disponibles: 4, salida_id: 41,
    }));
    traveler.book.and.returnValue(of({ id: 3, checkout_url: null } as TravelerBooking));
    render(false, true);
    chooseScheduleDay(day);
    expect(products.publicDepartures).toHaveBeenCalledWith(7, day);
    expect(traveler.quote).not.toHaveBeenCalled();
    const pay = Array.from(el().querySelectorAll('button')).find((button) => button.textContent?.includes('Reservar y pagar')) as HTMLButtonElement;
    expect(pay.disabled).toBeTrue();
    const slot = Array.from(el().querySelectorAll('button')).find((button) => button.textContent?.includes('10:00')) as HTMLButtonElement;
    slot.click(); fixture.detectChanges();
    expect(traveler.quote).toHaveBeenCalledWith({ producto_id: 7, fecha_inicio: day, cantidad: 1, salida_id: 41 });
    pay.click(); fixture.detectChanges();
    expect(traveler.book).toHaveBeenCalledWith({ producto_id: 7, fecha_inicio: day, cantidad: 1, salida_id: 41 }, jasmine.any(String));
  });

  it('permite disponibilidad diaria solo si la cotización devuelve salida_id null', () => {
    const day = tomorrow();
    traveler.quote.and.returnValue(of({
      total: '450.00', precio_unitario: '450.00', moneda_simbolo: 'Bs', disponible: true,
      disponibles: 4, salida_id: null,
    }));
    traveler.book.and.returnValue(of({ id: 3, checkout_url: null } as TravelerBooking));
    render(false, true);
    chooseScheduleDay(day);
    expect(el().textContent).toContain('Disponibilidad por día, sin horario específico');
    const pay = Array.from(el().querySelectorAll('button')).find((button) => button.textContent?.includes('Reservar y pagar')) as HTMLButtonElement;
    expect(pay.disabled).toBeFalse();
    pay.click(); fixture.detectChanges();
    expect(traveler.book).toHaveBeenCalledWith({ producto_id: 7, fecha_inicio: day, cantidad: 1 }, jasmine.any(String));
  });

  it('no inventa disponibilidad diaria si no hay salidas públicas pero la cotización asigna una salida', () => {
    const day = tomorrow();
    traveler.quote.and.returnValue(of({
      total: '450.00', precio_unitario: '450.00', moneda_simbolo: 'Bs', disponible: false,
      disponibles: 0, salida_id: 41,
    }));
    render(false, true);
    chooseScheduleDay(day);
    const pay = Array.from(el().querySelectorAll('button')).find((button) => button.textContent?.includes('Reservar y pagar')) as HTMLButtonElement;
    expect(pay.disabled).toBeTrue();
    expect(el().textContent).not.toContain('Disponibilidad por día, sin horario específico');
  });

  it('revalida al cambiar personas o fecha y deshabilita un horario sin cupo suficiente', () => {
    const day = tomorrow();
    const next = addCalendarDays(day, 1);
    products.publicDepartures.and.callFake((_id, date) => of([departure(date, 1)]));
    traveler.quote.and.returnValue(of({
      total: '450.00', precio_unitario: '450.00', moneda_simbolo: 'Bs', disponible: true,
      disponibles: 1, salida_id: 41,
    }));
    render(false, true);
    chooseScheduleDay(day);
    (Array.from(el().querySelectorAll('button')).find((button) => button.textContent?.includes('10:00')) as HTMLButtonElement).click();
    const quantity = el().querySelector('select[aria-label="Cantidad"]') as HTMLSelectElement;
    quantity.value = '2'; quantity.dispatchEvent(new Event('change')); fixture.detectChanges();
    expect(products.publicDepartures).toHaveBeenCalledTimes(2);
    expect((Array.from(el().querySelectorAll('button')).find((button) => button.textContent?.includes('10:00')) as HTMLButtonElement).disabled).toBeTrue();
    chooseScheduleDay(next);
    expect(products.publicDepartures).toHaveBeenCalledWith(7, next);
    expect(traveler.book).not.toHaveBeenCalled();
  });

  it('no permite fechas pasadas ni horarios cerrados o vencidos', () => {
    const day = tomorrow();
    products.publicDepartures.and.returnValue(of([
      { ...departure(day), cerrado: true },
      { ...departure(day), id: 42, inicio: '2020-01-01T10:00:00-04:00' },
    ]));
    render(false, true);
    chooseScheduleDay('2020-01-01');
    expect(products.publicDepartures).not.toHaveBeenCalled();
    chooseScheduleDay(day);
    const slots = Array.from(el().querySelectorAll('button')).filter((button) => button.textContent?.includes('10:00'));
    expect(slots.length).toBe(2);
    expect(slots.every((button) => button.disabled)).toBeTrue();
    expect(traveler.quote).not.toHaveBeenCalled();
  });

  it('muestra el error del backend y revalida al perder el cupo en una reserva simultánea', () => {
    const day = tomorrow();
    products.publicDepartures.and.returnValue(of([departure(day)]));
    traveler.quote.and.returnValue(of({
      total: '450.00', precio_unitario: '450.00', moneda_simbolo: 'Bs', disponible: true,
      disponibles: 4, salida_id: 41,
    }));
    traveler.book.and.returnValue(throwError(() => new HttpErrorResponse({
      status: 409, error: { error: { message: 'Ya no quedan cupos para esta salida.' } },
    })));
    render(false, true);
    chooseScheduleDay(day);
    (Array.from(el().querySelectorAll('button')).find((button) => button.textContent?.includes('10:00')) as HTMLButtonElement).click();
    fixture.detectChanges();
    (Array.from(el().querySelectorAll('button')).find((button) => button.textContent?.includes('Reservar y pagar')) as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(products.publicDepartures).toHaveBeenCalledTimes(2);
    expect(el().textContent).toContain('Ya no quedan cupos para esta salida.');
  });
  const discount = {
    id: 21, modalidad: 'EXISTENTE' as const, nombre: 'Oferta local', porcentaje_descuento: '20.00',
    precio_original: '100.00', precio_final: '80.00', monto_descuento: '20.00',
    total_original: '100.00', descuento_total: '20.00', total: '80.00',
    inicio: '2026-11-01T10:00:00-04:00', fin: '2026-11-30T10:00:00-04:00',
  };

  it('envía promocion_id al cotizar y reservar, con desglose del servidor', () => {
    const day = tomorrow();
    traveler.quote.and.returnValue(of({ total: '80.00', precio_unitario: '80.00', moneda_simbolo: 'Bs', disponible: true, disponibles: 4, promocion: discount }));
    traveler.book.and.returnValue(of({ id: 13, checkout_url: null, importe: { cantidad: 1, unidad: 'servicio', precio_unitario: '80.00', total: '80.00' }, promocion: discount } as unknown as TravelerBooking));
    render(false, false, 21);
    pickDate('Fecha de inicio', day);
    expect(traveler.quote).toHaveBeenCalledWith({ producto_id: 7, fecha_inicio: day, cantidad: 1, promocion_id: 21 });
    expect(el().textContent).toContain('Original: Bs 100.00');
    expect(el().textContent).toContain('Bs 80.00');
    (Array.from(el().querySelectorAll('button')).find((button) => button.textContent?.includes('Reservar y pagar')) as HTMLButtonElement).click();
    expect(traveler.book).toHaveBeenCalledWith({ producto_id: 7, fecha_inicio: day, cantidad: 1, promocion_id: 21 }, jasmine.any(String));
  });

  it('impide reservar si la promoción desapareció o cambió su precio al revalidar', () => {
    const day = tomorrow();
    traveler.quote.and.returnValues(
      of({ total: '80.00', precio_unitario: '80.00', moneda_simbolo: 'Bs', disponible: true, disponibles: 4, promocion: discount }),
      of({ total: '75.00', precio_unitario: '75.00', moneda_simbolo: 'Bs', disponible: true, disponibles: 4, promocion: { ...discount, total: '75.00' } }),
    );
    render(false, false, 21);
    pickDate('Fecha de inicio', day);
    (Array.from(el().querySelectorAll('button')).find((button) => button.textContent?.includes('Reservar y pagar')) as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(traveler.book).not.toHaveBeenCalled();
    expect(el().textContent).toContain('Revisa la nueva cotización');
  });
});
