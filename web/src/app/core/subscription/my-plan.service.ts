import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export type MyPlanState = 'ACTIVA' | 'POR_VENCER' | 'VENCIDA' | 'CANCELADA' | 'SUSPENDIDA' | 'SIN_PLAN';

export interface MyPlanUsage {
  recurso: string;
  etiqueta: string;
  usado: number;
  limite: number;
}

export interface MyPlanPayment {
  id: number;
  plan: string;
  monto: string;
  moneda: string;
  estado: 'PENDIENTE' | 'APROBADO' | 'ANULADO';
  fecha: string;
}

export interface MyPlan {
  empresa: { id: number; nombre: string; estado: string };
  estado: MyPlanState;
  /** Plan vencido: la empresa no vende ni puede crear o editar oferta. */
  restringida: boolean;
  plan: {
    codigo: string;
    nombre: string;
    periodicidad: 'MENSUAL' | 'ANUAL';
    precio: string;
    moneda: string;
    precio_renovacion: string;
  } | null;
  inicio: string | null;
  vence: string | null;
  dias_restantes: number | null;
  renovacion_automatica: boolean;
  uso: MyPlanUsage[];
  es_propietario: boolean;
  puede_pagar: boolean;
  pagos: MyPlanPayment[];
}

/** "Mi plan" de la empresa del encabezado X-Tenant-ID. */
@Injectable({ providedIn: 'root' })
export class MyPlanService {
  private readonly http = inject(HttpClient);
  private readonly url = `${environment.apiUrl}/empresa/mi-plan/`;

  get(tenantId: number): Observable<MyPlan> {
    return this.http.get<MyPlan>(this.url, { headers: this.headers(tenantId) });
  }

  setAutoRenew(tenantId: number, value: boolean): Observable<MyPlan> {
    return this.http.patch<MyPlan>(this.url, { renovacion_automatica: value }, { headers: this.headers(tenantId) });
  }

  /** Abre el pago en Stripe; sin plan elegido renueva el actual. */
  pay(tenantId: number, planCodigo?: string): Observable<{ checkout_url: string }> {
    return this.http.post<{ checkout_url: string }>(
      `${this.url}pagar/`,
      planCodigo ? { plan_codigo: planCodigo } : {},
      { headers: this.headers(tenantId) },
    );
  }

  private headers(tenantId: number): Record<string, string> {
    return { 'X-Tenant-ID': tenantId.toString() };
  }
}
