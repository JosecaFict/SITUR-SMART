import { ProductStatus } from '../products/products.models';

export interface LodgingType {
  id: number;
  codigo: string;
  nombre: string;
}

/**
 * Establecimiento de hospedaje. Los datos comunes (nombre, ubicación, moneda,
 * estado, imagen) vienen del producto turístico que el backend resuelve; acá
 * llegan ya planos.
 */
export interface LodgingEstablishment {
  id: number;
  producto_id: number;
  empresa_id: number;
  empresa: string;
  tipo_hospedaje_codigo: string;
  tipo_hospedaje: string;
  nombre: string;
  descripcion: string | null;
  ciudad_id: number;
  ciudad: string;
  pais_id: number;
  pais: string;
  localidad: string | null;
  moneda_codigo: string;
  moneda_simbolo: string;
  capacidad_maxima: number;
  estado: ProductStatus;
  imagen_url: string | null;
  direccion: string | null;
  categoria_estrellas: number | null;
  hora_check_in: string | null;
  hora_check_out: string | null;
  servicios: string[];
  /** Precio de la habitación publicada más económica. Nulo si no tiene ninguna. */
  precio_desde: string | null;
  total_habitaciones: number;
  creado_en: string;
  actualizado_en: string;
}

/** Tipo de habitación, no una habitación física numerada. */
export interface Room {
  id: number;
  producto_id: number;
  establecimiento_id: number;
  establecimiento: string;
  empresa_id: number;
  empresa: string;
  nombre: string;
  descripcion: string | null;
  ciudad_id: number;
  ciudad: string;
  pais_id: number;
  pais: string;
  localidad: string | null;
  moneda_codigo: string;
  moneda_simbolo: string;
  precio_noche: string;
  capacidad_maxima: number;
  capacidad_adultos: number;
  capacidad_ninos: number;
  cantidad_habitaciones: number;
  tipo_cama: string | null;
  incluye_desayuno: boolean;
  estado: ProductStatus;
  imagen_url: string | null;
  creado_en: string;
  actualizado_en: string;
}

/** No incluye precio: el de un hotel se deriva de sus habitaciones. */
export interface LodgingPayload {
  tipo_hospedaje_codigo?: string;
  nombre: string;
  descripcion?: string;
  ciudad_id: number;
  localidad?: string;
  moneda_codigo: string;
  capacidad_maxima: number;
  estado: ProductStatus;
  imagen_url?: string;
  direccion?: string;
  categoria_estrellas?: number | null;
  hora_check_in?: string | null;
  hora_check_out?: string | null;
  servicios?: string[];
}

/**
 * No incluye ciudad ni localidad: el backend las hereda del establecimiento, y
 * mandarlas no tendría efecto.
 */
export interface RoomPayload {
  nombre: string;
  descripcion?: string;
  moneda_codigo?: string;
  precio_base: number;
  capacidad_maxima: number;
  estado: ProductStatus;
  imagen_url?: string;
  cantidad_habitaciones?: number;
  capacidad_adultos?: number;
  capacidad_ninos?: number;
  tipo_cama?: string;
  incluye_desayuno?: boolean;
}

export interface LodgingMarketplaceFilters {
  pais?: number;
  ciudad?: number;
  localidad?: string;
  buscar?: string;
  estrellas?: number;
  tipo_hospedaje?: string;
  precio_min?: number;
  precio_max?: number;
  orden?: 'recientes' | 'precio_asc' | 'precio_desc' | 'nombre';
  page?: number;
  page_size?: number;
}

export interface RoomMarketplaceFilters extends Omit<LodgingMarketplaceFilters, 'estrellas' | 'tipo_hospedaje'> {
  hospedaje?: number;
  huespedes?: number;
}

export interface LodgingPage {
  count: number;
  next: string | null;
  previous: string | null;
  results: LodgingEstablishment[];
}

export interface RoomPage {
  count: number;
  next: string | null;
  previous: string | null;
  results: Room[];
}
