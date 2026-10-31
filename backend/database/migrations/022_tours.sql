-- SITUR-SMART - Tours y experiencias (CU20): ficha, paradas, guias y salidas
-- Ejecutar despues de 021_datos_facturacion_reserva.sql.
--
-- Este archivo es la referencia legible del esquema. La via normal para
-- aplicarlo es la migracion de Django apps/catalog/migrations/0011_tours.py,
-- que lleva el mismo DDL en forma idempotente y es lo unico que corre el
-- deploy de Railway.
--
-- Igual que hospedaje, no toca producto_turistico: los datos comunes (nombre,
-- ciudad, precio por persona, capacidad, estado, imagen) siguen en el producto
-- y aqui solo va lo propio del tour. Las salidas NO son una tabla nueva: son
-- filas de disponibilidad con su hora real, la misma tabla que ya usan las
-- reservas y la cancelacion de salidas de CU43. Solo se le agrega el guia.
--
-- Aislamiento multitenant en la base, como en hospedaje: cada tabla lleva
-- id_tenant y lo encadena por FK compuesta, asi que una parada no puede colgar
-- del tour de otra empresa ni una salida llevar el guia de otra empresa.

BEGIN;

-- ============================================================
-- FICHA DEL TOUR
-- ============================================================
-- Extiende 1 a 1 un producto_turistico de tipo TOUR o EXPERIENCIA. Tenerla
-- pone al producto en "modo salidas": se reserva por salida y no por dia.

CREATE TABLE IF NOT EXISTS detalle_tour (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_producto         BIGINT NOT NULL,
    id_tenant           BIGINT NOT NULL,
    duracion_minutos    INTEGER,
    idioma              VARCHAR(80),
    dificultad          VARCHAR(10),
    edad_minima         SMALLINT,
    punto_encuentro     VARCHAR(250),
    latitud             NUMERIC(9,6),
    longitud            NUMERIC(9,6),
    incluye             JSONB NOT NULL DEFAULT '[]'::JSONB,
    no_incluye          JSONB NOT NULL DEFAULT '[]'::JSONB,
    requisitos          TEXT,
    creado_en           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_detalle_tour_producto_tenant
        FOREIGN KEY (id_producto, id_tenant)
        REFERENCES producto_turistico(id, id_tenant) ON DELETE RESTRICT,
    CONSTRAINT uq_detalle_tour_producto UNIQUE (id_producto),
    CONSTRAINT chk_detalle_tour_duracion CHECK (duracion_minutos IS NULL OR duracion_minutos > 0),
    CONSTRAINT chk_detalle_tour_dificultad CHECK (dificultad IS NULL OR dificultad IN ('BAJA', 'MEDIA', 'ALTA')),
    CONSTRAINT chk_detalle_tour_edad CHECK (edad_minima IS NULL OR edad_minima BETWEEN 0 AND 120),
    CONSTRAINT chk_detalle_tour_latitud CHECK (latitud IS NULL OR latitud BETWEEN -90 AND 90),
    CONSTRAINT chk_detalle_tour_longitud CHECK (longitud IS NULL OR longitud BETWEEN -180 AND 180),
    CONSTRAINT chk_detalle_tour_coordenadas CHECK ((latitud IS NULL) = (longitud IS NULL)),
    CONSTRAINT chk_detalle_tour_incluye CHECK (jsonb_typeof(incluye) = 'array'),
    CONSTRAINT chk_detalle_tour_no_incluye CHECK (jsonb_typeof(no_incluye) = 'array')
);

CREATE INDEX IF NOT EXISTS idx_detalle_tour_tenant ON detalle_tour (id_tenant);

DROP TRIGGER IF EXISTS trg_detalle_tour_actualizado ON detalle_tour;
CREATE TRIGGER trg_detalle_tour_actualizado
BEFORE UPDATE ON detalle_tour
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha();

-- ============================================================
-- PARADAS DEL RECORRIDO
-- ============================================================

CREATE TABLE IF NOT EXISTS parada_tour (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_producto         BIGINT NOT NULL,
    id_tenant           BIGINT NOT NULL,
    orden               SMALLINT NOT NULL,
    nombre              VARCHAR(150) NOT NULL,
    descripcion         TEXT,
    duracion_minutos    INTEGER,

    CONSTRAINT fk_parada_tour_producto_tenant
        FOREIGN KEY (id_producto, id_tenant)
        REFERENCES producto_turistico(id, id_tenant) ON DELETE RESTRICT,
    CONSTRAINT uq_parada_tour_orden UNIQUE (id_producto, orden),
    CONSTRAINT chk_parada_tour_orden CHECK (orden > 0),
    CONSTRAINT chk_parada_tour_duracion CHECK (duracion_minutos IS NULL OR duracion_minutos > 0)
);

CREATE INDEX IF NOT EXISTS idx_parada_tour_producto ON parada_tour (id_producto);

-- ============================================================
-- GUIAS
-- ============================================================

CREATE TABLE IF NOT EXISTS guia (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_tenant           BIGINT NOT NULL REFERENCES tenant(id) ON DELETE RESTRICT,
    nombres             VARCHAR(150) NOT NULL,
    telefono            VARCHAR(30),
    idiomas             JSONB NOT NULL DEFAULT '[]'::JSONB,
    estado              VARCHAR(10) NOT NULL DEFAULT 'ACTIVO',
    creado_en           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Habilita la FK compuesta de disponibilidad: el guia de una salida tiene
    -- que ser de la misma empresa que el tour.
    CONSTRAINT uq_guia_id_tenant UNIQUE (id, id_tenant),
    CONSTRAINT chk_guia_estado CHECK (estado IN ('ACTIVO', 'INACTIVO')),
    CONSTRAINT chk_guia_idiomas CHECK (jsonb_typeof(idiomas) = 'array')
);

CREATE INDEX IF NOT EXISTS idx_guia_tenant ON guia (id_tenant);

DROP TRIGGER IF EXISTS trg_guia_actualizado ON guia;
CREATE TRIGGER trg_guia_actualizado
BEFORE UPDATE ON guia
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha();

-- ============================================================
-- SALIDAS: guia en disponibilidad
-- ============================================================
-- Opcional. Con id_guia nulo la FK compuesta no se comprueba (MATCH SIMPLE),
-- asi que las filas de habitaciones y atracciones no cambian.

ALTER TABLE disponibilidad ADD COLUMN IF NOT EXISTS id_guia BIGINT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_disponibilidad_guia_tenant'
    ) THEN
        ALTER TABLE disponibilidad ADD CONSTRAINT fk_disponibilidad_guia_tenant
            FOREIGN KEY (id_guia, id_tenant) REFERENCES guia(id, id_tenant) ON DELETE RESTRICT;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_disponibilidad_guia ON disponibilidad (id_guia) WHERE id_guia IS NOT NULL;

COMMIT;
