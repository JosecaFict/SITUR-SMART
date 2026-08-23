-- SITUR-SMART - Esquema inicial PostgreSQL
-- Requiere PostgreSQL 15+.
-- Ejecutar sobre una base vacia. Este archivo no crea la base de datos.

BEGIN;

CREATE EXTENSION IF NOT EXISTS citext;

-- ============================================================
-- FUNCIONES GENERALES
-- ============================================================

CREATE OR REPLACE FUNCTION fn_actualizar_fecha()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.actualizado_en = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

-- ============================================================
-- CATALOGOS GLOBALES
-- ============================================================

CREATE TABLE pais (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo_iso      VARCHAR(3) NOT NULL,
    nombre          VARCHAR(100) NOT NULL,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_pais_codigo_iso UNIQUE (codigo_iso),
    CONSTRAINT uq_pais_nombre UNIQUE (nombre),
    CONSTRAINT chk_pais_codigo_iso CHECK (codigo_iso = UPPER(codigo_iso))
);

CREATE TABLE ciudad (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_pais         BIGINT NOT NULL REFERENCES pais(id) ON DELETE RESTRICT,
    nombre          VARCHAR(120) NOT NULL,
    latitud         NUMERIC(9,6),
    longitud        NUMERIC(9,6),
    zona_horaria    VARCHAR(80),
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_ciudad_pais_nombre UNIQUE (id_pais, nombre),
    CONSTRAINT chk_ciudad_latitud CHECK (latitud IS NULL OR latitud BETWEEN -90 AND 90),
    CONSTRAINT chk_ciudad_longitud CHECK (longitud IS NULL OR longitud BETWEEN -180 AND 180)
);

CREATE TABLE moneda (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo_iso      VARCHAR(3) NOT NULL,
    nombre          VARCHAR(80) NOT NULL,
    simbolo         VARCHAR(10) NOT NULL,
    decimales       SMALLINT NOT NULL DEFAULT 2,

    CONSTRAINT uq_moneda_codigo_iso UNIQUE (codigo_iso),
    CONSTRAINT chk_moneda_codigo_iso CHECK (codigo_iso = UPPER(codigo_iso)),
    CONSTRAINT chk_moneda_decimales CHECK (decimales BETWEEN 0 AND 6)
);

-- ============================================================
-- EMPRESAS, PLANES Y SUSCRIPCIONES
-- ============================================================

CREATE TABLE tenant (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_ciudad           BIGINT REFERENCES ciudad(id) ON DELETE RESTRICT,
    razon_social        VARCHAR(180) NOT NULL,
    nombre_comercial    VARCHAR(180) NOT NULL,
    subdominio          CITEXT NOT NULL,
    nit                 VARCHAR(30),
    email_contacto      CITEXT,
    telefono            VARCHAR(30),
    estado              VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE',
    creado_en           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_tenant_subdominio UNIQUE (subdominio),
    CONSTRAINT uq_tenant_nit UNIQUE (nit),
    CONSTRAINT chk_tenant_subdominio CHECK (subdominio::TEXT ~ '^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$'),
    CONSTRAINT chk_tenant_estado CHECK (estado IN ('PENDIENTE', 'ACTIVO', 'INACTIVO', 'SUSPENDIDO'))
);

CREATE TRIGGER trg_tenant_actualizado_en
BEFORE UPDATE ON tenant
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha();

CREATE TABLE plan (
    id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_moneda               BIGINT NOT NULL REFERENCES moneda(id) ON DELETE RESTRICT,
    codigo                  VARCHAR(50) NOT NULL UNIQUE,
    nombre                  VARCHAR(100) NOT NULL UNIQUE,
    precio_mensual          NUMERIC(12,2) NOT NULL,
    max_usuarios            INTEGER NOT NULL,
    max_productos           INTEGER NOT NULL,
    porcentaje_comision     NUMERIC(5,2) NOT NULL DEFAULT 0,
    activo                  BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT chk_plan_precio CHECK (precio_mensual >= 0),
    CONSTRAINT chk_plan_max_usuarios CHECK (max_usuarios > 0),
    CONSTRAINT chk_plan_max_productos CHECK (max_productos > 0),
    CONSTRAINT chk_plan_comision CHECK (porcentaje_comision BETWEEN 0 AND 100)
);

CREATE TABLE suscripcion (
    id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_tenant               BIGINT NOT NULL REFERENCES tenant(id) ON DELETE RESTRICT,
    id_plan                 BIGINT NOT NULL REFERENCES plan(id) ON DELETE RESTRICT,
    fecha_inicio            DATE NOT NULL,
    fecha_fin               DATE,
    estado                  VARCHAR(20) NOT NULL DEFAULT 'ACTIVA',
    renovacion_automatica   BOOLEAN NOT NULL DEFAULT FALSE,
    creado_en               TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_suscripcion_fechas CHECK (fecha_fin IS NULL OR fecha_fin >= fecha_inicio),
    CONSTRAINT chk_suscripcion_estado CHECK (estado IN ('ACTIVA', 'VENCIDA', 'CANCELADA', 'SUSPENDIDA'))
);

CREATE UNIQUE INDEX uq_suscripcion_activa_tenant
    ON suscripcion (id_tenant) WHERE estado = 'ACTIVA';

-- ============================================================
-- IDENTIDAD, MEMBRESIAS, ROLES Y PERMISOS
-- usuario es global: SuperAdmin y turistas no pertenecen a un tenant.
-- usuario_tenant representa la relacion laboral con una empresa.
-- ============================================================

CREATE TABLE usuario (
    id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email                   CITEXT NOT NULL UNIQUE,
    password_hash           TEXT NOT NULL,
    nombres                 VARCHAR(120) NOT NULL,
    apellidos               VARCHAR(120) NOT NULL,
    telefono                VARCHAR(30),
    estado                  VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE',
    email_verificado_en     TIMESTAMPTZ,
    ultimo_acceso_en        TIMESTAMPTZ,
    creado_en               TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_usuario_estado CHECK (estado IN ('PENDIENTE', 'ACTIVO', 'INACTIVO', 'BLOQUEADO'))
);

CREATE TRIGGER trg_usuario_actualizado_en
BEFORE UPDATE ON usuario
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha();

CREATE TABLE perfil_cliente (
    id_usuario          BIGINT PRIMARY KEY REFERENCES usuario(id) ON DELETE RESTRICT,
    tipo_documento      VARCHAR(30),
    numero_documento    VARCHAR(50),
    fecha_nacimiento    DATE,
    preferencias        JSONB NOT NULL DEFAULT '{}'::JSONB,
    creado_en           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_cliente_documento UNIQUE (tipo_documento, numero_documento)
);

CREATE TABLE usuario_tenant (
    id_usuario      BIGINT NOT NULL REFERENCES usuario(id) ON DELETE RESTRICT,
    id_tenant       BIGINT NOT NULL REFERENCES tenant(id) ON DELETE RESTRICT,
    estado          VARCHAR(20) NOT NULL DEFAULT 'ACTIVO',
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_usuario_tenant PRIMARY KEY (id_usuario, id_tenant),
    CONSTRAINT chk_usuario_tenant_estado CHECK (estado IN ('ACTIVO', 'INACTIVO', 'INVITADO'))
);

CREATE TABLE rol (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_tenant       BIGINT REFERENCES tenant(id) ON DELETE RESTRICT,
    codigo          VARCHAR(60) NOT NULL,
    nombre          VARCHAR(120) NOT NULL,
    ambito          VARCHAR(20) NOT NULL,
    es_sistema      BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT chk_rol_ambito CHECK (ambito IN ('GLOBAL', 'TENANT')),
    CONSTRAINT chk_rol_tenant CHECK (
        (ambito = 'GLOBAL' AND id_tenant IS NULL)
        OR ambito = 'TENANT'
    )
);

CREATE UNIQUE INDEX uq_rol_sin_tenant
    ON rol (codigo, ambito) WHERE id_tenant IS NULL;
CREATE UNIQUE INDEX uq_rol_por_tenant
    ON rol (id_tenant, codigo) WHERE id_tenant IS NOT NULL;

CREATE TABLE permiso (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo          VARCHAR(100) NOT NULL UNIQUE,
    modulo          VARCHAR(80) NOT NULL,
    nombre          VARCHAR(150) NOT NULL
);

CREATE TABLE rol_permiso (
    id_rol          BIGINT NOT NULL REFERENCES rol(id) ON DELETE CASCADE,
    id_permiso      BIGINT NOT NULL REFERENCES permiso(id) ON DELETE CASCADE,
    PRIMARY KEY (id_rol, id_permiso)
);

CREATE TABLE usuario_rol (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario      BIGINT NOT NULL REFERENCES usuario(id) ON DELETE RESTRICT,
    id_rol          BIGINT NOT NULL REFERENCES rol(id) ON DELETE RESTRICT,
    id_tenant       BIGINT REFERENCES tenant(id) ON DELETE RESTRICT,
    asignado_en     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX uq_usuario_rol_global
    ON usuario_rol (id_usuario, id_rol) WHERE id_tenant IS NULL;
CREATE UNIQUE INDEX uq_usuario_rol_tenant
    ON usuario_rol (id_usuario, id_rol, id_tenant) WHERE id_tenant IS NOT NULL;

CREATE OR REPLACE FUNCTION fn_validar_asignacion_rol()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_ambito rol.ambito%TYPE;
    v_tenant_rol rol.id_tenant%TYPE;
BEGIN
    SELECT ambito, id_tenant INTO v_ambito, v_tenant_rol
      FROM rol WHERE id = NEW.id_rol;

    IF v_ambito = 'GLOBAL' AND NEW.id_tenant IS NOT NULL THEN
        RAISE EXCEPTION 'Un rol global no puede asignarse dentro de un tenant';
    END IF;

    IF v_ambito = 'TENANT' THEN
        IF NEW.id_tenant IS NULL THEN
            RAISE EXCEPTION 'Un rol de tenant requiere id_tenant';
        END IF;
        IF v_tenant_rol IS NOT NULL AND v_tenant_rol <> NEW.id_tenant THEN
            RAISE EXCEPTION 'El rol pertenece a otro tenant';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM usuario_tenant
             WHERE id_usuario = NEW.id_usuario AND id_tenant = NEW.id_tenant
        ) THEN
            RAISE EXCEPTION 'El usuario no pertenece al tenant indicado';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validar_asignacion_rol
BEFORE INSERT OR UPDATE ON usuario_rol
FOR EACH ROW EXECUTE FUNCTION fn_validar_asignacion_rol();

-- Las sesiones y tokens se guardan mediante hash, nunca en texto plano.
CREATE TABLE sesion_usuario (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario          BIGINT NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    refresh_token_hash  TEXT NOT NULL UNIQUE,
    user_agent          TEXT,
    ip                  INET,
    expira_en           TIMESTAMPTZ NOT NULL,
    revocada_en         TIMESTAMPTZ,
    creada_en           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_sesion_expiracion CHECK (expira_en > creada_en)
);

CREATE TABLE token_recuperacion (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario          BIGINT NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    token_hash          TEXT NOT NULL UNIQUE,
    expira_en           TIMESTAMPTZ NOT NULL,
    usado_en            TIMESTAMPTZ,
    creado_en           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_token_expiracion CHECK (expira_en > creado_en)
);

-- ============================================================
-- PRODUCTOS GENERICOS (se especializaran en hoteles, habitaciones y tours)
-- ============================================================

CREATE TABLE tipo_producto (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo          VARCHAR(50) NOT NULL UNIQUE,
    nombre          VARCHAR(120) NOT NULL UNIQUE
);

CREATE TABLE politica_cancelacion (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_tenant       BIGINT NOT NULL REFERENCES tenant(id) ON DELETE RESTRICT,
    nombre          VARCHAR(120) NOT NULL,
    reembolsable    BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_politica_tenant_nombre UNIQUE (id_tenant, nombre),
    CONSTRAINT uq_politica_id_tenant UNIQUE (id, id_tenant)
);

CREATE TABLE regla_penalizacion (
    id                          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_politica                 BIGINT NOT NULL REFERENCES politica_cancelacion(id) ON DELETE CASCADE,
    dias_antes_min              INTEGER NOT NULL,
    dias_antes_max              INTEGER,
    porcentaje_penalizacion     NUMERIC(5,2) NOT NULL,

    CONSTRAINT chk_regla_dias_min CHECK (dias_antes_min >= 0),
    CONSTRAINT chk_regla_dias_max CHECK (dias_antes_max IS NULL OR dias_antes_max >= dias_antes_min),
    CONSTRAINT chk_regla_porcentaje CHECK (porcentaje_penalizacion BETWEEN 0 AND 100),
    CONSTRAINT uq_regla_rango UNIQUE (id_politica, dias_antes_min, dias_antes_max)
);

CREATE TABLE producto_turistico (
    id                          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_tenant                   BIGINT NOT NULL REFERENCES tenant(id) ON DELETE RESTRICT,
    id_tipo_producto            BIGINT NOT NULL REFERENCES tipo_producto(id) ON DELETE RESTRICT,
    id_ciudad                   BIGINT NOT NULL REFERENCES ciudad(id) ON DELETE RESTRICT,
    id_moneda                   BIGINT NOT NULL REFERENCES moneda(id) ON DELETE RESTRICT,
    id_politica_cancelacion     BIGINT,
    codigo                      VARCHAR(60) NOT NULL,
    nombre                      VARCHAR(180) NOT NULL,
    descripcion                 TEXT,
    precio_base                 NUMERIC(12,2) NOT NULL,
    capacidad_maxima            INTEGER NOT NULL,
    estado                      VARCHAR(20) NOT NULL DEFAULT 'BORRADOR',
    creado_en                   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en              TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_producto_politica_tenant
        FOREIGN KEY (id_politica_cancelacion, id_tenant)
        REFERENCES politica_cancelacion(id, id_tenant) ON DELETE RESTRICT,
    CONSTRAINT uq_producto_tenant_codigo UNIQUE (id_tenant, codigo),
    CONSTRAINT uq_producto_id_tenant UNIQUE (id, id_tenant),
    CONSTRAINT chk_producto_precio CHECK (precio_base >= 0),
    CONSTRAINT chk_producto_capacidad CHECK (capacidad_maxima > 0),
    CONSTRAINT chk_producto_estado CHECK (estado IN ('BORRADOR', 'PUBLICADO', 'INACTIVO'))
);

CREATE TRIGGER trg_producto_actualizado_en
BEFORE UPDATE ON producto_turistico
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha();

CREATE TABLE disponibilidad (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_producto     BIGINT NOT NULL,
    id_tenant       BIGINT NOT NULL,
    inicio          TIMESTAMPTZ NOT NULL,
    fin             TIMESTAMPTZ NOT NULL,
    cupo_total      INTEGER NOT NULL,
    cerrado         BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT fk_disponibilidad_producto_tenant
        FOREIGN KEY (id_producto, id_tenant)
        REFERENCES producto_turistico(id, id_tenant) ON DELETE RESTRICT,
    CONSTRAINT uq_disponibilidad_producto_inicio UNIQUE (id_producto, inicio),
    CONSTRAINT uq_disponibilidad_id_tenant UNIQUE (id, id_tenant),
    CONSTRAINT chk_disponibilidad_periodo CHECK (fin > inicio),
    CONSTRAINT chk_disponibilidad_cupo CHECK (cupo_total >= 0)
);

-- ============================================================
-- ORDEN GLOBAL Y RESERVAS POR TENANT
-- Una orden puede agrupar reservas pertenecientes a distintas empresas.
-- ============================================================

CREATE TABLE orden_reserva (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_cliente          BIGINT NOT NULL REFERENCES perfil_cliente(id_usuario) ON DELETE RESTRICT,
    codigo              VARCHAR(60) NOT NULL UNIQUE,
    estado              VARCHAR(25) NOT NULL DEFAULT 'CREADA',
    creado_en           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_orden_estado CHECK (estado IN ('CREADA', 'PAGO_PARCIAL', 'CONFIRMADA', 'CANCELADA', 'EXPIRADA', 'COMPLETADA'))
);

CREATE TRIGGER trg_orden_actualizado_en
BEFORE UPDATE ON orden_reserva
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha();

CREATE TABLE reserva (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_orden            BIGINT NOT NULL REFERENCES orden_reserva(id) ON DELETE RESTRICT,
    id_tenant           BIGINT NOT NULL REFERENCES tenant(id) ON DELETE RESTRICT,
    id_moneda           BIGINT NOT NULL REFERENCES moneda(id) ON DELETE RESTRICT,
    codigo_reserva      VARCHAR(60) NOT NULL,
    estado              VARCHAR(25) NOT NULL DEFAULT 'CREADA',
    fecha_expiracion    TIMESTAMPTZ,
    creado_en           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_reserva_tenant_codigo UNIQUE (id_tenant, codigo_reserva),
    CONSTRAINT uq_reserva_id_tenant UNIQUE (id, id_tenant),
    CONSTRAINT chk_reserva_estado CHECK (estado IN ('CREADA', 'PAGO_PARCIAL', 'CONFIRMADA', 'CANCELADA', 'EXPIRADA_LIBERADA', 'COMPLETADA')),
    CONSTRAINT chk_reserva_expiracion CHECK (fecha_expiracion IS NULL OR fecha_expiracion >= creado_en)
);

CREATE TRIGGER trg_reserva_actualizado_en
BEFORE UPDATE ON reserva
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha();

CREATE TABLE reserva_detalle (
    id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_reserva              BIGINT NOT NULL,
    id_tenant               BIGINT NOT NULL,
    id_disponibilidad       BIGINT NOT NULL,
    cantidad_personas       INTEGER NOT NULL,
    precio_unitario         NUMERIC(12,2) NOT NULL,
    subtotal                NUMERIC(14,2) GENERATED ALWAYS AS (cantidad_personas * precio_unitario) STORED,

    CONSTRAINT fk_detalle_reserva_tenant
        FOREIGN KEY (id_reserva, id_tenant)
        REFERENCES reserva(id, id_tenant) ON DELETE RESTRICT,
    CONSTRAINT fk_detalle_disponibilidad_tenant
        FOREIGN KEY (id_disponibilidad, id_tenant)
        REFERENCES disponibilidad(id, id_tenant) ON DELETE RESTRICT,
    CONSTRAINT uq_reserva_detalle_slot UNIQUE (id_reserva, id_disponibilidad),
    CONSTRAINT chk_detalle_cantidad CHECK (cantidad_personas > 0),
    CONSTRAINT chk_detalle_precio CHECK (precio_unitario >= 0)
);

CREATE OR REPLACE FUNCTION fn_validar_moneda_detalle()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_moneda_reserva BIGINT;
    v_moneda_producto BIGINT;
BEGIN
    SELECT id_moneda INTO v_moneda_reserva
      FROM reserva WHERE id = NEW.id_reserva;

    SELECT pt.id_moneda INTO v_moneda_producto
      FROM disponibilidad d
      JOIN producto_turistico pt ON pt.id = d.id_producto
     WHERE d.id = NEW.id_disponibilidad;

    IF v_moneda_reserva <> v_moneda_producto THEN
        RAISE EXCEPTION 'La moneda del producto debe coincidir con la moneda de la reserva';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validar_moneda_detalle
BEFORE INSERT OR UPDATE OF id_reserva, id_disponibilidad ON reserva_detalle
FOR EACH ROW EXECUTE FUNCTION fn_validar_moneda_detalle();

CREATE TABLE bloqueo_inventario (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_disponibilidad   BIGINT NOT NULL,
    id_reserva          BIGINT NOT NULL,
    id_tenant           BIGINT NOT NULL,
    cantidad            INTEGER NOT NULL,
    fecha_expiracion    TIMESTAMPTZ NOT NULL,
    estado              VARCHAR(20) NOT NULL DEFAULT 'ACTIVO',
    creado_en           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_bloqueo_disponibilidad_tenant
        FOREIGN KEY (id_disponibilidad, id_tenant)
        REFERENCES disponibilidad(id, id_tenant) ON DELETE RESTRICT,
    CONSTRAINT fk_bloqueo_reserva_tenant
        FOREIGN KEY (id_reserva, id_tenant)
        REFERENCES reserva(id, id_tenant) ON DELETE RESTRICT,
    CONSTRAINT uq_bloqueo_reserva_disponibilidad UNIQUE (id_reserva, id_disponibilidad),
    CONSTRAINT chk_bloqueo_cantidad CHECK (cantidad > 0),
    CONSTRAINT chk_bloqueo_expiracion CHECK (fecha_expiracion > creado_en),
    CONSTRAINT chk_bloqueo_estado CHECK (estado IN ('ACTIVO', 'LIBERADO', 'CONSUMIDO', 'EXPIRADO'))
);

CREATE TABLE pago (
    id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_reserva              BIGINT NOT NULL REFERENCES reserva(id) ON DELETE RESTRICT,
    id_usuario_pagador      BIGINT REFERENCES usuario(id) ON DELETE RESTRICT,
    id_moneda               BIGINT NOT NULL REFERENCES moneda(id) ON DELETE RESTRICT,
    monto                   NUMERIC(12,2) NOT NULL,
    metodo                  VARCHAR(30) NOT NULL,
    estado                  VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE',
    proveedor               VARCHAR(60) NOT NULL DEFAULT 'SIMULADO',
    referencia              VARCHAR(150),
    idempotency_key         VARCHAR(100) NOT NULL UNIQUE,
    creado_en               TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    procesado_en            TIMESTAMPTZ,

    CONSTRAINT uq_pago_proveedor_referencia UNIQUE (proveedor, referencia),
    CONSTRAINT chk_pago_monto CHECK (monto > 0),
    CONSTRAINT chk_pago_metodo CHECK (metodo IN ('QR', 'TARJETA', 'TRANSFERENCIA', 'EFECTIVO', 'OTRO')),
    CONSTRAINT chk_pago_estado CHECK (estado IN ('PENDIENTE', 'APROBADO', 'RECHAZADO', 'ANULADO'))
);

CREATE OR REPLACE FUNCTION fn_validar_moneda_pago()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_id_moneda BIGINT;
BEGIN
    SELECT id_moneda INTO v_id_moneda
      FROM reserva WHERE id = NEW.id_reserva;

    IF v_id_moneda <> NEW.id_moneda THEN
        RAISE EXCEPTION 'La moneda del pago debe coincidir con la moneda de la reserva';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validar_moneda_pago
BEFORE INSERT OR UPDATE OF id_reserva, id_moneda ON pago
FOR EACH ROW EXECUTE FUNCTION fn_validar_moneda_pago();

CREATE TABLE cancelacion (
    id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_reserva              BIGINT NOT NULL UNIQUE REFERENCES reserva(id) ON DELETE RESTRICT,
    id_regla_penalizacion   BIGINT REFERENCES regla_penalizacion(id) ON DELETE SET NULL,
    motivo                  TEXT,
    dias_anticipacion       INTEGER NOT NULL,
    porcentaje_aplicado     NUMERIC(5,2) NOT NULL DEFAULT 0,
    monto_penalizacion      NUMERIC(12,2) NOT NULL DEFAULT 0,
    monto_reembolso         NUMERIC(12,2) NOT NULL DEFAULT 0,
    creado_en               TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_cancelacion_dias CHECK (dias_anticipacion >= 0),
    CONSTRAINT chk_cancelacion_porcentaje CHECK (porcentaje_aplicado BETWEEN 0 AND 100),
    CONSTRAINT chk_cancelacion_montos CHECK (monto_penalizacion >= 0 AND monto_reembolso >= 0)
);

CREATE OR REPLACE FUNCTION fn_validar_regla_cancelacion_tenant()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_tenant_reserva BIGINT;
    v_tenant_politica BIGINT;
BEGIN
    IF NEW.id_regla_penalizacion IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT id_tenant INTO v_tenant_reserva
      FROM reserva WHERE id = NEW.id_reserva;

    SELECT pc.id_tenant INTO v_tenant_politica
      FROM regla_penalizacion rp
      JOIN politica_cancelacion pc ON pc.id = rp.id_politica
     WHERE rp.id = NEW.id_regla_penalizacion;

    IF v_tenant_reserva <> v_tenant_politica THEN
        RAISE EXCEPTION 'La regla de cancelacion pertenece a otro tenant';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validar_regla_cancelacion_tenant
BEFORE INSERT OR UPDATE OF id_reserva, id_regla_penalizacion ON cancelacion
FOR EACH ROW EXECUTE FUNCTION fn_validar_regla_cancelacion_tenant();

CREATE TABLE historial_estado_reserva (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_reserva          BIGINT NOT NULL REFERENCES reserva(id) ON DELETE RESTRICT,
    id_usuario          BIGINT REFERENCES usuario(id) ON DELETE RESTRICT,
    estado_anterior     VARCHAR(25),
    estado_nuevo        VARCHAR(25) NOT NULL,
    motivo              TEXT,
    creado_en           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_historial_estado_anterior CHECK (
        estado_anterior IS NULL OR estado_anterior IN (
            'CREADA', 'PAGO_PARCIAL', 'CONFIRMADA', 'CANCELADA',
            'EXPIRADA_LIBERADA', 'COMPLETADA'
        )
    ),
    CONSTRAINT chk_historial_estado_nuevo CHECK (
        estado_nuevo IN (
            'CREADA', 'PAGO_PARCIAL', 'CONFIRMADA', 'CANCELADA',
            'EXPIRADA_LIBERADA', 'COMPLETADA'
        )
    ),
    CONSTRAINT chk_historial_cambio CHECK (estado_anterior IS DISTINCT FROM estado_nuevo)
);

-- ============================================================
-- AUDITORIA
-- id_tenant es NULL para acciones globales del SuperAdmin.
-- ============================================================

CREATE TABLE bitacora (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_tenant           BIGINT REFERENCES tenant(id) ON DELETE RESTRICT,
    id_usuario          BIGINT REFERENCES usuario(id) ON DELETE RESTRICT,
    accion              VARCHAR(50) NOT NULL,
    entidad             VARCHAR(100) NOT NULL,
    entidad_id          VARCHAR(100),
    datos_anteriores    JSONB,
    datos_nuevos        JSONB,
    ip                  INET,
    user_agent          TEXT,
    request_id          VARCHAR(100),
    creado_en           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- INVENTARIO: CONSULTA Y BLOQUEO ATOMICO
-- El backend debe usar fn_crear_bloqueo, no insertar bloqueos directamente.
-- ============================================================

CREATE OR REPLACE VIEW vw_disponibilidad_resumen AS
WITH reservados AS (
    SELECT rd.id_disponibilidad, SUM(rd.cantidad_personas)::BIGINT AS cantidad
      FROM reserva_detalle rd
      JOIN reserva r ON r.id = rd.id_reserva
     WHERE r.estado IN ('CONFIRMADA', 'COMPLETADA')
     GROUP BY rd.id_disponibilidad
), bloqueados AS (
    SELECT id_disponibilidad, SUM(cantidad)::BIGINT AS cantidad
      FROM bloqueo_inventario
     WHERE estado = 'ACTIVO' AND fecha_expiracion > CURRENT_TIMESTAMP
     GROUP BY id_disponibilidad
)
SELECT d.id,
       d.id_producto,
       d.id_tenant,
       d.inicio,
       d.fin,
       d.cupo_total,
       COALESCE(r.cantidad, 0) AS cupo_reservado,
       COALESCE(b.cantidad, 0) AS cupo_bloqueado,
       GREATEST(d.cupo_total - COALESCE(r.cantidad, 0) - COALESCE(b.cantidad, 0), 0) AS cupo_disponible,
       d.cerrado
  FROM disponibilidad d
  LEFT JOIN reservados r ON r.id_disponibilidad = d.id
  LEFT JOIN bloqueados b ON b.id_disponibilidad = d.id;

CREATE OR REPLACE FUNCTION fn_crear_bloqueo(
    p_id_reserva BIGINT,
    p_id_disponibilidad BIGINT,
    p_cantidad INTEGER,
    p_fecha_expiracion TIMESTAMPTZ
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_tenant_reserva BIGINT;
    v_tenant_disponibilidad BIGINT;
    v_cupo_total INTEGER;
    v_ocupado BIGINT;
    v_id_bloqueo BIGINT;
BEGIN
    IF p_cantidad <= 0 THEN
        RAISE EXCEPTION 'La cantidad debe ser mayor que cero';
    END IF;
    IF p_fecha_expiracion <= CURRENT_TIMESTAMP THEN
        RAISE EXCEPTION 'La expiracion debe ser futura';
    END IF;

    SELECT id_tenant INTO v_tenant_reserva
      FROM reserva WHERE id = p_id_reserva;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Reserva inexistente';
    END IF;

    SELECT id_tenant, cupo_total
      INTO v_tenant_disponibilidad, v_cupo_total
      FROM disponibilidad
     WHERE id = p_id_disponibilidad AND cerrado = FALSE
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Disponibilidad inexistente o cerrada';
    END IF;
    IF v_tenant_reserva <> v_tenant_disponibilidad THEN
        RAISE EXCEPTION 'La reserva y la disponibilidad pertenecen a tenants distintos';
    END IF;

    UPDATE bloqueo_inventario
       SET estado = 'EXPIRADO'
     WHERE id_disponibilidad = p_id_disponibilidad
       AND estado = 'ACTIVO'
       AND fecha_expiracion <= CURRENT_TIMESTAMP;

    SELECT COALESCE((
        SELECT SUM(rd.cantidad_personas)
          FROM reserva_detalle rd
          JOIN reserva r ON r.id = rd.id_reserva
         WHERE rd.id_disponibilidad = p_id_disponibilidad
           AND r.estado IN ('CONFIRMADA', 'COMPLETADA')
    ), 0) + COALESCE((
        SELECT SUM(bi.cantidad)
          FROM bloqueo_inventario bi
         WHERE bi.id_disponibilidad = p_id_disponibilidad
           AND bi.estado = 'ACTIVO'
           AND bi.fecha_expiracion > CURRENT_TIMESTAMP
    ), 0)
    INTO v_ocupado;

    IF v_ocupado + p_cantidad > v_cupo_total THEN
        RAISE EXCEPTION 'Cupo insuficiente. Disponible: %', GREATEST(v_cupo_total - v_ocupado, 0);
    END IF;

    INSERT INTO bloqueo_inventario (
        id_disponibilidad, id_reserva, id_tenant, cantidad, fecha_expiracion
    ) VALUES (
        p_id_disponibilidad, p_id_reserva, v_tenant_reserva, p_cantidad, p_fecha_expiracion
    )
    RETURNING id INTO v_id_bloqueo;

    RETURN v_id_bloqueo;
END;
$$;

CREATE OR REPLACE VIEW vw_reserva_totales AS
WITH totales AS (
    SELECT id_reserva, SUM(subtotal)::NUMERIC(14,2) AS total
      FROM reserva_detalle GROUP BY id_reserva
), pagados AS (
    SELECT id_reserva, SUM(monto)::NUMERIC(14,2) AS monto_pagado
      FROM pago WHERE estado = 'APROBADO' GROUP BY id_reserva
)
SELECT r.id,
       r.id_orden,
       r.id_tenant,
       r.id_moneda,
       r.codigo_reserva,
       r.estado,
       COALESCE(t.total, 0)::NUMERIC(14,2) AS total,
       COALESCE(p.monto_pagado, 0)::NUMERIC(14,2) AS monto_pagado,
       GREATEST(COALESCE(t.total, 0) - COALESCE(p.monto_pagado, 0), 0)::NUMERIC(14,2) AS saldo_pendiente
  FROM reserva r
  LEFT JOIN totales t ON t.id_reserva = r.id
  LEFT JOIN pagados p ON p.id_reserva = r.id;

-- ============================================================
-- INDICES DE CONSULTA
-- ============================================================

CREATE INDEX idx_usuario_tenant_tenant ON usuario_tenant (id_tenant, estado);
CREATE INDEX idx_usuario_rol_usuario_tenant ON usuario_rol (id_usuario, id_tenant);
CREATE INDEX idx_sesion_usuario_activa ON sesion_usuario (id_usuario, expira_en) WHERE revocada_en IS NULL;
CREATE INDEX idx_producto_tenant_estado ON producto_turistico (id_tenant, estado);
CREATE INDEX idx_producto_ciudad ON producto_turistico (id_ciudad);
CREATE INDEX idx_disponibilidad_busqueda ON disponibilidad (inicio, id_producto) WHERE cerrado = FALSE;
CREATE INDEX idx_orden_cliente_fecha ON orden_reserva (id_cliente, creado_en DESC);
CREATE INDEX idx_reserva_tenant_estado_fecha ON reserva (id_tenant, estado, creado_en DESC);
CREATE INDEX idx_reserva_orden ON reserva (id_orden);
CREATE INDEX idx_detalle_disponibilidad ON reserva_detalle (id_disponibilidad);
CREATE INDEX idx_bloqueo_activo_expiracion ON bloqueo_inventario (id_disponibilidad, fecha_expiracion) WHERE estado = 'ACTIVO';
CREATE INDEX idx_pago_reserva_estado ON pago (id_reserva, estado);
CREATE INDEX idx_historial_reserva_fecha ON historial_estado_reserva (id_reserva, creado_en DESC);
CREATE INDEX idx_bitacora_tenant_fecha ON bitacora (id_tenant, creado_en DESC);
CREATE INDEX idx_bitacora_usuario_fecha ON bitacora (id_usuario, creado_en DESC);

COMMIT;
