export interface ProductReview {
  id: number;
  producto_id: number;
  autor: string;
  es_propia: boolean;
  calificacion: number;
  comentario: string;
  creado_en: string;
  actualizado_en: string;
}

export interface ReviewPage {
  count: number;
  next: string | null;
  previous: string | null;
  results: ProductReview[];
  /** Recuento de todas las reseñas del producto, no solo de esta página. */
  distribucion_calificaciones: Record<1 | 2 | 3 | 4 | 5, number>;
}

export interface ReviewPayload {
  calificacion: number;
  comentario: string;
}
