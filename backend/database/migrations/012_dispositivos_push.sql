-- SITUR-SMART - Celulares que reciben notificaciones push (Firebase)
-- Ejecutar despues de 011_notificaciones.sql.
--
-- Este archivo es la referencia legible del esquema. La via normal para
-- aplicarlo es la migracion de Django
-- apps/notifications/migrations/0002_dispositivo_push.py, que lleva el mismo DDL
-- en forma idempotente y es lo unico que corre el deploy de Railway.
--
-- Una fila por instalacion de la app con sesion iniciada. El token lo entrega
-- Firebase al celular y es unico: si en el mismo celular entra otra cuenta, la
-- fila pasa a la cuenta nueva y la anterior deja de recibir avisos ahi.

BEGIN;

CREATE TABLE IF NOT EXISTS dispositivo_push (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario      BIGINT NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    token           VARCHAR(512) NOT NULL,
    plataforma      VARCHAR(20) NOT NULL DEFAULT 'ANDROID',
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_dispositivo_push_token UNIQUE (token),
    CONSTRAINT chk_dispositivo_push_plataforma CHECK (plataforma IN ('ANDROID', 'IOS'))
);

-- notify() busca los celulares de un usuario en cada aviso.
CREATE INDEX IF NOT EXISTS idx_dispositivo_push_usuario ON dispositivo_push (id_usuario);

COMMIT;
