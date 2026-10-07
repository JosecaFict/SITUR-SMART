-- SITUR-SMART - Reservas vistas por la empresa: llegada del cliente y reportes
-- Ejecutar despues de 016_permiso_clientes.sql.
--
-- Este archivo es la referencia legible del esquema. La via normal para
-- aplicarlo es la migracion de Django apps/bookings/migrations/0002_llegada_y_reportes.py,
-- que lleva el mismo DDL en forma idempotente y es lo unico que corre Railway.
--
-- * reserva.llegada_en / id_llegada_validada_por: la empresa valida el voucher
--   cuando el cliente llega. Una vez marcada, no se vuelve a usar.
-- * reporte_cliente: la empresa avisa a la plataforma de un problema con un
--   cliente. No lo bloquea: eso lo decide el SuperAdmin desde Clientes.

BEGIN;

ALTER TABLE reserva ADD COLUMN IF NOT EXISTS llegada_en TIMESTAMPTZ;
ALTER TABLE reserva ADD COLUMN IF NOT EXISTS id_llegada_validada_por BIGINT REFERENCES usuario(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS reporte_cliente (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_tenant           BIGINT NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    id_cliente          BIGINT NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    id_reserva          BIGINT REFERENCES reserva(id) ON DELETE SET NULL,
    id_reportado_por    BIGINT REFERENCES usuario(id) ON DELETE SET NULL,
    motivo              TEXT NOT NULL,
    creado_en           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_reporte_cliente_motivo CHECK (length(btrim(motivo)) >= 5)
);

CREATE INDEX IF NOT EXISTS idx_reporte_cliente_cliente ON reporte_cliente (id_cliente, creado_en DESC);

COMMIT;
