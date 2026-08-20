export type UserRole = 'superadmin' | 'dueno' | 'trabajador' | 'cliente';

export interface AuthUser {
  id: string;
  nombre: string;
  email: string;
  role: UserRole;
  tenantId: string | null;
}

export interface AuthSession {
  token: string;
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
