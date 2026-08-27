# Sprint 01 - Acceso, usuarios y administración

## Objetivo

Entregar autenticación compartida para Angular y Flutter, administración de roles y permisos,
usuarios, bitácora y un dashboard inicial, utilizando el mismo backend Django y PostgreSQL.

## Dependencia común previa

Antes de dividir las pantallas, una persona debe integrar la base técnica común:

1. Proyecto Django y Django REST Framework.
2. Conexión a la base PostgreSQL existente.
3. Modelo de usuario personalizado compatible con la tabla `usuario`.
4. Línea base de migraciones para las 28 tablas existentes.
5. JWT, manejo uniforme de errores y documentación OpenAPI.
6. Contexto global/tenant y clases base de permisos.

Esta tarea es compartida y bloquea los endpoints, pero no obliga a esperar para avanzar en las
interfaces usando contratos y respuestas simuladas.

## Orden de implementación

```text
Base Django + modelo User
          |
          +--> Autenticación API --> Login web
          |                     \--> Login móvil
          |
          +--> RBAC API -----------> Roles y permisos
          |                     \--> CRUD usuarios web/móvil
          |
          +--> Auditoría ----------> Bitácora
          |
          \--> Sesión + métricas ---> Dashboard
```

## Alcance: Login web

### Backend requerido

```text
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/auth/me
```

### Contrato mínimo de login

Solicitud:

```json
{
  "email": "admin@situr.bo",
  "password": "********"
}
```

Respuesta:

```json
{
  "access": "jwt-access",
  "refresh": "jwt-refresh",
  "user": {
    "id": 1,
    "email": "admin@situr.bo",
    "nombres": "Administrador",
    "apellidos": "SITUR",
    "roles": ["SUPER_ADMIN"],
    "permisos": ["TENANTS_LEER", "TENANTS_GESTIONAR"],
    "tenants": []
  }
}
```

Para un usuario de empresa, `tenants` contendrá sus membresías. El backend debe validar que el
usuario y la membresía estén activos.

### Web Angular

- Sustituir el `AuthService` simulado por llamadas HTTP.
- Guardar el access token sólo durante la sesión de la aplicación.
- Implementar interceptor para `Authorization: Bearer <token>`.
- Implementar refresh controlado cuando expire el access token.
- Mantener el guard de rutas, pero validarlo contra la sesión real.
- Redirigir según contexto: SuperAdmin o tenant.
- Mostrar mensajes del backend sin revelar información sensible.

## Alcance: Roles y permisos

### Backend requerido

```text
GET    /api/v1/permissions
GET    /api/v1/roles
POST   /api/v1/roles
GET    /api/v1/roles/{id}
PATCH  /api/v1/roles/{id}
DELETE /api/v1/roles/{id}
PUT    /api/v1/roles/{id}/permissions
```

### Reglas

- `SUPER_ADMIN` y `CLIENTE` son roles globales del sistema.
- `TENANT_ADMIN`, `TENANT_EMPLOYEE` y `GUIA` son plantillas de ámbito tenant.
- Los roles marcados como `es_sistema` no se eliminan ni cambian de ámbito.
- Un Tenant Admin administra roles únicamente dentro de su tenant.
- Un rol de otro tenant nunca puede consultarse, asignarse o modificarse.
- El backend valida permisos; ocultar botones en Angular es solamente una ayuda visual.
- Cada cambio de rol o permisos genera un registro en `bitacora`.

### Web Angular

- Listado y búsqueda de roles.
- Formulario para crear o editar roles propios del tenant.
- Matriz de permisos agrupada por módulo.
- Confirmación antes de eliminar un rol.
- Bloqueo visual de roles del sistema.
- Estados de carga, vacío y error.

## División sugerida del equipo

| Trabajo | Puede empezar | Dependencia para integrar |
|---|---|---|
| Login web | Sí, con contrato simulado | Auth API |
| Login móvil | Sí, con contrato simulado | Auth API |
| Roles y permisos | Sí, con datos simulados | RBAC API |
| Bitácora | Sí, interfaz y filtros | Middleware/servicio de auditoría |
| CRUD usuarios web | Sí, interfaz | Auth + RBAC + tenancy |
| CRUD usuarios móvil | Revisar alcance primero | Auth + definición del usuario móvil |
| Dashboard | Sí, estructura visual | Sesión y endpoints de métricas |

## Criterios de aceptación de la parte Login web + Roles

- El usuario válido inicia sesión contra Django.
- Un usuario bloqueado o inactivo no puede ingresar.
- Logout revoca la sesión de refresh.
- Las rutas privadas requieren sesión.
- La pantalla distingue roles globales y roles de tenant.
- Un Tenant Admin no ve roles de otra empresa.
- No se puede eliminar un rol del sistema.
- La asignación de permisos queda persistida.
- Los cambios relevantes aparecen en bitácora.
- Existen pruebas del backend para autorización y aislamiento.

## Decisión pendiente del equipo

El punto `CRUD USUARIOS MÓVIL` debe aclararse. Para turistas, móvil debería permitir registro y
edición del perfil propio, no un CRUD administrativo completo. La administración de empleados y
roles corresponde principalmente a la web.

