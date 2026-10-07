import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface CompanyBooking {
  id: number;
  codigo: string;
  orden: string;
  estado: string;
  estado_nombre: string;
  empresa: string;
  producto: {
    id: number;
    nombre: string;
    tipo: string;
    ciudad: string;
    localidad: string | null;
    establecimiento: string | null;
    es_hospedaje: boolean;
  } | null;
  fechas: { inicio: string; fin: string; noches: number | null } | null;
  importe: { cantidad: number; unidad: string; precio_unitario: string | null; total: string };
  huespedes: number | null;
  moneda_codigo: string;
  moneda_simbolo: string;
  pago: { estado: string; proveedor: string; monto: string; procesado_en: string | null } | null;
  vence_en: string | null;
  creado_en: string;
  cliente: { nombre: string; email: string; telefono: string | null };
  llegada: { en: string; por: string | null } | null;
  comprobante_url: string | null;
}

export interface CompanyBookingSummary {
  llegadas_hoy: number;
  proximas: number;
  pendientes_pago: number;
  ingresos_mes: { moneda: string; total: string }[];
}

export interface CompanyBookingPage {
  count: number;
  next: string | null;
  previous: string | null;
  results: CompanyBooking[];
  resumen: CompanyBookingSummary;
}

export interface CompanyBookingFilters {
  buscar?: string;
  estado?: string;
  desde?: string;
  hasta?: string;
  llegadas?: string;
  page?: number;
}

export interface VoucherCheck {
  reserva: CompanyBooking;
  puede_marcar_llegada: boolean;
  motivo: string | null;
}

/** Reservas de la empresa del encabezado X-Tenant-ID (empresa/reservas/). */
@Injectable({ providedIn: 'root' })
export class CompanyBookingsService {
  private readonly http = inject(HttpClient);
  private readonly url = `${environment.apiUrl}/empresa/reservas/`;

  list(tenantId: number, filters: CompanyBookingFilters): Observable<CompanyBookingPage> {
    const params: Record<string, string> = {};
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== '') params[key] = String(value);
    }
    return this.http.get<CompanyBookingPage>(this.url, { params, headers: this.headers(tenantId) });
  }

  /** Código (RES-…) o contenido del QR. */
  check(tenantId: number, codigo: string): Observable<VoucherCheck> {
    return this.http.post<VoucherCheck>(`${this.url}validar/`, { codigo }, { headers: this.headers(tenantId) });
  }

  checkIn(tenantId: number, id: number): Observable<CompanyBooking> {
    return this.http.post<CompanyBooking>(`${this.url}${id}/llegada/`, null, { headers: this.headers(tenantId) });
  }

  report(tenantId: number, id: number, motivo: string): Observable<{ detail: string }> {
    return this.http.post<{ detail: string }>(`${this.url}${id}/reportar/`, { motivo }, { headers: this.headers(tenantId) });
  }

  private headers(tenantId: number): Record<string, string> {
    return { 'X-Tenant-ID': tenantId.toString() };
  }
}
