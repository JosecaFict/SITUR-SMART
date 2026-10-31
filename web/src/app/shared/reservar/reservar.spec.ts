import { HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { AccountService } from '../../core/auth/account.service';
import { AuthService } from '../../core/auth/auth.service';
import { TravelerBooking } from '../../core/traveler/traveler.models';
import { TravelerService } from '../../core/traveler/traveler.service';
import { Reservar } from './reservar';

describe('Reservar', () => {
  let fixture: ComponentFixture<Reservar>;
  let traveler: jasmine.SpyObj<TravelerService>;
  const logged = signal(true);
  const el = () => fixture.nativeElement as HTMLElement;

  function render(isRoom = false): void {
    fixture = TestBed.createComponent(Reservar);
    fixture.componentRef.setInput('productId', 7);
    fixture.componentRef.setInput('isRoom', isRoom);
    fixture.componentRef.setInput('maxQuantity', 4);
    fixture.componentRef.setInput('capacityPerUnit', 2);
    fixture.detectChanges();
  }

  function pickDate(label: string, value: string): void {
    const input = el().querySelector(`input[aria-label="${label}"]`) as HTMLInputElement;
    input.value = value;
    input.dispatchEvent(new Event('change'));
    fixture.detectChanges();
  }

  function acceptPolicy(): void {
    const checkbox = el().querySelector('input[type="checkbox"]') as HTMLInputElement;
    checkbox.checked = true;
    checkbox.dispatchEvent(new Event('change'));
    fixture.detectChanges();
  }

  beforeEach(async () => {
    logged.set(true);
    traveler = jasmine.createSpyObj<TravelerService>('TravelerService', ['quote', 'book']);
    traveler.quote.and.returnValue(of({
      total: '450.00', precio_unitario: '450.00', moneda_simbolo: 'Bs', disponible: true, disponibles: 10,
      politica_cancelacion: {
        id: 12, nombre: 'Política estándar SITUR-SMART', reembolsable: true,
        reglas: [
          { dias_antes_min: 0, dias_antes_max: 0, porcentaje_penalizacion: '100.00' },
          { dias_antes_min: 7, dias_antes_max: null, porcentaje_penalizacion: '0.00' },
        ],
      },
    }));
    await TestBed.configureTestingModule({
      imports: [Reservar],
      providers: [
        provideRouter([]),
        { provide: TravelerService, useValue: traveler },
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
    acceptPolicy();
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
    acceptPolicy();
    (Array.from(el().querySelectorAll('button')).find((b) => b.textContent?.includes('Reservar y pagar')) as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(el().querySelector('situr-verificar-correo')).not.toBeNull();
  });

  it('con todo listo abre el pago', () => {
    traveler.book.and.returnValue(of({ id: 3, checkout_url: null } as TravelerBooking));
    render();
    pickDate('Fecha de inicio', '2026-10-20');
    acceptPolicy();
    (Array.from(el().querySelectorAll('button')).find((b) => b.textContent?.includes('Reservar y pagar')) as HTMLButtonElement).click();
    expect(traveler.book).toHaveBeenCalledWith({
      producto_id: 7,
      fecha_inicio: '2026-10-20',
      cantidad: 1,
      politica_cancelacion_id: 12,
      acepta_politica_cancelacion: true,
      razon_social_facturacion: '',
      nit_facturacion: '',
    }, jasmine.any(String));
  });

  describe('en un tour que se vende por salidas', () => {
    const departures = [
      { id: 31, tour_id: 7, inicio: '2026-11-08T08:00:00-04:00', fin: '2026-11-08T11:30:00-04:00', disponibles: 3, guia: 'Marcelo Choque', guia_idiomas: ['Español'] },
      { id: 32, tour_id: 7, inicio: '2026-11-09T08:00:00-04:00', fin: '2026-11-09T11:30:00-04:00', disponibles: 0, guia: null, guia_idiomas: null },
    ];

    function renderTour(list = departures): void {
      fixture = TestBed.createComponent(Reservar);
      fixture.componentRef.setInput('productId', 7);
      fixture.componentRef.setInput('maxQuantity', 12);
      fixture.componentRef.setInput('departures', list);
      fixture.detectChanges();
    }

    function chooseDeparture(id: number): void {
      const select = el().querySelector('select[aria-label="Salida"]') as HTMLSelectElement;
      select.value = String(id);
      select.dispatchEvent(new Event('change'));
      fixture.detectChanges();
    }

    it('pide elegir una salida en vez de una fecha', () => {
      renderTour();
      expect(el().querySelector('input[aria-label="Fecha de inicio"]')).toBeNull();
      const options = Array.from(el().querySelectorAll('select[aria-label="Salida"] option')) as HTMLOptionElement[];
      expect(options.length).toBe(3);
      expect(options[2].disabled).toBeTrue();
      expect(options[2].textContent).toContain('agotada');
    });

    it('cotiza con la salida y sin fecha, y muestra el guía', () => {
      renderTour();
      chooseDeparture(31);
      expect(traveler.quote).toHaveBeenCalledWith({ producto_id: 7, salida_id: 31, cantidad: 1 });
      expect(el().textContent).toContain('Guía: Marcelo Choque');
    });

    it('no ofrece más personas que los lugares libres de la salida', () => {
      renderTour();
      chooseDeparture(31);
      const options = el().querySelectorAll('select[aria-label="Cantidad"] option');
      expect(options.length).toBe(3);
    });

    it('sin salidas próximas lo dice y no deja reservar', () => {
      renderTour([]);
      expect(el().textContent).toContain('no tiene salidas próximas');
      const button = Array.from(el().querySelectorAll('button')).find((b) => b.textContent?.includes('Reservar y pagar')) as HTMLButtonElement;
      expect(button.disabled).toBeTrue();
    });
  });

  it('no permite pagar hasta aceptar la política', () => {
    render();
    pickDate('Fecha de inicio', '2026-10-20');
    const button = Array.from(el().querySelectorAll('button'))
      .find((item) => item.textContent?.includes('Reservar y pagar')) as HTMLButtonElement;
    expect(button.disabled).toBeTrue();
    acceptPolicy();
    expect(button.disabled).toBeFalse();
  });
});
