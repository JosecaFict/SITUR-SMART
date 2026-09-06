-- SITUR-SMART - Permisos del rol GUIA
-- Ejecutar despues de 002_seed_catalogs.sql.
--
-- El rol GUIA quedo sin permisos en el seed original. Un guia solo necesita
-- consultar los productos que dicta y ver las reservas/participantes de sus
-- propios tours; no gestiona productos, reservas ni usuarios.

BEGIN;

INSERT INTO rol_permiso (id_rol, id_permiso)
SELECT r.id, p.id
  FROM rol r
  JOIN permiso p ON p.codigo IN ('PRODUCTOS_LEER', 'RESERVAS_LEER')
 WHERE r.codigo = 'GUIA' AND r.ambito = 'TENANT' AND r.id_tenant IS NULL
ON CONFLICT DO NOTHING;

COMMIT;
