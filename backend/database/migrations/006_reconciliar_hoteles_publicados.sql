-- SITUR-SMART - Reconciliacion de hoteles heredados publicados sin habitaciones
-- Ejecutar despues de 005_backfill_establecimientos.sql.
--
-- La via normal para aplicarlo es la migracion de Django
-- apps/catalog/migrations/0006_reconciliar_hoteles_publicados.py. Este archivo
-- es la referencia legible.
--
-- Los hoteles anteriores al modulo de Hospedaje conservaron su estado. 005 les
-- creo la ficha, pero ninguno tiene habitaciones: quedaron PUBLICADO sin una
-- sola habitacion publicada con precio, que es lo que la regla del modulo
-- prohibe. Se los pasa a BORRADOR para que la empresa los complete.
--
-- Un hotel creado por la API no puede caer en esta condicion: el servicio no
-- permite publicarlo sin habitacion ofertable. Por eso no hace falta distinguir
-- heredados de nuevos.
--
-- El NOT EXISTS garantiza que un hotel con una habitacion valida nunca se toque.
--
-- Es idempotente: repetirlo no cambia nada, porque los afectados ya quedaron en
-- BORRADOR.

BEGIN;

UPDATE producto_turistico p
   SET estado = 'BORRADOR'
 WHERE p.estado = 'PUBLICADO'
   AND EXISTS (
       SELECT 1 FROM tipo_producto tp
        WHERE tp.id = p.id_tipo_producto AND tp.codigo = 'HOTEL'
   )
   AND EXISTS (
       SELECT 1 FROM establecimiento_hospedaje e WHERE e.id_producto = p.id
   )
   AND NOT EXISTS (
       SELECT 1
         FROM habitacion h
         JOIN establecimiento_hospedaje e ON e.id = h.id_establecimiento
         JOIN producto_turistico hp ON hp.id = h.id_producto
        WHERE e.id_producto = p.id
          AND hp.estado = 'PUBLICADO'
          AND hp.precio_base > 0
   );

COMMIT;
