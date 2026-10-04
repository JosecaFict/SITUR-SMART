import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  LodgingEstablishment,
  LodgingMarketplaceFilters,
  LodgingPage,
  LodgingPayload,
  LodgingType,
  Room,
  RoomMarketplaceFilters,
  RoomPage,
  RoomPayload,
} from './lodging.models';

@Injectable({ providedIn: 'root' })
export class LodgingService {
  private readonly http = inject(HttpClient);

  private tenantHeaders(tenantId: number): Record<string, string> {
    return { 'X-Tenant-ID': tenantId.toString() };
  }

  private queryParams(filters: object): HttpParams {
    let params = new HttpParams();
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== null && value !== '') params = params.set(key, String(value));
    }
    return params;
  }

  listTypes(): Observable<LodgingType[]> {
    return this.http.get<LodgingType[]>(`${environment.apiUrl}/catalogos/tipos-hospedaje/`);
  }

  // --- Panel empresarial -------------------------------------------------

  listCompanyLodgings(tenantId: number): Observable<LodgingEstablishment[]> {
    return this.http.get<LodgingEstablishment[]>(`${environment.apiUrl}/hospedajes/`, {
      headers: this.tenantHeaders(tenantId),
    });
  }

  getCompanyLodging(tenantId: number, lodgingId: number): Observable<LodgingEstablishment> {
    return this.http.get<LodgingEstablishment>(`${environment.apiUrl}/hospedajes/${lodgingId}/`, {
      headers: this.tenantHeaders(tenantId),
    });
  }

  createLodging(tenantId: number, payload: LodgingPayload): Observable<LodgingEstablishment> {
    return this.http.post<LodgingEstablishment>(`${environment.apiUrl}/hospedajes/`, payload, {
      headers: this.tenantHeaders(tenantId),
    });
  }

  updateLodging(
    tenantId: number,
    lodgingId: number,
    payload: Partial<LodgingPayload>,
  ): Observable<LodgingEstablishment> {
    return this.http.patch<LodgingEstablishment>(
      `${environment.apiUrl}/hospedajes/${lodgingId}/`,
      payload,
      { headers: this.tenantHeaders(tenantId) },
    );
  }

  deactivateLodging(tenantId: number, lodgingId: number): Observable<LodgingEstablishment> {
    return this.http.delete<LodgingEstablishment>(`${environment.apiUrl}/hospedajes/${lodgingId}/`, {
      headers: this.tenantHeaders(tenantId),
    });
  }

  listRooms(tenantId: number, lodgingId: number): Observable<Room[]> {
    return this.http.get<Room[]>(`${environment.apiUrl}/hospedajes/${lodgingId}/habitaciones/`, {
      headers: this.tenantHeaders(tenantId),
    });
  }

  createRoom(tenantId: number, lodgingId: number, payload: RoomPayload): Observable<Room> {
    return this.http.post<Room>(
      `${environment.apiUrl}/hospedajes/${lodgingId}/habitaciones/`,
      payload,
      { headers: this.tenantHeaders(tenantId) },
    );
  }

  updateRoom(tenantId: number, roomId: number, payload: Partial<RoomPayload>): Observable<Room> {
    return this.http.patch<Room>(`${environment.apiUrl}/habitaciones/${roomId}/`, payload, {
      headers: this.tenantHeaders(tenantId),
    });
  }

  deactivateRoom(tenantId: number, roomId: number): Observable<Room> {
    return this.http.delete<Room>(`${environment.apiUrl}/habitaciones/${roomId}/`, {
      headers: this.tenantHeaders(tenantId),
    });
  }

  // --- Marketplace publico ------------------------------------------------

  listPublicLodgings(filters: LodgingMarketplaceFilters = {}): Observable<LodgingPage> {
    return this.http.get<LodgingPage>(`${environment.apiUrl}/marketplace/hospedajes/`, {
      params: this.queryParams(filters),
    });
  }

  getPublicLodging(lodgingId: number): Observable<LodgingEstablishment> {
    return this.http.get<LodgingEstablishment>(
      `${environment.apiUrl}/marketplace/hospedajes/${lodgingId}/`,
    );
  }

  listPublicLodgingRooms(lodgingId: number): Observable<Room[]> {
    return this.http.get<Room[]>(
      `${environment.apiUrl}/marketplace/hospedajes/${lodgingId}/habitaciones/`,
    );
  }

  listPublicRooms(filters: RoomMarketplaceFilters = {}): Observable<RoomPage> {
    return this.http.get<RoomPage>(`${environment.apiUrl}/marketplace/habitaciones/`, {
      params: this.queryParams(filters),
    });
  }

  /**
   * Habitación publicada por su id, sin recorrer el listado.
   *
   * Devuelve `establecimiento_id`, que la página usa para comprobar que la
   * habitación pertenezca al hospedaje de la URL.
   */
  getPublicRoom(roomId: number): Observable<Room> {
    return this.http.get<Room>(`${environment.apiUrl}/marketplace/habitaciones/${roomId}/`);
  }
}
