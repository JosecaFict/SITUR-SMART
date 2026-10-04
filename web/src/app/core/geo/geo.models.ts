/**
 * Un punto del mapa. Las coordenadas van como número porque Leaflet las
 * necesita así; al mandarlas al backend se vuelven cadena con seis decimales.
 */
export interface LatLng {
  lat: number;
  lng: number;
}

/**
 * Resultado del geocodificador, ya traducido por el backend.
 *
 * El navegador nunca habla con el proveedor: la clave no sale del servidor. Las
 * coordenadas llegan con nombre y no como `[lon, lat]`, que es el orden en que
 * las entrega Pelias.
 */
export interface GeoPlace {
  etiqueta: string;
  nombre: string;
  localidad: string | null;
  region: string | null;
  pais: string | null;
  latitud: string;
  longitud: string;
  confianza: number | null;
  capa: string | null;
}

export interface GeoSearchResponse {
  resultados: GeoPlace[];
}

export interface GeoReverseResponse {
  resultado: GeoPlace | null;
}
