import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  DeparturePayload,
  Guide,
  GuidePayload,
  PublicDeparture,
  RecurringDeparturePayload,
  RecurringDepartureResult,
  Tour,
  TourDeparture,
  TourPayload,
  TourStop,
  TourStopPayload,
} from './tours.models';

function tenantHeaders(tenantId: number): Record<string, string> {
  return { 'X-Tenant-ID': tenantId.toString() };
}

/** Tours y experiencias de la empresa, y su ficha pública. */
@Injectable({ providedIn: 'root' })
export class ToursService {
  private readonly http = inject(HttpClient);
  private readonly api = environment.apiUrl;

  list(tenantId: number): Observable<Tour[]> {
    return this.http.get<Tour[]>(`${this.api}/tours/`, { headers: tenantHeaders(tenantId) });
  }

  get(tenantId: number, tourId: number): Observable<Tour> {
    return this.http.get<Tour>(`${this.api}/tours/${tourId}/`, { headers: tenantHeaders(tenantId) });
  }

  create(tenantId: number, payload: TourPayload): Observable<Tour> {
    return this.http.post<Tour>(`${this.api}/tours/`, payload, { headers: tenantHeaders(tenantId) });
  }

  update(tenantId: number, tourId: number, payload: TourPayload): Observable<Tour> {
    return this.http.patch<Tour>(`${this.api}/tours/${tourId}/`, payload, { headers: tenantHeaders(tenantId) });
  }

  deactivate(tenantId: number, tourId: number): Observable<Tour> {
    return this.http.delete<Tour>(`${this.api}/tours/${tourId}/`, { headers: tenantHeaders(tenantId) });
  }

  saveStops(tenantId: number, tourId: number, stops: TourStopPayload[]): Observable<TourStop[]> {
    return this.http.put<TourStop[]>(`${this.api}/tours/${tourId}/paradas/`, { paradas: stops }, {
      headers: tenantHeaders(tenantId),
    });
  }

  /** 404 si el tour no está publicado o todavía no tiene ficha. */
  getPublic(tourId: number): Observable<Tour> {
    return this.http.get<Tour>(`${this.api}/marketplace/tours/${tourId}/`);
  }
}

/** Salidas de un tour: fecha, hora, cupo y guía. */
@Injectable({ providedIn: 'root' })
export class DeparturesService {
  private readonly http = inject(HttpClient);
  private readonly api = environment.apiUrl;

  list(tenantId: number, tourId: number, desde?: string, hasta?: string): Observable<TourDeparture[]> {
    let params = new HttpParams();
    if (desde) params = params.set('desde', desde);
    if (hasta) params = params.set('hasta', hasta);
    return this.http.get<TourDeparture[]>(`${this.api}/tours/${tourId}/salidas/`, {
      headers: tenantHeaders(tenantId),
      params,
    });
  }

  create(tenantId: number, tourId: number, payload: DeparturePayload): Observable<TourDeparture> {
    return this.http.post<TourDeparture>(`${this.api}/tours/${tourId}/salidas/`, payload, {
      headers: tenantHeaders(tenantId),
    });
  }

  createRecurring(
    tenantId: number,
    tourId: number,
    payload: RecurringDeparturePayload,
  ): Observable<RecurringDepartureResult> {
    return this.http.post<RecurringDepartureResult>(`${this.api}/tours/${tourId}/salidas/`, payload, {
      headers: tenantHeaders(tenantId),
    });
  }

  update(tenantId: number, departureId: number, payload: DeparturePayload): Observable<TourDeparture> {
    return this.http.patch<TourDeparture>(`${this.api}/salidas/${departureId}/`, payload, {
      headers: tenantHeaders(tenantId),
    });
  }

  close(tenantId: number, departureId: number): Observable<TourDeparture> {
    return this.http.post<TourDeparture>(`${this.api}/salidas/${departureId}/cerrar/`, {}, {
      headers: tenantHeaders(tenantId),
    });
  }

  remove(tenantId: number, departureId: number): Observable<void> {
    return this.http.delete<void>(`${this.api}/salidas/${departureId}/`, { headers: tenantHeaders(tenantId) });
  }

  listPublic(tourId: number): Observable<PublicDeparture[]> {
    return this.http.get<PublicDeparture[]>(`${this.api}/marketplace/tours/${tourId}/salidas/`);
  }
}

/** Guías de la empresa. */
@Injectable({ providedIn: 'root' })
export class GuidesService {
  private readonly http = inject(HttpClient);
  private readonly api = environment.apiUrl;

  list(tenantId: number): Observable<Guide[]> {
    return this.http.get<Guide[]>(`${this.api}/guias/`, { headers: tenantHeaders(tenantId) });
  }

  create(tenantId: number, payload: GuidePayload): Observable<Guide> {
    return this.http.post<Guide>(`${this.api}/guias/`, payload, { headers: tenantHeaders(tenantId) });
  }

  update(tenantId: number, guideId: number, payload: GuidePayload): Observable<Guide> {
    return this.http.patch<Guide>(`${this.api}/guias/${guideId}/`, payload, { headers: tenantHeaders(tenantId) });
  }

  deactivate(tenantId: number, guideId: number): Observable<Guide> {
    return this.http.delete<Guide>(`${this.api}/guias/${guideId}/`, { headers: tenantHeaders(tenantId) });
  }
}
