import { MarketplacePage } from '../products/products.models';

export interface PackageComponent {
  id: number;
  producto_id: number;
  nombre: string;
  tipo: string;
  tipo_codigo: string;
  empresa: string;
  ciudad: string;
  imagen_url: string | null;
  fecha_inicio: string;
  fecha_fin: string | null;
  cantidad: number;
  huespedes: number | null;
  salida_id: number | null;
  inicio: string | null;
  hora_inicio: string | null;
  precio_unitario: string;
  total: string;
  total_actual: string | null;
  disponible: boolean;
  requiere_revalidacion: boolean;
  motivo: string | null;
}

export interface CustomPackage {
  id: number;
  nombre: string;
  ciudad_id: number | null;
  ciudad: string | null;
  fecha_inicio: string;
  fecha_fin: string;
  personas: number;
  estado: 'BORRADOR' | 'GUARDADO';
  total: string;
  cantidad_servicios: number;
  creado_en: string;
  actualizado_en: string;
  componentes?: PackageComponent[];
  advertencias?: string[];
  requiere_revalidacion?: boolean;
  compra?: { id: number; estado: string; total: string; reservas: number[] } | null;
}

export interface PackagePayload {
  nombre: string;
  ciudad_id: number | null;
  fecha_inicio: string;
  fecha_fin: string;
  personas: number;
}

export interface ComponentPayload {
  componente_id?: number;
  producto_id: number;
  fecha_inicio: string;
  fecha_fin?: string | null;
  cantidad: number;
  huespedes?: number | null;
  salida_id?: number | null;
}

export interface PackageQuote {
  producto_id: number;
  precio_unitario: string;
  total: string;
  moneda_simbolo: string;
  disponible: boolean;
  salida_id: number | null;
}

export type PackageCatalogPage = MarketplacePage;

export interface PackagePurchaseResult {
  id: number;
  estado: 'CREADA' | 'CONFIRMADA' | 'CANCELADA' | 'EXPIRADA' | 'REEMBOLSADA';
  total: string;
  checkout_url: string | null;
  reservas: number[];
}

export interface PackageCancellationQuote {
  compra_id: number;
  pagado: string;
  penalizacion: string;
  reembolso: string;
  componentes: { reserva_id: number; empresa: string; pagado: string; penalizacion: string; reembolso: string; porcentaje_penalizacion: string; politica: string }[];
}
