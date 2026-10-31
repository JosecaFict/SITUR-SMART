-- CU35: opiniones por producto turistico. El despliegue normal aplica la
-- migracion Django catalog/0009_resenas_producto.py, que contiene el mismo DDL.
-- Este script tambien puede ejecutarse antes: CREATE IF NOT EXISTS evita
-- duplicar la tabla o su indice cuando Django registre despues su estado.
BEGIN;

CREATE TABLE IF NOT EXISTS resena_producto (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario      BIGINT NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    id_producto     BIGINT NOT NULL REFERENCES producto_turistico(id) ON DELETE CASCADE,
    calificacion    SMALLINT NOT NULL,
    comentario      TEXT NOT NULL,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_resena_usuario_producto UNIQUE (id_usuario, id_producto),
    CONSTRAINT chk_resena_calificacion CHECK (calificacion BETWEEN 1 AND 5),
    CONSTRAINT chk_resena_comentario CHECK (length(btrim(comentario)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_resena_producto_fecha
    ON resena_producto (id_producto, creado_en DESC, id DESC);

COMMIT;
