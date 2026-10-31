import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { ComponentPayload, CustomPackage, PackageCatalogPage, PackagePayload, PackagePurchaseResult, PackageQuote } from './packages.models';

@Injectable({ providedIn: 'root' })
export class PackagesService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/me/paquetes/`;

  list(): Observable<CustomPackage[]> { return this.http.get<CustomPackage[]>(this.base); }
  get(id: number): Observable<CustomPackage> { return this.http.get<CustomPackage>(`${this.base}${id}/`); }
  create(data: PackagePayload): Observable<CustomPackage> { return this.http.post<CustomPackage>(this.base, data); }
  update(id: number, data: Partial<PackagePayload>): Observable<CustomPackage> {
    return this.http.patch<CustomPackage>(`${this.base}${id}/`, data);
  }
  catalog(filters: { ciudad?: number; tipo?: string; buscar?: string; page?: number; page_size?: number }): Observable<PackageCatalogPage> {
    let params = new HttpParams();
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== '') params = params.set(key, String(value));
    }
    return this.http.get<PackageCatalogPage>(`${this.base}catalogo/`, { params });
  }
  quote(id: number, data: ComponentPayload): Observable<PackageQuote> {
    return this.http.post<PackageQuote>(`${this.base}${id}/cotizar/`, data);
  }
  add(id: number, data: ComponentPayload): Observable<CustomPackage> {
    return this.http.post<CustomPackage>(`${this.base}${id}/componentes/`, data);
  }
  change(id: number, componentId: number, data: Partial<ComponentPayload>): Observable<CustomPackage> {
    return this.http.patch<CustomPackage>(`${this.base}${id}/componentes/${componentId}/`, data);
  }
  remove(id: number, componentId: number): Observable<CustomPackage> {
    return this.http.delete<CustomPackage>(`${this.base}${id}/componentes/${componentId}/`);
  }
  validate(id: number, save: boolean): Observable<CustomPackage> {
    return this.http.post<CustomPackage>(`${this.base}${id}/validar/`, { guardar: save });
  }
  purchase(id: number, data: { acepta_politicas: boolean; razon_social_facturacion: string; nit_facturacion: string; success_url: string; cancel_url: string }, key: string): Observable<PackagePurchaseResult> {
    return this.http.post<PackagePurchaseResult>(`${this.base}${id}/comprar/`, data, {
      headers: { 'Idempotency-Key': key },
    });
  }
}
