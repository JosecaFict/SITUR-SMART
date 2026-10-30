import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface PaymentMovement {
  id: number;
  reserva_id: number;
  reserva: string;
  estado_reserva: string;
  empresa_id: number;
  empresa: string;
  cliente: { nombre: string; email: string };
  producto: { id: number; nombre: string; tipo: string } | null;
  moneda: string;
  simbolo: string;
  amount: string;
  method: string;
  status: string;
  provider: string;
  created_at: string;
  processed_at: string | null;
  reembolsos: {
    id: number;
    estado: string;
    monto: string;
    motivo: string | null;
    referencia: string | null;
    solicitado_en: string;
    procesado_en: string | null;
    motivo_fallo: string | null;
  }[];
}

export interface PaymentPage {
  count: number;
  next: string | null;
  previous: string | null;
  results: PaymentMovement[];
  resumen?: { moneda: string; simbolo: string; cobrado: string; pendiente: string; reembolsado: string; neto: string }[];
}

export interface PaymentFilters {
  buscar?: string;
  estado?: string;
  metodo?: string;
  desde?: string;
  hasta?: string;
  page?: number;
}
export interface Departure { id: number; producto: string; inicio: string; fin: string; reservas_activas: number; }
export interface ReconciliationIssue {
  id: number; empresa: string; resource_type: string; resource_id: number; kind: string;
  local_status: string; provider_status: string; details: Record<string, unknown>;
  resolved: boolean; detected_at: string; last_seen_at: string; resolved_at: string | null;
}

@Injectable({ providedIn: 'root' })
export class PaymentsService {
  private readonly http = inject(HttpClient);
  private readonly api = environment.apiUrl;

  mine(filters: PaymentFilters = {}): Observable<PaymentPage> {
    return this.http.get<PaymentPage>(`${this.api}/me/pagos/`, { params: this.params(filters) });
  }

  detail(id: number): Observable<PaymentMovement> {
    return this.http.get<PaymentMovement>(`${this.api}/me/pagos/${id}/`);
  }

  company(tenantId: number, filters: PaymentFilters = {}): Observable<PaymentPage> {
    return this.http.get<PaymentPage>(`${this.api}/empresa/pagos/`, {
      params: this.params(filters),
      headers: { 'X-Tenant-ID': tenantId.toString() },
    });
  }

  global(filters: PaymentFilters & { empresa_id?: number } = {}): Observable<PaymentPage> {
    return this.http.get<PaymentPage>(`${this.api}/admin/pagos/`, { params: this.params(filters) });
  }

  departures(tenantId: number): Observable<Departure[]> {
    return this.http.get<Departure[]>(`${this.api}/empresa/salidas/`, { headers: { 'X-Tenant-ID': String(tenantId) } });
  }

  cancelDeparture(tenantId: number, id: number, motivo: string, key: string): Observable<{ total: number; procesados: number; requieren_revision: number }> {
    return this.http.post<{ total: number; procesados: number; requieren_revision: number }>(
      `${this.api}/empresa/salidas/${id}/cancelacion/`, { motivo },
      { headers: { 'X-Tenant-ID': String(tenantId), 'Idempotency-Key': key } },
    );
  }

  reconciliation(): Observable<{ abiertas: number; resultados: ReconciliationIssue[] }> {
    return this.http.get<{ abiertas: number; resultados: ReconciliationIssue[] }>(`${this.api}/admin/pagos/conciliacion/`);
  }

  reconcileNow(): Observable<{ omitida: boolean; pagos: Record<string, number>; reembolsos: Record<string, number> }> {
    return this.http.post<{ omitida: boolean; pagos: Record<string, number>; reembolsos: Record<string, number> }>(`${this.api}/admin/pagos/conciliacion/`, {});
  }

  registerManual(
    tenantId: number,
    data: { reserva_id: number; metodo: 'EFECTIVO' | 'QR' | 'TRANSFERENCIA'; referencia: string },
    idempotencyKey: string,
  ): Observable<PaymentMovement> {
    return this.http.post<PaymentMovement>(`${this.api}/empresa/pagos/manuales/`, data, {
      headers: { 'X-Tenant-ID': tenantId.toString(), 'Idempotency-Key': idempotencyKey },
    });
  }

  private params(filters: PaymentFilters): Record<string, string> {
    return Object.fromEntries(
      Object.entries(filters)
        .filter(([, value]) => value !== undefined && value !== '')
        .map(([key, value]) => [key, String(value)]),
    );
  }
}
