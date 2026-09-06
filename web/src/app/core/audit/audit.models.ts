export interface AuditLogEntry {
  id: number;
  tenant_id: number | null;
  empresa: string | null;
  user_id: number | null;
  usuario_email: string | null;
  usuario_nombre: string | null;
  action: string;
  entity: string;
  entity_id: string | null;
  previous_data: unknown;
  new_data: unknown;
  ip: string | null;
  request_id: string | null;
  created_at: string;
}

export interface AuditLogResponse {
  total: number;
  limit: number;
  offset: number;
  resultados: AuditLogEntry[];
}

export interface AuditLogFilters {
  entidad?: string;
  accion?: string;
  usuario?: string;
  desde?: string;
  hasta?: string;
  limit?: number;
  offset?: number;
}
