import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { Tour, TourDeparture } from '../../../core/tours/tours.models';
import { DeparturesService } from '../../../core/tours/tours.service';
import { parseLanguages } from '../guias/guias';
import { TourSalidas } from './tour-salidas';

const SALIDA: TourDeparture = {
  id: 31, tour_id: 3, inicio: '2026-11-08T08:00:00-04:00', fin: '2026-11-08T11:30:00-04:00',
  cupo: 12, reservados: 2, disponibles: 10, cerrada: false, guia_id: null, guia: null,
};

describe('TourSalidas', () => {
  let fixture: ComponentFixture<TourSalidas>;
  let component: TourSalidas;
  let departures: jasmine.SpyObj<DeparturesService>;

  beforeEach(async () => {
    departures = jasmine.createSpyObj<DeparturesService>('DeparturesService', ['list', 'create', 'createRecurring', 'update', 'close', 'remove']);
    departures.list.and.returnValue(of([SALIDA]));
    await TestBed.configureTestingModule({
      imports: [TourSalidas],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: DeparturesService, useValue: departures },
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: convertToParamMap({ id: '3' }), queryParamMap: convertToParamMap({ empresa: '7' }), data: {} } },
        },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(TourSalidas);
    component = fixture.componentInstance;
    component['companyId'].set(7);
    component['tour'].set({ id: 3, capacidad_maxima: 12 } as Tour);
  });

  it('las salidas repetidas mandan días, horas y rango', () => {
    departures.createRecurring.and.returnValue(of({ creadas: [SALIDA], omitidas: 1 }));
    component['toggleWeekday'](3);
    component['toggleWeekday'](0);
    component['startTime'].set('08:00');
    component['from'].set('2026-11-01');
    component['to'].set('2026-11-28');
    component['capacity'].set(10);
    component['create']();
    expect(departures.createRecurring).toHaveBeenCalledWith(7, 3, {
      cupo: 10, guia_id: null, dias_semana: [0, 3], hora_inicio: '08:00', hora_fin: null,
      desde: '2026-11-01', hasta: '2026-11-28',
    });
    expect(component['successMessage']()).toContain('1 omitidas');
  });

  it('sin días elegidos no llama al backend', () => {
    component['create']();
    expect(departures.createRecurring).not.toHaveBeenCalled();
    expect(component['createError']()).toContain('día');
  });

  it('una salida suelta manda inicio y fin en la hora local', () => {
    departures.create.and.returnValue(of(SALIDA));
    component['mode'].set('una');
    component['day'].set('2026-11-08');
    component['startTime'].set('08:00');
    component['endTime'].set('11:30');
    component['create']();
    expect(departures.create).toHaveBeenCalledWith(7, 3, jasmine.objectContaining({
      inicio: '2026-11-08T08:00', fin: '2026-11-08T11:30',
    }));
  });

  it('agrupa las salidas por día', () => {
    component['departures'].set([SALIDA, { ...SALIDA, id: 32, inicio: '2026-11-08T15:00:00-04:00' }]);
    expect(component['groups']().length).toBe(1);
    expect(component['groups']()[0].departures.length).toBe(2);
  });

  it('solo marca el cupo como cambiado si es distinto', () => {
    component['draftCapacity'](SALIDA, '12');
    expect(component['capacityChanged'](SALIDA)).toBeFalse();
    component['draftCapacity'](SALIDA, '8');
    expect(component['capacityChanged'](SALIDA)).toBeTrue();
  });
});

describe('parseLanguages', () => {
  it('separa por coma y quita vacíos y repetidos', () => {
    expect(parseLanguages('Español, inglés, , español,Quechua')).toEqual(['Español', 'inglés', 'Quechua']);
  });
});
