/** Modelos del área del viajero (me/reservas, me/favoritos, me/itinerarios, me/notificaciones). */

export interface TravelerBooking {
  id: number;
  codigo: string;
  orden: string;
  estado: 'CREADA' | 'PAGO_PARCIAL' | 'CONFIRMADA' | 'CANCELADA' | 'EXPIRADA_LIBERADA' | 'COMPLETADA';
  estado_nombre: string;
  empresa: string;
  producto: {
    id: number;
    nombre: string;
    tipo_codigo: string;
    tipo: string;
    ciudad: string;
    localidad: string | null;
    imagen_url: string | null;
    es_hospedaje: boolean;
    hospedaje_id: number | null;
    establecimiento: string | null;
  } | null;
  fechas: { inicio: string; fin: string; noches: number | null } | null;
  importe: {
    cantidad: number;
    unidad: string;
    precio_unitario: string | null;
    precio_original: string;
    descuento: string;
    total: string;
  };
  huespedes: number | null;
  moneda_codigo: string;
  moneda_simbolo: string;
  pago: { estado: string; metodo: string; proveedor: string; referencia: string | null; monto: string; procesado_en: string | null } | null;
  datos_facturacion: { razon_social: string | null; nit: string | null } | null;
  vence_en: string | null;
  qr: string | null;
  creado_en: string;
  checkout_url?: string | null;
}

export interface BookingRequest {
  producto_id: number;
  /** En un tour con salidas basta `salida_id`. */
  fecha_inicio?: string;
  salida_id?: number;
  fecha_fin?: string;
  cantidad: number;
  huespedes?: number;
  politica_cancelacion_id?: number;
  acepta_politica_cancelacion?: boolean;
  razon_social_facturacion?: string;
  nit_facturacion?: string;
}

export interface CancellationPolicyRule {
  dias_antes_min: number;
  dias_antes_max: number | null;
  porcentaje_penalizacion: string;
}

export interface CancellationPolicySummary {
  id: number;
  nombre: string;
  reembolsable: boolean;
  reglas: CancellationPolicyRule[];
}

export interface BookingQuote {
  total: string;
  precio_unitario: string;
  moneda_simbolo: string;
  disponible: boolean;
  disponibles: number;
  noches?: number | null;
  /** La salida cotizada, en tours que se venden por salidas. */
  salida_id?: number | null;
  salida_inicio?: string | null;
  politica_cancelacion: CancellationPolicySummary | null;
}

export interface CancellationQuote {
  reserva_id: number;
  politica_id: number;
  politica: string;
  regla_id: number | null;
  dias_anticipacion: number;
  monto_pagado: string;
  porcentaje_penalizacion: string;
  monto_penalizacion: string;
  monto_reembolso: string;
}

export interface PaidCancellationResult {
  cancelacion_id: number;
  reserva_id: number;
  estado_reserva: TravelerBooking['estado'];
  dias_anticipacion: number;
  porcentaje_penalizacion: string;
  monto_penalizacion: string;
  monto_reembolso: string;
  reembolso: {
    id: number;
    estado: 'SOLICITADO' | 'PROCESANDO' | 'COMPLETADO' | 'FALLIDO' | 'CANCELADO';
    monto: string;
    moneda_id: number;
    referencia: string | null;
    solicitado_en: string;
    procesado_en: string | null;
    motivo_fallo: string | null;
  } | null;
}

export interface Itinerary {
  id: number;
  nombre: string;
  ciudad_id: number | null;
  ciudad: string | null;
  inicio: string;
  fin: string;
  notas: string | null;
  dias: number;
  actividades: number;
}

export interface ItineraryActivity {
  id: number;
  tipo: 'LIBRE' | 'PRODUCTO';
  fecha: string;
  hora: string | null;
  titulo: string;
  nota: string | null;
  producto: { id: number; nombre: string; hospedaje_id: number | null; imagen_url: string | null } | null;
}

export interface ItineraryBookingEntry {
  tipo: 'RESERVA';
  reserva_id: number;
  codigo: string;
  momento: 'LLEGADA' | 'SALIDA' | null;
  titulo: string;
}

export interface ItineraryDetail extends Itinerary {
  agenda: { fecha: string; reservas: ItineraryBookingEntry[]; actividades: ItineraryActivity[] }[];
}

export interface AppNotification {
  id: number;
  tipo: string;
  titulo: string;
  mensaje: string;
  datos: { reserva_id?: number; codigo?: string };
  leida: boolean;
  creado_en: string;
}

export interface Paged<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
