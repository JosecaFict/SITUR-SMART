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
