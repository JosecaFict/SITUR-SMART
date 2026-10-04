import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { GeoReverseResponse, GeoSearchResponse } from './geo.models';

/**
 * Geocodificación de direcciones.
 *
 * Separado de `LodgingService` a propósito: las coordenadas son del hospedaje,
 * pero buscar una dirección es un servicio externo con su propia cuota, su
 * propio límite de peticiones y su propio modo de fallar. Mezclarlos haría
 * creer que un buscador caído impide guardar un hotel, y no es así.
 *
 * Los dos endpoints exigen `X-Tenant-ID` y el permiso de gestión de productos:
 * buscar una dirección es parte de cargar un hospedaje.
 */
@Injectable({ providedIn: 'root' })
export class GeoService {
  private readonly http = inject(HttpClient);

  /** Mínimo que acepta el backend. Evita gastar cuota en una letra. */
  static readonly MIN_QUERY_LENGTH = 3;

  private tenantHeaders(tenantId: number): Record<string, string> {
    return { 'X-Tenant-ID': tenantId.toString() };
  }

  /**
   * Busca direcciones por texto, restringido a Bolivia.
   *
   * `cityId` no manda un centro, solo la ciudad: el backend resuelve sus
   * coordenadas y las usa para priorizar lo cercano, sin descartar lo lejano.
   */
  search(
    tenantId: number,
    text: string,
    cityId?: number | null,
    limit = 5,
  ): Observable<GeoSearchResponse> {
    let params = new HttpParams().set('texto', text).set('limite', String(limit));
    if (cityId) params = params.set('ciudad_id', String(cityId));
    return this.http.get<GeoSearchResponse>(`${environment.apiUrl}/geo/buscar/`, {
      headers: this.tenantHeaders(tenantId),
      params,
    });
  }

  /**
   * Dirección de un punto. `resultado` nulo es una respuesta válida: en el
   * altiplano lo habitual es que no haya ninguna calle registrada cerca.
   */
  reverse(tenantId: number, lat: number, lng: number): Observable<GeoReverseResponse> {
    const params = new HttpParams()
      .set('latitud', lat.toFixed(6))
      .set('longitud', lng.toFixed(6));
    return this.http.get<GeoReverseResponse>(`${environment.apiUrl}/geo/inverso/`, {
      headers: this.tenantHeaders(tenantId),
      params,
    });
  }
}
