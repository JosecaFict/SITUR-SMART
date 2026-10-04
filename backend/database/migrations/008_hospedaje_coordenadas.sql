-- SITUR-SMART - Ubicacion exacta del establecimiento de hospedaje
-- Ejecutar despues de 007_plan_limites.sql.
--
-- Este archivo es la referencia legible del esquema. La via normal para
-- aplicarlo es la migracion de Django
-- apps/catalog/migrations/0007_hospedaje_coordenadas.py, que lleva el mismo
-- DDL en forma idempotente y es lo unico que corre el deploy de Railway.
--
-- Agrega latitud y longitud opcionales al establecimiento. No se toca
-- habitacion: una habitacion no tiene ubicacion propia, usa la de su hotel,
-- igual que ya hereda ciudad y localidad.
--
-- No se usa PostGIS ni se crea indice geografico: no hay ninguna consulta que
-- filtre u ordene por distancia. Dos NUMERIC bastan y evitan una extension.

BEGIN;

-- Misma forma que ciudad.latitud/longitud, definidas en 001_initial_schema.sql:
-- NUMERIC(9,6) son 3 digitos enteros y 6 decimales, que resuelven ~11 cm y le
-- alcanzan justo a 180.000000. Los decimales de sobra que manda un GPS se
-- redondean antes de llegar aqui.
ALTER TABLE establecimiento_hospedaje
    ADD COLUMN latitud  NUMERIC(9,6),
    ADD COLUMN longitud NUMERIC(9,6);

ALTER TABLE establecimiento_hospedaje
    ADD CONSTRAINT chk_establecimiento_latitud
        CHECK (latitud IS NULL OR latitud BETWEEN -90 AND 90),
    ADD CONSTRAINT chk_establecimiento_longitud
        CHECK (longitud IS NULL OR longitud BETWEEN -180 AND 180),
    -- Las dos juntas o ninguna. La regla vive en la base y no solo en el
    -- backend porque la base puede expresarla: asi tambien la respetan un
    -- comando de gestion, un shell o cualquier SQL externo.
    ADD CONSTRAINT chk_establecimiento_coordenadas
        CHECK ((latitud IS NULL) = (longitud IS NULL));

COMMIT;
