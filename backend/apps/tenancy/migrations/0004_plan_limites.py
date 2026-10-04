import django.db.models.deletion
from django.db import migrations, models

# Mismo DDL que database/migrations/007_plan_limites.sql, en forma idempotente:
# el deploy de Railway solo corre `migrate`, y la migracion tiene que poder
# aplicarse tanto sobre una base donde el script se ejecuto a mano como sobre
# una que nunca lo vio.
#
# ADD CONSTRAINT no admite IF NOT EXISTS, asi que se consulta pg_constraint
# antes de cada uno.
#
# Nada se renombra: la columna fisica precio_mensual se conserva para no romper
# SQL externo, consultas guardadas ni procesos que la lean por nombre. El
# atributo Python se llama `price` y apunta a esa misma columna.

CREATE_PLAN_LIMIT = """
CREATE TABLE IF NOT EXISTS plan_limite (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_plan     BIGINT NOT NULL REFERENCES plan(id) ON DELETE CASCADE,
    recurso     VARCHAR(40) NOT NULL,
    limite      INTEGER,

    CONSTRAINT uq_plan_limite UNIQUE (id_plan, recurso),
    -- NULL se admite a proposito: es "ilimitado". 0 es "no permitido".
    CONSTRAINT chk_plan_limite CHECK (limite IS NULL OR limite >= 0)
);

CREATE INDEX IF NOT EXISTS idx_plan_limite_plan ON plan_limite (id_plan);
"""

ADD_PLAN_COLUMNS = """
ALTER TABLE plan
    ADD COLUMN IF NOT EXISTS periodicidad VARCHAR(10) NOT NULL DEFAULT 'MENSUAL',
    ADD COLUMN IF NOT EXISTS descripcion  TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_plan_periodicidad'
    ) THEN
        ALTER TABLE plan ADD CONSTRAINT chk_plan_periodicidad
            CHECK (periodicidad IN ('MENSUAL', 'ANUAL'));
    END IF;
END $$;
"""

ADD_SUBSCRIPTION_COLUMNS = """
ALTER TABLE suscripcion
    ADD COLUMN IF NOT EXISTS precio_contratado       NUMERIC(12,2),
    ADD COLUMN IF NOT EXISTS id_moneda_contratada    BIGINT REFERENCES moneda(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS periodicidad_contratada VARCHAR(10);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_suscripcion_precio_contratado'
    ) THEN
        ALTER TABLE suscripcion ADD CONSTRAINT chk_suscripcion_precio_contratado
            CHECK (precio_contratado IS NULL OR precio_contratado >= 0);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_suscripcion_periodicidad_contratada'
    ) THEN
        ALTER TABLE suscripcion ADD CONSTRAINT chk_suscripcion_periodicidad_contratada
            CHECK (periodicidad_contratada IS NULL
                   OR periodicidad_contratada IN ('MENSUAL', 'ANUAL'));
    END IF;
END $$;
"""

# El orden es deliberado: primero los topes explicitos, despues los usuarios, y
# al final se completa con NULL lo que quedo sin fila. Asi la regla de fondo se
# dice una sola vez: lo que no tiene tope, no tiene tope.
SEED_LIMITS = """
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

-- El 999999 de EMPRESARIAL es el centinela de "ilimitado" que esta migracion
-- viene a eliminar, asi que se traduce a NULL en vez de copiarse. Sin esto el
-- plan Max quedaria con un tope numerico de usuarios y la regla de "todos los
-- recursos en NULL" se incumpliria por arrastre de un dato viejo.
INSERT INTO plan_limite (id_plan, recurso, limite)
SELECT p.id,
       'USUARIOS_ACTIVOS',
       CASE WHEN p.max_usuarios >= 999999 THEN NULL ELSE p.max_usuarios END
  FROM plan p
ON CONFLICT (id_plan, recurso) DO NOTHING;

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
"""

# Solo el nombre visible. Los codigos tienen suscripciones apuntando a ellos.
RENAME_VISIBLE_NAMES = """
UPDATE plan SET nombre = 'Básico' WHERE codigo = 'BASICO'      AND nombre <> 'Básico';
UPDATE plan SET nombre = 'Pro'    WHERE codigo = 'PROFESIONAL' AND nombre <> 'Pro';
UPDATE plan SET nombre = 'Max'    WHERE codigo = 'EMPRESARIAL' AND nombre <> 'Max';
"""

# Se rellena AHORA, en la misma migracion que crea las columnas y antes de que
# exista forma de editar precios. Hoy copiar el precio del plan es exacto porque
# ningun plan cambio de precio desde que se sembro: no hay endpoint que lo
# permita. Cuando la Fase 4 lo habilite, este relleno pasaria a ser una
# suposicion. La ventana para hacerlo bien es esta.
BACKFILL_CONTRACTED = """
UPDATE suscripcion s
   SET precio_contratado       = p.precio_mensual,
       id_moneda_contratada    = p.id_moneda,
       periodicidad_contratada = p.periodicidad
  FROM plan p
 WHERE p.id = s.id_plan
   AND s.precio_contratado IS NULL;
"""


def apply_plan_limits(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(CREATE_PLAN_LIMIT)
        cursor.execute(ADD_PLAN_COLUMNS)
        cursor.execute(ADD_SUBSCRIPTION_COLUMNS)
        cursor.execute(SEED_LIMITS)
        cursor.execute(RENAME_VISIBLE_NAMES)
        cursor.execute(BACKFILL_CONTRACTED)
        cursor.execute("SELECT COUNT(*) FROM plan_limite")
        limites = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM suscripcion WHERE precio_contratado IS NOT NULL")
        contratadas = cursor.fetchone()[0]
        # Queda en el log del Pre-Deploy para poder contrastarlo.
        print(f"  plan_limite: {limites} filas | suscripciones con condiciones: {contratadas}")


def revert_plan_limits(apps, schema_editor):
    """Deshace el esquema, no los datos.

    Los nombres visibles y el backfill no se revierten: no hay registro de los
    valores anteriores, y el backfill solo escribio sobre columnas que se
    eliminan aqui.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS plan_limite")
        cursor.execute(
            """
            ALTER TABLE suscripcion
                DROP COLUMN IF EXISTS precio_contratado,
                DROP COLUMN IF EXISTS id_moneda_contratada,
                DROP COLUMN IF EXISTS periodicidad_contratada
            """
        )
        cursor.execute(
            """
            ALTER TABLE plan
                DROP COLUMN IF EXISTS periodicidad,
                DROP COLUMN IF EXISTS descripcion
            """
        )


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0003_plan_suscripcion"), ("catalog", "0001_catalog_api")]

    operations = [
        migrations.RunPython(apply_plan_limits, revert_plan_limits),
        # --- Estado de Django ---
        # Solo cambia el nombre del atributo en Python; la columna fisica sigue
        # siendo precio_mensual, asi que no se genera DDL (el modelo es managed=False).
        migrations.RenameField(model_name="plan", old_name="monthly_price", new_name="price"),
        migrations.AlterField(
            model_name="plan",
            name="price",
            field=models.DecimalField(db_column="precio_mensual", decimal_places=2, max_digits=12),
        ),
        migrations.AddField(
            model_name="plan",
            name="periodicity",
            field=models.CharField(
                choices=[("MENSUAL", "Mensual"), ("ANUAL", "Anual")],
                db_column="periodicidad",
                default="MENSUAL",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="plan",
            name="description",
            field=models.TextField(blank=True, db_column="descripcion", null=True),
        ),
        migrations.AlterModelOptions(
            name="plan", options={"ordering": ("price",), "managed": False}
        ),
        migrations.AddField(
            model_name="subscription",
            name="contracted_price",
            field=models.DecimalField(
                blank=True, db_column="precio_contratado", decimal_places=2, max_digits=12, null=True
            ),
        ),
        migrations.AddField(
            model_name="subscription",
            name="contracted_currency",
            field=models.ForeignKey(
                blank=True,
                db_column="id_moneda_contratada",
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="contracted_subscriptions",
                to="catalog.currency",
            ),
        ),
        migrations.AddField(
            model_name="subscription",
            name="contracted_periodicity",
            field=models.CharField(
                blank=True,
                choices=[("MENSUAL", "Mensual"), ("ANUAL", "Anual")],
                db_column="periodicidad_contratada",
                max_length=10,
                null=True,
            ),
        ),
        migrations.CreateModel(
            name="PlanLimit",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "resource",
                    models.CharField(
                        choices=[
                            ("HOTELES_PUBLICADOS", "Hoteles publicados"),
                            ("HABITACIONES_OFERTADAS", "Habitaciones ofertadas"),
                            ("TOURS_PUBLICADOS", "Tours publicados"),
                            ("RESTAURANTES_PUBLICADOS", "Restaurantes publicados"),
                            ("EXPERIENCIAS_PUBLICADAS", "Experiencias publicadas"),
                            ("ATRACCIONES_PUBLICADAS", "Atracciones publicadas"),
                            ("PAQUETES_PUBLICADOS", "Paquetes publicados"),
                            ("USUARIOS_ACTIVOS", "Usuarios activos"),
                        ],
                        db_column="recurso",
                        max_length=40,
                    ),
                ),
                ("limit", models.IntegerField(blank=True, db_column="limite", null=True)),
                (
                    "plan",
                    models.ForeignKey(
                        db_column="id_plan",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="limits",
                        to="tenancy.plan",
                    ),
                ),
            ],
            options={
                "db_table": "plan_limite",
                "ordering": ("resource",),
                "managed": False,
                "unique_together": {("plan", "resource")},
            },
        ),
    ]
