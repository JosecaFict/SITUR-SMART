import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { CustomerDetail, CustomerPage, CustomersService } from '../../../core/customers/customers.service';
import { Clientes } from './clientes';

const ROW = {
  id: 7, email: 'turista1@situr.com.bo', nombres: 'Turista', apellidos: 'Uno', telefono: null,
  estado: 'ACTIVO' as const, correo_verificado: true, registrado_en: '2026-10-01T10:00:00-04:00',
  ultimo_acceso: null, reservas: 2, total_pagado: [{ moneda: 'BOB', total: '900.00' }],
};
const PAGE: CustomerPage = {
  count: 1, next: null, previous: null, results: [ROW],
  resumen: { total: 4, nuevos_mes: 1, con_reservas: 2, bloqueados: 0 },
};
const DETAIL: CustomerDetail = {
  ...ROW,
  actividad: { reservas: 2, pagadas: 1, pendientes: 1, canceladas: 0, total_pagado: ROW.total_pagado },
  sesiones_abiertas: 1, dispositivos_push: 1, reservas: [], historial: [],
};

describe('Clientes', () => {
  let fixture: ComponentFixture<Clientes>;
  let service: jasmine.SpyObj<CustomersService>;
  const text = () => fixture.nativeElement.textContent as string;
  const button = (label: string) =>
    Array.from(fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>)
      .find((item) => item.textContent?.includes(label))!;

  beforeEach(async () => {
    service = jasmine.createSpyObj<CustomersService>('CustomersService', ['list', 'detail', 'block', 'unblock', 'closeSessions', 'sendPasswordReset']);
    service.list.and.returnValue(of(PAGE));
    service.detail.and.returnValue(of(DETAIL));
    service.block.and.returnValue(of({ ...DETAIL, estado: 'BLOQUEADO' }));
    await TestBed.configureTestingModule({
      imports: [Clientes],
      providers: [{ provide: CustomersService, useValue: service }],
    }).compileComponents();
    fixture = TestBed.createComponent(Clientes);
    fixture.detectChanges();
  });

  it('lista los clientes con sus totales', () => {
    expect(text()).toContain('turista1@situr.com.bo');
    expect(text()).toContain('2 reservas');
    expect(text()).toContain('Nuevos este mes');
  });

  it('bloquear pide motivo y muestra la cuenta bloqueada', () => {
    button('Turista Uno').click();
    fixture.detectChanges();
    expect(text()).toContain('BOB 900.00');

    button('Bloquear').click();
    fixture.detectChanges();
    button('Bloquear').click(); // confirmar sin motivo
    fixture.detectChanges();
    expect(service.block).not.toHaveBeenCalled();
    expect(text()).toContain('al menos 5 caracteres');

    const motivo = fixture.nativeElement.querySelector('textarea') as HTMLTextAreaElement;
    motivo.value = 'Reservas falsas';
    motivo.dispatchEvent(new Event('input'));
    button('Bloquear').click();
    fixture.detectChanges();
    expect(service.block).toHaveBeenCalledWith(7, 'Reservas falsas');
    expect(text()).toContain('Cuenta bloqueada');
  });
});
