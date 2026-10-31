import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, forkJoin, map, of, switchMap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { apiErrorMessage } from '../http/api-error';
import { TourismProduct } from '../products/products.models';
import { Paged } from '../traveler/traveler.models';
import { Promotion, PromotionComponentInput, PromotionEvaluation, PromotionMode, PromotionPayload, PromotionUpdate } from './promotions.models';

/** The API pages at 50 maximum; gather pages before applying local filters. */
@Injectable({ providedIn: 'root' })
export class PromotionsService {
  private readonly http = inject(HttpClient);
  private readonly api = environment.apiUrl;
  private readonly companyBase = `${this.api}/promociones/`;
  private readonly publicBase = `${this.api}/marketplace/promociones/`;

  private headers(tenantId: number): Record<string, string> {
    return { 'X-Tenant-ID': String(tenantId) };
  }

  private allPages<T>(url: string, tenantId?: number, extra: Record<string, string> = {}): Observable<T[]> {
    const options = (page: number) => ({
      params: new HttpParams({ fromObject: { ...extra, page: String(page), page_size: '50' } }),
      ...(tenantId === undefined ? {} : { headers: this.headers(tenantId) }),
    });
    return this.http.get<Paged<T>>(url, options(1)).pipe(switchMap((first) => {
      const pages = Math.ceil(first.count / 50);
      if (pages <= 1) return of(first.results);
      const rest = Array.from({ length: pages - 1 }, (_, i) => this.http.get<Paged<T>>(url, options(i + 2)));
      return forkJoin(rest).pipe(map((remaining) => [first.results, ...remaining.map((page) => page.results)].flat()));
    }));
  }

  listCompany(tenantId: number): Observable<Promotion[]> {
    return this.allPages<Promotion>(this.companyBase, tenantId);
  }

  getCompany(tenantId: number, id: number): Observable<Promotion> {
    return this.http.get<Promotion>(`${this.companyBase}${id}/`, { headers: this.headers(tenantId) });
  }

  eligible(tenantId: number, mode: PromotionMode): Observable<TourismProduct[]> {
    return this.allPages<TourismProduct>(`${this.companyBase}productos-elegibles/`, tenantId, { modalidad: mode });
  }

  preview(tenantId: number, payload: PromotionPayload): Observable<PromotionEvaluation> {
    return this.http.post<PromotionEvaluation>(`${this.companyBase}cotizar/`, payload, { headers: this.headers(tenantId) });
  }

  create(tenantId: number, payload: PromotionPayload): Observable<Promotion> {
    return this.http.post<Promotion>(this.companyBase, payload, { headers: this.headers(tenantId) });
  }

  update(tenantId: number, id: number, payload: PromotionUpdate): Observable<Promotion> {
    return this.http.patch<Promotion>(`${this.companyBase}${id}/`, payload, { headers: this.headers(tenantId) });
  }

  publish(tenantId: number, id: number): Observable<Promotion> {
    return this.http.post<Promotion>(`${this.companyBase}${id}/publicar/`, {}, { headers: this.headers(tenantId) });
  }

  deactivate(tenantId: number, id: number): Observable<Promotion> {
    return this.http.post<Promotion>(`${this.companyBase}${id}/desactivar/`, {}, { headers: this.headers(tenantId) });
  }

  recalculate(tenantId: number, id: number): Observable<Promotion> {
    return this.http.get<Promotion>(`${this.companyBase}${id}/cotizacion/`, { headers: this.headers(tenantId) });
  }

  addComponent(tenantId: number, id: number, data: PromotionComponentInput): Observable<Promotion> {
    return this.http.post<Promotion>(`${this.companyBase}${id}/componentes/`, data, { headers: this.headers(tenantId) });
  }

  updateComponent(tenantId: number, id: number, componentId: number, data: Partial<PromotionComponentInput>): Observable<Promotion> {
    return this.http.patch<Promotion>(`${this.companyBase}${id}/componentes/${componentId}/`, data, { headers: this.headers(tenantId) });
  }

  removeComponent(tenantId: number, id: number, componentId: number): Observable<Promotion> {
    return this.http.delete<Promotion>(`${this.companyBase}${id}/componentes/${componentId}/`, { headers: this.headers(tenantId) });
  }

  listPublic(): Observable<Promotion[]> {
    return this.allPages<Promotion>(this.publicBase);
  }

  getPublic(id: number, options?: { fecha?: string; cantidad?: number }): Observable<Promotion> {
    let params = new HttpParams();
    if (options?.fecha) params = params.set('fecha', options.fecha);
    if (options?.cantidad) params = params.set('cantidad', String(options.cantidad));
    return this.http.get<Promotion>(`${this.publicBase}${id}/`, { params });
  }
}

export function promotionApiError(error: HttpErrorResponse, fallback = 'No se pudo cargar la promoción.'): string {
  const message = apiErrorMessage(error, fallback);
  return error.status === 500
    ? `${message} Comprueba que las migraciones de CU51 estén aplicadas en este entorno.`
    : message;
}
