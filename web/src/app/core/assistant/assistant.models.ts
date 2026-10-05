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
}

export interface AssistantStatus {
  chat: boolean;
  voz: boolean;
}
