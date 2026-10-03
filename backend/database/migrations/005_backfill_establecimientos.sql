-- SITUR-SMART - Ficha de hospedaje para los hoteles heredados
-- Ejecutar despues de 004_hospedaje.sql.
--
-- Los productos de tipo HOTEL creados antes del modulo de hospedaje no tienen
-- fila en establecimiento_hospedaje: no admiten habitaciones y la consulta
-- publica de hospedaje no los encuentra. Se les crea una ficha minima (tipo
-- HOTEL, sin direccion ni estrellas) para que la empresa la complete desde el
-- panel.
--
-- No se modifica producto_turistico. Un hotel heredado conserva su precio_base
-- aunque el Marketplace ya no lo muestre, y aparece sin precio "desde" hasta
-- que tenga su primera habitacion publicada.
--
-- Las habitaciones heredadas no se pueden reparar aqui: no hay dato que indique
-- a que hotel pertenecen. Siguen existiendo como productos y quedan fuera de
-- /marketplace/habitaciones/ hasta registrarlas bajo su establecimiento.
--
-- Es idempotente: volver a ejecutarlo no duplica fichas.

BEGIN;

INSERT INTO establecimiento_hospedaje (id_producto, id_tenant, id_tipo_hospedaje, servicios)
SELECT p.id,
       p.id_tenant,
       (SELECT id FROM tipo_hospedaje WHERE codigo = 'HOTEL'),
       '[]'::JSONB
  FROM producto_turistico p
  JOIN tipo_producto tp ON tp.id = p.id_tipo_producto
 WHERE tp.codigo = 'HOTEL'
   AND NOT EXISTS (
       SELECT 1 FROM establecimiento_hospedaje e WHERE e.id_producto = p.id
   );

COMMIT;
