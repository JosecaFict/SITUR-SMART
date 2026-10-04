import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { AdminCountry } from '../../../core/locations/locations.models';
import { LocationsService } from '../../../core/locations/locations.service';
import { Ubicaciones } from './ubicaciones';

const BOLIVIA: AdminCountry = {
  id: 1,
  codigo: 'BOL',
  nombre: 'Bolivia',
  activo: true,
  ciudades: 9,
};

class LocationsServiceDouble {
  listCountries = jasmine.createSpy('listCountries').and.returnValue(of([BOLIVIA]));
  listCities = jasmine.createSpy('listCities').and.returnValue(of([]));
  createCountry = jasmine.createSpy('createCountry');
  updateCountry = jasmine.createSpy('updateCountry');
  changeCountryStatus = jasmine.createSpy('changeCountryStatus').and.returnValue(
    of({ ...BOLIVIA, activo: false }),
  );
  createCity = jasmine.createSpy('createCity');
  updateCity = jasmine.createSpy('updateCity');
  changeCityStatus = jasmine.createSpy('changeCityStatus');
}

describe('Ubicaciones', () => {
  let fixture: ComponentFixture<Ubicaciones>;
  let component: Ubicaciones;
  let locations: LocationsServiceDouble;

  beforeEach(async () => {
    locations = new LocationsServiceDouble();
    await TestBed.configureTestingModule({
      imports: [Ubicaciones],
      providers: [{ provide: LocationsService, useValue: locations }],
    }).compileComponents();
    fixture = TestBed.createComponent(Ubicaciones);
    component = fixture.componentInstance;
  });

  type Internal = {
    selectedCountry: () => AdminCountry | null;
    mapPoint: () => { lat: number; lng: number } | null;
    pendingStatus: {
      (): { kind: 'country' | 'city'; id: number; name: string; active: boolean } | null;
      set: (value: { kind: 'country'; id: number; name: string; active: boolean }) => void;
    };
    loadCountries: () => void;
    pickPoint: (point: { lat: number; lng: number }) => void;
    confirmStatus: () => void;
  };

  const inner = () => component as unknown as Internal;

  it('selecciona el primer país y carga sus ciudades', () => {
    inner().loadCountries();
    expect(inner().selectedCountry()?.id).toBe(1);
    expect(locations.listCities).toHaveBeenCalledOnceWith(1, '');
  });

  it('redondea las coordenadas del centro a seis decimales', () => {
    inner().pickPoint({ lat: -17.78333349, lng: -63.18214551 });
    expect(inner().mapPoint()).toEqual({ lat: -17.783333, lng: -63.182146 });
  });

  it('confirma la desactivación por el endpoint de estado', () => {
    inner().pendingStatus.set({ kind: 'country', id: 1, name: 'Bolivia', active: false });
    inner().confirmStatus();
    expect(locations.changeCountryStatus).toHaveBeenCalledOnceWith(1, false);
  });
});
