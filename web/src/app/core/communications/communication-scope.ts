import { AuthUser } from '../auth/auth.models';

/** Sin cabecera solo se admite el ámbito global del SuperAdmin. */
export function communicationScope(user: AuthUser | undefined, company: string | null): number | undefined {
  const global = user?.roles.includes('SUPER_ADMIN') ?? false;
  if (company !== null) {
    const id = Number(company);
    if (!Number.isSafeInteger(id) || id <= 0 || (!global && !user?.tenants.some((tenant) => tenant.id === id))) {
      throw new Error('Selecciona una empresa válida de tu sesión.');
    }
    return id;
  }
  if (global) return undefined;
  const id = user?.tenants[0]?.id;
  if (!id) throw new Error('Tu sesión no tiene una empresa disponible para gestionar comunicaciones.');
  return id;
}
