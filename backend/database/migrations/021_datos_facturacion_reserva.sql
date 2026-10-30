-- SITUR-SMART - Datos fiscales opcionales congelados en la reserva.
-- La vía normal es la migración Django bookings/0005.
BEGIN;
ALTER TABLE reserva ADD COLUMN IF NOT EXISTS razon_social_facturacion VARCHAR(180);
ALTER TABLE reserva ADD COLUMN IF NOT EXISTS nit_facturacion VARCHAR(40);
COMMIT;
