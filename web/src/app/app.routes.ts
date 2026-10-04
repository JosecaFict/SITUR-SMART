import { Routes } from '@angular/router';
import {
  authGuard,
  companyPermissionGuard,
  guestGuard,
  permissionGuard,
  superAdminGuard,
} from './core/auth/auth.guard';
import { AppShell } from './core/layout/app-shell/app-shell';

export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    loadComponent: () =>
      import('./features/marketplace/busqueda/busqueda').then((m) => m.Busqueda),
  },
  {
    path: 'login',
    canActivate: [guestGuard],
    loadComponent: () => import('./features/auth/login/login').then((m) => m.Login),
  },
  {
    path: 'planes',
    loadComponent: () => import('./features/marketplace/planes/planes').then((m) => m.Planes),
  },
  // Páginas públicas del hospedaje: fuera del AppShell, sin authGuard. La más
  // específica va primero para que ':id' no capture el tramo de habitaciones.
  {
    path: 'marketplace/hospedajes/:hospedajeId/habitaciones/:habitacionId',
    loadComponent: () =>
      import('./features/marketplace/hospedaje/habitacion-publica').then((m) => m.HabitacionPublica),
  },
  {
    path: 'marketplace/hospedajes/:id',
    loadComponent: () =>
      import('./features/marketplace/hospedaje/hospedaje-publico').then((m) => m.HospedajePublico),
  },
  {
    path: 'registro',
    canActivate: [guestGuard],
    loadComponent: () => import('./features/auth/registro/registro').then((m) => m.Registro),
  },
  {
    path: 'crear-cuenta',
    canActivate: [guestGuard],
    loadComponent: () => import('./features/auth/register/register').then((m) => m.Register),
  },
  {
    path: 'registro-turista',
    redirectTo: 'crear-cuenta',
    pathMatch: 'full',
  },
  {
    path: 'recuperar',
    canActivate: [guestGuard],
    loadComponent: () =>
      import('./features/auth/forgot-password/forgot-password').then((m) => m.ForgotPassword),
  },
  {
    path: '',
    component: AppShell,
    canActivate: [authGuard],
    children: [
      {
        path: 'dashboard',
        loadComponent: () => import('./features/dashboard/dashboard/dashboard').then((m) => m.Dashboard),
      },
      {
        path: 'perfil',
        loadComponent: () => import('./features/profile/perfil').then((m) => m.Perfil),
      },
      {
        path: 'empresas',
        canActivate: [superAdminGuard],
        loadComponent: () =>
          import('./features/admin/empresas/empresas').then((m) => m.Empresas),
      },
      {
        path: 'roles',
        canActivate: [permissionGuard('ROLES_GESTIONAR')],
        loadComponent: () => import('./features/admin/roles/roles').then((m) => m.Roles),
      },
      {
        path: 'usuarios',
        canActivate: [companyPermissionGuard('USUARIOS_GESTIONAR')],
        loadComponent: () => import('./features/admin/usuarios/usuarios').then((m) => m.Usuarios),
      },
      {
        path: 'productos',
        canActivate: [permissionGuard('PRODUCTOS_LEER')],
        loadComponent: () =>
          import('./features/admin/productos/productos').then((m) => m.Productos),
      },
      // El orden importa: 'nuevo' va antes de ':id' para que no lo capture como
      // identificador. La ficha y su pestaña de habitaciones son el mismo
      // componente; 'tab' decide cuál se abre, y así cada una tiene su URL.
      {
        path: 'hospedajes',
        canActivate: [permissionGuard('PRODUCTOS_LEER')],
        loadComponent: () =>
          import('./features/admin/hospedajes/hospedajes-lista').then((m) => m.HospedajesLista),
      },
      {
        path: 'hospedajes/nuevo',
        canActivate: [permissionGuard('PRODUCTOS_LEER')],
        loadComponent: () =>
          import('./features/admin/hospedajes/hospedaje-detalle').then((m) => m.HospedajeDetalle),
      },
      {
        path: 'hospedajes/:id',
        canActivate: [permissionGuard('PRODUCTOS_LEER')],
        data: { tab: 'general' },
        loadComponent: () =>
          import('./features/admin/hospedajes/hospedaje-detalle').then((m) => m.HospedajeDetalle),
      },
      {
        path: 'hospedajes/:id/habitaciones',
        canActivate: [permissionGuard('PRODUCTOS_LEER')],
        data: { tab: 'habitaciones' },
        loadComponent: () =>
          import('./features/admin/hospedajes/hospedaje-detalle').then((m) => m.HospedajeDetalle),
      },
      {
        path: 'bitacora',
        canActivate: [permissionGuard('BITACORA_LEER')],
        loadComponent: () => import('./features/admin/bitacora/bitacora').then((m) => m.Bitacora),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];

