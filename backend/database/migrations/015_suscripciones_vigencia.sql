-- SITUR-SMART - Vigencia, avisos y pago de las suscripciones
-- Ejecutar despues de 014_respaldos_automaticos.sql.
--
-- Este archivo es la referencia legible del esquema. La via normal para
-- aplicarlo es la migracion de Django
-- apps/tenancy/migrations/0006_suscripciones_vigencia.py, que lleva el mismo
-- DDL en forma idempotente y es lo unico que corre el deploy de Railway.
--
-- Hasta aqui las suscripciones se creaban sin fecha_fin y nunca vencian. Desde
-- ahora cada periodo dura un mes o un ano segun la periodicidad contratada, y
-- el cron (tareas_programadas) avisa antes de vencer, renueva las que tienen
-- renovacion automatica y vence las demas: la empresa queda restringida hasta
-- pagar la renovacion con Stripe.

BEGIN;

-- 1. Ultimo aviso enviado (7 o 1 dias antes), para no repetirlo en cada vuelta
--    del cron. Se limpia al empezar un periodo nuevo.
ALTER TABLE suscripcion ADD COLUMN IF NOT EXISTS ultimo_aviso_dias SMALLINT;

-- 2. Las activas sin fecha_fin reciben el proximo corte de su periodo que caiga
--    despues de hoy: ninguna vence de golpe con este cambio.
UPDATE suscripcion
   SET fecha_fin = (
       fecha_inicio + make_interval(months => paso * (
           floor((date_part('year', age(current_date, fecha_inicio)) * 12
                  + date_part('month', age(current_date, fecha_inicio))) / paso)::int + 1
       ))
   )::date
  FROM (SELECT id AS id_s,
               CASE WHEN COALESCE(periodicidad_contratada, 'MENSUAL') = 'ANUAL' THEN 12 ELSE 1 END AS paso
          FROM suscripcion) p
 WHERE p.id_s = suscripcion.id
   AND estado = 'ACTIVA'
   AND fecha_fin IS NULL;

-- 3. Pagos de una renovacion o cambio de plan. pago es solo de reservas
--    (id_reserva NOT NULL), por eso las suscripciones tienen su propia tabla.
CREATE TABLE IF NOT EXISTS pago_suscripcion (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_tenant           BIGINT NOT NULL REFERENCES tenant(id) ON DELETE RESTRICT,
    id_plan             BIGINT NOT NULL REFERENCES plan(id) ON DELETE RESTRICT,
    id_suscripcion      BIGINT REFERENCES suscripcion(id) ON DELETE SET NULL,
    id_usuario_pagador  BIGINT REFERENCES usuario(id) ON DELETE SET NULL,
    id_moneda           BIGINT NOT NULL REFERENCES moneda(id) ON DELETE RESTRICT,
    monto               NUMERIC(12,2) NOT NULL,
    estado              VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE',
    proveedor           VARCHAR(60) NOT NULL DEFAULT 'STRIPE',
    referencia          VARCHAR(150),
    creado_en           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    procesado_en        TIMESTAMPTZ,

    CONSTRAINT uq_pago_suscripcion_referencia UNIQUE (proveedor, referencia),
    CONSTRAINT chk_pago_suscripcion_monto CHECK (monto > 0),
    CONSTRAINT chk_pago_suscripcion_estado CHECK (estado IN ('PENDIENTE', 'APROBADO', 'ANULADO'))
);

CREATE INDEX IF NOT EXISTS idx_pago_suscripcion_tenant ON pago_suscripcion (id_tenant, creado_en DESC);

COMMIT;
