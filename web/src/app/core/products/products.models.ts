export type ProductStatus = 'BORRADOR' | 'PUBLICADO' | 'INACTIVO';

export interface ProductType { id: number; codigo: string; nombre: string; }
export interface Currency { id: number; codigo: string; nombre: string; simbolo: string; }

export interface TourismProduct {
  id: number;
  empresa_id: number;
  empresa: string;
  tipo_codigo: string;
  tipo: string;
  ciudad_id: number;
  ciudad: string;
  pais_id: number;
  pais: string;
  moneda_codigo: string;
  moneda_simbolo: string;
  codigo: string;
  nombre: string;
  descripcion: string | null;
  localidad: string | null;
  precio_base: string;
  /**
   * Precio de la habitación publicada más económica. Solo lo traen los
   * hoteles, y solo en las consultas públicas; en el resto es null.
   */
  precio_desde: string | null;
  capacidad_maxima: number;
  estado: ProductStatus;
  imagen_url: string | null;
  /**
   * Establecimiento cuyo detalle corresponde abrir: la ficha propia si es un
   * hotel, la del hotel que la aloja si es una habitación. Es el id de
   * `establecimiento_hospedaje`, distinto del id del producto.
   */
  hospedaje_id: number | null;
  /** Nombre del hotel. Solo en habitaciones. */
  establecimiento: string | null;
  /** Publicación programada: el sistema lo publica o retira solo a esa hora. */
  publicar_en?: string | null;
  retirar_en?: string | null;
  /** Cuándo lo publicó el sistema solo (publicación programada). */
  publicado_automaticamente_en?: string | null;
  creado_en: string;
  actualizado_en: string;
}

export interface ProductPayload {
  tipo_codigo: string;
  ciudad_id: number;
  moneda_codigo: string;
  nombre: string;
  descripcion?: string;
  localidad?: string;
  precio_base: number;
  capacidad_maxima: number;
  estado: ProductStatus;
  imagen_url?: string;
}

export interface MarketplaceFilters {
  pais?: number;
  ciudad?: number;
  localidad?: string;
  tipo?: string;
  fecha?: string;
  buscar?: string;
  precio_min?: number;
  precio_max?: number;
  orden?: 'recientes' | 'precio_asc' | 'precio_desc' | 'nombre';
  page?: number;
  page_size?: number;
}

export interface MarketplacePage {
  count: number;
  next: string | null;
  previous: string | null;
  results: TourismProduct[];
}
