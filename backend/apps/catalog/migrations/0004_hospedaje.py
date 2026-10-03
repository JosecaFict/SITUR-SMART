import django.db.models.deletion
from django.db import migrations, models

# Mismo DDL que database/migrations/004_hospedaje.sql, en forma idempotente:
# la migracion debe poder aplicarse tanto sobre una base donde el script ya se
# ejecuto a mano como sobre Railway, donde el deploy solo corre `migrate`.
CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS tipo_hospedaje (
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

CREATE TABLE IF NOT EXISTS establecimiento_hospedaje (
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
    CONSTRAINT uq_establecimiento_producto UNIQUE (id_producto),
    CONSTRAINT uq_establecimiento_id_tenant UNIQUE (id, id_tenant),
    CONSTRAINT chk_establecimiento_estrellas
        CHECK (categoria_estrellas IS NULL OR categoria_estrellas BETWEEN 1 AND 5),
    CONSTRAINT chk_establecimiento_servicios
        CHECK (jsonb_typeof(servicios) = 'array')
);

CREATE INDEX IF NOT EXISTS idx_establecimiento_tenant
    ON establecimiento_hospedaje (id_tenant);
CREATE INDEX IF NOT EXISTS idx_establecimiento_tipo
    ON establecimiento_hospedaje (id_tipo_hospedaje);

CREATE TABLE IF NOT EXISTS habitacion (
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
    CONSTRAINT fk_habitacion_establecimiento_tenant
        FOREIGN KEY (id_establecimiento, id_tenant)
        REFERENCES establecimiento_hospedaje(id, id_tenant) ON DELETE RESTRICT,
    CONSTRAINT uq_habitacion_producto UNIQUE (id_producto),
    CONSTRAINT chk_habitacion_cantidad CHECK (cantidad_habitaciones > 0),
    CONSTRAINT chk_habitacion_adultos CHECK (capacidad_adultos > 0),
    CONSTRAINT chk_habitacion_ninos CHECK (capacidad_ninos >= 0)
);

CREATE INDEX IF NOT EXISTS idx_habitacion_establecimiento
    ON habitacion (id_establecimiento);
CREATE INDEX IF NOT EXISTS idx_habitacion_tenant
    ON habitacion (id_tenant);
"""

# PostgreSQL no admite CREATE TRIGGER IF NOT EXISTS, asi que se recrean.
CREATE_TRIGGERS = """
DROP TRIGGER IF EXISTS trg_establecimiento_actualizado ON establecimiento_hospedaje;
CREATE TRIGGER trg_establecimiento_actualizado
BEFORE UPDATE ON establecimiento_hospedaje
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha();

DROP TRIGGER IF EXISTS trg_habitacion_actualizado ON habitacion;
CREATE TRIGGER trg_habitacion_actualizado
BEFORE UPDATE ON habitacion
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha();
"""

# No se eliminan los tipos de hospedaje referenciados por algun establecimiento.
DROP_TABLES = """
DROP TABLE IF EXISTS habitacion;
DROP TABLE IF EXISTS establecimiento_hospedaje;
DROP TABLE IF EXISTS tipo_hospedaje;
"""


def create_lodging_tables(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(CREATE_TABLES)
    schema_editor.execute(CREATE_TRIGGERS)


def drop_lodging_tables(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_TABLES)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0003_product_locality_and_availability_state")]

    operations = [
        migrations.RunPython(create_lodging_tables, drop_lodging_tables),
        migrations.CreateModel(
            name="LodgingType",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("code", models.CharField(db_column="codigo", max_length=50, unique=True)),
                ("name", models.CharField(db_column="nombre", max_length=120, unique=True)),
            ],
            options={"db_table": "tipo_hospedaje", "ordering": ("name",), "managed": False},
        ),
        migrations.CreateModel(
            name="LodgingEstablishment",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("address", models.CharField(blank=True, db_column="direccion", max_length=250, null=True)),
                ("star_rating", models.SmallIntegerField(blank=True, db_column="categoria_estrellas", null=True)),
                ("check_in", models.TimeField(blank=True, db_column="hora_check_in", null=True)),
                ("check_out", models.TimeField(blank=True, db_column="hora_check_out", null=True)),
                ("services", models.JSONField(blank=True, db_column="servicios", default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_column="creado_en")),
                ("updated_at", models.DateTimeField(auto_now=True, db_column="actualizado_en")),
                (
                    "lodging_type",
                    models.ForeignKey(
                        db_column="id_tipo_hospedaje",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="establishments",
                        to="catalog.lodgingtype",
                    ),
                ),
                (
                    "product",
                    models.OneToOneField(
                        db_column="id_producto",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="lodging",
                        to="catalog.tourismproduct",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="id_tenant",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="lodgings",
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={"db_table": "establecimiento_hospedaje", "ordering": ("id",), "managed": False},
        ),
        migrations.CreateModel(
            name="Room",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("quantity", models.PositiveIntegerField(db_column="cantidad_habitaciones", default=1)),
                ("adults_capacity", models.PositiveSmallIntegerField(db_column="capacidad_adultos", default=2)),
                ("children_capacity", models.PositiveSmallIntegerField(db_column="capacidad_ninos", default=0)),
                ("bed_type", models.CharField(blank=True, db_column="tipo_cama", max_length=60, null=True)),
                ("includes_breakfast", models.BooleanField(db_column="incluye_desayuno", default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_column="creado_en")),
                ("updated_at", models.DateTimeField(auto_now=True, db_column="actualizado_en")),
                (
                    "establishment",
                    models.ForeignKey(
                        db_column="id_establecimiento",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="rooms",
                        to="catalog.lodgingestablishment",
                    ),
                ),
                (
                    "product",
                    models.OneToOneField(
                        db_column="id_producto",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="room",
                        to="catalog.tourismproduct",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="id_tenant",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="rooms",
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={"db_table": "habitacion", "ordering": ("id",), "managed": False},
        ),
    ]
