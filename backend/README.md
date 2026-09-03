# Backend SITUR-SMART

API REST compartida para Angular y Flutter, desarrollada con Django, Django REST Framework y
PostgreSQL.

## Preparación local

1. Instalar Python 3.12 o posterior.
2. Crear el entorno virtual dentro de `backend`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements\development.txt
```

3. Copiar `.env.example` como `.env` y configurar la conexión local.
4. Registrar la línea base y crear las tablas internas de Django:

```powershell
python manage.py migrate
```

Las migraciones iniciales de `accounts`, `tenancy`, `rbac` y `audit` mantienen únicamente el
estado de los modelos existentes (`managed = False`); no recrean las 28 tablas de negocio.

5. Verificar el proyecto:

```powershell
python manage.py check
python manage.py spectacular --file openapi.yaml --validate
pytest
```

## Base existente

Las tablas de negocio ya fueron creadas mediante los scripts de `database/migrations`. Los modelos
iniciales usan `managed = False` para impedir que Django intente recrearlas. La migración de línea
base ya fue generada y validada contra PostgreSQL 17. Los cambios futuros deberán incorporarse
mediante migraciones nuevas y revisadas; no se debe editar una migración ya aplicada en entornos
compartidos.

## Primer SuperAdmin

Con la base y los catálogos iniciales disponibles:

```powershell
python manage.py createsituradmin
```

La contraseña se procesa con los hashers de Django y nunca se guarda en texto plano.

## Administración interna de Django

Después de ejecutar las migraciones y crear el SuperAdmin, iniciar el servidor:

```powershell
python manage.py runserver
```

El panel interno estará disponible en `http://127.0.0.1:8000/admin/`. Se ingresa con el correo y
la contraseña registrados mediante `createsituradmin`. Este panel es una herramienta interna del
backend y no sustituye las pantallas administrativas que tendrá la aplicación web Angular.

## Despliegue en Railway

Configurar el servicio con el directorio raíz `/backend`. Railpack detecta `requirements.txt`,
instala las dependencias de producción y utiliza Python 3.12 según `.python-version`.

```text
Pre-Deploy: python manage.py migrate --noinput
Start:      gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
Health:     /api/v1/health/
```

## Endpoints iniciales

```text
GET  /api/v1/health/
POST /api/v1/auth/login/
POST /api/v1/auth/refresh/
POST /api/v1/auth/logout/
GET  /api/v1/auth/me/
GET  /api/v1/permissions/
GET  /api/v1/roles/
POST /api/v1/roles/
GET  /api/v1/roles/{id}/
PATCH /api/v1/roles/{id}/
DELETE /api/v1/roles/{id}/
GET  /api/v1/usuarios/
POST /api/v1/usuarios/
GET  /api/v1/usuarios/{id}/
PATCH /api/v1/usuarios/{id}/
DELETE /api/v1/usuarios/{id}/
GET  /api/v1/catalogos/paises/
GET  /api/v1/catalogos/ciudades/
GET  /api/v1/catalogos/tipos-producto/
GET  /api/v1/catalogos/monedas/
GET  /api/v1/empresas/
POST /api/v1/empresas/
GET  /api/v1/empresas/{id}/
PATCH /api/v1/empresas/{id}/
PUT  /api/v1/empresas/{id}/propietario/
GET  /api/v1/productos/
POST /api/v1/productos/
GET  /api/v1/productos/{id}/
PATCH /api/v1/productos/{id}/
DELETE /api/v1/productos/{id}/
GET  /api/v1/marketplace/productos/
GET  /api/v1/marketplace/productos/{id}/
GET  /api/schema/
GET  /api/docs/
```

Los endpoints de tenant requieren el encabezado `X-Tenant-ID`. Este valor nunca concede acceso por
sí mismo: el backend valida la membresía activa y los permisos del usuario.

El Marketplace es público y solo devuelve productos con estado `PUBLICADO` pertenecientes a
empresas activas. Admite los filtros `pais`, `ciudad`, `localidad`, `tipo`, `fecha`, `buscar`,
`precio_min` y `precio_max`. El filtro por fecha consulta los bloques abiertos registrados en
`disponibilidad`.
