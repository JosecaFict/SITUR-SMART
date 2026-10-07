-- SITUR-SMART - Copias de seguridad automaticas
-- Ejecutar despues de 013_itinerarios.sql.
--
-- Este archivo es la referencia legible del esquema. La via normal para
-- aplicarlo es la migracion de Django apps/backups/migrations/0001_initial.py,
-- que lleva el mismo DDL en forma idempotente y es lo unico que corre el
-- deploy de Railway.
--
-- programacion_respaldo tiene una sola fila: cada cuanto se respalda. El cron
-- (tareas_programadas) la consulta y, cuando toca, genera la copia, la guarda
-- privada fuera de Railway (Cloudinary) y avisa por correo al SuperAdmin.
-- copia_seguridad registra cada copia guardada; el archivo no vive en la base.

BEGIN;

CREATE TABLE IF NOT EXISTS programacion_respaldo (
    id                  SMALLINT PRIMARY KEY DEFAULT 1,
    frecuencia          VARCHAR(20) NOT NULL DEFAULT 'SEMANAL',
    ultima_ejecucion    TIMESTAMPTZ,
    actualizado_en      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    id_actualizado_por  BIGINT REFERENCES usuario(id) ON DELETE SET NULL,

    CONSTRAINT chk_programacion_respaldo_unica CHECK (id = 1),
    CONSTRAINT chk_programacion_respaldo_frecuencia
        CHECK (frecuencia IN ('DESACTIVADA', 'CADA_3_DIAS', 'SEMANAL'))
);

INSERT INTO programacion_respaldo (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS copia_seguridad (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    archivo         VARCHAR(120) NOT NULL,
    id_almacen      VARCHAR(255) NOT NULL,
    tamano_bytes    BIGINT NOT NULL,
    sha256          CHAR(64) NOT NULL,
    origen          VARCHAR(20) NOT NULL,
    id_solicitada_por BIGINT REFERENCES usuario(id) ON DELETE SET NULL,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_copia_seguridad_almacen UNIQUE (id_almacen),
    CONSTRAINT chk_copia_seguridad_origen CHECK (origen IN ('PROGRAMADA', 'A_PEDIDO'))
);

CREATE INDEX IF NOT EXISTS idx_copia_seguridad_creado ON copia_seguridad (creado_en DESC);

COMMIT;
