export interface Role {
  id: number;
  tenant_id: number | null;
  code: string;
  name: string;
  scope: 'GLOBAL' | 'TENANT';
  is_system: boolean;
  permissions: string[];
}

export interface Permission {
  id: number;
  code: string;
  module: string;
  name: string;
}
