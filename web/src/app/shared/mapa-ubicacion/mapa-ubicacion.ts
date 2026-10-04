import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnDestroy,
  ViewEncapsulation,
  effect,
  input,
  output,
  viewChild,
} from '@angular/core';
import * as L from 'leaflet';
import { LatLng } from '../../core/geo/geo.models';

/** Centro de Bolivia, para cuando todavía no hay ni ciudad ni pin. */
const BOLIVIA_CENTER: LatLng = { lat: -16.5, lng: -64.5 };
const BOLIVIA_ZOOM = 5;
const CITY_ZOOM = 12;
const PIN_ZOOM = 16;

/**
 * Atribución obligatoria de la política de teselas de OpenStreetMap.
 *
 * La política exige que esté «visible, abajo a la derecha, no oculta bajo la
 * interfaz ni detrás de un interruptor». El control de atribución de Leaflet la
 * pone ahí solo; no hay que desactivarlo ni taparlo.
 */
const OSM_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors';
const OSM_TILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

/**
 * Mapa con un pin, en modo lectura o edición.
 *
 * Un solo componente para el panel y para la página pública: lo que cambia es
 * si el pin se puede mover. Tenerlos separados haría que la ficha y el
 * Marketplace dibujaran el mismo punto con dos códigos distintos.
 *
 * El icono es un `divIcon` y no el marcador por omisión de Leaflet a propósito:
 * el de serie pide `marker-icon.png` por ruta relativa y con el hashing de
 * archivos de Angular no resuelve -- es el fallo clásico del paquete bajo un
 * bundler. Un icono de HTML no tiene ese problema y además se pinta con los
 * tokens del proyecto.
 */
@Component({
  selector: 'situr-mapa-ubicacion',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="relative">
      <div
        #canvas
        class="h-64 w-full overflow-hidden rounded-xl border border-input-border sm:h-80"
        [class.cursor-crosshair]="editable()"
        role="application"
        [attr.aria-label]="
          editable()
            ? 'Mapa para ubicar el hospedaje. Haz clic para colocar el punto.'
            : 'Mapa con la ubicación del hospedaje'
        "
      ></div>
    </div>
  `,
  // El CSS de Leaflet vive en angular.json como estilo global. No puede ir
  // aquí: ocupa ~15 kB y el presupuesto de `anyComponentStyle` da error a los
  // 8 kB, así que rompería el build de producción.
  //
  // `ViewEncapsulation.None` es obligatorio: Leaflet construye su DOM por fuera
  // de Angular, así que una regla con ámbito de componente no alcanzaría al pin.
  styles: [
    `
      .situr-pin {
        display: block;
        width: 1.5rem;
        height: 1.5rem;
        border: 3px solid #fff;
        border-radius: 9999px;
        background: var(--color-accent-dark, #0f766e);
        box-shadow: 0 2px 6px rgb(0 0 0 / 35%);
      }
    `,
  ],
  encapsulation: ViewEncapsulation.None,
})
export class MapaUbicacion implements AfterViewInit, OnDestroy {
  private readonly canvas = viewChild.required<ElementRef<HTMLElement>>('canvas');

  /** Punto marcado. `null` dibuja el mapa sin pin. */
  readonly value = input<LatLng | null>(null);
  /** Centro cuando no hay pin: normalmente la ciudad elegida. */
  readonly center = input<LatLng | null>(null);
  readonly editable = input(false);

  /** Emite al hacer clic en el mapa o al soltar el pin. */
  readonly picked = output<LatLng>();

  private map?: L.Map;
  private marker?: L.Marker;

  constructor() {
    // Reacciona a los cambios de entrada después de que el mapa exista. El
    // `effect` se salta solo mientras `this.map` es undefined, así que no hace
    // falta coordinarlo con ngAfterViewInit.
    effect(() => {
      const value = this.value();
      const center = this.center();
      if (!this.map) return;
      this.renderMarker(value);
      if (value) {
        this.map.setView([value.lat, value.lng], Math.max(this.map.getZoom(), PIN_ZOOM));
      } else if (center) {
        this.map.setView([center.lat, center.lng], CITY_ZOOM);
      }
    });
  }

  ngAfterViewInit(): void {
    const value = this.value();
    const center = value ?? this.center() ?? BOLIVIA_CENTER;
    const zoom = value ? PIN_ZOOM : this.center() ? CITY_ZOOM : BOLIVIA_ZOOM;

    this.map = L.map(this.canvas().nativeElement, {
      center: [center.lat, center.lng],
      zoom,
      // En móvil el gesto de rueda/pinch pertenece a la página: capturarlo
      // dejaría a la persona atrapada en el mapa al intentar bajar.
      scrollWheelZoom: false,
      // Un mapa de lectura no necesita interacción; lo único que debe permitir
      // es ver dónde está el hotel.
      dragging: true,
      zoomControl: true,
      attributionControl: true,
    });

    L.tileLayer(OSM_TILES, {
      attribution: OSM_ATTRIBUTION,
      maxZoom: 19,
      // Sin precarga ni modo offline: la política de teselas de OSM prohíbe
      // traer teselas que la persona no está mirando.
      crossOrigin: true,
    }).addTo(this.map);

    if (this.editable()) {
      this.map.on('click', (event: L.LeafletMouseEvent) => {
        this.picked.emit({ lat: event.latlng.lat, lng: event.latlng.lng });
      });
    }

    this.renderMarker(value);
  }

  ngOnDestroy(): void {
    // Sin esto Leaflet deja escuchadores de resize y de teclado vivos, y cada
    // navegación al panel acumularía uno más.
    this.map?.remove();
    this.map = undefined;
    this.marker = undefined;
  }

  private renderMarker(value: LatLng | null): void {
    if (!this.map) return;
    if (!value) {
      this.marker?.remove();
      this.marker = undefined;
      return;
    }

    if (!this.marker) {
      this.marker = L.marker([value.lat, value.lng], {
        draggable: this.editable(),
        keyboard: this.editable(),
        icon: L.divIcon({
          className: '',
          html: '<span class="situr-pin"></span>',
          iconSize: [24, 24],
          iconAnchor: [12, 12],
        }),
        title: this.editable() ? 'Arrastra para ajustar la ubicación' : 'Ubicación del hospedaje',
      }).addTo(this.map);

      if (this.editable()) {
        this.marker.on('dragend', () => {
          const position = this.marker?.getLatLng();
          if (position) this.picked.emit({ lat: position.lat, lng: position.lng });
        });
      }
      return;
    }
    this.marker.setLatLng([value.lat, value.lng]);
  }
}
