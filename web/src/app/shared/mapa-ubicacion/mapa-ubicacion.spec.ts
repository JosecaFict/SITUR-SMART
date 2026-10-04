import { Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { LatLng } from '../../core/geo/geo.models';
import { MapaUbicacion } from './mapa-ubicacion';

/**
 * Anfitrión mínimo: Leaflet necesita un elemento con medidas reales en el DOM,
 * así que el componente se monta de verdad en vez de instanciarse suelto.
 */
@Component({
  standalone: true,
  imports: [MapaUbicacion],
  template: `
    <situr-mapa-ubicacion
      [value]="punto()"
      [center]="centro()"
      [editable]="editable()"
      (picked)="elegido = $event"
    />
  `,
})
class Anfitrion {
  readonly punto = signal<LatLng | null>(null);
  readonly centro = signal<LatLng | null>(null);
  readonly editable = signal(false);
  elegido: LatLng | null = null;
}

describe('MapaUbicacion', () => {
  let fixture: ComponentFixture<Anfitrion>;
  let host: Anfitrion;

  const canvas = () => fixture.nativeElement.querySelector('div[role="application"]');
  const pins = () => fixture.nativeElement.querySelectorAll('.situr-pin');

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [Anfitrion] }).compileComponents();
    fixture = TestBed.createComponent(Anfitrion);
    host = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('dibuja el mapa', () => {
    expect(canvas()).not.toBeNull();
    // Leaflet marca su contenedor; si no está, el mapa no se inicializó.
    expect(canvas().classList).toContain('leaflet-container');
  });

  it('muestra la atribución de OpenStreetMap', () => {
    // La política de teselas la exige visible, no detrás de un interruptor.
    const atribucion = fixture.nativeElement.querySelector('.leaflet-control-attribution');

    expect(atribucion).not.toBeNull();
    expect(atribucion.textContent).toContain('OpenStreetMap');
  });

  it('pide las teselas por HTTPS', () => {
    const tile: HTMLImageElement | null = fixture.nativeElement.querySelector('img.leaflet-tile');

    // En un mapa recién creado puede no haber ninguna pintada todavía.
    if (tile) expect(tile.src.startsWith('https://')).toBeTrue();
  });

  it('sin valor no dibuja ningún pin', () => {
    expect(pins().length).toBe(0);
  });

  it('con valor dibuja el pin', () => {
    host.punto.set({ lat: -20.46035, lng: -66.82532 });
    fixture.detectChanges();

    expect(pins().length).toBe(1);
  });

  it('quitar el valor quita el pin', () => {
    host.punto.set({ lat: -20.46035, lng: -66.82532 });
    fixture.detectChanges();
    expect(pins().length).toBe(1);

    host.punto.set(null);
    fixture.detectChanges();

    expect(pins().length).toBe(0);
  });

  it('en modo lectura el mapa no es un selector', () => {
    expect(canvas().classList).not.toContain('cursor-crosshair');
    expect(canvas().getAttribute('aria-label')).toContain('ubicación del hospedaje');
  });

  it('en modo edición invita a hacer clic', () => {
    host.editable.set(true);
    fixture.detectChanges();

    expect(canvas().getAttribute('aria-label')).toContain('clic');
  });

  it('se destruye liberando el contenedor de Leaflet', () => {
    // `map.remove()` borra el `_leaflet_id` del elemento. Es justo lo que hay
    // que comprobar: sin eso Leaflet deja escuchadores vivos y reutilizar el
    // contenedor lanza "Map container is already initialized" en la siguiente
    // navegación al panel. La clase `leaflet-container` sí se queda puesta, así
    // que no sirve como señal.
    const elemento = canvas() as HTMLElement & { _leaflet_id?: number };
    expect(elemento._leaflet_id).toBeDefined();

    fixture.destroy();

    expect(elemento._leaflet_id).toBeUndefined();
  });

  it('un segundo montaje no choca con el primero', () => {
    fixture.destroy();

    const otro = TestBed.createComponent(Anfitrion);
    otro.detectChanges();

    expect(otro.nativeElement.querySelector('div[role="application"]')).not.toBeNull();
    otro.destroy();
  });
});
