-- SITUR-SMART - Notificaciones dentro de la app
-- Ejecutar despues de 010_reservas.sql.
--
-- Este archivo es la referencia legible del esquema. La via normal para
-- aplicarlo es la migracion de Django
-- apps/notifications/migrations/0001_initial.py, que lleva el mismo DDL y es lo
-- unico que corre el deploy de Railway.
--
-- Una fila por aviso al usuario (reserva confirmada, vencida, cancelada...).
-- "datos" lleva a donde navegar al tocarla, p. ej. {"reserva_id": 12}. El push
-- de Firebase, cuando llegue, se envia a partir de estas mismas filas.

BEGIN;

CREATE TABLE IF NOT EXISTS notificacion (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario      BIGINT NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    tipo            VARCHAR(40) NOT NULL,
    titulo          VARCHAR(150) NOT NULL,
    mensaje         TEXT NOT NULL,
    datos           JSONB NOT NULL DEFAULT '{}'::JSONB,
    leida_en        TIMESTAMPTZ,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_notificacion_datos CHECK (jsonb_typeof(datos) = 'object')
);

-- La bandeja se lee por usuario, de la mas nueva a la mas vieja.
CREATE INDEX IF NOT EXISTS idx_notificacion_usuario_creado
    ON notificacion (id_usuario, creado_en DESC);
-- El contador de no leidas se consulta seguido y solo mira esas filas.
CREATE INDEX IF NOT EXISTS idx_notificacion_no_leidas
    ON notificacion (id_usuario) WHERE leida_en IS NULL;

COMMIT;
