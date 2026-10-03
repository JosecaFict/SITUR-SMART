-- SITUR-SMART - Modulo de Hospedaje (establecimientos y habitaciones)
-- Ejecutar despues de 003_seed_guia_permisos.sql, sobre una base que todavia
-- no tenga estas tablas.
--
-- NO es idempotente: los CREATE TABLE de este archivo no llevan IF NOT EXISTS,
-- igual que en 001_initial_schema.sql. Una segunda ejecucion falla.
-- La via normal para aplicarlo es la migracion de Django
-- apps/catalog/migrations/0004_hospedaje.py, que si usa IF NOT EXISTS y por eso
-- puede encontrar las tablas ya creadas sin fallar. Este archivo es la
-- referencia legible del esquema y sirve para reconstruir la base desde cero.
--
-- Agrega las tablas especializadas del sector Hospedaje sin tocar
-- producto_turistico: los datos comunes (nombre, descripcion, ciudad,
-- localidad, moneda, precio, capacidad, estado, imagen) siguen viviendo en el
-- producto y aqui solo se guarda lo propio del establecimiento y del tipo de
-- habitacion. Ningun producto existente se modifica ni se elimina.
--
-- El aislamiento multitenant no queda a cargo del backend: ambas tablas
-- llevan id_tenant y lo encadenan por clave foranea compuesta contra
-- producto_turistico(id, id_tenant) y establecimiento_hospedaje(id, id_tenant).
-- Como las dos FK de habitacion comparten la misma columna id_tenant, apuntar
-- al establecimiento de otra empresa es imposible a nivel de base de datos.
--
-- Lo que si valida el backend (no se puede expresar como CHECK sin un trigger
-- que consulte otra tabla): que el producto del establecimiento sea de tipo
-- HOTEL y que el producto de la habitacion sea de tipo HABITACION.

BEGIN;

-- ============================================================
-- CATALOGO DE TIPOS DE HOSPEDAJE
-- ============================================================
-- Los cinco tipos quedan sembrados desde el inicio para no rediseniar la base
-- al incorporarlos. En esta fase la interfaz solo ofrece HOTEL.

CREATE TABLE tipo_hospedaje (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo          VARCHAR(50) NOT NULL,
    nombre          VARCHAR(120) NOT NULL,

    CONSTRAINT uq_tipo_hospedaje_codigo UNIQUE (codigo),
    CONSTRAINT uq_tipo_hospedaje_nombre UNIQUE (nombre),
    CONSTRAINT chk_tipo_hospedaje_codigo CHECK (codigo = UPPER(codigo))
);

INSERT INTO tipo_hospedaje (codigo, nombre)
VALUES
    ('HOTEL',                 'Hotel'),
    ('HOSTAL',                'Hostal'),
    ('CABANA',                'Cabaña'),
    ('APARTAMENTO_TURISTICO', 'Apartamento turístico'),
    ('HOSPEDAJE_RURAL',       'Hospedaje rural')
ON CONFLICT (codigo) DO NOTHING;

-- ============================================================
-- ESTABLECIMIENTO DE HOSPEDAJE
-- ============================================================
-- Extiende 1 a 1 un producto_turistico de tipo HOTEL. La ubicacion principal
-- (ciudad y localidad) pertenece al producto; aqui se guarda la direccion
-- exacta, que el producto no modela.

CREATE TABLE establecimiento_hospedaje (
    id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_producto             BIGINT NOT NULL,
    id_tenant               BIGINT NOT NULL,
    id_tipo_hospedaje       BIGINT NOT NULL REFERENCES tipo_hospedaje(id) ON DELETE RESTRICT,
    direccion               VARCHAR(250),
    categoria_estrellas     SMALLINT,
    hora_check_in           TIME,
    hora_check_out          TIME,
    servicios               JSONB NOT NULL DEFAULT '[]'::JSONB,
    creado_en               TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_establecimiento_producto_tenant
        FOREIGN KEY (id_producto, id_tenant)
        REFERENCES producto_turistico(id, id_tenant) ON DELETE RESTRICT,
    -- Un producto no puede tener dos establecimientos.
    CONSTRAINT uq_establecimiento_producto UNIQUE (id_producto),
    -- Habilita la FK compuesta de habitacion y con ella la regla de tenant.
    CONSTRAINT uq_establecimiento_id_tenant UNIQUE (id, id_tenant),
    CONSTRAINT chk_establecimiento_estrellas
        CHECK (categoria_estrellas IS NULL OR categoria_estrellas BETWEEN 1 AND 5),
    CONSTRAINT chk_establecimiento_servicios
        CHECK (jsonb_typeof(servicios) = 'array')
);

CREATE INDEX idx_establecimiento_tenant ON establecimiento_hospedaje (id_tenant);
CREATE INDEX idx_establecimiento_tipo ON establecimiento_hospedaje (id_tipo_hospedaje);

CREATE TRIGGER trg_establecimiento_actualizado
BEFORE UPDATE ON establecimiento_hospedaje
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha();

-- ============================================================
-- HABITACION (TIPO DE HABITACION)
-- ============================================================
-- Extiende 1 a 1 un producto_turistico de tipo HABITACION y lo cuelga de un
-- establecimiento. No modela habitaciones fisicas numeradas: cantidad_habitaciones
-- indica cuantas unidades de este tipo existen, mientras capacidad_adultos y
-- capacidad_ninos indican cuantas personas entran en una. El precio por noche y
-- la capacidad total declarada son producto_turistico.precio_base y
-- producto_turistico.capacidad_maxima.

CREATE TABLE habitacion (
    id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_producto             BIGINT NOT NULL,
    id_establecimiento      BIGINT NOT NULL,
    id_tenant               BIGINT NOT NULL,
    cantidad_habitaciones   INTEGER NOT NULL DEFAULT 1,
    capacidad_adultos       SMALLINT NOT NULL DEFAULT 2,
    capacidad_ninos         SMALLINT NOT NULL DEFAULT 0,
    tipo_cama               VARCHAR(60),
    incluye_desayuno        BOOLEAN NOT NULL DEFAULT FALSE,
    creado_en               TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_habitacion_producto_tenant
        FOREIGN KEY (id_producto, id_tenant)
        REFERENCES producto_turistico(id, id_tenant) ON DELETE RESTRICT,
    -- Comparte id_tenant con la FK anterior: el establecimiento y la habitacion
    -- quedan obligados a pertenecer a la misma empresa.
    CONSTRAINT fk_habitacion_establecimiento_tenant
        FOREIGN KEY (id_establecimiento, id_tenant)
        REFERENCES establecimiento_hospedaje(id, id_tenant) ON DELETE RESTRICT,
    CONSTRAINT uq_habitacion_producto UNIQUE (id_producto),
    CONSTRAINT chk_habitacion_cantidad CHECK (cantidad_habitaciones > 0),
    CONSTRAINT chk_habitacion_adultos CHECK (capacidad_adultos > 0),
    CONSTRAINT chk_habitacion_ninos CHECK (capacidad_ninos >= 0)
);

-- Soporta el listado de habitaciones de un hotel y el calculo del precio
-- "desde" del establecimiento en el Marketplace.
CREATE INDEX idx_habitacion_establecimiento ON habitacion (id_establecimiento);
CREATE INDEX idx_habitacion_tenant ON habitacion (id_tenant);

CREATE TRIGGER trg_habitacion_actualizado
BEFORE UPDATE ON habitacion
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha();

COMMIT;
