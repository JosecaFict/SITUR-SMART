# Base de datos de SITUR-SMART

Esta carpeta contiene las migraciones iniciales de PostgreSQL. La base separa:

- usuarios globales: SuperAdmin y turistas;
- membresias de usuarios en empresas (`usuario_tenant`);
- datos privados de cada empresa mediante `id_tenant`;
- una orden global que puede agrupar reservas de diferentes empresas;
- bloqueos atomicos de inventario para reducir el riesgo de sobreventa.

## Requisitos

- PostgreSQL 15 o posterior.
- pgAdmin 4 para administracion grafica (opcional).
- Una base de datos vacia.

pgAdmin 4 no instala ni ejecuta por si solo el servidor de PostgreSQL. En local debe estar instalado y activo PostgreSQL Server.

## Crear la base local con pgAdmin 4

1. Abrir pgAdmin 4.
2. En `Servers`, registrar o abrir el servidor PostgreSQL local.
3. Pulsar con el boton derecho en `Databases` y elegir `Create > Database`.
4. Usar el nombre `situr_smart`, seleccionar el propietario y guardar.
5. Seleccionar `situr_smart` y abrir `Tools > Query Tool`.
6. Abrir y ejecutar, en este orden:
   1. `migrations/001_initial_schema.sql`
   2. `migrations/002_seed_catalogs.sql`
7. Verificar que ambos scripts terminen sin errores y con `COMMIT`.

No se debe ejecutar varias veces `001_initial_schema.sql` sobre la misma base. Para cambios posteriores se crearan migraciones `003_...`, `004_...`, etc.

## Consultas de verificacion

```sql
SELECT current_database(), current_user, version();

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

SELECT codigo, nombre, ambito
FROM rol
ORDER BY ambito, codigo;

SELECT codigo, modulo, nombre
FROM permiso
ORDER BY modulo, codigo;
```

## Crear el primer SuperAdmin

No se incluye una contrasena en los datos semilla. La contrasena debe ser procesada por el backend con Argon2 o bcrypt. No se debe guardar texto plano ni generar hashes manualmente desde pgAdmin.

Cuando exista el endpoint de inicializacion, el flujo sera:

1. Crear el usuario con correo y hash seguro.
2. Obtener el rol global `SUPER_ADMIN`.
3. Insertar la asignacion en `usuario_rol` con `id_tenant = NULL`.

## Uso desde el backend

La aplicacion debe usar una variable de entorno y nunca guardar credenciales en Git:

```env
DATABASE_URL=postgresql+psycopg://usuario:contrasena@host:5432/situr_smart
```

Para crear retenciones de inventario, el backend debe llamar a la funcion transaccional:

```sql
SELECT fn_crear_bloqueo(
    :id_reserva,
    :id_disponibilidad,
    :cantidad,
    :fecha_expiracion
);
```

No debe insertar directamente en `bloqueo_inventario`.

## Preparacion para Railway

1. Crear un servicio PostgreSQL dentro del proyecto Railway.
2. Copiar la variable `DATABASE_URL` proporcionada por Railway al servicio backend.
3. Conectarse desde pgAdmin usando los valores publicos de host, puerto, usuario, contrasena y base de datos mostrados por Railway.
4. Ejecutar las migraciones en el mismo orden solamente una vez.
5. Mantener SSL habilitado (`sslmode=require`) cuando se utilice la conexion publica.

En Railway normalmente la base ya existe; no se debe intentar ejecutar `CREATE DATABASE`. Solamente se aplican las migraciones dentro de la base proporcionada.

## Siguientes migraciones previstas

- hoteles, tipos de habitacion, habitaciones y servicios;
- tours, guias, horarios y puntos de encuentro;
- tarifas dinamicas, promociones y paquetes;
- reservas grupales, invitaciones y pagos divididos;
- itinerarios, carrito y preferencias de IA;
- QR, check-in, notificaciones, favoritos y resenas;
- politicas RLS de PostgreSQL una vez definido el contexto de conexion del backend.
