"""CU51 sobre PostgreSQL local aislado. Stripe, correo y push simulados."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from threading import Barrier, Lock
from types import SimpleNamespace

import pytest
from django.db import IntegrityError, connection, connections, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings.models import Booking, InventoryLock
from apps.bookings.services import confirm_paid_session
from apps.catalog import departures
from apps.catalog.models import Availability, Currency, ProductType, TourismProduct
from apps.payments.models import Payment
from apps.promotions.models import BookingPromotionSnapshot, Promotion
from apps.promotions.pricing import EXISTING_PRODUCT_CODES
from apps.rbac.models import Permission, Role, RolePermission, UserRole
from apps.tenancy.models import Subscription, UserTenant

from .datos import OTRO_TURISTA, TURISTA, cliente, habitacion_publicada, tour_publicado

pytestmark = pytest.mark.django_db
BASE = "/api/v1/promociones/"
PUBLIC = "/api/v1/marketplace/promociones/"


@pytest.fixture
def company(firebase):
    source = tour_publicado()
    user = (
        UserRole.objects.select_related("user")
        .filter(tenant_id=source.tenant_id, role__code="TENANT_ADMIN")
        .first()
        .user
    )
    client = APIClient()
    client.force_authenticate(user)
    client.credentials(HTTP_X_TENANT_ID=str(source.tenant_id))

    def product(code="PAQUETE", price="100.00", tenant_id=None):
        return TourismProduct.objects.create(
            tenant_id=tenant_id or source.tenant_id,
            product_type=ProductType.objects.get(code=code),
            currency=source.currency,
            city=source.city,
            name=f"CU51 {code}",
            code=f"CU51-{TourismProduct.objects.count()}",
            base_price=Decimal(price),
            max_capacity=10,
            status="PUBLICADO",
        )

    return SimpleNamespace(
        client=client,
        user=user,
        tenant_id=source.tenant_id,
        product=product,
        package=product(),
        day=timezone.localdate() + timedelta(days=10),
    )


def payload(company, **changes):
    data = {
        "modalidad": "EXISTENTE",
        "producto_id": company.package.id,
        "nombre": "Oferta CU51",
        "porcentaje_descuento": "20.00",
        "inicio": (timezone.now() - timedelta(minutes=1)).isoformat(),
        "fin": (timezone.now() + timedelta(days=2)).isoformat(),
    }
    data.update(changes)
    return data


def create(company, **changes):
    response = company.client.post(BASE, payload(company, **changes), format="json")
    assert response.status_code == 201, response.json()
    return response.json()


def publish(company, promotion):
    response = company.client.post(f"{BASE}{promotion['id']}/publicar/")
    assert response.status_code == 200, response.json()
    return response.json()


def component(company, product, **changes):
    data = {
        "producto_id": product.id,
        "fecha_inicio": company.day.isoformat(),
        "cantidad": 2,
    }
    data.update(changes)
    return data


def combined(company):
    a, b = (
        company.product("RESTAURANTE", "60.00"),
        company.product("ATRACCION", "40.00"),
    )
    data = create(
        company,
        modalidad="COMBINADO",
        producto_id=None,
        componentes=[component(company, a), component(company, b)],
    )
    return data, a, b


def test_existing_price_publication_marketplace_and_quote(company):
    data = create(company)
    assert data["estado"] == "BORRADOR"
    assert APIClient().get(f"{PUBLIC}{data['id']}/").status_code == 404
    active = publish(company, data)
    assert (
        active["admite_reservas"]
        and not active["reservable"]
        and active["disponible"] is None
    )
    assert (
        active["precio_original"],
        active["monto_descuento"],
        active["precio_final"],
    ) == ("100.00", "20.00", "80.00")
    public = (
        APIClient()
        .get(
            f"{PUBLIC}{data['id']}/", {"fecha": company.day.isoformat(), "cantidad": 2}
        )
        .json()
    )
    assert public["reservable"] and public["disponible"]
    assert public["cotizacion"]["total"] == "160.00"
    assert public["cupos_restantes"] == 10
    product = (
        APIClient().get(f"/api/v1/marketplace/productos/{company.package.id}/").json()
    )
    assert (
        product["precio_base"] == "100.00"
        and product["promocion"]["precio_final"] == "80.00"
    )
    request = component(company, company.package)
    response = cliente().post("/api/v1/me/reservas/cotizacion/", request, format="json")
    assert response.status_code == 200, response.json()
    assert Decimal(str(response.json()["total"])) == Decimal("160.00")
    assert response.json()["promocion"]["id"] == data["id"]
    company.package.refresh_from_db()
    assert company.package.base_price == Decimal("100.00")


@pytest.mark.parametrize("code", ["RESTAURANTE", "TOUR", "EXPERIENCIA", "ATRACCION", "PAQUETE"])
def test_existing_discount_on_each_bookable_product(company, stripe, code):
    product = company.product(code)
    eligible = company.client.get(
        f"{BASE}productos-elegibles/", {"modalidad": "EXISTENTE"}
    )
    assert eligible.status_code == 200
    assert product.id in {item["id"] for item in eligible.json()["results"]}

    offer = publish(company, create(company, producto_id=product.id))
    assert (offer["precio_original"], offer["monto_descuento"], offer["precio_final"]) == (
        "100.00", "20.00", "80.00"
    )
    public = APIClient().get(f"/api/v1/marketplace/productos/{product.id}/")
    assert public.status_code == 200
    assert public.json()["promocion"]["id"] == offer["id"]
    assert public.json()["promocion"]["precio_final"] == "80.00"
    listed = APIClient().get(
        "/api/v1/marketplace/productos/", {"tipo": code, "buscar": product.name}
    )
    assert listed.status_code == 200
    assert any(
        item["id"] == product.id and item["promocion"]["id"] == offer["id"]
        for item in listed.json()["results"]
    )

    request = component(company, product, promocion_id=offer["id"])
    quote = cliente().post("/api/v1/me/reservas/cotizacion/", request, format="json")
    assert quote.status_code == 200, quote.json()
    assert Decimal(str(quote.json()["total"])) == Decimal("160.00")
    assert quote.json()["promocion"]["descuento_total"] == "40.00"
    booked = cliente().post(
        "/api/v1/me/reservas/?origen=web", request, format="json",
        HTTP_IDEMPOTENCY_KEY=f"cu51-existing-{code.lower()}",
    )
    assert booked.status_code == 201, booked.json()
    snapshot = BookingPromotionSnapshot.objects.get(booking_id=booked.json()["id"])
    assert snapshot.total == stripe.created[0]["amount"] == Decimal("160.00")
    assert snapshot.discount_amount == Decimal("40.00")
    assert snapshot.booking.details.first().unit_price == Decimal("80.00")


def test_existing_rejects_hotel_room_and_foreign_restaurant(company):
    room = habitacion_publicada()
    hotel = room.establishment.product
    for product in (hotel, room.product):
        assert product.product_type.code not in EXISTING_PRODUCT_CODES
        response = company.client.post(
            BASE, payload(company, producto_id=product.id), format="json"
        )
        assert response.status_code in (400, 404), response.json()

    foreign_tenant = (
        TourismProduct.objects.exclude(tenant_id=company.tenant_id)
        .filter(status="PUBLICADO").first().tenant_id
    )
    foreign = company.product("RESTAURANTE", tenant_id=foreign_tenant)
    response = company.client.post(
        BASE, payload(company, producto_id=foreign.id), format="json"
    )
    assert response.status_code in (400, 404), response.json()
    assert not Promotion.objects.filter(product=foreign).exists()


@pytest.mark.parametrize("percentage", ["0", "100", "-1", "100.01", "nan"])
def test_invalid_percentages(company, percentage):
    assert (
        company.client.post(
            BASE, payload(company, porcentaje_descuento=percentage), format="json"
        ).status_code
        == 400
    )


def test_dates_states_boundaries_and_disabled(company):
    now = timezone.now()
    assert (
        company.client.post(
            BASE,
            payload(company, fin=(now - timedelta(days=1)).isoformat()),
            format="json",
        ).status_code
        == 400
    )
    assert (
        company.client.post(
            BASE,
            payload(company, inicio=(now + timedelta(days=3)).isoformat()),
            format="json",
        ).status_code
        == 400
    )
    data = create(company, inicio=(now + timedelta(days=1)).isoformat())
    assert publish(company, data)["estado"] == "PROGRAMADA"
    promotion = Promotion.objects.get(id=data["id"])
    assert (
        promotion.state_at(promotion.starts_at - timedelta(microseconds=1))
        == "PROGRAMADA"
    )
    assert promotion.state_at(promotion.starts_at) == "VIGENTE"
    assert promotion.state_at(promotion.ends_at) == "VENCIDA"
    assert APIClient().get(f"{PUBLIC}{data['id']}/").status_code == 404
    disabled = company.client.post(f"{BASE}{data['id']}/desactivar/").json()
    assert disabled["estado"] == "DESACTIVADA"
    edited = company.client.patch(
        f"{BASE}{data['id']}/",
        {"porcentaje_descuento": "25", "inicio": now.isoformat()},
        format="json",
    )
    assert edited.status_code == 200 and edited.json()["precio_final"] == "75.00"
    assert publish(company, data)["estado"] == "VIGENTE"


def test_overlap_and_database_guard(company):
    first = publish(company, create(company))
    second = create(company)
    assert company.client.post(f"{BASE}{second['id']}/publicar/").status_code == 400
    with pytest.raises(IntegrityError), transaction.atomic():
        Promotion.objects.filter(id=second["id"]).update(
            administrative_status="HABILITADA"
        )
    promotion = Promotion.objects.get(id=first["id"])
    company.client.patch(
        f"{BASE}{second['id']}/",
        {
            "inicio": promotion.ends_at.isoformat(),
            "fin": (promotion.ends_at + timedelta(days=1)).isoformat(),
        },
        format="json",
    )
    assert publish(company, second)["estado"] == "PROGRAMADA"


def test_tenant_permissions_and_ids(company):
    data = create(company)
    assert APIClient().get(BASE).status_code == 401
    assert (
        cliente().get(BASE, HTTP_X_TENANT_ID=str(company.tenant_id)).status_code == 403
    )
    company.client.credentials()
    assert company.client.get(BASE).status_code == 400
    assert company.client.get(BASE, HTTP_X_TENANT_ID="incorrecto").status_code == 400
    company.client.credentials(HTTP_X_TENANT_ID="999999")
    assert company.client.get(f"{BASE}{data['id']}/").status_code == 403
    foreign = (
        TourismProduct.objects.exclude(tenant_id=company.tenant_id)
        .filter(status="PUBLICADO")
        .first()
    )
    company.client.credentials(HTTP_X_TENANT_ID=str(company.tenant_id))
    assert company.client.post(
        BASE, payload(company, producto_id=foreign.id), format="json"
    ).status_code in (400, 404)
    assert (
        company.client.patch(
            f"{BASE}{data['id']}/", {"producto_id": foreign.id}, format="json"
        ).status_code
        == 400
    )


def test_combined_quote_recalculate_no_inventory_and_no_checkout(company, stripe):
    before = (
        Booking.objects.count(),
        InventoryLock.objects.count(),
        Payment.objects.count(),
        Availability.objects.count(),
    )
    data, a, _ = combined(company)
    assert data["precio_original"] == "200.00" and data["precio_final"] == "160.00"
    active = publish(company, data)
    assert active["disponible"] and not active["reservable"]
    assert "checkout" in active["motivo_no_reservable"]
    assert APIClient().get(f"{PUBLIC}{data['id']}/").status_code == 200
    assert before == (
        Booking.objects.count(),
        InventoryLock.objects.count(),
        Payment.objects.count(),
        Availability.objects.count(),
    )
    a.base_price = Decimal("80.00")
    a.save(update_fields=["base_price"])
    recalculated = company.client.get(f"{BASE}{data['id']}/cotizacion/").json()
    assert (
        recalculated["precio_original"] == "240.00"
        and recalculated["precio_final"] == "192.00"
    )
    assert recalculated["requiere_revalidacion"]
    for product in (company.package, a):
        response = cliente().post(
            "/api/v1/me/reservas/",
            component(company, product, promocion_id=data["id"]),
            format="json",
        )
        assert response.status_code == 400, response.json()
    assert not stripe.created
    assert Booking.objects.count() == before[0]


def test_components_crud_and_readonly_while_enabled(company):
    data, _a, _ = combined(company)
    item = data["componentes"][0]
    endpoint = f"{BASE}{data['id']}/componentes/{item['id']}/"
    assert (
        company.client.patch(endpoint, {"cantidad": 3}, format="json").status_code
        == 200
    )
    publish(company, data)
    assert (
        company.client.patch(endpoint, {"cantidad": 4}, format="json").status_code
        == 400
    )
    assert company.client.delete(endpoint).status_code == 400
    company.client.post(f"{BASE}{data['id']}/desactivar/")
    assert company.client.delete(endpoint).status_code == 200
    assert company.client.post(f"{BASE}{data['id']}/publicar/").status_code == 400
    assert company.client.get(f"{BASE}{data['id']}/componentes/").status_code == 200
    assert (
        company.client.patch(
            f"{BASE}{data['id']}/componentes/999999/", {"cantidad": 1}, format="json"
        ).status_code
        == 404
    )


def test_invalid_components_currency_duplicates_and_owner(company):
    data, a, _ = combined(company)
    url = f"{BASE}{data['id']}/componentes/"
    assert (
        company.client.post(url, component(company, a), format="json").status_code
        == 400
    )
    assert (
        company.client.post(
            url, component(company, a, cantidad=0), format="json"
        ).status_code
        == 400
    )
    assert (
        company.client.post(
            url, component(company, company.package), format="json"
        ).status_code
        == 400
    )
    # Un tour visible de otra empresa activa: uno de una empresa suspendida
    # daria 404 (no existe para nadie) y no probaria la regla de empresa.
    foreign = (
        TourismProduct.objects.filter(status="PUBLICADO", product_type__code="TOUR", tenant__status="ACTIVO")
        .exclude(tenant_id=company.tenant_id)
        .order_by("id")
        .first()
    )
    assert (
        company.client.post(url, component(company, foreign), format="json").status_code
        == 400
    )
    hotel = habitacion_publicada().establishment.product
    assert (
        company.client.post(url, component(company, hotel), format="json").status_code
        == 404
    )
    other_currency = company.product("ATRACCION")
    other_currency.currency = Currency.objects.exclude(id=a.currency_id).first()
    other_currency.save(update_fields=["currency"])
    assert (
        company.client.post(
            url, component(company, other_currency), format="json"
        ).status_code
        == 400
    )
    assert (
        company.client.post(
            url,
            component(
                company, a, fecha_inicio=(company.day - timedelta(days=50)).isoformat()
            ),
            format="json",
        ).status_code
        == 400
    )


def test_components_unpublished_or_no_capacity_disappear_publicly(company):
    data, a, _ = combined(company)
    publish(company, data)
    slot_start = bookings_start(company.day)
    Availability.objects.create(
        product=a,
        tenant_id=company.tenant_id,
        start=slot_start,
        end=slot_start + timedelta(days=1),
        total_capacity=1,
        closed=True,
    )
    assert APIClient().get(f"{PUBLIC}{data['id']}/").status_code == 404
    private = company.client.get(f"{BASE}{data['id']}/").json()
    assert not private["valida"] and private["advertencias"]
    Availability.objects.filter(product=a).update(closed=False, total_capacity=10)
    a.status = "INACTIVO"
    a.save(update_fields=["status"])
    assert APIClient().get(f"{PUBLIC}{data['id']}/").status_code == 404


def bookings_start(day):
    from apps.bookings.services import _slot_start

    return _slot_start(day)


def test_explicit_departures_and_legacy_daily(company):
    tour = company.product("TOUR")
    data = create(company, modalidad="COMBINADO", producto_id=None)
    url = f"{BASE}{data['id']}/componentes/"
    assert (
        company.client.post(url, component(company, tour), format="json").status_code
        == 400
    )
    start = bookings_start(company.day)
    legacy = Availability.objects.create(
        product=tour,
        tenant_id=company.tenant_id,
        start=start,
        end=start + timedelta(days=1),
        total_capacity=10,
        closed=False,
    )
    assert departures.is_legacy_daily(legacy)
    added = company.client.post(url, component(company, tour), format="json")
    assert added.status_code == 201, added.json()
    company.client.delete(f"{url}{added.json()['componentes'][0]['id']}/")
    legacy.delete()
    slot = Availability.objects.create(
        product=tour,
        tenant_id=company.tenant_id,
        start=start + timedelta(hours=9),
        end=start + timedelta(hours=11),
        total_capacity=3,
        closed=False,
    )
    assert (
        company.client.post(url, component(company, tour), format="json").status_code
        == 400
    )
    assert (
        company.client.post(
            url, component(company, tour, salida_id=slot.id, cantidad=4), format="json"
        ).status_code
        == 400
    )
    assert (
        company.client.post(
            url, component(company, tour, salida_id=slot.id), format="json"
        ).status_code
        == 201
    )


def test_booking_snapshot_amount_payment_and_expiration(company, stripe):
    data = publish(company, create(company))
    request = component(company, company.package, promocion_id=data["id"])
    response = cliente().post(
        "/api/v1/me/reservas/?origen=web",
        request,
        format="json",
        HTTP_IDEMPOTENCY_KEY="cu51",
    )
    assert response.status_code == 201, response.json()
    booking = Booking.objects.get(id=response.json()["id"])
    payment = Payment.objects.get(booking=booking)
    snapshot = BookingPromotionSnapshot.objects.get(booking=booking)
    assert (
        payment.amount
        == stripe.created[0]["amount"]
        == snapshot.total
        == Decimal("160.00")
    )
    assert snapshot.original_total == Decimal(
        "200.00"
    ) and snapshot.discount_amount == Decimal("40.00")
    assert booking.details.first().unit_price == Decimal("80.00")
    edited = company.client.patch(
        f"{BASE}{data['id']}/", {"porcentaje_descuento": "30.00"}, format="json"
    )
    assert edited.status_code == 200, edited.json()
    company.client.post(f"{BASE}{data['id']}/desactivar/")
    retry = cliente().post(
        "/api/v1/me/reservas/?origen=web",
        request,
        format="json",
        HTTP_IDEMPOTENCY_KEY="cu51",
    )
    assert retry.status_code == 201 and retry.json()["id"] == booking.id
    assert retry.json()["importe"]["total"] == "160.00" and len(stripe.created) == 1
    company.package.base_price = Decimal("200.00")
    company.package.save(update_fields=["base_price"])
    assert (
        cliente()
        .post("/api/v1/me/reservas/cotizacion/", request, format="json")
        .status_code
        == 400
    )
    request.pop("promocion_id")
    ordinary = (
        cliente().post("/api/v1/me/reservas/cotizacion/", request, format="json").json()
    )
    assert ordinary["promocion"] is None and Decimal(str(ordinary["total"])) == Decimal(
        "400.00"
    )
    stripe.pay(payment.reference)
    confirm_paid_session(payment.reference)
    saved = cliente().get(f"/api/v1/me/reservas/{booking.id}/").json()
    assert (
        saved["importe"]["total"] == "160.00"
        and saved["promocion"]["total_original"] == "200.00"
    )
    assert (
        cliente().post(f"/api/v1/me/reservas/{booking.id}/cancelar/").status_code == 400
    )


def test_existing_product_unpublished_and_expired_no_discount(company):
    data = publish(company, create(company))
    now = timezone.now()
    Promotion.objects.filter(id=data["id"]).update(
        starts_at=now - timedelta(days=2), ends_at=now - timedelta(seconds=1)
    )
    assert APIClient().get(f"{PUBLIC}{data['id']}/").status_code == 404
    quote = (
        cliente()
        .post(
            "/api/v1/me/reservas/cotizacion/",
            component(company, company.package),
            format="json",
        )
        .json()
    )
    assert quote["promocion"] is None
    company.package.status = "INACTIVO"
    company.package.save(update_fields=["status"])
    assert company.client.post(f"{BASE}{data['id']}/publicar/").status_code == 400


def test_eligible_and_preview_without_persistence(company):
    response = company.client.get(f"{BASE}productos-elegibles/")
    assert response.status_code == 200
    assert company.package.id in {
        product["id"] for product in response.json()["results"]
    }
    assert all(
        product["tipo_codigo"] in EXISTING_PRODUCT_CODES
        and product["empresa_id"] == company.tenant_id
        for product in response.json()["results"]
    )
    count = Promotion.objects.count()
    preview = company.client.post(f"{BASE}cotizar/", payload(company), format="json")
    assert preview.status_code == 200 and preview.json()["precio_final"] == "80.00"
    assert Promotion.objects.count() == count


def test_rounding_zero_final_and_ordinary_products(company):
    company.package.base_price = Decimal("0.01")
    company.package.save(update_fields=["base_price"])
    assert (
        company.client.post(
            BASE, payload(company, porcentaje_descuento="99.99"), format="json"
        ).status_code
        == 400
    )
    company.package.base_price = Decimal("19.99")
    company.package.save(update_fields=["base_price"])
    data = publish(company, create(company, porcentaje_descuento="12.50"))
    assert data["precio_final"] == "17.49" and data["monto_descuento"] == "2.50"
    service = company.product("RESTAURANTE", "45.00")
    quote = (
        cliente()
        .post(
            "/api/v1/me/reservas/cotizacion/",
            component(company, service),
            format="json",
        )
        .json()
    )
    assert quote["promocion"] is None and Decimal(str(quote["total"])) == Decimal(
        "90.00"
    )


def test_reader_permission_tenant_isolation_and_subscription(company):
    data = publish(company, create(company))
    reader = UserRole.objects.get(user__email=TURISTA, tenant__isnull=True).user
    role = Role.objects.create(
        tenant_id=company.tenant_id,
        code="CU51_LECTOR",
        name="Lector CU51",
        scope="TENANT",
        is_system=False,
    )
    RolePermission.objects.create(
        role=role, permission=Permission.objects.get(code="PRODUCTOS_LEER")
    )
    UserTenant.objects.create(user=reader, tenant_id=company.tenant_id, status="ACTIVO")
    UserRole.objects.create(user=reader, role=role, tenant_id=company.tenant_id)
    api = cliente()
    api.credentials(HTTP_X_TENANT_ID=str(company.tenant_id))
    assert api.get(BASE).status_code == 200
    assert api.post(BASE, payload(company), format="json").status_code == 403
    assert api.post(f"{BASE}{data['id']}/desactivar/").status_code == 403
    foreign_assignment = (
        UserRole.objects.select_related("user")
        .filter(role__code="TENANT_ADMIN")
        .exclude(tenant_id=company.tenant_id)
        .first()
    )
    foreign = APIClient()
    foreign.force_authenticate(foreign_assignment.user)
    foreign.credentials(HTTP_X_TENANT_ID=str(foreign_assignment.tenant_id))
    assert foreign.get(f"{BASE}{data['id']}/").status_code == 404
    assert (
        foreign.patch(
            f"{BASE}{data['id']}/", {"nombre": "Ajeno"}, format="json"
        ).status_code
        == 404
    )
    assert foreign.post(f"{BASE}{data['id']}/desactivar/").status_code == 404
    Subscription.objects.filter(tenant_id=company.tenant_id).update(status="VENCIDA")
    assert company.client.post(BASE, payload(company), format="json").status_code == 403
    assert APIClient().get(f"{PUBLIC}{data['id']}/").status_code == 404


def test_hotel_rooms_nights_and_closed_inventory(company):
    room = habitacion_publicada()
    assignment = (
        UserRole.objects.select_related("user")
        .filter(tenant_id=room.tenant_id, role__code="TENANT_ADMIN")
        .first()
    )
    company.tenant_id = room.tenant_id
    company.user = assignment.user
    company.client.force_authenticate(assignment.user)
    company.client.credentials(HTTP_X_TENANT_ID=str(room.tenant_id))
    service = company.product("RESTAURANTE", "50.00", tenant_id=room.tenant_id)
    item = component(
        company,
        room.product,
        cantidad=1,
        huespedes=1,
        fecha_fin=(company.day + timedelta(days=2)).isoformat(),
    )
    data = create(
        company,
        modalidad="COMBINADO",
        producto_id=None,
        componentes=[item, component(company, service, cantidad=1)],
    )
    assert Decimal(data["precio_original"]) == room.product.base_price * 2 + Decimal(
        "50.00"
    )
    publish(company, data)
    start = bookings_start(company.day + timedelta(days=1))
    Availability.objects.update_or_create(
        product=room.product,
        start=start,
        defaults={
            "tenant_id": room.tenant_id,
            "end": start + timedelta(days=1),
            "total_capacity": room.quantity,
            "closed": True,
        },
    )
    assert APIClient().get(f"{PUBLIC}{data['id']}/").status_code == 404


def test_public_list_and_product_list_have_no_per_package_queries(company):
    publish(company, create(company))
    api = APIClient()
    with CaptureQueriesContext(connection) as single:
        response = api.get(PUBLIC)
    assert response.status_code == 200
    for _ in range(4):
        company.package = company.product()
        publish(company, create(company))
    with CaptureQueriesContext(connection) as multiple:
        response = api.get(PUBLIC)
    assert response.json()["count"] == 5
    assert len(single) == len(multiple)
    with CaptureQueriesContext(connection) as one_product:
        response = api.get(
            "/api/v1/marketplace/productos/", {"tipo": "PAQUETE", "page_size": 1}
        )
    with CaptureQueriesContext(connection) as many_products:
        response = api.get(
            "/api/v1/marketplace/productos/", {"tipo": "PAQUETE", "page_size": 20}
        )
    assert response.status_code == 200
    assert len(many_products) <= len(one_product) + 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_publications_only_enable_one(company):
    first, second = create(company), create(company)
    gate = Barrier(2)

    def enable(promotion):
        connections.close_all()
        try:
            api = APIClient()
            api.force_authenticate(company.user)
            api.credentials(HTTP_X_TENANT_ID=str(company.tenant_id))
            gate.wait(timeout=10)
            return api.post(f"{BASE}{promotion['id']}/publicar/").status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(enable, (first, second)))
    assert sorted(outcomes) == [200, 400]
    assert (
        Promotion.objects.filter(
            product=company.package, administrative_status="HABILITADA"
        ).count()
        == 1
    )


@pytest.mark.django_db(transaction=True)
def test_concurrent_discounted_bookings_preserve_price_and_capacity(
    company, stripe, monkeypatch
):
    company.package.max_capacity = 1
    company.package.save(update_fields=["max_capacity"])
    data = publish(company, create(company))
    gate, stripe_lock = Barrier(2), Lock()
    original = stripe.create_checkout_session

    def checkout(**kwargs):
        with stripe_lock:
            session = original(**kwargs)
            # Las tablas históricas managed=False no se vacían con flush.
            # Esta prueba transaccional usa su propio namespace de sesiones.
            unique_id = f"{session.id}_cu51_concurrent"
            stripe.sessions[unique_id] = stripe.sessions.pop(session.id)
            return replace(
                session, id=unique_id, url=f"https://checkout.stripe.test/{unique_id}"
            )

    monkeypatch.setattr("apps.payments.gateway.create_checkout_session", checkout)

    def reserve(email):
        connections.close_all()
        try:
            api = cliente(email)
            gate.wait(timeout=10)
            return api.post(
                "/api/v1/me/reservas/",
                component(
                    company, company.package, cantidad=1, promocion_id=data["id"]
                ),
                format="json",
            ).status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(reserve, (TURISTA, OTRO_TURISTA)))
    assert sorted(outcomes) == [201, 409]
    snapshot = BookingPromotionSnapshot.objects.get(promotion_id=data["id"])
    assert snapshot.total == stripe.created[0]["amount"] == Decimal("80.00")
