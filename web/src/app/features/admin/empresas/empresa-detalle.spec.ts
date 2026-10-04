import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { AuthService } from '../../../core/auth/auth.service';
import {
  Company,
  CompanyStatus,
  CompanySubscriptionInfo,
  Subscription,
} from '../../../core/companies/companies.models';
import { CompaniesService } from '../../../core/companies/companies.service';
import { EmpresaDetalle } from './empresa-detalle';

const COMPANY: Company = {
  id: 7,
  razon_social: 'ToursBo SRL',
  nombre_comercial: 'ToursBo',
  ciudad_id: 1,
  ciudad: {
    id: 1,
    nombre: 'Santa Cruz de la Sierra',
    pais_id: 1,
    pais: 'Bolivia',
    latitud: '-17.783300',
    longitud: '-63.182100',
  },
  subdominio: 'toursbo',
  nit: '123456',
  email_contacto: 'contacto@toursbo.test',
  telefono: '70000000',
  estado: 'PENDIENTE',
  propietario: {
    id: 4,
    email: 'propietario@toursbo.test',
    nombres: 'Ana',
    apellidos: 'Pérez',
    telefono: null,
  },
  creado_en: '2026-10-04T12:00:00Z',
  actualizado_en: '2026-10-04T12:00:00Z',
};

class CompaniesServiceDouble {
  get = jasmine.createSpy('get').and.returnValue(of(COMPANY));
  getSubscription = jasmine.createSpy('getSubscription').and.returnValue(
    of({ suscripcion: null, uso: { usuarios: 1, productos: 0 } }),
  );
  listCities = jasmine.createSpy('listCities').and.returnValue(of([]));
  listPlans = jasmine.createSpy('listPlans').and.returnValue(of([]));
  update = jasmine.createSpy('update').and.returnValue(of(COMPANY));
  assignOwner = jasmine.createSpy('assignOwner').and.returnValue(of(COMPANY));
  changeSubscription = jasmine.createSpy('changeSubscription');
  updateStatus = jasmine
    .createSpy('updateStatus')
    .and.callFake((_id: number, estado: CompanyStatus) => of({ ...COMPANY, estado }));
}

describe('EmpresaDetalle', () => {
  let fixture: ComponentFixture<EmpresaDetalle>;
  let component: EmpresaDetalle;
  let companies: CompaniesServiceDouble;

  beforeEach(async () => {
    companies = new CompaniesServiceDouble();
    await TestBed.configureTestingModule({
      imports: [EmpresaDetalle],
      providers: [
        provideRouter([]),
        { provide: CompaniesService, useValue: companies },
        {
          provide: AuthService,
          useValue: {
            session: signal({
              user: {
                roles: [],
                permisos: [
                  'TENANTS_LEER',
                  'TENANTS_GESTIONAR',
                  'SUSCRIPCIONES_GESTIONAR',
                ],
              },
            }),
          },
        },
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: convertToParamMap({ id: '7' }) } },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(EmpresaDetalle);
    component = fixture.componentInstance;
    (component as unknown as { company: { set: (value: Company) => void } }).company.set(COMPANY);
  });

  type Internal = {
    availableTransitions: () => Array<{ value: CompanyStatus }>;
    pendingStatus: () => { value: CompanyStatus } | null;
    company: () => Company | null;
    subscription: {
      (): CompanySubscriptionInfo | null;
      set: (value: CompanySubscriptionInfo) => void;
    };
    errorMessage: () => string | null;
    ownerForm: {
      patchValue: (value: Record<string, string>) => void;
    };
    selectedPlanCode: () => string;
    autoRenew: () => boolean;
    requestStatusChange: (option: {
      value: CompanyStatus;
      label: string;
      description: string;
      tone: 'positive' | 'warning' | 'danger';
    }) => void;
    confirmStatusChange: () => void;
    startOwnerEdit: () => void;
    submitOwner: () => void;
    startPlanEdit: () => void;
    selectPlan: (code: string) => void;
    submitPlan: () => void;
  };

  const inner = () => component as unknown as Internal;

  it('desde pendiente solo ofrece activar o inactivar', () => {
    expect(inner().availableTransitions().map((option) => option.value)).toEqual([
      'ACTIVO',
      'INACTIVO',
    ]);
  });

  it('desde activa nunca permite volver a pendiente', () => {
    (component as unknown as { company: { set: (value: Company) => void } }).company.set({
      ...COMPANY,
      estado: 'ACTIVO',
    });

    expect(inner().availableTransitions().map((option) => option.value)).toEqual([
      'SUSPENDIDO',
      'INACTIVO',
    ]);
  });

  it('pide confirmación antes de llamar al backend', () => {
    const option = {
      value: 'ACTIVO' as const,
      label: 'Activar empresa',
      description: 'Puede operar.',
      tone: 'positive' as const,
    };

    inner().requestStatusChange(option);

    expect(inner().pendingStatus()?.value).toBe('ACTIVO');
    expect(companies.updateStatus).not.toHaveBeenCalled();
  });

  it('confirma usando la acción específica y actualiza la ficha', () => {
    inner().requestStatusChange({
      value: 'ACTIVO',
      label: 'Activar empresa',
      description: 'Puede operar.',
      tone: 'positive',
    });

    inner().confirmStatusChange();

    expect(companies.updateStatus).toHaveBeenCalledOnceWith(7, 'ACTIVO');
    expect(inner().company()?.estado).toBe('ACTIVO');
    expect(inner().pendingStatus()).toBeNull();
  });

  it('conserva abierta la confirmación si el backend rechaza la activación', () => {
    companies.updateStatus.and.returnValue(
      throwError(() => ({
        status: 400,
        error: { error: { details: { propietario: ['Falta propietario.'] } } },
      })),
    );
    inner().requestStatusChange({
      value: 'ACTIVO',
      label: 'Activar empresa',
      description: 'Puede operar.',
      tone: 'positive',
    });

    inner().confirmStatusChange();

    expect(inner().pendingStatus()?.value).toBe('ACTIVO');
    expect(inner().errorMessage()).toBe('Falta propietario.');
  });

  it('asigna un propietario sin enviar una contraseña vacía', () => {
    const updated = {
      ...COMPANY,
      propietario: { ...COMPANY.propietario!, nombres: 'María' },
    };
    companies.assignOwner.and.returnValue(of(updated));
    inner().startOwnerEdit();
    inner().ownerForm.patchValue({ nombres: 'María', password: '' });

    inner().submitOwner();

    expect(companies.assignOwner).toHaveBeenCalledOnceWith(7, {
      email: 'propietario@toursbo.test',
      nombres: 'María',
      apellidos: 'Pérez',
      telefono: undefined,
      password: undefined,
    });
    expect(inner().company()?.propietario?.nombres).toBe('María');
  });

  it('inicia el cambio con las condiciones actuales y conserva el uso', () => {
    const activeSubscription = {
      id: 11,
      plan: {
        id: 2,
        codigo: 'PRO',
        nombre: 'Pro',
        moneda: 'BOB',
        precio: '200.00',
        periodicidad: 'MENSUAL' as const,
        descripcion: null,
        precio_mensual: '200.00',
        max_usuarios: 10,
        max_productos: 100,
        porcentaje_comision: '0.00',
        activo: true,
      },
      fecha_inicio: '2026-10-04',
      fecha_fin: null,
      estado: 'ACTIVA' as const,
      renovacion_automatica: true,
      precio_contratado: '200.00',
      moneda_contratada: 'BOB',
      periodicidad_contratada: 'MENSUAL' as const,
      creado_en: '2026-10-04T12:00:00Z',
    };
    inner().subscription.set({
      suscripcion: activeSubscription,
      uso: { usuarios: 3, productos: 8 },
    });
    companies.changeSubscription.and.returnValue(
      of({ ...activeSubscription, id: 12, renovacion_automatica: false } as Subscription),
    );

    inner().startPlanEdit();
    expect(inner().selectedPlanCode()).toBe('PRO');
    expect(inner().autoRenew()).toBeTrue();

    inner().selectPlan('BASICO');
    inner().submitPlan();

    expect(companies.changeSubscription).toHaveBeenCalledOnceWith(7, 'BASICO', true);
    expect(inner().subscription()?.uso).toEqual({ usuarios: 3, productos: 8 });
    expect(inner().subscription()?.suscripcion?.id).toBe(12);
  });
});
