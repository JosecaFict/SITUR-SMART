import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { AuthService } from '../../../core/auth/auth.service';
import { CompaniesService } from '../../../core/companies/companies.service';
import { CompanyBooking, CompanyBookingsService } from '../../../core/company-bookings/company-bookings.service';
import { Reservas } from './reservas';

const BOOKING: CompanyBooking = {
  id: 9, codigo: 'RES-B6803CA6', orden: 'ORD-0A25942C', estado: 'CONFIRMADA', estado_nombre: 'Confirmada',
  empresa: 'Hotel Cortez',
  producto: { id: 3, nombre: 'Habitación Simple', tipo: 'Habitación', ciudad: 'Santa Cruz', localidad: null, establecimiento: 'Hotel Cortez', es_hospedaje: true },
  fechas: { inicio: '2026-10-07', fin: '2026-10-09', noches: 2 },
  importe: { cantidad: 1, unidad: 'habitación', precio_unitario: '350.00', total: '700.00' },
  huespedes: 1, moneda_codigo: 'BOB', moneda_simbolo: 'Bs',
  pago: { estado: 'APROBADO', proveedor: 'STRIPE', monto: '700.00', procesado_en: null },
  vence_en: null, creado_en: '2026-10-06T22:51:00-04:00',
  cliente: { nombre: 'Lucía Fernández Rojas', email: 'turista1@situr.com.bo', telefono: null },
  llegada: null, comprobante_url: 'https://api.test/comprobantes/x/',
};

describe('Reservas', () => {
  let fixture: ComponentFixture<Reservas>;
  let service: jasmine.SpyObj<CompanyBookingsService>;
  const text = () => fixture.nativeElement.textContent as string;
  const button = (label: string) =>
    Array.from(fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>)
      .find((item) => item.textContent?.includes(label))!;

  beforeEach(async () => {
    service = jasmine.createSpyObj<CompanyBookingsService>('CompanyBookingsService', ['list', 'check', 'checkIn', 'report']);
    service.list.and.returnValue(of({
      count: 1, next: null, previous: null, results: [BOOKING],
      resumen: { llegadas_hoy: 1, proximas: 3, pendientes_pago: 0, ingresos_mes: [{ moneda: 'BOB', total: '700.00' }] },
    }));
    service.check.and.returnValue(of({ reserva: BOOKING, puede_marcar_llegada: true, motivo: null }));
    service.checkIn.and.returnValue(of({ ...BOOKING, llegada: { en: '2026-10-07T14:00:00-04:00', por: 'Jefe Admin' } }));
    await TestBed.configureTestingModule({
      imports: [Reservas],
      providers: [
        { provide: CompanyBookingsService, useValue: service },
        { provide: CompaniesService, useValue: { list: () => of([]) } },
        { provide: AuthService, useValue: { session: signal({ user: { roles: ['TENANT_ADMIN'], permisos: ['RESERVAS_LEER', 'RESERVAS_GESTIONAR'], tenants: [{ id: 5 }] } }) } },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(Reservas);
    fixture.detectChanges();
  });

  it('lista las reservas de su empresa con el cliente y los totales', () => {
    expect(service.list).toHaveBeenCalledWith(5, jasmine.objectContaining({ page: 1 }));
    expect(text()).toContain('Lucía Fernández Rojas');
    expect(text()).toContain('Llegadas de hoy');
    expect(text()).toContain('BOB 700.00');
  });

  it('valida el voucher y marca la llegada', () => {
    const input = fixture.nativeElement.querySelector('input[aria-label="Código de la reserva"]') as HTMLInputElement;
    input.value = 'RES-B6803CA6';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    button('Validar').click();
    fixture.detectChanges();
    expect(service.check).toHaveBeenCalledWith(5, 'RES-B6803CA6');

    button('Marcar llegada').click();
    fixture.detectChanges();
    expect(service.checkIn).toHaveBeenCalledWith(5, 9);
    expect(text()).toContain('Llegada de Lucía Fernández Rojas registrada');
  });
});
