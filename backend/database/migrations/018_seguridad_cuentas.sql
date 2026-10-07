-- SITUR-SMART - Seguridad de las cuentas
-- Ejecutar despues de 017_reservas_empresa.sql.
--
-- Este archivo es la referencia legible. La via normal para aplicarlo es la
-- migracion de Django apps/accounts/migrations/0003_seguridad_cuentas.py, que
-- lleva el mismo SQL y es lo unico que corre el deploy de Railway.
--
-- * intentos_fallidos / bloqueo_temporal_hasta: 5 contrasenas mal seguidas
--   traban la cuenta 15 minutos.
-- * verificacion_correo: codigo de 6 digitos para confirmar el correo; sin
--   correo verificado un turista explora pero no reserva.

BEGIN;

ALTER TABLE usuario ADD COLUMN IF NOT EXISTS intentos_fallidos SMALLINT NOT NULL DEFAULT 0;
ALTER TABLE usuario ADD COLUMN IF NOT EXISTS bloqueo_temporal_hasta TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS verificacion_correo (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario      BIGINT NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    codigo_hash     TEXT NOT NULL,
    intentos        SMALLINT NOT NULL DEFAULT 0,
    expira_en       TIMESTAMPTZ NOT NULL,
    usado_en        TIMESTAMPTZ,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_verificacion_correo_usuario ON verificacion_correo (id_usuario, creado_en DESC);

-- Las cuentas que ya existian no se traban: se dan por verificadas.
UPDATE usuario SET email_verificado_en = COALESCE(email_verificado_en, creado_en)
 WHERE email_verificado_en IS NULL;

COMMIT;
