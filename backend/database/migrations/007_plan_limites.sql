-- SITUR-SMART - Planes configurables: limites por recurso y condiciones contratadas
-- Ejecutar despues de 006_reconciliar_hoteles_publicados.sql.
--
-- La via normal para aplicarlo es la migracion de Django
-- apps/tenancy/migrations/0004_plan_limites.py. Este archivo es la referencia
-- legible del esquema.
--
-- Tres cambios, todos aditivos. Ningun plan ni suscripcion se pierde.
--
-- 1. plan_limite: los limites pasan de columnas a filas. Agregar un recurso deja
--    de ser una migracion y pasa a ser un INSERT, que es lo que permite que el
--    SUPER_ADMIN los administre sin tocar el esquema.
--
--    NULL  = ilimitado
--    0     = el recurso no esta permitido en ese plan
--    N > 0 = tope
--
--    Esto reemplaza el centinela 999999 que hoy usa el plan EMPRESARIAL, que
--    existia solo porque max_productos es NOT NULL CHECK (> 0) y no admite
--    expresar "sin tope".
--
-- 2. plan gana periodicidad y descripcion.
--
--    La columna de precio NO se renombra ni se duplica: sigue llamandose
--    precio_mensual para no romper SQL externo, consultas guardadas ni procesos
--    que la lean por nombre. La API expone `precio` (nombre nuevo) y
--    `precio_mensual` (alias deprecado) apuntando a esa misma columna, asi que
--    los dos nombres no pueden divergir. En Django el atributo se llama `price`
--    con db_column="precio_mensual", porque "mensual" miente en cuanto un plan
--    sea ANUAL.
--
-- 3. suscripcion guarda las condiciones contratadas. Una suscripcion activa deja
--    de depender del precio comercial del plan, asi que cambiarlo ya no altera
--    lo que una empresa acepto pagar.
--
-- Las columnas max_productos y max_usuarios quedan DEPRECADAS pero presentes.
-- La logica activa sigue usandolas en esta fase; el reemplazo es la Fase 3.

BEGIN;

-- ============================================================
-- 1. LIMITES POR RECURSO
-- ============================================================

CREATE TABLE plan_limite (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_plan     BIGINT NOT NULL REFERENCES plan(id) ON DELETE CASCADE,
    recurso     VARCHAR(40) NOT NULL,
    limite      INTEGER,

    -- Un plan no puede tener dos topes para el mismo recurso.
    CONSTRAINT uq_plan_limite UNIQUE (id_plan, recurso),
    -- NULL se admite a proposito: es "ilimitado". 0 es "no permitido".
    CONSTRAINT chk_plan_limite CHECK (limite IS NULL OR limite >= 0)
);

CREATE INDEX idx_plan_limite_plan ON plan_limite (id_plan);

-- ============================================================
-- 2. PERIODICIDAD Y DESCRIPCION DEL PLAN
-- ============================================================

ALTER TABLE plan
    ADD COLUMN periodicidad VARCHAR(10) NOT NULL DEFAULT 'MENSUAL',
    ADD COLUMN descripcion  TEXT;

-- Los planes que ya existen son todos mensuales; el DEFAULT los cubre.
ALTER TABLE plan
    ADD CONSTRAINT chk_plan_periodicidad CHECK (periodicidad IN ('MENSUAL', 'ANUAL'));

-- ============================================================
-- 3. CONDICIONES CONTRATADAS DE LA SUSCRIPCION
-- ============================================================

ALTER TABLE suscripcion
    ADD COLUMN precio_contratado       NUMERIC(12,2),
    ADD COLUMN id_moneda_contratada    BIGINT REFERENCES moneda(id) ON DELETE RESTRICT,
    ADD COLUMN periodicidad_contratada VARCHAR(10);

ALTER TABLE suscripcion
    ADD CONSTRAINT chk_suscripcion_precio_contratado
        CHECK (precio_contratado IS NULL OR precio_contratado >= 0),
    ADD CONSTRAINT chk_suscripcion_periodicidad_contratada
        CHECK (periodicidad_contratada IS NULL
               OR periodicidad_contratada IN ('MENSUAL', 'ANUAL'));

-- ============================================================
-- 4. SIEMBRA DE LIMITES
-- ============================================================
-- El orden importa y es deliberado: primero los topes explicitos, despues los
-- usuarios, y al final se completa con NULL todo lo que quedo sin fila. Asi la
-- regla de fondo queda dicha una sola vez: lo que no tiene tope, no tiene tope.

-- 4a. Topes finitos de Basico y Pro.
INSERT INTO plan_limite (id_plan, recurso, limite)
SELECT p.id, v.recurso, v.limite
  FROM plan p
  JOIN (VALUES
      ('BASICO',      'HOTELES_PUBLICADOS',      1),
      ('BASICO',      'HABITACIONES_OFERTADAS', 10),
      ('BASICO',      'TOURS_PUBLICADOS',        4),
      ('BASICO',      'RESTAURANTES_PUBLICADOS', 2),
      ('PROFESIONAL', 'HOTELES_PUBLICADOS',      2),
      ('PROFESIONAL', 'HABITACIONES_OFERTADAS', 20),
      ('PROFESIONAL', 'TOURS_PUBLICADOS',        8),
      ('PROFESIONAL', 'RESTAURANTES_PUBLICADOS', 4)
  ) AS v(codigo, recurso, limite) ON v.codigo = p.codigo
ON CONFLICT (id_plan, recurso) DO NOTHING;

-- 4b. USUARIOS_ACTIVOS desde max_usuarios.
--
-- El 999999 de EMPRESARIAL es el centinela de "ilimitado" que esta migracion
-- viene a eliminar, asi que se traduce a NULL en lugar de copiarse. Sin esto,
-- el plan Max quedaria con un tope numerico y la regla de "todos los recursos
-- en NULL" se incumpliria por arrastre de un dato viejo.
INSERT INTO plan_limite (id_plan, recurso, limite)
SELECT p.id,
       'USUARIOS_ACTIVOS',
       CASE WHEN p.max_usuarios >= 999999 THEN NULL ELSE p.max_usuarios END
  FROM plan p
ON CONFLICT (id_plan, recurso) DO NOTHING;

-- 4c. Todo lo que falte queda ilimitado: los tres recursos que Basico y Pro
--     todavia no acotan, y los ocho de Max.
INSERT INTO plan_limite (id_plan, recurso, limite)
SELECT p.id, r.recurso, NULL
  FROM plan p
 CROSS JOIN (VALUES
      ('HOTELES_PUBLICADOS'),
      ('HABITACIONES_OFERTADAS'),
      ('TOURS_PUBLICADOS'),
      ('RESTAURANTES_PUBLICADOS'),
      ('EXPERIENCIAS_PUBLICADAS'),
      ('ATRACCIONES_PUBLICADAS'),
      ('PAQUETES_PUBLICADOS'),
      ('USUARIOS_ACTIVOS')
  ) AS r(recurso)
ON CONFLICT (id_plan, recurso) DO NOTHING;

-- ============================================================
-- 5. NOMBRES VISIBLES
-- ============================================================
-- Solo el nombre. Los codigos no se tocan porque hay suscripciones apuntando a
-- ellos y cambiarlos las romperia.

UPDATE plan SET nombre = 'Básico' WHERE codigo = 'BASICO'      AND nombre <> 'Básico';
UPDATE plan SET nombre = 'Pro'    WHERE codigo = 'PROFESIONAL' AND nombre <> 'Pro';
UPDATE plan SET nombre = 'Max'    WHERE codigo = 'EMPRESARIAL' AND nombre <> 'Max';

-- ============================================================
-- 6. BACKFILL DE CONDICIONES CONTRATADAS
-- ============================================================
-- Se hace AHORA, en la misma migracion que crea las columnas y antes de que
-- exista forma de editar precios. Hoy copiar el precio del plan es exacto,
-- porque ningun plan cambio de precio desde que se sembro: no hay endpoint que
-- lo permita. En cuanto la Fase 4 lo habilite, este relleno pasaria a ser una
-- suposicion. La ventana para hacerlo bien es esta.

UPDATE suscripcion s
   SET precio_contratado       = p.precio_mensual,
       id_moneda_contratada    = p.id_moneda,
       periodicidad_contratada = p.periodicidad
  FROM plan p
 WHERE p.id = s.id_plan
   AND s.precio_contratado IS NULL;

COMMIT;
