import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { Tour } from '../../../core/tours/tours.models';
import { ToursService } from '../../../core/tours/tours.service';
import { TourForm } from './tour-form';

const TOUR: Tour = {
  id: 3, empresa_id: 7, empresa: 'Salar Tours', tipo_codigo: 'TOUR', tipo: 'Tour', codigo: 'SALAR',
  nombre: 'Salar al amanecer', descripcion: null, ciudad_id: 5, ciudad: 'Uyuni', pais: 'Bolivia',
  localidad: null, moneda_codigo: 'BOB', moneda_simbolo: 'Bs', precio_base: '350.00', capacidad_maxima: 12,
  estado: 'BORRADOR', imagen_url: null, publicar_en: null, retirar_en: null,
  detalle: {
    duracion_minutos: 210, duracion: '3 h 30 min', idioma: 'Español', dificultad: 'MEDIA', edad_minima: 8,
    punto_encuentro: 'Plaza principal', latitud: '-20.460000', longitud: '-66.825000',
    incluye: ['Transporte'], no_incluye: [], requisitos: null,
  },
  paradas: [{ id: 1, orden: 1, nombre: 'Isla Incahuasi', descripcion: null, duracion_minutos: 60 }],
  salidas_proximas: 0, proxima_salida: null, aviso: null,
  creado_en: '2026-10-31T12:00:00Z', actualizado_en: '2026-10-31T12:00:00Z',
};

/**
 * Formulario del tour. Como en HospedajeDetalle, se crea sin `detectChanges()`
 * para no disparar las cargas de `ngOnInit`; los datos se aplican a mano.
 */
describe('TourForm', () => {
  let fixture: ComponentFixture<TourForm>;
  let component: TourForm;
  let tours: jasmine.SpyObj<ToursService>;

  beforeEach(async () => {
    tours = jasmine.createSpyObj<ToursService>('ToursService', ['get', 'create', 'update', 'deactivate']);
    await TestBed.configureTestingModule({
      imports: [TourForm],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: ToursService, useValue: tours },
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: convertToParamMap({ id: '3' }), queryParamMap: convertToParamMap({ empresa: '7' }), data: {} } },
        },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(TourForm);
    component = fixture.componentInstance;
    component['companyId'].set(7);
    component['cities'].set([{ id: 5, nombre: 'Uyuni', pais_id: 1, pais: 'Bolivia', latitud: null, longitud: null }]);
    component['applyTour'](TOUR);
  });

  it('convierte horas y minutos a minutos y manda las coordenadas en par', () => {
    component['form'].patchValue({ duracion_horas: 2, duracion_min: 15 });
    const payload = component.buildPayload();
    expect(payload.duracion_minutos).toBe(135);
    expect(payload.latitud).toBe('-20.460000');
    expect(payload.longitud).toBe('-66.825000');
  });

  it('sin punto en el mapa manda las dos coordenadas en null', () => {
    component['clearPin']();
    const payload = component.buildPayload();
    expect(payload.latitud).toBeNull();
    expect(payload.longitud).toBeNull();
  });

  it('el recorrido viaja en el orden de la lista', () => {
    component['addStop']();
    component['updateStop'](1, 'nombre', 'Ojos del Salar');
    component['moveStop'](1, -1);
    expect(component.buildPayload().paradas?.map((stop) => stop.nombre)).toEqual(['Ojos del Salar', 'Isla Incahuasi']);
  });

  it('no repite un elemento de "incluye"', () => {
    component['newInclude'].setValue('transporte');
    component['addItem']('includes');
    component['newInclude'].setValue('Desayuno');
    component['addItem']('includes');
    expect(component['includes']()).toEqual(['Transporte', 'Desayuno']);
  });

  it('no guarda si una parada quedó sin nombre', () => {
    component['addStop']();
    component['save']();
    expect(tours.update).not.toHaveBeenCalled();
    expect(component['formErrors']()[0]).toContain('parada');
  });

  it('al publicar muestra todo lo que falta, no solo lo primero', () => {
    tours.update.and.returnValue(throwError(() => new HttpErrorResponse({
      status: 400,
      error: { error: { message: 'Datos inválidos', details: { estado: ['Indica el punto de encuentro.', 'Programa al menos una salida futura.'] } } },
    })));
    component['togglePublication']();
    expect(tours.update).toHaveBeenCalledWith(7, 3, { estado: 'PUBLICADO' });
    expect(component['formErrors']()).toEqual(['Indica el punto de encuentro.', 'Programa al menos una salida futura.']);
  });

  it('muestra el aviso cuando el backend devuelve el tour a borrador', () => {
    tours.update.and.returnValue(of({ ...TOUR, aviso: 'El tour pasó a borrador: ahora se vende por salidas.' }));
    component['save']();
    expect(component['notice']()).toContain('borrador');
  });
});
