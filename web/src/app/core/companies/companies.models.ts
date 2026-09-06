export interface Country {
  id: number;
  codigo: string;
  nombre: string;
}

export interface City {
  id: number;
  nombre: string;
  pais_id: number;
  pais: string;
}

export interface CompanyOwner {
  id: number;
  email: string;
  nombres: string;
  apellidos: string;
  telefono: string | null;
}

export type CompanyStatus = 'PENDIENTE' | 'ACTIVO' | 'INACTIVO' | 'SUSPENDIDO';

export interface Company {
  id: number;
  razon_social: string;
  nombre_comercial: string;
  ciudad_id: number | null;
  ciudad: City | null;
  subdominio: string;
  nit: string | null;
  email_contacto: string | null;
  telefono: string | null;
  estado: CompanyStatus;
  propietario: CompanyOwner | null;
  creado_en: string;
  actualizado_en: string;
}

export interface OwnerPayload {
  email: string;
  nombres: string;
  apellidos: string;
  telefono?: string;
  password?: string;
}

export interface CreateCompanyPayload {
  razon_social: string;
  nombre_comercial: string;
  ciudad_id?: number | null;
  subdominio?: string;
  nit?: string;
  email_contacto?: string;
  telefono?: string;
  propietario: OwnerPayload;
}

export interface UpdateCompanyPayload {
  razon_social?: string;
  nombre_comercial?: string;
  ciudad_id?: number | null;
  nit?: string;
  email_contacto?: string;
  telefono?: string;
  estado?: CompanyStatus;
}

export interface Plan {
  id: number;
  codigo: string;
  nombre: string;
  moneda: string;
  precio_mensual: string;
  max_usuarios: number;
  max_productos: number;
  porcentaje_comision: string;
  activo: boolean;
}

export type SubscriptionStatus = 'ACTIVA' | 'VENCIDA' | 'CANCELADA' | 'SUSPENDIDA';

export interface Subscription {
  id: number;
  plan: Plan;
  fecha_inicio: string;
  fecha_fin: string | null;
  estado: SubscriptionStatus;
  renovacion_automatica: boolean;
  creado_en: string;
}

export interface SubscriptionUsage {
  usuarios: number;
  productos: number;
}

export interface CompanySubscriptionInfo {
  suscripcion: Subscription | null;
  uso: SubscriptionUsage;
}

export interface SelfSignupPayload {
  razon_social: string;
  nombre_comercial: string;
  plan_codigo: string;
  ciudad_id?: number | null;
  nit?: string;
  email_contacto?: string;
  telefono?: string;
  propietario: OwnerPayload;
}

export interface SelfSignupResponse {
  empresa: Company;
  suscripcion: Subscription;
}
