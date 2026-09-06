import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  City,
  CompanySubscriptionInfo,
  Country,
  Company,
  CompanyStatus,
  CreateCompanyPayload,
  OwnerPayload,
  Plan,
  SelfSignupPayload,
  SelfSignupResponse,
  Subscription,
  UpdateCompanyPayload,
} from './companies.models';

@Injectable({ providedIn: 'root' })
export class CompaniesService {
  private readonly http = inject(HttpClient);

  list(search = '', status = ''): Observable<Company[]> {
    let params = new HttpParams();
    if (search.trim()) {
      params = params.set('buscar', search.trim());
    }
    if (status) {
      params = params.set('estado', status);
    }
    return this.http.get<Company[]>(`${environment.apiUrl}/empresas/`, { params });
  }

  create(payload: CreateCompanyPayload): Observable<Company> {
    return this.http.post<Company>(`${environment.apiUrl}/empresas/`, payload);
  }

  update(companyId: number, payload: UpdateCompanyPayload): Observable<Company> {
    return this.http.patch<Company>(`${environment.apiUrl}/empresas/${companyId}/`, payload);
  }

  updateStatus(companyId: number, status: CompanyStatus): Observable<Company> {
    return this.update(companyId, { estado: status });
  }

  assignOwner(companyId: number, owner: OwnerPayload): Observable<Company> {
    return this.http.put<Company>(`${environment.apiUrl}/empresas/${companyId}/propietario/`, {
      propietario: owner,
    });
  }

  listCities(): Observable<City[]> {
    return this.http.get<City[]>(`${environment.apiUrl}/catalogos/ciudades/`);
  }

  listCountries(): Observable<Country[]> {
    return this.http.get<Country[]>(`${environment.apiUrl}/catalogos/paises/`);
  }

  listPlans(): Observable<Plan[]> {
    return this.http.get<Plan[]>(`${environment.apiUrl}/planes/`);
  }

  selfSignup(payload: SelfSignupPayload): Observable<SelfSignupResponse> {
    return this.http.post<SelfSignupResponse>(`${environment.apiUrl}/empresas/autoregistro/`, payload);
  }

  getSubscription(companyId: number): Observable<CompanySubscriptionInfo> {
    return this.http.get<CompanySubscriptionInfo>(`${environment.apiUrl}/empresas/${companyId}/suscripcion/`);
  }

  changeSubscription(companyId: number, planCodigo: string): Observable<Subscription> {
    return this.http.put<Subscription>(`${environment.apiUrl}/empresas/${companyId}/suscripcion/`, {
      plan_codigo: planCodigo,
    });
  }
}
