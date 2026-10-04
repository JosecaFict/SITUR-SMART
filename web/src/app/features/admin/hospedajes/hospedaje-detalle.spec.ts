import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { City, Country } from '../../../core/companies/companies.models';
import { HospedajeDetalle } from './hospedaje-detalle';

const BOLIVIA: Country = { id: 1, codigo: 'BOL', nombre: 'Bolivia' };
const PERU: Country = { id: 2, codigo: 'PER', nombre: 'Perú' };

const CIUDADES: City[] = [
  { id: 5, nombre: 'Uyuni', pais_id: 1, pais: 'Bolivia' },
  { id: 6, nombre: 'La Paz', pais_id: 1, pais: 'Bolivia' },
  { id: 9, nombre: 'Cusco', pais_id: 2, pais: 'Perú' },
];

/**
 * País y ciudad del formulario de hospedaje.
 *
 * El componente se crea sin `detectChanges()` a propósito: así no corre
 * `ngOnInit` y no hay peticiones que atender. Los catálogos se siembran
 * directamente en las señales, que es lo que haría la carga real, y se ejercita
 * la lógica de filtrado tal como está escrita.
 *
 * Se usa acceso por corchetes porque los miembros son `protected`/`private`:
 * es deliberado, la alternativa sería abrirlos solo para poder probarlos.
 */
describe('HospedajeDetalle · país y ciudad', () => {
  let fixture: ComponentFixture<HospedajeDetalle>;
  let component: HospedajeDetalle;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HospedajeDetalle],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          // Alta: sin :id en la ruta.
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              paramMap: convertToParamMap({}),
              queryParamMap: convertToParamMap({}),
              data: {},
            },
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(HospedajeDetalle);
    component = fixture.componentInstance;

    const instancia = component as unknown as Record<string, { set: (v: unknown) => void }>;
    instancia['countries'].set([BOLIVIA, PERU]);
    instancia['cities'].set(CIUDADES);
  });

  const form = () => (component as unknown as { lodgingForm: any }).lodgingForm;
  const ciudadesVisibles = () =>
    (component as unknown as { filteredCities: () => City[] }).filteredCities();
  const cambiarPais = (valor: string) => {
    form().controls.pais.setValue(valor);
    (component as unknown as { countryChanged: () => void }).countryChanged();
  };

  it('no ofrece ninguna ciudad mientras no haya país', () => {
    expect(ciudadesVisibles()).toEqual([]);
  });

  it('el país es obligatorio', () => {
    expect(form().controls.pais.hasError('required')).toBeTrue();
  });

  it('al elegir un país ofrece solo sus ciudades', () => {
    cambiarPais('1');

    expect(ciudadesVisibles().map((c) => c.nombre)).toEqual(['Uyuni', 'La Paz']);
  });

  it('al cambiar de país ofrece las del nuevo', () => {
    cambiarPais('1');
    cambiarPais('2');

    expect(ciudadesVisibles().map((c) => c.nombre)).toEqual(['Cusco']);
  });

  it('al cambiar de país limpia una ciudad que ya no pertenece', () => {
    cambiarPais('1');
    form().controls.ciudad_id.setValue(5); // Uyuni, Bolivia

    cambiarPais('2'); // Perú

    expect(form().controls.ciudad_id.value).toBe(0);
  });

  it('al cambiar de país conserva la ciudad si sigue siendo compatible', () => {
    cambiarPais('1');
    form().controls.ciudad_id.setValue(6); // La Paz, Bolivia

    cambiarPais('1'); // mismo país

    expect(form().controls.ciudad_id.value).toBe(6);
  });

  it('volver a "sin país" deja la lista vacía y limpia la ciudad', () => {
    cambiarPais('1');
    form().controls.ciudad_id.setValue(5);

    cambiarPais('');

    expect(ciudadesVisibles()).toEqual([]);
    expect(form().controls.ciudad_id.value).toBe(0);
  });

  it('el formulario es inválido sin país ni ciudad', () => {
    expect(form().invalid).toBeTrue();
  });

  it('el país no forma parte de lo que se envía al backend', () => {
    // El backend deriva el país de la ciudad: solo recibe ciudad_id.
    cambiarPais('1');
    form().controls.ciudad_id.setValue(5);
    form().controls.nombre.setValue('Hotel de prueba');

    const enviado = (component as unknown as { buildLodgingPayload: () => object })
      .buildLodgingPayload();

    expect(Object.keys(enviado)).not.toContain('pais');
    expect((enviado as { ciudad_id: number }).ciudad_id).toBe(5);
  });
});
