import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap } from '@angular/router';
import { of } from 'rxjs';
import { AuthService } from '../../../core/auth/auth.service';
import { CompaniesService } from '../../../core/companies/companies.service';
import { MyPlan, MyPlanService } from '../../../core/subscription/my-plan.service';
import { MiPlan } from './mi-plan';

const PLAN: MyPlan = {
  empresa: { id: 5, nombre: 'Hotel Cortez', estado: 'ACTIVO' },
  estado: 'VENCIDA',
  restringida: true,
  plan: { codigo: 'BASICO', nombre: 'Básico', periodicidad: 'MENSUAL', precio: '150.00', moneda: 'BOB', precio_renovacion: '150.00' },
  inicio: '2026-09-06',
  vence: '2026-10-06',
  dias_restantes: null,
  renovacion_automatica: false,
  uso: [{ recurso: 'productos', etiqueta: 'Productos', usado: 9, limite: 10 }],
  es_propietario: true,
  puede_pagar: true,
  pagos: [],
};

describe('MiPlan', () => {
  let fixture: ComponentFixture<MiPlan>;
  let service: jasmine.SpyObj<MyPlanService>;

  beforeEach(async () => {
    service = jasmine.createSpyObj<MyPlanService>('MyPlanService', ['get', 'setAutoRenew', 'pay']);
    service.get.and.returnValue(of(PLAN));
    const companies = jasmine.createSpyObj<CompaniesService>('CompaniesService', ['listPlans']);
    companies.listPlans.and.returnValue(of([]));
    await TestBed.configureTestingModule({
      imports: [MiPlan],
      providers: [
        { provide: MyPlanService, useValue: service },
        { provide: CompaniesService, useValue: companies },
        { provide: AuthService, useValue: { session: signal({ user: { roles: ['TENANT_ADMIN'], tenants: [{ id: 5 }] } }) } },
        { provide: ActivatedRoute, useValue: { snapshot: { queryParamMap: convertToParamMap({ pago: 'exito' }) } } },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(MiPlan);
    fixture.detectChanges();
  });

  it('muestra el plan vencido, la restricción y el uso', () => {
    const text = fixture.nativeElement.textContent as string;
    expect(service.get).toHaveBeenCalledWith(5);
    expect(text).toContain('Básico');
    expect(text).toContain('Vencido');
    expect(text).toContain('Tu plan venció');
    expect(text).toContain('9 de 10');
    expect(text).toContain('¡Pago recibido!');
  });

  it('el propietario puede pagar la renovación', () => {
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Renovar o cambiar de plan');
    expect(text).toContain('Pagar BOB 150.00');
  });
});
