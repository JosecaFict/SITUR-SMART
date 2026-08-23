export interface TenantContext {
  id: number;
  name: string;
  subdomain: string;
}

export interface AuthUser {
  id: number;
  email: string;
  nombres: string;
  apellidos: string;
  estado: string;
  roles: string[];
  permisos: string[];
  tenants: TenantContext[];
}

export interface AuthSession {
  access: string;
  refresh: string;
  user: AuthUser;
}

export interface LoginPayload {
  email: string;
  password: string;
  remember: boolean;
}

export interface RegisterPayload {
  nombre: string;
  email: string;
  password: string;
}

export interface ApiErrorResponse {
  error?: {
    status?: number;
    message?: string;
    details?: unknown;
  };
}
