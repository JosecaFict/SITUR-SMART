export interface TenantContext {
  id: number;
  name: string;
  subdomain: string;
}

export interface CustomerProfileData {
  tipo_documento?: string | null;
  numero_documento?: string | null;
  fecha_nacimiento?: string | null;
}

export interface AuthUser {
  id: number;
  email: string;
  nombres: string;
  apellidos: string;
  telefono?: string | null;
  estado: string;
  roles: string[];
  permisos: string[];
  tenants: TenantContext[];
  perfil?: CustomerProfileData | null;
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
  nombres: string;
  apellidos: string;
  email: string;
  password: string;
  telefono?: string | null;
}

export interface ProfileUpdatePayload {
  nombres?: string;
  apellidos?: string;
  telefono?: string | null;
  tipo_documento?: string | null;
  numero_documento?: string | null;
  fecha_nacimiento?: string | null;
}


export interface ApiErrorResponse {
  error?: {
    status?: number;
    message?: string;
    details?: unknown;
  };
}

export interface PasswordResetRequestPayload {
  email: string;
}

export interface PasswordResetVerifyPayload {
  email: string;
  code: string;
}

export interface PasswordResetConfirmPayload {
  email: string;
  code: string;
  new_password: string;
  new_password_confirm: string;
}

export interface PasswordResetResponse {
  detail: string;
  valid?: boolean;
}

