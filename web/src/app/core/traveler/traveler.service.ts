import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { TourismProduct } from '../products/products.models';
import {
  AppNotification,
  BookingQuote,
  BookingRequest,
  Itinerary,
  ItineraryDetail,
  Paged,
  TravelerBooking,
} from './traveler.models';

/** Reservas, favoritos, itinerarios y avisos del turista con sesión iniciada. */
@Injectable({ providedIn: 'root' })
export class TravelerService {
  private readonly http = inject(HttpClient);
  private readonly api = environment.apiUrl;

  /** No leídas, compartido por la campana del menú y la bandeja. */
  readonly unread = signal(0);

  // --- Reservas ---------------------------------------------------------------

  quote(request: BookingRequest): Observable<BookingQuote> {
    return this.http.post<BookingQuote>(`${this.api}/me/reservas/cotizacion/`, request);
  }

  /** Aparta el cupo y devuelve la reserva con checkout_url de Stripe (que vuelve a la web). */
  book(request: BookingRequest, idempotencyKey: string): Observable<TravelerBooking> {
    return this.http.post<TravelerBooking>(`${this.api}/me/reservas/?origen=web`, request, {
      headers: { 'Idempotency-Key': idempotencyKey },
    });
  }

  bookings(): Observable<TravelerBooking[]> {
    return this.http.get<TravelerBooking[]>(`${this.api}/me/reservas/`);
  }

  booking(id: number): Observable<TravelerBooking> {
    return this.http.get<TravelerBooking>(`${this.api}/me/reservas/${id}/`);
  }

  pay(id: number): Observable<{ checkout_url: string }> {
    return this.http.post<{ checkout_url: string }>(`${this.api}/me/reservas/${id}/pagar/`, {});
  }

  cancel(id: number): Observable<TravelerBooking> {
    return this.http.post<TravelerBooking>(`${this.api}/me/reservas/${id}/cancelar/`, {});
  }

  receiptUrl(id: number): Observable<{ url: string }> {
    return this.http.get<{ url: string }>(`${this.api}/me/reservas/${id}/comprobante/`);
  }

  // --- Favoritos --------------------------------------------------------------

  favorites(): Observable<TourismProduct[]> {
    return this.http.get<TourismProduct[]>(`${this.api}/me/favoritos/`);
  }

  addFavorite(productId: number): Observable<unknown> {
    return this.http.put(`${this.api}/me/favoritos/${productId}/`, {});
  }

  removeFavorite(productId: number): Observable<unknown> {
    return this.http.delete(`${this.api}/me/favoritos/${productId}/`);
  }

  // --- Itinerarios ------------------------------------------------------------

  itineraries(): Observable<Itinerary[]> {
    return this.http.get<Itinerary[]>(`${this.api}/me/itinerarios/`);
  }

  itinerary(id: number): Observable<ItineraryDetail> {
    return this.http.get<ItineraryDetail>(`${this.api}/me/itinerarios/${id}/`);
  }

  createItinerary(data: { nombre: string; inicio: string; fin: string; notas?: string }): Observable<ItineraryDetail> {
    return this.http.post<ItineraryDetail>(`${this.api}/me/itinerarios/`, data);
  }

  deleteItinerary(id: number): Observable<void> {
    return this.http.delete<void>(`${this.api}/me/itinerarios/${id}/`);
  }

  addActivity(
    itineraryId: number,
    data: { fecha: string; hora?: string | null; titulo?: string; producto_id?: number; nota?: string },
  ): Observable<unknown> {
    return this.http.post(`${this.api}/me/itinerarios/${itineraryId}/actividades/`, data);
  }

  deleteActivity(itineraryId: number, activityId: number): Observable<void> {
    return this.http.delete<void>(`${this.api}/me/itinerarios/${itineraryId}/actividades/${activityId}/`);
  }

  // --- Notificaciones ---------------------------------------------------------

  notifications(page = 1): Observable<Paged<AppNotification>> {
    return this.http.get<Paged<AppNotification>>(`${this.api}/me/notificaciones/`, { params: { page } });
  }

  refreshUnread(): Observable<{ no_leidas: number }> {
    return this.http
      .get<{ no_leidas: number }>(`${this.api}/me/notificaciones/no-leidas/`)
      .pipe(tap(({ no_leidas }) => this.unread.set(no_leidas)));
  }

  markRead(id: number): Observable<AppNotification> {
    return this.http
      .post<AppNotification>(`${this.api}/me/notificaciones/${id}/leer/`, {})
      .pipe(tap(() => this.unread.update((n) => Math.max(0, n - 1))));
  }

  markAllRead(): Observable<void> {
    return this.http
      .post<void>(`${this.api}/me/notificaciones/leer-todas/`, {})
      .pipe(tap(() => this.unread.set(0)));
  }
}

/** Clave para no reservar dos veces si se repite el clic o la red falla. */
export function newIdempotencyKey(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}
