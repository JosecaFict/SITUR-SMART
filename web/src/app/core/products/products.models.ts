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
  capacidad_maxima: number;
  estado: ProductStatus;
  imagen_url: string | null;
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
}
