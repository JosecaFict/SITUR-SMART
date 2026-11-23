/** Respuesta de GET /dashboard/: importes como texto con dos decimales, en Bs. */

export interface MonthPoint {
  mes: string;
  etiqueta: string;
  cobrado: string;
  reembolsado: string;
  neto: string;
  reservas: number;
}

export interface StateCount {
  estado: string;
  etiqueta: string;
  total: number;
  porcentaje: number;
}

export interface DashboardAlert {
  clave: string;
  titulo: string;
  detalle: string;
  nivel: 'alta' | 'media' | 'info';
  total: number;
  ruta: string;
}

export interface LatestReview {
  autor: string;
  calificacion: number;
  comentario: string;
  producto: string;
  fecha: string;
}

export interface TopProduct {
  id: number;
  nombre: string;
  ciudad: string | null;
  reservas: number;
  unidades: number;
  ingreso: string;
}

export interface UpcomingBooking {
  reserva: string;
  inicio: string;
  cliente: string;
  producto: string;
  cantidad: number;
  dias: number;
  monto: string;
  estado: string;
}

export interface ActivePromotion {
  id: number;
  nombre: string;
  porcentaje: string;
  usos: number;
  inicia: string;
  vence: string;
  vigente: boolean;
}

export interface RankedCompany {
  id: number;
  nombre: string;
  cobrado: string;
  reservas: number;
  calificacion: number | null;
}

export interface CompanyComparison {
  id: number;
  nombre: string;
  cobrado: string;
  reembolsado: string;
  neto: string;
  reservas: number;
  canceladas: number;
  ocupacion: number | null;
  calificacion: number | null;
  serie: { etiqueta: string; neto: string }[];
}

export interface LatestBooking {
  reserva: string;
  empresa: string;
  cliente: string;
  monto: string;
  moneda: string;
  estado: string;
  fecha: string;
}

export interface DashboardStats {
  alcance: 'empresa' | 'plataforma';
  empresas: number[];
  generado: string;
  mes: string;
  finanzas: {
    moneda: string;
    cobrado: string;
    reembolsado: string;
    neto: string;
    variacion_neto: number | null;
    serie: MonthPoint[];
  };
  reservas: { total: number; variacion: number | null; canceladas: number; por_estado: StateCount[] };
  ocupacion: { vendidos: number; capacidad: number; porcentaje: number | null };
  calificacion: { promedio: number | null; total: number; nuevas_mes: number; ultimas?: LatestReview[] };
  alertas: DashboardAlert[];
  productos_top: TopProduct[];
  catalogo: { publicados: number; total: number };
  // Solo empresa
  proximas?: UpcomingBooking[];
  promociones?: ActivePromotion[];
  // Solo SuperAdmin
  plataforma?: {
    empresas: { total: number; activas: number; tasa_activacion: number | null };
    turistas: { total: number; nuevos_mes: number; con_compra: number; porcentaje_compra: number | null };
  };
  ranking?: RankedCompany[];
  suscripciones?: { plan: string; empresas: number }[];
  ciudades?: { ciudad: string; reservas: number }[];
  ultimas_reservas?: LatestBooking[];
  comparacion?: CompanyComparison[];
}
