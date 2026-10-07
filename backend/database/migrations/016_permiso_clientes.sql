-- SITUR-SMART - Permiso para administrar las cuentas de los turistas
-- Ejecutar despues de 015_suscripciones_vigencia.sql.
--
-- Este archivo es la referencia legible. La via normal para aplicarlo es la
-- migracion de Django apps/rbac/migrations/0002_permiso_clientes.py, que lleva
-- el mismo SQL y es lo unico que corre el deploy de Railway.
--
-- CLIENTES_GESTIONAR es global: lo tiene el SuperAdmin y puede darselo a un rol
-- de soporte de la plataforma. Nunca a un rol de empresa.

BEGIN;

INSERT INTO permiso (codigo, modulo, nombre)
VALUES ('CLIENTES_GESTIONAR', 'Usuarios', 'Administrar cuentas de turistas')
ON CONFLICT (codigo) DO NOTHING;

INSERT INTO rol_permiso (id_rol, id_permiso)
SELECT r.id, p.id
  FROM rol r
  JOIN permiso p ON p.codigo = 'CLIENTES_GESTIONAR'
 WHERE r.codigo = 'SUPER_ADMIN' AND r.ambito = 'GLOBAL'
ON CONFLICT DO NOTHING;

COMMIT;
