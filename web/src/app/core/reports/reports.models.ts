export type ReportType = 'plataforma' | 'catalogo' | 'hospedajes' | 'actividad';

export interface ReportMetric {
  clave: string;
  etiqueta: string;
  valor: number | string;
  detalle: string;
}

export interface ReportResponse {
  tipo: ReportType;
  alcance: 'GLOBAL' | 'EMPRESA';
  empresa: { id: number; nombre: string } | null;
  indicadores: ReportMetric[];
  columnas: [string, string][];
  filas: Record<string, unknown>[];
  nota: string;
}

export interface ReportFilters {
  tipo: ReportType;
  desde?: string;
  hasta?: string;
  estado?: string;
}

