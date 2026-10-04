"""Pruebas del modelo configurable de planes (Fase 2).

Los modelos usan ``managed = False`` y la suite corre sobre SQLite, asi que las
tablas no existen aqui. Se verifica el contrato: el significado de los tres
estados de ``limite``, lo que siembra el SQL de la migracion, y que los
serializers conserven el alias deprecado.

Las restricciones de PostgreSQL -- UNIQUE(plan, recurso) y
CHECK(limite IS NULL OR limite >= 0) -- se comprueban leyendo el DDL, igual que
se hizo con la reconciliacion de hoteles: ejecutarlas necesita la base real.
"""

import re
from decimal import Decimal
from importlib import import_module
from typing import ClassVar
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.tenancy.models import Plan, PlanLimit, Subscription
from apps.tenancy.serializers import (
    PlanLimitSerializer,
    PlanSerializer,
    SubscriptionSerializer,
)
from apps.tenancy.services import _open_subscription

# El nombre del modulo empieza con digito y no admite un import normal.
migration = import_module("apps.tenancy.migrations.0004_plan_limites")


def squeeze(sql: str) -> str:
    """Normaliza SQL para poder buscar frases, descartando los comentarios.

    Quitarlos importa: los comentarios de la migracion nombran planes y
    columnas al explicar las decisiones, y una asercion que los incluyera
    pasaria o fallaria por la prosa en vez de por el SQL.
    """
    sin_comentarios = re.sub(r"--[^\n]*", " ", sql)
    return re.sub(r"\s+", " ", sin_comentarios).strip().upper()


DDL = squeeze(
    migration.CREATE_PLAN_LIMIT
    + migration.ADD_PLAN_COLUMNS
    + migration.ADD_SUBSCRIPTION_COLUMNS
)
SEED = squeeze(migration.SEED_LIMITS)


class LimitSemanticsTests(SimpleTestCase):
    """limite tiene tres estados y ninguno es intercambiable.

    NULL = ilimitado, 0 = no permitido, N = tope. Confundir NULL con 0 daria un
    plan que no permite nada, que es el error exactamente opuesto.
    """

    def test_null_means_unlimited(self):
        self.assertTrue(PlanLimit(limit=None).is_unlimited)

    def test_zero_is_not_unlimited(self):
        """0 es "no permitido": un plan que no habilita el recurso."""
        limite = PlanLimit(limit=0)

        self.assertFalse(limite.is_unlimited)
        self.assertEqual(limite.limit, 0)

    def test_a_finite_limit_is_not_unlimited(self):
        self.assertFalse(PlanLimit(limit=10).is_unlimited)

    def test_the_column_admits_null_and_rejects_negatives(self):
        self.assertIn("CHECK (LIMITE IS NULL OR LIMITE >= 0)", DDL)

    def test_the_model_field_is_nullable(self):
        campo = PlanLimit._meta.get_field("limit")

        self.assertTrue(campo.null)
        # Un IntegerField, no Positive*: 0 es valido y el rango lo cuida el CHECK.
        self.assertEqual(campo.get_internal_type(), "IntegerField")


class UniquenessTests(SimpleTestCase):
    def test_one_limit_per_plan_and_resource(self):
        self.assertIn("CONSTRAINT UQ_PLAN_LIMITE UNIQUE (ID_PLAN, RECURSO)", DDL)
        self.assertEqual(
            PlanLimit._meta.unique_together, (("plan", "resource"),)
        )

    def test_the_seed_cannot_duplicate_on_a_rerun(self):
        """Las tres siembras usan ON CONFLICT: repetir la migracion no duplica."""
        self.assertEqual(SEED.count("ON CONFLICT (ID_PLAN, RECURSO) DO NOTHING"), 3)

    def test_deleting_a_plan_takes_its_limits(self):
        self.assertIn("REFERENCES PLAN(ID) ON DELETE CASCADE", DDL)


class SeededResourcesTests(SimpleTestCase):
    """Los ocho recursos quedan sembrados en los tres planes.

    Importa que esten TODOS, incluso los que arrancan en NULL: el SUPER_ADMIN
    tiene que poder acotarlos despues sin una migracion, y para eso la fila
    tiene que existir.
    """

    RECURSOS: ClassVar[list[str]] = [
        "HOTELES_PUBLICADOS",
        "HABITACIONES_OFERTADAS",
        "TOURS_PUBLICADOS",
        "RESTAURANTES_PUBLICADOS",
        "EXPERIENCIAS_PUBLICADAS",
        "ATRACCIONES_PUBLICADAS",
        "PAQUETES_PUBLICADOS",
        "USUARIOS_ACTIVOS",
    ]

    def test_the_model_declares_the_eight_resources(self):
        self.assertEqual(
            sorted(choice.value for choice in PlanLimit.Resource), sorted(self.RECURSOS)
        )

    def test_the_fill_step_covers_the_eight_for_every_plan(self):
        """El CROSS JOIN final deja una fila por plan y recurso."""
        relleno = SEED[SEED.index("CROSS JOIN"):]
        for recurso in self.RECURSOS:
            with self.subTest(recurso=recurso):
                self.assertIn(f"('{recurso}')", relleno)
        self.assertIn("CROSS JOIN (VALUES", relleno)

    def test_basico_finite_limits(self):
        for recurso, limite in (
            ("HOTELES_PUBLICADOS", 1),
            ("HABITACIONES_OFERTADAS", 10),
            ("TOURS_PUBLICADOS", 4),
            ("RESTAURANTES_PUBLICADOS", 2),
        ):
            with self.subTest(recurso=recurso):
                self.assertRegex(SEED, rf"\('BASICO', *'{recurso}', *{limite}\)")

    def test_pro_finite_limits(self):
        for recurso, limite in (
            ("HOTELES_PUBLICADOS", 2),
            ("HABITACIONES_OFERTADAS", 20),
            ("TOURS_PUBLICADOS", 8),
            ("RESTAURANTES_PUBLICADOS", 4),
        ):
            with self.subTest(recurso=recurso):
                self.assertRegex(SEED, rf"\('PROFESIONAL', *'{recurso}', *{limite}\)")

    def test_max_gets_no_finite_limit(self):
        """A EMPRESARIAL no se le siembra ningun tope: cae todo al relleno NULL."""
        explicitos = SEED[: SEED.index("USUARIOS_ACTIVOS")]

        self.assertNotIn("EMPRESARIAL", explicitos)

    def test_experiences_attractions_packages_start_unlimited(self):
        """Basico y Pro no los acotan todavia: solo los cubre el relleno NULL."""
        explicitos = SEED[: SEED.index("USUARIOS_ACTIVOS")]

        for recurso in ("EXPERIENCIAS_PUBLICADAS", "ATRACCIONES_PUBLICADAS", "PAQUETES_PUBLICADOS"):
            with self.subTest(recurso=recurso):
                self.assertNotIn(recurso, explicitos)


class ActiveUsersBackfillTests(SimpleTestCase):
    def test_takes_the_value_from_max_usuarios(self):
        self.assertIn("ELSE P.MAX_USUARIOS END", SEED)

    def test_the_999999_sentinel_becomes_null(self):
        """Es el centinela de "ilimitado" que esta fase viene a eliminar.

        Copiarlo tal cual dejaria al plan Max con un tope numerico de usuarios,
        incumpliendo "todos los recursos en NULL" por arrastre de un dato viejo.
        """
        self.assertIn("CASE WHEN P.MAX_USUARIOS >= 999999 THEN NULL", SEED)


class ContractedConditionsTests(SimpleTestCase):
    """Una suscripcion activa conserva lo que acepto pagar."""

    BACKFILL = squeeze(migration.BACKFILL_CONTRACTED)

    def test_backfill_copies_the_three_conditions(self):
        for columna in ("PRECIO_CONTRATADO", "ID_MONEDA_CONTRATADA", "PERIODICIDAD_CONTRATADA"):
            with self.subTest(columna=columna):
                self.assertIn(columna, self.BACKFILL)

    def test_backfill_reads_them_from_the_plan(self):
        self.assertIn("= P.PRECIO_MENSUAL", self.BACKFILL)
        self.assertIn("= P.ID_MONEDA", self.BACKFILL)
        self.assertIn("= P.PERIODICIDAD", self.BACKFILL)

    def test_backfill_only_touches_rows_without_conditions(self):
        """Idempotente, y no sobreescribe una condicion ya registrada."""
        self.assertIn("AND S.PRECIO_CONTRATADO IS NULL", self.BACKFILL)

    def test_changing_the_plan_price_does_not_touch_the_subscription(self):
        """La garantia es estructural: son columnas de tablas distintas.

        Nada en la migracion ni en el modelo deriva precio_contratado de
        plan.precio despues del backfill, asi que un UPDATE sobre el plan no
        puede alcanzar a una suscripcion.
        """
        columna = Plan._meta.get_field("price").column
        self.assertEqual(columna, "precio_mensual")

        contratado = migration.__dict__
        # Ninguna sentencia de la migracion reescribe precio_contratado fuera
        # del backfill inicial.
        escrituras = [
            clave
            for clave, valor in contratado.items()
            if isinstance(valor, str) and "PRECIO_CONTRATADO" in squeeze(valor) and "SET" in squeeze(valor)
        ]
        self.assertEqual(escrituras, ["BACKFILL_CONTRACTED"])

    def test_the_subscription_model_holds_the_three_conditions(self):
        """Nullable durante la transicion: el backfill las completa."""
        esperado = {
            "contracted_price": "precio_contratado",
            "contracted_currency": "id_moneda_contratada",
            "contracted_periodicity": "periodicidad_contratada",
        }
        for atributo, columna in esperado.items():
            with self.subTest(campo=atributo):
                campo = Subscription._meta.get_field(atributo)

                self.assertEqual(campo.column, columna)
                self.assertTrue(campo.null)


class NewSubscriptionFreezesConditionsTests(SimpleTestCase):
    """Toda suscripcion nueva congela las condiciones del plan al contratar.

    El backfill de la migracion solo cubre las filas anteriores. Sin esto, toda
    contratacion, cambio de plan y renovacion posterior al deploy nacia con las
    tres condiciones en NULL.
    """

    databases: ClassVar[set[str]] = {"default"}

    @staticmethod
    def _plan(codigo="BASICO", precio="149.00", moneda_id=1, periodicidad="MENSUAL"):
        plan = MagicMock()
        plan.code = codigo
        plan.price = Decimal(precio)
        plan.currency_id = moneda_id
        plan.periodicity = periodicidad
        return plan

    @patch("apps.tenancy.services.Subscription.objects.create")
    @patch("apps.tenancy.services.Subscription.objects.filter")
    def test_a_new_subscription_freezes_the_three_conditions(self, _filter, create):
        plan = self._plan()

        _open_subscription(tenant=MagicMock(), plan=plan)

        valores = create.call_args.kwargs
        self.assertEqual(valores["contracted_price"], Decimal("149.00"))
        self.assertEqual(valores["contracted_currency_id"], 1)
        self.assertEqual(valores["contracted_periodicity"], "MENSUAL")

    @patch("apps.tenancy.services.Subscription.objects.create")
    @patch("apps.tenancy.services.Subscription.objects.filter")
    def test_the_conditions_travel_in_the_same_insert(self, _filter, create):
        """No en un UPDATE posterior: la fila nunca existe sin sus condiciones."""
        _open_subscription(tenant=MagicMock(), plan=self._plan())

        create.assert_called_once()
        self.assertIn("contracted_price", create.call_args.kwargs)

    @patch("apps.tenancy.services.Subscription.objects.create")
    @patch("apps.tenancy.services.Subscription.objects.filter")
    def test_changing_plan_opens_a_subscription_with_the_new_plan_conditions(
        self, _filter, create
    ):
        """Un cambio de plan no reusa la fila: abre una nueva con el precio nuevo."""
        nuevo = self._plan(codigo="PROFESIONAL", precio="349.00", periodicidad="ANUAL")

        _open_subscription(tenant=MagicMock(), plan=nuevo)

        valores = create.call_args.kwargs
        self.assertEqual(valores["plan"], nuevo)
        self.assertEqual(valores["contracted_price"], Decimal("349.00"))
        self.assertEqual(valores["contracted_periodicity"], "ANUAL")

    @patch("apps.tenancy.services.Subscription.objects.create")
    @patch("apps.tenancy.services.Subscription.objects.filter")
    def test_the_previous_subscription_is_cancelled_not_edited(self, filtro, create):
        """La anterior conserva lo que pago: se cancela, no se reescribe."""
        _open_subscription(tenant=MagicMock(), plan=self._plan())

        actualizado = filtro.return_value.update.call_args.kwargs
        self.assertEqual(actualizado["status"], "CANCELADA")
        # No se le toca el precio contratado a la que se cierra.
        self.assertNotIn("contracted_price", actualizado)

    @patch("apps.tenancy.services.Subscription.objects.create")
    @patch("apps.tenancy.services.Subscription.objects.filter")
    def test_a_later_plan_price_change_cannot_reach_an_existing_subscription(
        self, _filter, create
    ):
        """Contratar a 149 y que el plan pase a 199 no cambia lo contratado.

        La garantia es estructural: el servicio copia el precio una vez, al
        crear, y nada vuelve a derivarlo. Se simula subiendo el precio del plan
        despues de la contratacion.
        """
        plan = self._plan(precio="149.00")
        _open_subscription(tenant=MagicMock(), plan=plan)
        congelado = create.call_args.kwargs["contracted_price"]

        # El SUPER_ADMIN sube el precio comercial mas tarde.
        plan.price = Decimal("199.00")

        self.assertEqual(congelado, Decimal("149.00"))
        self.assertNotEqual(congelado, plan.price)
        # Y crear no se volvio a llamar: nada reescribio la fila.
        create.assert_called_once()


class PriceAndPeriodicityTests(SimpleTestCase):
    def test_the_physical_column_is_never_renamed(self):
        """La fase es aditiva: renombrar romperia SQL externo y procesos viejos."""
        todo = squeeze(
            migration.CREATE_PLAN_LIMIT
            + migration.ADD_PLAN_COLUMNS
            + migration.ADD_SUBSCRIPTION_COLUMNS
            + migration.SEED_LIMITS
            + migration.RENAME_VISIBLE_NAMES
            + migration.BACKFILL_CONTRACTED
        )

        self.assertNotIn("RENAME COLUMN", todo)
        self.assertNotIn("RENAME CONSTRAINT", todo)

    def test_price_and_its_alias_cannot_diverge(self):
        """Los dos nombres de la API salen de la misma columna fisica."""
        campos = PlanSerializer().fields
        columna = Plan._meta.get_field("price").column

        self.assertEqual(columna, "precio_mensual")
        self.assertEqual(campos["precio"].source, "price")
        self.assertEqual(campos["precio_mensual"].source, "price")

    def test_no_second_price_column_is_added(self):
        self.assertNotIn("ADD COLUMN IF NOT EXISTS PRECIO ", DDL)

    def test_the_backfill_reads_the_physical_column(self):
        self.assertIn("= P.PRECIO_MENSUAL", squeeze(migration.BACKFILL_CONTRACTED))

    def test_periodicity_defaults_to_monthly(self):
        self.assertIn("PERIODICIDAD VARCHAR(10) NOT NULL DEFAULT 'MENSUAL'", DDL)

    def test_periodicity_is_constrained(self):
        self.assertIn("CHECK (PERIODICIDAD IN ('MENSUAL', 'ANUAL'))", DDL)

    def test_the_model_offers_both_periodicities(self):
        self.assertEqual(
            [choice.value for choice in Plan.Periodicity], ["MENSUAL", "ANUAL"]
        )

    def test_description_is_nullable(self):
        self.assertTrue(Plan._meta.get_field("description").null)


class VisibleNamesTests(SimpleTestCase):
    RENAMES = squeeze(migration.RENAME_VISIBLE_NAMES)

    def test_only_the_visible_name_changes(self):
        self.assertEqual(self.RENAMES.count("SET NOMBRE"), 3)
        self.assertNotIn("SET CODIGO", self.RENAMES)

    def test_codes_are_preserved_because_subscriptions_point_at_them(self):
        for codigo, nombre in (("BASICO", "BÁSICO"), ("PROFESIONAL", "PRO"), ("EMPRESARIAL", "MAX")):
            with self.subTest(codigo=codigo):
                self.assertIn(f"WHERE CODIGO = '{codigo}'", self.RENAMES)
                self.assertIn(f"SET NOMBRE = '{nombre}'", self.RENAMES)

    def test_renames_are_idempotent(self):
        """Repetirlas no cambia nada: ya traen la comparacion de desigualdad."""
        self.assertEqual(self.RENAMES.count("AND NOMBRE <>"), 3)


class SerializerContractTests(SimpleTestCase):
    def test_price_is_exposed_under_the_new_name(self):
        campos = PlanSerializer().fields

        self.assertEqual(campos["precio"].source, "price")
        self.assertEqual(campos["periodicidad"].source, "periodicity")

    def test_the_deprecated_alias_survives_and_reads_the_same_column(self):
        """Quitarlo ahora romperia la pantalla /planes y los clientes moviles."""
        campos = PlanSerializer().fields

        self.assertIn("precio_mensual", campos)
        self.assertEqual(campos["precio_mensual"].source, "price")
        self.assertTrue(campos["precio_mensual"].read_only)

    def test_limits_travel_with_the_plan(self):
        campos = PlanSerializer().fields

        self.assertIn("limites", campos)
        self.assertEqual(campos["limites"].source, "limits")

    def test_a_null_limit_serializes_as_null_not_zero(self):
        representado = PlanLimitSerializer().to_representation(
            PlanLimit(id=1, resource="HOTELES_PUBLICADOS", limit=None)
        )

        self.assertIsNone(representado["limite"])

    def test_a_zero_limit_serializes_as_zero(self):
        representado = PlanLimitSerializer().to_representation(
            PlanLimit(id=1, resource="HOTELES_PUBLICADOS", limit=0)
        )

        self.assertEqual(representado["limite"], 0)

    def test_the_subscription_exposes_its_contracted_conditions(self):
        campos = SubscriptionSerializer().fields

        self.assertEqual(campos["precio_contratado"].source, "contracted_price")
        self.assertEqual(campos["periodicidad_contratada"].source, "contracted_periodicity")

    def test_the_contracted_conditions_are_read_only(self):
        """Son un registro historico: ningun endpoint debe poder reescribirlas."""
        campos = SubscriptionSerializer().fields

        for nombre in ("precio_contratado", "moneda_contratada", "periodicidad_contratada"):
            with self.subTest(campo=nombre):
                self.assertTrue(
                    campos[nombre].read_only,
                    f"{nombre} deberia ser de solo lectura",
                )

    def test_sending_the_contracted_conditions_as_input_changes_nothing(self):
        """Un intento de reescribirlas no llega al modelo.

        Se envian las tres y nada mas: validated_data queda vacio, asi que no
        hay nada que pudiera aplicarse a la suscripcion.
        """
        serializer = SubscriptionSerializer(
            data={
                "precio_contratado": "1.00",
                "moneda_contratada": "USD",
                "periodicidad_contratada": "ANUAL",
            },
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data, {})

    def test_an_attacker_cannot_lower_the_contracted_price_alongside_valid_fields(self):
        """Tampoco colandolas junto a campos que si se aceptan."""
        serializer = SubscriptionSerializer(
            data={
                "renovacion_automatica": True,
                "precio_contratado": "1.00",
                "periodicidad_contratada": "ANUAL",
            },
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(set(serializer.validated_data), {"auto_renew"})

    def test_the_deprecated_plan_quotas_are_still_exposed(self):
        """La logica activa las sigue usando; se retiran en la Fase 3."""
        campos = PlanSerializer().fields

        self.assertIn("max_usuarios", campos)
        self.assertIn("max_productos", campos)


class MigrationShapeTests(SimpleTestCase):
    def test_it_depends_on_the_plan_seed_and_the_currency(self):
        self.assertIn(("tenancy", "0003_plan_suscripcion"), migration.Migration.dependencies)
        self.assertIn(("catalog", "0001_catalog_api"), migration.Migration.dependencies)

    def test_it_does_nothing_outside_postgresql(self):
        class FakeEditor:
            def __init__(self):
                self.connection = type("conn", (), {"vendor": "sqlite"})()
                self.used = False

            def cursor(self):  # pragma: no cover
                self.used = True
                raise AssertionError("no debe abrir cursor fuera de postgresql")

        editor = FakeEditor()
        migration.apply_plan_limits(None, editor)

        self.assertFalse(editor.used)

    def test_the_create_is_idempotent(self):
        self.assertIn("CREATE TABLE IF NOT EXISTS PLAN_LIMITE", DDL)

    def test_the_column_additions_are_idempotent(self):
        self.assertGreaterEqual(DDL.count("ADD COLUMN IF NOT EXISTS"), 5)

    def test_the_constraints_check_before_being_added(self):
        self.assertIn("FROM PG_CONSTRAINT WHERE CONNAME = 'CHK_PLAN_PERIODICIDAD'", DDL)
        self.assertIn(
            "FROM PG_CONSTRAINT WHERE CONNAME = 'CHK_SUSCRIPCION_PRECIO_CONTRATADO'", DDL
        )

    def test_it_never_drops_the_deprecated_quota_columns(self):
        """max_productos y max_usuarios quedan para la Fase 3."""
        todo = squeeze(
            migration.CREATE_PLAN_LIMIT
            + migration.ADD_PLAN_COLUMNS
            + migration.ADD_SUBSCRIPTION_COLUMNS
            + migration.SEED_LIMITS
        )

        self.assertNotIn("DROP COLUMN MAX_PRODUCTOS", todo)
        self.assertNotIn("DROP COLUMN MAX_USUARIOS", todo)
