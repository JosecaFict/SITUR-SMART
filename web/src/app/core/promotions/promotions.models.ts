export type PromotionMode = 'EXISTENTE' | 'COMBINADO';
export type PromotionState = 'BORRADOR' | 'PROGRAMADA' | 'VIGENTE' | 'DESACTIVADA' | 'VENCIDA';

export interface PromotionComponentInput {
  producto_id: number;
  fecha_inicio: string;
  fecha_fin?: string | null;
  cantidad: number;
  huespedes?: number | null;
  salida_id?: number | null;
}

export interface PromotionComponent extends PromotionComponentInput {
  id: number;
  nombre?: string;
  tipo_codigo?: string;
  imagen_url?: string | null;
  precio_unitario: string | null;
  total: string | null;
  disponible: boolean;
  motivo: string | null;
  precio_cambio: boolean;
  inicio?: string | null;
  fin?: string | null;
}

export interface PromotionEvaluation {
  valida: boolean;
  advertencias: string[];
  componentes: PromotionComponent[];
  precio_original: string | null;
  precio_final: string | null;
  monto_descuento: string | null;
  moneda_codigo: string | null;
  moneda_simbolo: string | null;
  imagen_url: string | null;
  requiere_revalidacion: boolean;
}

export interface Promotion extends PromotionEvaluation {
  id: number;
  empresa_id: number;
  empresa: string;
  modalidad: PromotionMode;
  producto_id: number | null;
  nombre: string;
  descripcion: string;
  porcentaje_descuento: string;
  inicio: string;
  fin: string;
  estado: PromotionState;
  estado_administrativo: 'BORRADOR' | 'HABILITADA' | 'DESACTIVADA';
  publicado: boolean;
  admite_reservas: boolean;
  reservable: boolean;
  disponible: boolean | null;
  cupos_restantes: number | null;
  motivo_no_reservable: string | null;
  requiere_fecha: boolean;
  cotizacion?: PromotionDiscount;
  creado_en: string;
  actualizado_en: string;
}

/** Summary returned by ProductSerializer, quote and booking responses. */
export interface PromotionDiscount {
  id: number;
  modalidad: 'EXISTENTE';
  nombre: string;
  porcentaje_descuento: string;
  precio_original: string;
  precio_final: string;
  monto_descuento: string;
  total_original: string;
  descuento_total: string;
  total: string;
  inicio: string;
  fin: string;
}

/** BookingSerializer stores a snapshot without a current mode or unit saving field. */
export type BookingPromotionSnapshot = Omit<PromotionDiscount, 'modalidad' | 'monto_descuento'>;

export interface PromotionPayload {
  modalidad: PromotionMode;
  producto_id: number | null;
  nombre: string;
  descripcion?: string;
  porcentaje_descuento: string;
  inicio: string;
  fin: string;
  componentes?: PromotionComponentInput[];
}

export type PromotionUpdate = Pick<PromotionPayload, 'nombre' | 'descripcion' | 'porcentaje_descuento' | 'inicio' | 'fin'>;

export interface PromotionPage {
  count: number;
  next: string | null;
  previous: string | null;
  results: Promotion[];
}
