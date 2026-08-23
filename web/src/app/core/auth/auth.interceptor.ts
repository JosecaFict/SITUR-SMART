import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from './auth.service';

const PUBLIC_AUTH_PATHS = ['/auth/login/', '/auth/refresh/', '/auth/logout/'];

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const auth = inject(AuthService);
  const access = auth.accessToken();
  const authenticatedRequest = access
    ? request.clone({ setHeaders: { Authorization: `Bearer ${access}` } })
    : request;

  return next(authenticatedRequest).pipe(
    catchError((error: HttpErrorResponse) => {
      const isPublicAuthRequest = PUBLIC_AUTH_PATHS.some((path) => request.url.includes(path));
      if (error.status !== 401 || isPublicAuthRequest || !auth.session()) {
        return throwError(() => error);
      }

      return auth.refreshSession().pipe(
        switchMap((session) =>
          next(request.clone({ setHeaders: { Authorization: `Bearer ${session.access}` } })),
        ),
        catchError((refreshError) => {
          auth.clearSession();
          return throwError(() => refreshError);
        }),
      );
    }),
  );
};
