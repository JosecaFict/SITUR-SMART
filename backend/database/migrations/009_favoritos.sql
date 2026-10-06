-- SITUR-SMART - Favoritos del turista
-- Ejecutar despues de 008_hospedaje_coordenadas.sql.
--
-- Este archivo es la referencia legible del esquema. La via normal para
-- aplicarlo es la migracion de Django
-- apps/favorites/migrations/0001_initial.py, que lleva el mismo DDL en forma
-- idempotente y es lo unico que corre el deploy de Railway.
--
-- Un favorito apunta al producto, no al establecimiento: un hotel se marca por
-- su producto y asi tours, restaurantes y hoteles comparten una sola tabla.
-- Es global al usuario (no lleva id_tenant): la lista mezcla empresas.

BEGIN;

CREATE TABLE favorito (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario      BIGINT NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    id_producto     BIGINT NOT NULL REFERENCES producto_turistico(id) ON DELETE CASCADE,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_favorito_usuario_producto UNIQUE (id_usuario, id_producto)
);

-- La lista se lee siempre por usuario y del mas reciente al mas viejo.
CREATE INDEX idx_favorito_usuario_creado ON favorito (id_usuario, creado_en DESC);

COMMIT;
