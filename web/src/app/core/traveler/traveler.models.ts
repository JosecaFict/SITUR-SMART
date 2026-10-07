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
  importe: { cantidad: number; unidad: string; precio_unitario: string | null; total: string };
  huespedes: number | null;
  moneda_codigo: string;
  moneda_simbolo: string;
  pago: { estado: string; proveedor: string; monto: string; procesado_en: string | null } | null;
  vence_en: string | null;
  qr: string | null;
  creado_en: string;
  checkout_url?: string | null;
}

export interface BookingRequest {
  producto_id: number;
  fecha_inicio: string;
  fecha_fin?: string;
  cantidad: number;
  huespedes?: number;
}

export interface BookingQuote {
  total: string;
  precio_unitario: string;
  moneda_simbolo: string;
  disponible: boolean;
  disponibles: number;
  noches?: number | null;
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
