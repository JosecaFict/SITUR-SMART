import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export type CustomerStatus = 'ACTIVO' | 'BLOQUEADO' | 'INACTIVO' | 'PENDIENTE';

export interface CustomerTotal {
  moneda: string;
  total: string;
}

/** Datos de la cuenta, comunes a la fila de la lista y a la ficha. */
interface CustomerAccount {
  id: number;
  email: string;
  nombres: string;
  apellidos: string;
  telefono: string | null;
  estado: CustomerStatus;
  correo_verificado: boolean;
  registrado_en: string;
  ultimo_acceso: string | null;
}

export interface CustomerRow extends CustomerAccount {
  /** Cantidad de reservas. */
  reservas: number;
  total_pagado: CustomerTotal[];
}

export interface CustomerSummary {
  total: number;
  nuevos_mes: number;
  con_reservas: number;
  bloqueados: number;
}

export interface CustomerPage {
  count: number;
  next: string | null;
  previous: string | null;
  results: CustomerRow[];
  resumen: CustomerSummary;
}

/** Reserva del turista tal como la ve la plataforma en su ficha. */
export interface CustomerBooking {
  id: number;
  codigo: string;
  estado: string;
  empresa: string;
  producto: string | null;
  fechas: { inicio: string; fin: string; noches: number | null } | null;
  total: string;
  moneda: string;
  creado_en: string;
}

export interface CustomerDetail extends CustomerAccount {
  actividad: {
    reservas: number;
    pagadas: number;
    pendientes: number;
    canceladas: number;
    total_pagado: CustomerTotal[];
  };
  sesiones_abiertas: number;
  dispositivos_push: number;
  /** Las últimas 20 reservas. */
  reservas: CustomerBooking[];
  historial: { fecha: string; accion: string; por: string; motivo: string | null }[];
}

export interface CustomerFilters {
  buscar?: string;
  estado?: string;
  con_reservas?: string;
  page?: number;
}

/** Cuentas de los turistas (admin/clientes/). Solo SuperAdmin o CLIENTES_GESTIONAR. */
@Injectable({ providedIn: 'root' })
export class CustomersService {
  private readonly http = inject(HttpClient);
  private readonly url = `${environment.apiUrl}/admin/clientes/`;

  list(filters: CustomerFilters): Observable<CustomerPage> {
    const params: Record<string, string> = {};
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== '') params[key] = String(value);
    }
    return this.http.get<CustomerPage>(this.url, { params });
  }

  detail(id: number): Observable<CustomerDetail> {
    return this.http.get<CustomerDetail>(`${this.url}${id}/`);
  }

  block(id: number, motivo: string): Observable<CustomerDetail> {
    return this.http.post<CustomerDetail>(`${this.url}${id}/bloquear/`, { motivo });
  }

  unblock(id: number, motivo: string): Observable<CustomerDetail> {
    return this.http.post<CustomerDetail>(`${this.url}${id}/desbloquear/`, { motivo });
  }

  closeSessions(id: number, motivo: string): Observable<CustomerDetail> {
    return this.http.post<CustomerDetail>(`${this.url}${id}/cerrar-sesiones/`, { motivo });
  }

  sendPasswordReset(id: number): Observable<void> {
    return this.http.post<void>(`${this.url}${id}/recuperar-contrasena/`, null);
  }
}
