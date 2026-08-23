-- SITUR-SMART - Catalogos y seguridad inicial
-- Ejecutar despues de 001_initial_schema.sql.

BEGIN;

INSERT INTO moneda (codigo_iso, nombre, simbolo, decimales)
VALUES
    ('BOB', 'Boliviano', 'Bs', 2),
    ('USD', 'Dolar estadounidense', '$', 2)
ON CONFLICT (codigo_iso) DO NOTHING;

INSERT INTO pais (codigo_iso, nombre)
VALUES ('BOL', 'Bolivia')
ON CONFLICT (codigo_iso) DO NOTHING;

INSERT INTO tipo_producto (codigo, nombre)
VALUES
    ('HOTEL', 'Hotel'),
    ('HABITACION', 'Habitacion'),
    ('TOUR', 'Tour'),
    ('EXPERIENCIA', 'Experiencia'),
    ('ATRACCION', 'Atraccion')
ON CONFLICT (codigo) DO NOTHING;

INSERT INTO rol (codigo, nombre, ambito, es_sistema)
VALUES
    ('SUPER_ADMIN', 'Superadministrador de plataforma', 'GLOBAL', TRUE),
    ('CLIENTE', 'Cliente o turista', 'GLOBAL', TRUE),
    ('TENANT_ADMIN', 'Administrador de empresa', 'TENANT', TRUE),
    ('TENANT_EMPLOYEE', 'Empleado de empresa', 'TENANT', TRUE),
    ('GUIA', 'Guia turistico', 'TENANT', TRUE)
ON CONFLICT DO NOTHING;

INSERT INTO permiso (codigo, modulo, nombre)
VALUES
    ('TENANTS_LEER', 'SaaS', 'Consultar empresas'),
    ('TENANTS_GESTIONAR', 'SaaS', 'Crear y modificar empresas'),
    ('SUSCRIPCIONES_GESTIONAR', 'SaaS', 'Gestionar planes y suscripciones'),
    ('USUARIOS_LEER', 'Usuarios', 'Consultar usuarios'),
    ('USUARIOS_GESTIONAR', 'Usuarios', 'Crear y modificar usuarios'),
    ('ROLES_GESTIONAR', 'Usuarios', 'Gestionar roles y permisos'),
    ('PRODUCTOS_LEER', 'Catalogo', 'Consultar productos'),
    ('PRODUCTOS_GESTIONAR', 'Catalogo', 'Crear y modificar productos'),
    ('DISPONIBILIDAD_GESTIONAR', 'Inventario', 'Gestionar disponibilidad'),
    ('RESERVAS_LEER', 'Reservas', 'Consultar reservas'),
    ('RESERVAS_GESTIONAR', 'Reservas', 'Gestionar reservas'),
    ('REPORTES_TENANT', 'Reportes', 'Consultar reportes de la empresa'),
    ('REPORTES_GLOBALES', 'Reportes', 'Consultar reportes globales'),
    ('BITACORA_LEER', 'Auditoria', 'Consultar bitacora')
ON CONFLICT (codigo) DO NOTHING;

-- SuperAdmin recibe todos los permisos globales y de consulta.
INSERT INTO rol_permiso (id_rol, id_permiso)
SELECT r.id, p.id
  FROM rol r
 CROSS JOIN permiso p
 WHERE r.codigo = 'SUPER_ADMIN' AND r.ambito = 'GLOBAL'
ON CONFLICT DO NOTHING;

-- Administrador de empresa. El backend siempre debe filtrar por tenant.
INSERT INTO rol_permiso (id_rol, id_permiso)
SELECT r.id, p.id
  FROM rol r
  JOIN permiso p ON p.codigo IN (
      'USUARIOS_LEER', 'USUARIOS_GESTIONAR', 'ROLES_GESTIONAR',
      'PRODUCTOS_LEER', 'PRODUCTOS_GESTIONAR', 'DISPONIBILIDAD_GESTIONAR',
      'RESERVAS_LEER', 'RESERVAS_GESTIONAR', 'REPORTES_TENANT', 'BITACORA_LEER'
  )
 WHERE r.codigo = 'TENANT_ADMIN' AND r.ambito = 'TENANT'
ON CONFLICT DO NOTHING;

INSERT INTO rol_permiso (id_rol, id_permiso)
SELECT r.id, p.id
  FROM rol r
  JOIN permiso p ON p.codigo IN ('PRODUCTOS_LEER', 'RESERVAS_LEER', 'RESERVAS_GESTIONAR')
 WHERE r.codigo = 'TENANT_EMPLOYEE' AND r.ambito = 'TENANT'
ON CONFLICT DO NOTHING;

COMMIT;
