import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { City, Country } from '../../../core/companies/companies.models';
import { GeoPlace } from '../../../core/geo/geo.models';
import { GeoService } from '../../../core/geo/geo.service';
import { LodgingEstablishment } from '../../../core/lodging/lodging.models';
import { HospedajeDetalle } from './hospedaje-detalle';

const BOLIVIA: Country = { id: 1, codigo: 'BOL', nombre: 'Bolivia' };
const PERU: Country = { id: 2, codigo: 'PER', nombre: 'Perú' };

const CIUDADES: City[] = [
  { id: 5, nombre: 'Uyuni', pais_id: 1, pais: 'Bolivia', latitud: '-20.460350', longitud: '-66.825320' },
  { id: 6, nombre: 'La Paz', pais_id: 1, pais: 'Bolivia', latitud: '-16.500000', longitud: '-68.150000' },
  { id: 9, nombre: 'Cusco', pais_id: 2, pais: 'Perú', latitud: '-13.531950', longitud: '-71.967463' },
];

const LUGAR: GeoPlace = {
  etiqueta: 'Avenida Ferroviaria, Uyuni, Bolivia',
  nombre: 'Avenida Ferroviaria',
  localidad: 'Uyuni',
  region: 'Potosí',
  pais: 'Bolivia',
  latitud: '-20.461000',
  longitud: '-66.826000',
  confianza: 0.9,
  capa: 'street',
};

/** Respuesta del backend tras guardar, con lo mínimo que lee el componente. */
const HOTEL_GUARDADO = {
  id: 11,
  producto_id: 2,
  empresa_id: 3,
  empresa: 'ToursBo',
  tipo_hospedaje_codigo: 'HOTEL',
  tipo_hospedaje: 'Hotel',
  nombre: 'Hotel Kachi Wasi',
  descripcion: null,
  ciudad_id: 5,
  ciudad: 'Uyuni',
  pais_id: 1,
  pais: 'Bolivia',
  localidad: null,
  moneda_codigo: 'BOB',
  moneda_simbolo: 'Bs',
  capacidad_total: null,
  estado: 'BORRADOR' as const,
  imagen_url: null,
  direccion: null,
  latitud: null,
  longitud: null,
  categoria_estrellas: null,
  hora_check_in: null,
  hora_check_out: null,
  servicios: [],
  precio_desde: null,
  total_habitaciones: 0,
  creado_en: '2026-10-04T12:00:00Z',
  actualizado_en: '2026-10-04T12:00:00Z',
};

/** Doble del servicio de geo: ninguna prueba toca la red. */
class GeoServiceDoble {
  search = jasmine.createSpy('search').and.returnValue(of({ resultados: [LUGAR] }));
  reverse = jasmine.createSpy('reverse').and.returnValue(of({ resultado: LUGAR }));
}

/**
 * País, ciudad y ubicación en el mapa del formulario de hospedaje.
 *
 * El componente se crea sin `detectChanges()` a propósito: así no corre
 * `ngOnInit` y no hay peticiones que atender. Los catálogos se siembran
 * directamente en las señales, que es lo que haría la carga real, y se ejercita
 * la lógica tal como está escrita.
 *
 * Se usa acceso por corchetes porque los miembros son `protected`/`private`:
 * es deliberado, la alternativa sería abrirlos solo para poder probarlos.
 */
describe('HospedajeDetalle', () => {
  let fixture: ComponentFixture<HospedajeDetalle>;
  let component: HospedajeDetalle;
  let geo: GeoServiceDoble;

  beforeEach(async () => {
    geo = new GeoServiceDoble();

    await TestBed.configureTestingModule({
      imports: [HospedajeDetalle],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: GeoService, useValue: geo },
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
    instancia['companyId'].set(3);
  });

  type Interno = {
    lodgingForm: any;
    filteredCities: () => City[];
    countryChanged: () => void;
    cityChanged: () => void;
    buildLodgingPayload: () => Record<string, unknown>;
    coordinates: () => { lat: number; lng: number } | null;
    locationChanged: () => boolean;
    cityCenter: () => { lat: number; lng: number } | null;
    farFromCityKm: () => number | null;
    geoResults: () => GeoPlace[];
    geoError: () => string | null;
    geoSearched: () => boolean;
    suggestedAddress: () => string | null;
    geoSearchControl: { value: string; setValue: (v: string) => void };
    pinPicked: (p: { lat: number; lng: number }) => void;
    searchAddress: () => void;
    useGeoResult: (p: GeoPlace) => void;
    requestAddressForPin: () => void;
    useSuggestedAddress: () => void;
    clearLocation: () => void;
    prepareNew: () => void;
    applyLodging: (lodging: LodgingEstablishment) => void;
  };

  const inner = () => component as unknown as Interno;
  const form = () => inner().lodgingForm;
  const cambiarPais = (valor: string) => {
    form().controls.pais.setValue(valor);
    inner().countryChanged();
  };
  const elegirCiudad = (id: number) => {
    form().controls.ciudad_id.setValue(id);
    inner().cityChanged();
  };

  describe('país y ciudad', () => {
    it('no ofrece ninguna ciudad mientras no haya país', () => {
      expect(inner().filteredCities()).toEqual([]);
    });

    it('el país es obligatorio', () => {
      expect(form().controls.pais.hasError('required')).toBeTrue();
    });

    it('al elegir un país ofrece solo sus ciudades', () => {
      cambiarPais('1');

      expect(inner().filteredCities().map((c) => c.nombre)).toEqual(['Uyuni', 'La Paz']);
    });

    it('al cambiar de país ofrece las del nuevo', () => {
      cambiarPais('1');
      cambiarPais('2');

      expect(inner().filteredCities().map((c) => c.nombre)).toEqual(['Cusco']);
    });

    it('al cambiar de país limpia una ciudad que ya no pertenece', () => {
      cambiarPais('1');
      elegirCiudad(5); // Uyuni, Bolivia

      cambiarPais('2'); // Perú

      expect(form().controls.ciudad_id.value).toBe(0);
    });

    it('al cambiar de país conserva la ciudad si sigue siendo compatible', () => {
      cambiarPais('1');
      elegirCiudad(6); // La Paz, Bolivia

      cambiarPais('1'); // mismo país

      expect(form().controls.ciudad_id.value).toBe(6);
    });

    it('volver a "sin país" deja la lista vacía y limpia la ciudad', () => {
      cambiarPais('1');
      elegirCiudad(5);

      cambiarPais('');

      expect(inner().filteredCities()).toEqual([]);
      expect(form().controls.ciudad_id.value).toBe(0);
    });

    it('el formulario es inválido sin país ni ciudad', () => {
      expect(form().invalid).toBeTrue();
    });

    it('el país no forma parte de lo que se envía al backend', () => {
      // El backend deriva el país de la ciudad: solo recibe ciudad_id.
      cambiarPais('1');
      elegirCiudad(5);
      form().controls.nombre.setValue('Hotel de prueba');

      const enviado = inner().buildLodgingPayload();

      expect(Object.keys(enviado)).not.toContain('pais');
      expect(enviado['ciudad_id']).toBe(5);
    });

    it('con un solo país en el catálogo lo preselecciona', () => {
      (component as unknown as Record<string, { set: (v: unknown) => void }>)['countries'].set([
        BOLIVIA,
      ]);

      inner().prepareNew();

      expect(form().controls.pais.value).toBe('1');
      expect(inner().filteredCities().length).toBe(2);
    });
  });

  describe('ubicación en el mapa', () => {
    it('arranca sin ubicación', () => {
      expect(inner().coordinates()).toBeNull();
    });

    it('el mapa se centra en la ciudad elegida', () => {
      cambiarPais('1');
      elegirCiudad(5);

      expect(inner().cityCenter()).toEqual({ lat: -20.46035, lng: -66.82532 });
    });

    it('sin ciudad no hay centro que usar', () => {
      expect(inner().cityCenter()).toBeNull();
    });

    it('hacer clic en el mapa coloca el punto', () => {
      inner().pinPicked({ lat: -20.4611, lng: -66.8261 });

      expect(inner().coordinates()).toEqual({ lat: -20.4611, lng: -66.8261 });
    });

    it('avisa que la ubicación quedó sin guardar, y deja de avisar al guardarse', () => {
      expect(inner().locationChanged()).toBeFalse();
      inner().pinPicked({ lat: -20.4611, lng: -66.8261 });
      expect(inner().locationChanged()).toBeTrue();

      // Lo que hace el componente tras un guardado exitoso: releer la respuesta.
      inner().applyLodging({
        ...HOTEL_GUARDADO,
        latitud: '-20.461100',
        longitud: '-66.826100',
      });

      expect(inner().locationChanged()).toBeFalse();
      expect(inner().coordinates()).toEqual({ lat: -20.4611, lng: -66.8261 });
    });

    it('al releer un hospedaje sin ubicación el pin desaparece', () => {
      inner().pinPicked({ lat: -20.4611, lng: -66.8261 });

      inner().applyLodging({ ...HOTEL_GUARDADO, latitud: null, longitud: null });

      expect(inner().coordinates()).toBeNull();
    });

    it('mover el pin NO llama a la geocodificación inversa', () => {
      // Decisión D4: proteger la cuota. El inverso es una acción explícita.
      inner().pinPicked({ lat: -20.4611, lng: -66.8261 });

      expect(geo.reverse).not.toHaveBeenCalled();
    });

    it('las dos coordenadas viajan juntas', () => {
      inner().pinPicked({ lat: -20.4611, lng: -66.8261 });

      const enviado = inner().buildLodgingPayload();

      expect(enviado['latitud']).toBe('-20.461100');
      expect(enviado['longitud']).toBe('-66.826100');
    });

    it('sin ubicación manda las dos en null, nunca una sola', () => {
      const enviado = inner().buildLodgingPayload();

      expect(enviado['latitud']).toBeNull();
      expect(enviado['longitud']).toBeNull();
    });

    it('redondea a los seis decimales que guarda el backend', () => {
      // Lo que entrega el GPS del navegador.
      inner().pinPicked({ lat: -16.4956789123456, lng: -68.1234564999 });

      const enviado = inner().buildLodgingPayload();

      expect(enviado['latitud']).toBe('-16.495679');
      expect(enviado['longitud']).toBe('-68.123456');
    });

    it('quitar la ubicación borra las dos', () => {
      inner().pinPicked({ lat: -20.4611, lng: -66.8261 });

      inner().clearLocation();

      expect(inner().coordinates()).toBeNull();
      expect(inner().buildLodgingPayload()['latitud']).toBeNull();
      expect(inner().buildLodgingPayload()['longitud']).toBeNull();
    });

    it('avisa si el punto quedó muy lejos de la ciudad, sin bloquear', () => {
      cambiarPais('1');
      elegirCiudad(5); // Uyuni
      inner().pinPicked({ lat: -16.5, lng: -68.15 }); // La Paz, a ~440 km

      expect(inner().farFromCityKm()).toBeGreaterThan(100);
      // El aviso no invalida nada: el punto se puede guardar igual.
      expect(inner().buildLodgingPayload()['latitud']).toBe('-16.500000');
    });

    it('no avisa cuando el punto está cerca de la ciudad', () => {
      cambiarPais('1');
      elegirCiudad(5);
      inner().pinPicked({ lat: -20.4611, lng: -66.8261 });

      expect(inner().farFromCityKm()).toBeNull();
    });
  });

  describe('buscador de direcciones', () => {
    it('no busca mientras se escribe', () => {
      inner().geoSearchControl.setValue('avenida ferro');

      expect(geo.search).not.toHaveBeenCalled();
    });

    it('busca al pulsar el botón', () => {
      inner().geoSearchControl.setValue('avenida ferroviaria');

      inner().searchAddress();

      expect(geo.search).toHaveBeenCalled();
      expect(inner().geoResults().length).toBe(1);
    });

    it('no gasta una llamada con menos de tres caracteres', () => {
      inner().geoSearchControl.setValue('av');

      inner().searchAddress();

      expect(geo.search).not.toHaveBeenCalled();
    });

    it('manda la ciudad elegida para sesgar el resultado', () => {
      cambiarPais('1');
      elegirCiudad(5);
      inner().geoSearchControl.setValue('mercado');

      inner().searchAddress();

      expect(geo.search).toHaveBeenCalledWith(3, 'mercado', 5);
    });

    it('elegir un resultado coloca el punto y propone su dirección', () => {
      inner().useGeoResult(LUGAR);

      expect(inner().coordinates()).toEqual({ lat: -20.461, lng: -66.826 });
      expect(inner().suggestedAddress()).toBe('Avenida Ferroviaria, Uyuni, Bolivia');
    });

    it('la dirección propuesta no se copia sola al campo', () => {
      // Decisión D4: sobrescribir lo que alguien escribió sería perder su texto.
      form().controls.direccion.setValue('Al lado de la estación');

      inner().useGeoResult(LUGAR);

      expect(form().controls.direccion.value).toBe('Al lado de la estación');
    });

    it('la copia solo cuando se acepta', () => {
      inner().useGeoResult(LUGAR);

      inner().useSuggestedAddress();

      expect(form().controls.direccion.value).toBe('Avenida Ferroviaria, Uyuni, Bolivia');
      expect(inner().suggestedAddress()).toBeNull();
    });

    it('el inverso solo corre cuando se pide', () => {
      inner().pinPicked({ lat: -20.4611, lng: -66.8261 });
      expect(geo.reverse).not.toHaveBeenCalled();

      inner().requestAddressForPin();

      expect(geo.reverse).toHaveBeenCalledWith(3, -20.4611, -66.8261);
      expect(inner().suggestedAddress()).toBe('Avenida Ferroviaria, Uyuni, Bolivia');
    });

    it('un punto sin dirección registrada no es un error que rompa nada', () => {
      geo.reverse.and.returnValue(of({ resultado: null }));
      inner().pinPicked({ lat: -20.4611, lng: -66.8261 });

      inner().requestAddressForPin();

      expect(inner().suggestedAddress()).toBeNull();
      expect(inner().coordinates()).not.toBeNull();
    });

    it('si el geocodificador falla, el punto marcado se conserva y se puede guardar', () => {
      geo.search.and.returnValue(throwError(() => ({ status: 503 })));
      inner().pinPicked({ lat: -20.4611, lng: -66.8261 });
      inner().geoSearchControl.setValue('avenida ferroviaria');

      inner().searchAddress();

      expect(inner().geoError()).not.toBeNull();
      expect(inner().coordinates()).toEqual({ lat: -20.4611, lng: -66.8261 });
      expect(inner().buildLodgingPayload()['latitud']).toBe('-20.461100');
    });

    it('con el geocodificador entero caído, el pin manual se coloca y se guarda', () => {
      // La garantía central: ni buscar ni el inverso son requisito para guardar
      // una ubicación. Las dos salidas fallan y el flujo manual sigue intacto.
      geo.search.and.returnValue(throwError(() => ({ status: 503 })));
      geo.reverse.and.returnValue(throwError(() => ({ status: 503 })));
      cambiarPais('1');
      elegirCiudad(5);
      form().controls.nombre.setValue('Hotel Kachi Wasi');

      inner().pinPicked({ lat: -20.4611, lng: -66.8261 });
      inner().requestAddressForPin();

      expect(form().valid).toBeTrue();
      const enviado = inner().buildLodgingPayload();
      expect(enviado['latitud']).toBe('-20.461100');
      expect(enviado['longitud']).toBe('-66.826100');
      expect(inner().coordinates()).not.toBeNull();
    });

    it('una búsqueda sin resultados se distingue de no haber buscado', () => {
      geo.search.and.returnValue(of({ resultados: [] }));
      expect(inner().geoSearched()).toBeFalse();
      inner().geoSearchControl.setValue('calle inexistente');

      inner().searchAddress();

      expect(inner().geoSearched()).toBeTrue();
      expect(inner().geoResults()).toEqual([]);
    });
  });
});
