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

  beforeEach(async () => {
    logged.set(true);
    traveler = jasmine.createSpyObj<TravelerService>('TravelerService', ['quote', 'book']);
    traveler.quote.and.returnValue(of({ total: '450.00', precio_unitario: '450.00', moneda_simbolo: 'Bs', disponible: true, disponibles: 10 }));
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
});
