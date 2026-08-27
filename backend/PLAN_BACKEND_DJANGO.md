# Plan del backend Django de SITUR-SMART

## Decisión principal

SITUR-SMART tendrá un único backend y una única base PostgreSQL para atender dos clientes:

```text
Angular Web ──┐
              ├── Django REST API ── PostgreSQL
Flutter ──────┘          │
                         └── tareas asíncronas (posteriormente)
```

No se duplicará lógica entre web y móvil. Autenticación, permisos, precios, disponibilidad,
reservas, pagos y auditoría se resolverán siempre en el backend.

## Responsabilidad de cada interfaz

### Web Angular

- SuperAdmin: empresas, planes, suscripciones, parámetros y métricas globales.
- Tenant Admin: usuarios de su empresa, catálogo, inventario, reservas y reportes.
- Tenant Employee/Guía: operaciones permitidas por sus roles y permisos.
- Cliente: las funciones web para turistas que se decidan implementar.

### Móvil Flutter

- Registro e inicio de sesión del turista.
- Catálogo global de productos publicados por múltiples empresas.
- Búsqueda, favoritos, itinerarios y recomendaciones.
- Órdenes, reservas, pagos y viajes.
- Notificaciones y QR.

## Contextos de seguridad

La API distinguirá tres contextos:

1. **Global:** SuperAdmin, sin tenant.
2. **Tenant:** administradores, empleados y guías con una membresía activa.
3. **Cliente:** turista global, sin pertenecer obligatoriamente a una empresa.

El cliente nunca podrá elegir libremente un `tenant_id` y obtener acceso. El backend validará
la membresía y los permisos en cada operación. El aislamiento no dependerá únicamente de que
Angular o Flutter oculten botones.

## Convenciones de la API

- Prefijo: `/api/v1/`.
- Formato: JSON.
- Documentación: OpenAPI/Swagger.
- Autenticación: access token de corta duración y refresh token revocable.
- Fechas: ISO 8601 y UTC en la API.
- Errores: estructura uniforme con código, mensaje y detalles.
- Paginación en todos los listados administrativos y de catálogo.
- Idempotencia en creación de pagos y operaciones sensibles.

### Grupos iniciales de endpoints

```text
/api/v1/auth/           autenticación, sesión y recuperación
/api/v1/platform/       operaciones exclusivas del SuperAdmin
/api/v1/tenant/         operación de la empresa activa
/api/v1/catalog/        catálogo público/global
/api/v1/me/             perfil, favoritos, órdenes y viajes del turista
```

## Aplicaciones Django propuestas

```text
backend/
├── config/             configuración, URLs y ASGI/WSGI
├── apps/
│   ├── accounts/       usuarios, perfiles, sesiones y recuperación
│   ├── tenancy/        empresas, membresías, planes y suscripciones
│   ├── rbac/           roles y permisos
│   ├── catalog/        países, ciudades, monedas y productos
│   ├── inventory/      disponibilidad y bloqueos
│   ├── bookings/       órdenes, reservas y cancelaciones
│   ├── payments/       pagos
│   └── audit/          bitácora
└── manage.py
```

Cada aplicación tendrá separación entre modelos, servicios/casos de uso, selectores de consulta,
serializadores y vistas. La lógica transaccional no debe quedar dispersa dentro de los endpoints.

## Base de datos existente y migraciones Django

Las 28 tablas actuales constituyen la línea base. No se debe ejecutar `migrate` sobre ellas hasta
crear modelos compatibles y una migración inicial controlada.

Estrategia:

1. Crear el proyecto Django y el modelo de usuario personalizado antes de la primera migración.
2. Mapear explícitamente los nombres existentes mediante `Meta.db_table`.
3. Representar vistas, funciones y triggers mediante migraciones `RunSQL` cuando corresponda.
4. Generar la migración inicial de estado.
5. Comparar el SQL generado por Django con el esquema instalado.
6. Registrar la línea base con `--fake-initial` solamente después de verificar coincidencia.
7. Realizar desde entonces todos los cambios con migraciones nuevas y versionadas.

No se utilizará `inspectdb` como resultado final sin revisión: puede ayudar a generar un borrador,
pero no representa adecuadamente toda la lógica, restricciones y relaciones del dominio.

## Primer incremento recomendado

El primer incremento debe cerrar un flujo vertical y comprobable:

1. Proyecto Django y conexión PostgreSQL.
2. Modelos de cuentas, tenants, membresías, roles y permisos.
3. Comando para crear el primer SuperAdmin.
4. Login, refresh, logout y perfil actual.
5. CRUD de tenants exclusivo del SuperAdmin.
6. Creación/asignación de un Tenant Admin.
7. Pruebas de aislamiento entre dos empresas.
8. Conexión del login web y móvil con la misma API.

Al terminar este incremento se podrá demostrar:

```text
SuperAdmin crea empresa
        ↓
asigna Tenant Admin
        ↓
Tenant Admin entra y sólo ve su empresa
        ↓
turista inicia sesión desde web o móvil
```

## Criterios mínimos de calidad

- Ninguna contraseña o credencial en Git.
- Hash de contraseña administrado por Django con Argon2 como opción preferida.
- Pruebas de permisos y aislamiento multitenant.
- Transacciones para inventario, reservas y pagos.
- Logs sin contraseñas, tokens ni datos sensibles.
- Validación real en backend aunque exista validación en frontend.
- CORS limitado a los orígenes configurados.
- Swagger habilitado en desarrollo y protegido según el ambiente.
- Variables separadas para desarrollo, pruebas y producción.

## Decisiones que pueden esperar

- Celery y Redis, hasta implementar expiración de bloqueos y notificaciones.
- Proveedor real de pagos, porque el documento contempla inicialmente pagos simulados.
- Servicio de IA, hasta que catálogo, disponibilidad y reservas tengan contratos estables.
- Políticas RLS de PostgreSQL, hasta definir cómo se propagará el contexto del tenant desde Django.
- Despliegue definitivo, hasta completar autenticación y pruebas de aislamiento.

