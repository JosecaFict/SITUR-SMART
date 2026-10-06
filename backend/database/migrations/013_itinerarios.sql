-- SITUR-SMART - Itinerarios del turista
-- Ejecutar despues de 012_dispositivos_push.sql.
--
-- Este archivo es la referencia legible del esquema. La via normal para
-- aplicarlo es la migracion de Django
-- apps/itineraries/migrations/0001_initial.py, que lleva el mismo DDL en forma
-- idempotente y es lo unico que corre el deploy de Railway.
--
-- Un itinerario es el plan de un viaje: nombre, ciudad opcional y rango de
-- fechas. Cada actividad cae en un dia del rango y es un producto del
-- Marketplace o algo libre ("Comprar recuerdos"). Las reservas confirmadas NO
-- se copian aqui: la API las mezcla al leer, asi una cancelacion o un cambio
-- se ve solo y no hay dos verdades.

BEGIN;

CREATE TABLE IF NOT EXISTS itinerario (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario      BIGINT NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    nombre          VARCHAR(120) NOT NULL,
    id_ciudad       BIGINT REFERENCES ciudad(id) ON DELETE SET NULL,
    fecha_inicio    DATE NOT NULL,
    fecha_fin       DATE NOT NULL,
    notas           TEXT,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_itinerario_nombre CHECK (length(btrim(nombre)) > 0),
    CONSTRAINT chk_itinerario_fechas CHECK (fecha_fin >= fecha_inicio),
    -- Un viaje, no un calendario: 60 dias alcanzan y acotan lo que se dibuja.
    CONSTRAINT chk_itinerario_duracion CHECK (fecha_fin - fecha_inicio < 60)
);

CREATE INDEX IF NOT EXISTS idx_itinerario_usuario_inicio
    ON itinerario (id_usuario, fecha_inicio DESC);

CREATE TABLE IF NOT EXISTS itinerario_actividad (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_itinerario   BIGINT NOT NULL REFERENCES itinerario(id) ON DELETE CASCADE,
    fecha           DATE NOT NULL,
    hora            TIME,
    -- Si el producto se borra, la actividad queda con su titulo.
    id_producto     BIGINT REFERENCES producto_turistico(id) ON DELETE SET NULL,
    titulo          VARCHAR(150) NOT NULL,
    nota            TEXT,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_itinerario_actividad_titulo CHECK (length(btrim(titulo)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_itinerario_actividad_dia
    ON itinerario_actividad (id_itinerario, fecha, hora);

COMMIT;
