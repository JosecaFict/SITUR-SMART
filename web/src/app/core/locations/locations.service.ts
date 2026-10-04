import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AdminCity, AdminCountry, CityPayload } from './locations.models';

@Injectable({ providedIn: 'root' })
export class LocationsService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/admin/catalogos`;

  listCountries(search = '', active = ''): Observable<AdminCountry[]> {
    let params = new HttpParams();
    if (search.trim()) params = params.set('buscar', search.trim());
    if (active) params = params.set('activo', active);
    return this.http.get<AdminCountry[]>(`${this.base}/paises/`, { params });
  }

  createCountry(payload: { codigo: string; nombre: string }): Observable<AdminCountry> {
    return this.http.post<AdminCountry>(`${this.base}/paises/`, payload);
  }

  updateCountry(id: number, payload: { nombre: string }): Observable<AdminCountry> {
    return this.http.patch<AdminCountry>(`${this.base}/paises/${id}/`, payload);
  }

  changeCountryStatus(id: number, activo: boolean): Observable<AdminCountry> {
    return this.http.post<AdminCountry>(`${this.base}/paises/${id}/estado/`, { activo });
  }

  listCities(countryId: number, search = '', active = ''): Observable<AdminCity[]> {
    let params = new HttpParams().set('pais', countryId);
    if (search.trim()) params = params.set('buscar', search.trim());
    if (active) params = params.set('activo', active);
    return this.http.get<AdminCity[]>(`${this.base}/ciudades/`, { params });
  }

  createCity(payload: CityPayload): Observable<AdminCity> {
    return this.http.post<AdminCity>(`${this.base}/ciudades/`, payload);
  }

  updateCity(id: number, payload: CityPayload): Observable<AdminCity> {
    return this.http.patch<AdminCity>(`${this.base}/ciudades/${id}/`, payload);
  }

  changeCityStatus(id: number, activo: boolean): Observable<AdminCity> {
    return this.http.post<AdminCity>(`${this.base}/ciudades/${id}/estado/`, { activo });
  }
}
