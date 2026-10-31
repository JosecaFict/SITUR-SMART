import { ProductStatus } from '../products/products.models';

export type TourTypeCode = 'TOUR' | 'EXPERIENCIA';
export type TourDifficulty = 'BAJA' | 'MEDIA' | 'ALTA';

/** Ficha propia del tour. Null en un tour del Catálogo genérico que todavía no la tiene. */
export interface TourDetail {
  duracion_minutos: number | null;
  /** La duración como se lee: "3 h 30 min". */
  duracion: string | null;
  idioma: string | null;
  dificultad: TourDifficulty | null;
  edad_minima: number | null;
  punto_encuentro: string | null;
  /** Decimales como texto (`"-20.460000"`), igual que en hospedaje. */
  latitud: string | null;
  longitud: string | null;
  incluye: string[];
  no_incluye: string[];
  requisitos: string | null;
}

export interface TourStop {
  id: number;
  orden: number;
  nombre: string;
  descripcion: string | null;
  duracion_minutos: number | null;
}

export interface Tour {
  id: number;
  empresa_id: number;
  empresa: string;
  tipo_codigo: TourTypeCode;
  tipo: string;
  codigo: string;
  nombre: string;
  descripcion: string | null;
  ciudad_id: number;
  ciudad: string;
  pais: string;
  localidad: string | null;
  moneda_codigo: string;
  moneda_simbolo: string;
  precio_base: string;
  capacidad_maxima: number;
  estado: ProductStatus;
  imagen_url: string | null;
  publicar_en: string | null;
  retirar_en: string | null;
  detalle: TourDetail | null;
  paradas: TourStop[];
  salidas_proximas: number;
  proxima_salida: string | null;
  /** Explica un cambio que hizo el backend por su cuenta (por ejemplo, volver a borrador). */
  aviso: string | null;
  creado_en: string;
  actualizado_en: string;
}

export interface TourStopPayload {
  nombre: string;
  descripcion?: string | null;
  duracion_minutos?: number | null;
}

export interface TourPayload {
  tipo_codigo?: TourTypeCode;
  nombre?: string;
  descripcion?: string | null;
  ciudad_id?: number;
  localidad?: string | null;
  moneda_codigo?: string;
  precio_base?: number;
  capacidad_maxima?: number;
  estado?: ProductStatus;
  imagen_url?: string | null;
  duracion_minutos?: number | null;
  idioma?: string | null;
  dificultad?: TourDifficulty | null;
  edad_minima?: number | null;
  punto_encuentro?: string | null;
  latitud?: string | null;
  longitud?: string | null;
  incluye?: string[];
  no_incluye?: string[];
  requisitos?: string | null;
  paradas?: TourStopPayload[];
}

/** Una salida: fecha y hora concretas del tour, con su propio cupo. */
export interface TourDeparture {
  id: number;
  tour_id: number;
  inicio: string;
  fin: string;
  cupo: number;
  reservados: number;
  disponibles: number;
  cerrada: boolean;
  guia_id: number | null;
  guia: string | null;
}

/** Lo que ve el turista de una salida. */
export interface PublicDeparture {
  id: number;
  tour_id: number;
  inicio: string;
  fin: string;
  disponibles: number;
  guia: string | null;
  guia_idiomas: string[] | null;
}

export interface DeparturePayload {
  inicio?: string;
  fin?: string | null;
  cupo?: number;
  guia_id?: number | null;
  cerrada?: boolean;
}

/** Salidas repetidas: 0 = lunes … 6 = domingo. */
export interface RecurringDeparturePayload {
  dias_semana: number[];
  hora_inicio: string;
  hora_fin?: string | null;
  desde: string;
  hasta: string;
  cupo?: number;
  guia_id?: number | null;
}

export interface RecurringDepartureResult {
  creadas: TourDeparture[];
  omitidas: number;
}

export type GuideStatus = 'ACTIVO' | 'INACTIVO';

export interface Guide {
  id: number;
  nombres: string;
  telefono: string | null;
  idiomas: string[];
  estado: GuideStatus;
  creado_en: string;
}

export interface GuidePayload {
  nombres?: string;
  telefono?: string | null;
  idiomas?: string[];
  estado?: GuideStatus;
}
