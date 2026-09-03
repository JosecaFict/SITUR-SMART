import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';

export const authGuard: CanActivateFn = (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (auth.isAuthenticated()) {
    return true;
  }

  return router.createUrlTree(['/login'], { queryParams: { returnUrl: state.url } });
};

export const guestGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (!auth.isAuthenticated()) {
    return true;
  }

  return router.createUrlTree(['/dashboard']);
};

export const superAdminGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (auth.session()?.user.roles.includes('SUPER_ADMIN')) {
    return true;
  }

  return router.createUrlTree(['/dashboard']);
};

export const permissionGuard = (permission: string): CanActivateFn => () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const user = auth.session()?.user;

  if (user?.roles.includes('SUPER_ADMIN') || user?.permisos.includes(permission)) {
    return true;
  }
  return router.createUrlTree(['/dashboard']);
};

export const companyPermissionGuard = (permission: string): CanActivateFn => () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const user = auth.session()?.user;

  if (
    user &&
    !user.roles.includes('SUPER_ADMIN') &&
    user.tenants.length > 0 &&
    user.permisos.includes(permission)
  ) {
    return true;
  }

  return router.createUrlTree(['/dashboard']);
};
