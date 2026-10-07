-- SITUR-SMART - Publicacion programada de productos y hospedajes
-- Ejecutar despues de 018_seguridad_cuentas.sql.
--
-- Este archivo es la referencia legible. La via normal para aplicarlo es la
-- migracion de Django apps/catalog/migrations/0008_publicacion_programada.py,
-- que lleva el mismo SQL y es lo unico que corre el deploy de Railway.
--
-- La empresa elige "Publicar el ..." y/o "Retirar el ..."; el cron
-- (tareas_programadas, cada 10 minutos) lo hace a su hora, revisando las mismas
-- reglas que una publicacion a mano, y avisa por correo.

BEGIN;

ALTER TABLE producto_turistico ADD COLUMN IF NOT EXISTS publicar_en TIMESTAMPTZ;
ALTER TABLE producto_turistico ADD COLUMN IF NOT EXISTS retirar_en TIMESTAMPTZ;
ALTER TABLE producto_turistico ADD COLUMN IF NOT EXISTS publicado_automaticamente_en TIMESTAMPTZ;

-- El cron busca lo que toca publicar o retirar: solo las filas programadas.
CREATE INDEX IF NOT EXISTS idx_producto_publicar_en ON producto_turistico (publicar_en) WHERE publicar_en IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_producto_retirar_en ON producto_turistico (retirar_en) WHERE retirar_en IS NOT NULL;

COMMIT;
