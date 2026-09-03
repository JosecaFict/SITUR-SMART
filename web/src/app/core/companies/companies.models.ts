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
