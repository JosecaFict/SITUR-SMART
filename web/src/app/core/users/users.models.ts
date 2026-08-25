export interface TenantUser {
  id: number;
  email: string;
  nombres: string;
  apellidos: string;
  telefono: string | null;
  estado: string;
  roles: string[];
}

export interface CreateTenantUserPayload {
  email: string;
  first_names: string;
  last_names: string;
  phone?: string;
  password?: string;
  role_code: string;
}

export interface UpdateTenantUserPayload {
  first_names?: string;
  last_names?: string;
  phone?: string;
  role_code?: string;
}
