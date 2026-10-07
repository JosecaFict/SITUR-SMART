import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Currency, MarketplaceFilters, MarketplacePage, ProductPayload, ProductType, TourismProduct } from './products.models';

@Injectable({ providedIn: 'root' })
export class ProductsService {
  private readonly http = inject(HttpClient);

  private tenantHeaders(tenantId: number): Record<string, string> {
    return { 'X-Tenant-ID': tenantId.toString() };
  }

  listCompanyProducts(tenantId: number): Observable<TourismProduct[]> {
    return this.http.get<TourismProduct[]>(`${environment.apiUrl}/productos/`, {
      headers: this.tenantHeaders(tenantId),
    });
  }

  create(tenantId: number, payload: ProductPayload): Observable<TourismProduct> {
    return this.http.post<TourismProduct>(`${environment.apiUrl}/productos/`, payload, {
      headers: this.tenantHeaders(tenantId),
    });
  }

  update(tenantId: number, productId: number, payload: Partial<ProductPayload>): Observable<TourismProduct> {
    return this.http.patch<TourismProduct>(`${environment.apiUrl}/productos/${productId}/`, payload, {
      headers: this.tenantHeaders(tenantId),
    });
  }

  deactivate(tenantId: number, productId: number): Observable<TourismProduct> {
    return this.http.delete<TourismProduct>(`${environment.apiUrl}/productos/${productId}/`, {
      headers: this.tenantHeaders(tenantId),
    });
  }

  /** Programa la publicación y/o el retiro; null quita esa fecha. */
  schedule(
    tenantId: number,
    productId: number,
    fechas: { publicar_en: string | null; retirar_en: string | null },
  ): Observable<TourismProduct> {
    return this.http.put<TourismProduct>(`${environment.apiUrl}/productos/${productId}/programacion/`, fechas, {
      headers: this.tenantHeaders(tenantId),
    });
  }

  clearSchedule(tenantId: number, productId: number): Observable<TourismProduct> {
    return this.http.delete<TourismProduct>(`${environment.apiUrl}/productos/${productId}/programacion/`, {
      headers: this.tenantHeaders(tenantId),
    });
  }

  listTypes(): Observable<ProductType[]> {
    return this.http.get<ProductType[]>(`${environment.apiUrl}/catalogos/tipos-producto/`);
  }

  listCurrencies(): Observable<Currency[]> {
    return this.http.get<Currency[]>(`${environment.apiUrl}/catalogos/monedas/`);
  }

  listMarketplace(filters: MarketplaceFilters = {}): Observable<MarketplacePage> {
    let params = new HttpParams();
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== null && value !== '') params = params.set(key, String(value));
    }
    return this.http.get<MarketplacePage>(`${environment.apiUrl}/marketplace/productos/`, { params });
  }
}
