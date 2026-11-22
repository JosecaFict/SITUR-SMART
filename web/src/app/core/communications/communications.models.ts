export type CommunicationType = 'INTERNA' | 'OPERATIVA' | 'PROMOCIONAL';
export type AudienceGroup = 'TODOS' | 'PERSONAL' | 'CLIENTES' | 'PROPIETARIOS' | 'EMPLEADOS' | 'USUARIOS';

export interface CommunicationAudience {
  grupo: AudienceGroup;
  empresa_ids: number[];
  rol_ids: number[];
  usuario_ids: number[];
  reserva_id?: number;
  salida_id?: number;
}

export interface CommunicationPayload {
  titulo: string;
  mensaje: string;
  tipo: CommunicationType;
  audiencia: CommunicationAudience;
  reserva_id?: number | null;
  programado_en?: string | null;
  vence_en?: string | null;
  promocion_id?: number | null;
}

export type CommunicationSender = string | { id?: number; nombre?: string; nombres?: string; apellidos?: string; email?: string };

export interface Communication extends CommunicationPayload {
  readonly enviar_correo?: boolean;
  id: number;
  estado: 'BORRADOR' | 'PUBLICADA' | 'PROGRAMADA' | 'CANCELADA' | 'VENCIDA' | 'REVISION';
  remitente: CommunicationSender | null;
  creado_en: string;
  publicado_en: string | null;
  total_destinatarios: number;
  leidas: number;
  push_pendientes: number;
  push_aceptados: number;
  push_fallidos: number;
  sin_dispositivo: number;
  programados?: number;
  omitidos?: number;
  error_envio?: string;
  vencida?: boolean;
  correos_pendientes?: number;
  correos_aceptados?: number;
  correos_fallidos?: number;
  correos_omitidos?: number;
  correos_revision?: number;
}

export interface AudiencePreview {
  total: number;
  destinatarios: { id: number; nombre: string; email: string }[];
  huella: string;
  excluidos_promociones?: number;
}

export interface CommunicationOption { id: number; nombre: string; codigo?: string; ambito?: 'GLOBAL' | 'TENANT'; empresa_id?: number | null; }
export interface CommunicationOptions {
  empresas: CommunicationOption[];
  roles: CommunicationOption[];
  usuarios: (CommunicationOption & { email: string })[];
  reservas: CommunicationOption[];
  salidas: CommunicationOption[];
  es_global: boolean;
  promociones?: CommunicationOption[];
  correo_disponible?: boolean;
}

export interface CommunicationPage {
  count: number;
  next: string | null;
  previous: string | null;
  results: Communication[];
  resumen?: Record<string, number>;
}

export interface CommunicationOptionFilters { empresa_ids: number[]; rol_ids: number[]; grupo: AudienceGroup; tipo: CommunicationType; }

export interface CommunicationPreferences {
  preferencias: { empresa_id: number | null; nombre: string; promociones: boolean }[];
  limites: { por_empresa_24h: number; total_24h: number };
}

export function senderName(sender: CommunicationSender | null | undefined): string {
  if (typeof sender === 'string') return sender;
  return sender?.nombre || [sender?.nombres, sender?.apellidos].filter(Boolean).join(' ') || sender?.email || 'SITUR-SMART';
}
