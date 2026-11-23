"""Dashboard de la empresa y del SuperAdmin.

Las funciones puras se prueban sin base. Para las consultas se crean las tablas
legadas (``managed = False``) en el SQLite de pruebas, igual que en
test_communication_outbox: asi se valida el SQL real (campos, joins y
agrupaciones por mes) sin depender de PostgreSQL.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pytest
from django.db import connection
from django.test import SimpleTestCase
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.reports import dashboard
from apps.reports.dashboard import (
    Period,
    month_series,
    parse_companies,
    percentage,
    shift_month,
    short_name,
    state_breakdown,
    variation,
)
from apps.reports.views import DashboardView

LA_PAZ = ZoneInfo("America/La_Paz")
NOW = datetime(2026, 11, 25, 10, 0, tzinfo=LA_PAZ)


class PureFunctionTests(SimpleTestCase):
    def test_period_covers_current_previous_and_six_months(self):
        period = Period.current(NOW)
        self.assertEqual(period.month_start, datetime(2026, 11, 1, tzinfo=LA_PAZ))
        self.assertEqual(period.previous_start, datetime(2026, 10, 1, tzinfo=LA_PAZ))
        self.assertEqual([m.month for m in period.months()], [6, 7, 8, 9, 10, 11])

    def test_shift_month_crosses_years(self):
        start = datetime(2026, 2, 1, tzinfo=LA_PAZ)
        self.assertEqual(shift_month(start, -3), datetime(2025, 11, 1, tzinfo=LA_PAZ))
        self.assertEqual(shift_month(start, 11), datetime(2027, 1, 1, tzinfo=LA_PAZ))

    def test_parse_companies(self):
        self.assertEqual(parse_companies(None), [])
        self.assertEqual(parse_companies("7, 3,7"), [3, 7])
        for raw in ("a,b", "0", "1,2,3,4,5"):
            with self.assertRaises(ValidationError):
                parse_companies(raw)

    def test_variation_and_percentage_without_base(self):
        self.assertEqual(variation(Decimal("110"), Decimal("100")), 10.0)
        self.assertEqual(variation(5, 0), None)
        self.assertEqual(percentage(1, 3), 33.3)
        self.assertIsNone(percentage(4, 0))

    def test_month_series_fills_missing_months_with_zero(self):
        months = Period.current(NOW).months()
        series = month_series(
            months, {(2026, 11): Decimal("500")}, {(2026, 11): Decimal("80")}, {(2026, 10): 3}
        )
        self.assertEqual(len(series), 6)
        self.assertEqual(series[0], {
            "mes": "2026-06", "etiqueta": "Jun", "cobrado": "0.00", "reembolsado": "0.00",
            "neto": "0.00", "reservas": 0,
        })
        self.assertEqual(series[-1]["neto"], "420.00")
        self.assertEqual(series[-2]["reservas"], 3)

    def test_state_breakdown_keeps_main_states(self):
        rows = state_breakdown({"CONFIRMADA": 3, "COMPLETADA": 1})
        states = [row["estado"] for row in rows]
        self.assertEqual(states, ["CONFIRMADA", "COMPLETADA", "CREADA", "CANCELADA"])
        self.assertEqual(rows[0]["porcentaje"], 75.0)

    def test_short_name_hides_last_name(self):
        self.assertEqual(short_name("María José", "Quispe"), "María Q.")
        self.assertEqual(short_name("", ""), "Cliente")


class ViewTests(SimpleTestCase):
    @patch("apps.reports.views.build_dashboard", return_value={"alcance": "empresa"})
    def test_view_passes_tenant_and_filters(self, build):
        request = APIRequestFactory().get("/api/v1/dashboard/?empresas=2,3", HTTP_X_TENANT_ID="5")
        force_authenticate(request, user=Mock(is_authenticated=True))
        response = DashboardView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(build.call_args.kwargs["tenant_id"], 5)
        self.assertEqual(build.call_args.kwargs["params"]["empresas"], "2,3")

    @patch("apps.reports.dashboard.report_scope", side_effect=PermissionDenied("sin permiso"))
    def test_requires_report_permission(self, _scope):
        with self.assertRaises(PermissionDenied):
            dashboard.build_dashboard(user=Mock(), tenant_id=5, params={})


# ---------------------------------------------------------------- con tablas reales


@pytest.fixture
def tables(django_db_setup, django_db_blocker):
    from apps.accounts.models import CustomerProfile, User
    from apps.bookings.models import (
        Booking,
        BookingDetail,
        Cancellation,
        CustomerReport,
        Order,
    )
    from apps.catalog.models import (
        Availability,
        CancellationPolicy,
        Currency,
        Guide,
        PenaltyRule,
        ProductReview,
        ProductType,
        TourismProduct,
    )
    from apps.payments.models import Payment, Refund
    from apps.promotions.models import BookingPromotionSnapshot, Promotion
    from apps.tenancy.models import City, Country, Plan, Subscription, Tenant

    models = (
        Country, City, User, CustomerProfile, Tenant, Currency, ProductType, CancellationPolicy, PenaltyRule,
        TourismProduct, Guide, Availability, Order, Booking, BookingDetail, Cancellation, Payment, Refund,
        ProductReview, CustomerReport, Plan, Subscription, Promotion, BookingPromotionSnapshot,
    )
    with django_db_blocker.unblock():
        existing = set(connection.introspection.table_names())
        created = [model for model in models if model._meta.db_table not in existing]
        with connection.schema_editor() as editor:
            for model in created:
                editor.create_model(model)
        try:
            yield SimpleNamespace(**{model.__name__: model for model in models})
        finally:
            for model in reversed(models):
                model.objects.all()._raw_delete("default")
            with connection.schema_editor() as editor:
                for model in reversed(created):
                    editor.delete_model(model)


def _at(model, obj, **fields):
    """Fija fechas ``auto_now_add`` que ``create`` no deja elegir."""
    model.objects.filter(pk=obj.pk).update(**fields)


@pytest.fixture
def world(tables):
    t = tables
    bob = t.Currency.objects.create(iso_code="BOB", name="Boliviano", symbol="Bs")
    country = t.Country.objects.create(iso_code="BOL", name="Bolivia")
    scz = t.City.objects.create(country=country, name="Santa Cruz")
    lpz = t.City.objects.create(country=country, name="La Paz")
    hotel = t.Tenant.objects.create(legal_name="Hotel SA", trade_name="Hotel Cortez", subdomain="cortez",
                                    status="ACTIVO")
    tours = t.Tenant.objects.create(legal_name="Tours SRL", trade_name="Gravity", subdomain="gravity",
                                    status="ACTIVO")
    t.Tenant.objects.create(legal_name="Nueva", trade_name="Tupiza", subdomain="tupiza", status="PENDIENTE")
    kind = t.ProductType.objects.create(code="HOSPEDAJE", name="Hospedaje")

    def product(tenant, name, city):
        return t.TourismProduct.objects.create(
            tenant=tenant, product_type=kind, city=city, currency=bob, code=name[:10], name=name,
            base_price=Decimal("100"), max_capacity=10, status="PUBLICADO",
        )

    room = product(hotel, "Doble superior", scz)
    suite = product(hotel, "Suite", scz)
    walk = product(tours, "Death Road", lpz)
    product(hotel, "Borrador", scz).__class__.objects.filter(name="Borrador").update(status="BORRADOR")

    def person(email, first, last):
        user = t.User.objects.create(email=email, first_names=first, last_names=last, status="ACTIVO",
                                     password="x")
        return user, t.CustomerProfile.objects.create(user=user)

    maria, maria_profile = person("maria@x.test", "María", "Quispe")
    john, john_profile = person("john@x.test", "John", "Miller")
    _at(t.CustomerProfile, john_profile, created_at=datetime(2026, 9, 3, tzinfo=LA_PAZ))

    def book(code, tenant, customer, item, *, created, start, status="CONFIRMADA", qty=1, price="300",
             capacity=5, nights=1):
        order = t.Order.objects.create(customer=customer, code=f"O-{code}", status=status)
        booking = t.Booking.objects.create(order=order, tenant=tenant, currency=bob, code=code, status=status,
                                           final_amount=Decimal(price) * qty * nights,
                                           original_amount=Decimal(price) * qty * nights)
        _at(t.Booking, booking, created_at=created)
        for night in range(nights):
            slot = t.Availability.objects.create(product=item, tenant=tenant, start=start + timedelta(days=night),
                                                 end=start + timedelta(days=night + 1), total_capacity=capacity)
            t.BookingDetail.objects.create(booking=booking, tenant=tenant, slot=slot, quantity=qty,
                                           unit_price=Decimal(price))
        return booking

    def pay(booking, amount, when, status="APROBADO"):
        payment = t.Payment.objects.create(booking=booking, currency=bob, amount=Decimal(amount), method="QR",
                                           status=status, idempotency_key=f"k-{booking.code}-{amount}",
                                           processed_at=when if status == "APROBADO" else None)
        _at(t.Payment, payment, created_at=when)
        return payment

    nov = datetime(2026, 11, 10, 9, 0, tzinfo=LA_PAZ)
    soon = NOW + timedelta(days=2)
    b1 = book("R1", hotel, maria_profile, room, created=nov, start=soon, qty=2, nights=2)
    pay(b1, "1200", nov)
    b2 = book("R2", hotel, john_profile, suite, created=nov + timedelta(days=1), start=soon + timedelta(days=1),
              price="500")
    paid = pay(b2, "500", nov + timedelta(days=1))
    book("R3", hotel, john_profile, room, created=nov + timedelta(days=2), start=soon, status="CANCELADA")
    pending = book("R4", hotel, maria_profile, suite, created=NOW - timedelta(days=2),
                   start=soon + timedelta(days=4), status="CREADA")
    pay(pending, "500", NOW - timedelta(days=2), status="PENDIENTE")
    oct_booking = book("R5", hotel, maria_profile, room, created=datetime(2026, 10, 5, tzinfo=LA_PAZ),
                       start=datetime(2026, 10, 20, tzinfo=LA_PAZ))
    pay(oct_booking, "1000", datetime(2026, 10, 5, tzinfo=LA_PAZ))
    trip = book("G1", tours, john_profile, walk, created=nov, start=NOW + timedelta(days=20), qty=3, price="400")
    pay(trip, "1200", nov)

    policy = t.CancellationPolicy.objects.create(tenant=hotel, name="Flexible")
    rule = t.PenaltyRule.objects.create(policy=policy, minimum_days=0, penalty_percentage=Decimal("10"))
    cancel = t.Cancellation.objects.create(booking=b2, penalty_rule=rule, advance_days=3,
                                           applied_percentage=Decimal("40"), penalty_amount=Decimal("200"),
                                           refund_amount=Decimal("300"))
    t.Refund.objects.create(payment=paid, cancellation=cancel, currency=bob, amount=Decimal("300"),
                            status="COMPLETADO", idempotency_key="r1", processed_at=nov + timedelta(days=3),
                            requested_by=maria)
    t.Refund.objects.create(payment=paid, cancellation=cancel, currency=bob, amount=Decimal("50"),
                            status="FALLIDO", idempotency_key="r2", requested_by=maria)

    t.ProductReview.objects.create(user=maria, product=room, rating=5, comment="Excelente ubicación")
    old = t.ProductReview.objects.create(user=john, product=suite, rating=4, comment="Buena suite")
    _at(t.ProductReview, old, created_at=datetime(2026, 10, 2, tzinfo=LA_PAZ))
    t.ProductReview.objects.create(user=john, product=walk, rating=3, comment="Bien")

    plan = t.Plan.objects.create(currency=bob, code="PRO", name="Profesional", price=Decimal("300"),
                                 periodicity="MENSUAL", max_users=10, max_products=50)
    t.Subscription.objects.create(tenant=hotel, plan=plan, start_date=NOW.date() - timedelta(days=20),
                                  end_date=NOW.date() + timedelta(days=10))
    t.Subscription.objects.create(tenant=tours, plan=plan, start_date=NOW.date(),
                                  end_date=NOW.date() + timedelta(days=200))
    t.CustomerReport.objects.create(tenant=hotel, customer=john, booking=b2, reason="No se presentó")

    promo = t.Promotion.objects.create(tenant=hotel, mode="EXISTENTE", product=room, name="Fin de semana",
                                       percentage=Decimal("15"), starts_at=NOW - timedelta(days=5),
                                       ends_at=NOW + timedelta(days=5), administrative_status="HABILITADA",
                                       created_by=maria)
    t.BookingPromotionSnapshot.objects.create(
        booking=b1, promotion=promo, name=promo.name, currency=bob, percentage=Decimal("15"),
        original_unit_price=Decimal("300"), final_unit_price=Decimal("255"), quantity=2,
        original_total=Decimal("600"), discount_amount=Decimal("90"), total=Decimal("510"),
        starts_at=promo.starts_at, ends_at=promo.ends_at,
    )
    return SimpleNamespace(hotel=hotel, tours=tours)


def _build(world, *, platform, tenant_id=None, params=None):
    with patch("apps.reports.dashboard.report_scope", return_value=(platform, tenant_id)):
        return dashboard.build_dashboard(user=Mock(), tenant_id=tenant_id, params=params or {}, now=NOW)


def test_company_dashboard_only_counts_its_own_data(world):
    data = _build(world, platform=False, tenant_id=world.hotel.id)

    assert data["alcance"] == "empresa"
    money = data["finanzas"]
    assert (money["cobrado"], money["reembolsado"], money["neto"]) == ("1700.00", "300.00", "1400.00")
    assert money["variacion_neto"] == 40.0  # 1400 frente a 1000 en octubre
    assert [m["etiqueta"] for m in money["serie"]] == ["Jun", "Jul", "Ago", "Sep", "Oct", "Nov"]
    assert money["serie"][-2]["cobrado"] == "1000.00"
    assert money["serie"][-1]["reservas"] == 4

    bookings = data["reservas"]
    assert bookings["total"] == 4 and bookings["canceladas"] == 1 and bookings["variacion"] == 300.0
    assert {row["estado"]: row["total"] for row in bookings["por_estado"]}["CREADA"] == 1

    assert data["ocupacion"] == {"vendidos": 5, "capacidad": 20, "porcentaje": 25.0}
    assert data["calificacion"]["promedio"] == 4.5 and data["calificacion"]["nuevas_mes"] == 1
    assert data["calificacion"]["ultimas"][0]["autor"] in {"María Q.", "John M."}
    assert data["catalogo"] == {"publicados": 2, "total": 3}

    alerts = {item["clave"]: item["total"] for item in data["alertas"]}
    assert alerts == {"reembolsos_fallidos": 1, "pagos_revision": 1, "reservas_pendientes": 1}

    assert data["productos_top"][0]["nombre"] == "Doble superior"
    assert data["productos_top"][0]["ingreso"] == "1200.00"
    upcoming = data["proximas"]
    assert [row["reserva"] for row in upcoming] == ["R1", "R2"]
    assert upcoming[0]["dias"] == 2 and upcoming[0]["cliente"] == "María Quispe"
    assert data["promociones"][0]["usos"] == 1 and data["promociones"][0]["vigente"] is True
    assert "ranking" not in data and "comparacion" not in data


def test_platform_dashboard_ranks_and_alerts(world):
    data = _build(world, platform=True)

    assert data["alcance"] == "plataforma" and data["empresas"] == []
    assert data["finanzas"]["cobrado"] == "2900.00"
    assert data["reservas"]["total"] == 5
    people = data["plataforma"]
    assert people["empresas"] == {"total": 3, "activas": 2, "tasa_activacion": 66.7}
    assert people["turistas"]["total"] == 2 and people["turistas"]["nuevos_mes"] == 1
    assert people["turistas"]["con_compra"] == 2

    assert [row["nombre"] for row in data["ranking"]] == ["Hotel Cortez", "Gravity"]
    assert data["ranking"][1]["calificacion"] == 3.0
    assert data["suscripciones"] == [{"plan": "Profesional", "empresas": 2}]
    assert data["ciudades"][0] == {"ciudad": "Santa Cruz", "reservas": 4}
    assert len(data["ultimas_reservas"]) == 5

    alerts = {item["clave"]: item["total"] for item in data["alertas"]}
    assert alerts["clientes_reportados"] == 1
    assert alerts["empresas_pendientes"] == 1
    assert alerts["planes_por_vencer"] == 1
    assert data["comparacion"] == []


def test_superadmin_compares_selected_companies(world):
    ids = f"{world.hotel.id},{world.tours.id}"
    data = _build(world, platform=True, params={"empresas": ids})

    assert data["empresas"] == sorted([world.hotel.id, world.tours.id])
    by_name = {row["nombre"]: row for row in data["comparacion"]}
    assert by_name["Hotel Cortez"]["neto"] == "1400.00"
    assert by_name["Gravity"]["cobrado"] == "1200.00"
    assert by_name["Gravity"]["reservas"] == 1
    assert len(by_name["Gravity"]["serie"]) == 6


def test_superadmin_can_focus_one_company(world):
    data = _build(world, platform=True, params={"empresas": str(world.tours.id)})

    assert data["finanzas"]["cobrado"] == "1200.00"
    assert data["plataforma"]["empresas"]["total"] == 1
    assert data["comparacion"] == []
