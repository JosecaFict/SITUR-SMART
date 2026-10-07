export type AssistantRole = 'usuario' | 'asistente';

export interface AssistantHistoryItem {
  rol: AssistantRole;
  contenido: string;
}

/** Hospedaje que el asistente mencionó, listo para mostrarse como tarjeta. */
export interface AssistantLodgingCard {
  id: number;
  nombre: string;
  tipo: string;
  ciudad: string;
  localidad: string | null;
  empresa: string;
  estrellas: number | null;
  precio_desde: string | null;
  moneda: string;
  servicios: string[];
  imagen_url: string | null;
  url: string;
  puntaje?: number;
  motivos?: string[];
}

export interface AssistantChatResponse {
  respuesta: string;
  hospedajes: AssistantLodgingCard[];
  /** Solo para el personal y el SuperAdmin; un turista recibe una lista vacía. */
  reportes?: AssistantReport[];
}

export interface AssistantStatus {
  chat: boolean;
  voz: boolean;
}

/**
 * Reporte que el asistente armó para el personal o el SuperAdmin. La web baja el
 * archivo con /reportes/exportar/, que vuelve a verificar permisos.
 */
export interface AssistantReport {
  tipo: 'plataforma' | 'catalogo' | 'hospedajes' | 'actividad';
  titulo: string;
  formato: 'pdf' | 'excel' | null;
  desde: string | null;
  hasta: string | null;
  empresa_id: number | null;
  empresa: string | null;
  filas: number;
}
