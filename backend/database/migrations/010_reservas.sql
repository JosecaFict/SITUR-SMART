-- SITUR-SMART - Reservas del turista
-- Ejecutar despues de 009_favoritos.sql.
--
-- Este archivo es la referencia legible del esquema. La via normal para
-- aplicarlo es la migracion de Django apps/bookings/migrations/0001_initial.py,
-- que lleva el mismo DDL en forma idempotente y es lo unico que corre el
-- deploy de Railway.
--
-- Las tablas de ordenes, reservas, detalle, bloqueos, pagos e historial ya
-- existen desde 001_initial_schema.sql. Aqui solo se agrega lo que les falta:
--
-- * reserva.huespedes: en una habitacion, reserva_detalle.cantidad_personas
--   guarda cuantas habitaciones se toman por noche (es la unidad del cupo y
--   del precio). Los huespedes son otro dato y el voucher los necesita.
-- * Indices para calcular la ocupacion de un cupo sin recorrer la tabla.

BEGIN;

ALTER TABLE reserva
    ADD COLUMN huespedes INTEGER,
    ADD CONSTRAINT chk_reserva_huespedes CHECK (huespedes IS NULL OR huespedes > 0);

CREATE INDEX idx_reserva_detalle_disponibilidad ON reserva_detalle (id_disponibilidad);
CREATE INDEX idx_bloqueo_disponibilidad_activo
    ON bloqueo_inventario (id_disponibilidad) WHERE estado = 'ACTIVO';
CREATE INDEX idx_orden_cliente ON orden_reserva (id_cliente, creado_en DESC);
CREATE INDEX idx_pago_reserva ON pago (id_reserva);

COMMIT;
