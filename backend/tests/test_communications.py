"""Comunicaciones: ORM, RBAC y API reales sobre SQLite, sin servicios externos.

Las migraciones normales se ejecutan; schema_editor completa solamente las
tablas legacy necesarias. No se simulan resolve, autorizacion ni auditoria.
Los bloqueos concurrentes y el SQL legacy se verifican en integracion/.
"""

import importlib
import socket
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.db import IntegrityError, connection
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.audit.models import AuditLog
from apps.bookings.models import Booking, BookingDetail, BookingState, Order
from apps.catalog.models import (
    Availability,
    Currency,
    PenaltyRule,
    ProductType,
    TourismProduct,
)
from apps.notifications import communications, push
from apps.notifications.communication_views import validated
from apps.notifications.models import (
    Communication,
    CommunicationDelivery,
    CommunicationEmail,
    CommunicationPreference,
    Notification,
    PushAttempt,
)
from apps.rbac.models import Permission, Role, RolePermission, UserRole
from apps.tenancy.models import City, Country, Tenant, UserTenant

pytestmark = pytest.mark.django_db(transaction=True)


def _models_with_dependencies():
    ordered = []

    def visit(model):
        if model in ordered:
            return
        for field in model._meta.local_fields:
            if field.is_relation:
                visit(field.remote_field.model)
        ordered.append(model)

    for model in (
        UserTenant, UserRole, RolePermission, BookingDetail, PenaltyRule, Notification,
        AuditLog, CommunicationDelivery, CommunicationEmail, PushAttempt, CommunicationPreference,
    ):
        visit(model)
    return ordered


@pytest.fixture(scope="module")
def communication_schema(django_db_setup, django_db_blocker):
    """No cambia managed ni settings; restaura el esquema al terminar el modulo."""
    models = _models_with_dependencies()
    created = []
    with django_db_blocker.unblock(), connection.constraint_checks_disabled():
        existing = set(connection.introspection.table_names())
        with connection.schema_editor() as editor:
            for model in models:
                if model._meta.db_table not in existing:
                    editor.create_model(model)
                    created.append(model)
                    existing.add(model._meta.db_table)
    try:
        yield models
    finally:
        with django_db_blocker.unblock(), connection.constraint_checks_disabled():
            with connection.schema_editor() as editor:
                for model in reversed(created):
                    editor.delete_model(model)


@pytest.fixture(autouse=True)
def communication_db(communication_schema, transactional_db):
    yield
    # flush de Django omite managed=False. Limpiar por SQL evita que el
    # Collector busque relaciones ajenas cuyas tablas legacy no se crearon.
    with connection.constraint_checks_disabled(), connection.cursor() as cursor:
        for model in reversed(communication_schema):
            cursor.execute(f"DELETE FROM {connection.ops.quote_name(model._meta.db_table)}")
    connection.check_constraints()


@pytest.fixture(autouse=True)
def no_external_push(monkeypatch, settings):
    settings.PUSH_EN_SEGUNDO_PLANO = False
    settings.WEB_APP_URL = "https://web.situr.test"
    settings.API_PUBLIC_URL = "https://api.situr.test"
    guards = []
    for name in ("push_notification", "send_one", "_session"):
        guard = Mock(side_effect=AssertionError(f"Publicar no debe llamar push.{name}"))
        monkeypatch.setattr(push, name, guard)
        guards.append(guard)
    network = Mock(side_effect=AssertionError("Las pruebas no deben abrir conexiones de red"))
    monkeypatch.setattr(socket.socket, "connect", network)
    yield
    for guard in [*guards, network]:
        guard.assert_not_called()


def _user(name, status=User.Status.ACTIVE):
    return User.objects.create(
        email=f"{name}@communications.test", first_names=name, last_names="Prueba",
        password="!", status=status,
    )


def _role(code, tenant=None, scope=Role.Scope.TENANT, system=False):
    return Role.objects.create(tenant=tenant, code=code, name=code, scope=scope, is_system=system)


def _member(user, tenant, role=None, status=UserTenant.Status.ACTIVE):
    UserTenant.objects.create(user=user, tenant=tenant, status=status)
    if role is not None:
        UserRole.objects.create(user=user, tenant=tenant, role=role)


def _booking(user, tenant, currency, status=BookingState.CONFIRMED):
    profile, _ = CustomerProfile.objects.get_or_create(user=user)
    order = Order.objects.create(customer=profile, code=f"O-{Order.objects.count() + 1}")
    return Booking.objects.create(
        order=order, tenant=tenant, currency=currency, code=f"R-{order.pk}", status=status,
    )


@pytest.fixture
def world():
    a, b = [Tenant.objects.create(
        legal_name=f"Empresa {code}", trade_name=f"Empresa {code}",
        subdomain=f"comunicaciones-{code.lower()}", status=Tenant.Status.ACTIVE,
    ) for code in ("A", "B")]
    owner_role = _role("TENANT_ADMIN", system=True)
    employee_role = _role("EMPLEADO", system=True)
    local_role = _role("COMUNICADOR", a)
    foreign_role = _role("COMUNICADOR_B", b)
    super_role = _role("SUPER_ADMIN", scope=Role.Scope.GLOBAL, system=True)
    customer_role = _role("CLIENTE", scope=Role.Scope.GLOBAL, system=True)
    global_role = _role("SOPORTE", scope=Role.Scope.GLOBAL)
    permission = Permission.objects.create(
        code=communications.PERMISSION, module="Comunicaciones", name="Gestionar comunicaciones",
    )
    RolePermission.objects.create(role=local_role, permission=permission)
    RolePermission.objects.create(role=global_role, permission=permission)
    users = {name: _user(name) for name in (
        "owner_a", "owner_b", "employee", "manager", "dual", "customer_a",
        "customer_b", "tourist", "unassigned", "superadmin", "global_manager", "invited",
    )}
    users["inactive"] = _user("inactive", User.Status.INACTIVE)
    users["blocked"] = _user("blocked", User.Status.BLOCKED)
    users["pending"] = _user("pending", User.Status.PENDING)
    for name, tenant, role in (
        ("owner_a", a, owner_role), ("owner_b", b, owner_role),
        ("employee", a, employee_role), ("manager", a, local_role),
        ("dual", a, employee_role), ("inactive", a, employee_role),
        ("blocked", a, employee_role), ("pending", a, employee_role),
    ):
        _member(users[name], tenant, role)
    _member(users["invited"], a, employee_role, UserTenant.Status.INVITED)
    for name, role in (("superadmin", super_role), ("tourist", customer_role), ("global_manager", global_role)):
        UserRole.objects.create(user=users[name], role=role)
    CustomerProfile.objects.create(user=users["tourist"])
    currency = Currency.objects.create(iso_code="BOB", name="Boliviano", symbol="Bs")
    booking_a = _booking(users["customer_a"], a, currency)
    booking_b = _booking(users["customer_b"], b, currency)
    _booking(users["dual"], a, currency)
    _booking(users["dual"], a, currency)  # Dos reservas y pertenencia al personal.
    _booking(users["inactive"], a, currency)
    return SimpleNamespace(
        a=a, b=b, owner_role=owner_role, employee_role=employee_role,
        local_role=local_role, foreign_role=foreign_role, global_role=global_role,
        permission=permission, currency=currency, booking_a=booking_a, booking_b=booking_b, **users,
    )


def _payload(kind=Communication.Kind.OPERATIONAL, group="TODOS", **audience):
    return validated({
        "titulo": "Aviso de prueba", "mensaje": "Informacion para la audiencia autorizada.",
        "tipo": kind, "audiencia": {"grupo": group, **audience}, "reserva_id": None,
    })


def _api(user=None, tenant=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    if tenant is not None:
        client.credentials(HTTP_X_TENANT_ID=str(tenant.pk))
    return client


def _post(client, name, data, **kwargs):
    return client.post(reverse(name, kwargs=kwargs or None), data, format="json")


def _draft(client, payload=None):
    response = _post(client, "communications", payload or _payload())
    assert response.status_code == 201, response.content
    return response.json()


def _preview(client, payload):
    response = _post(client, "communication-audience", payload)
    assert response.status_code == 200, response.content
    return response.json()


def _publish(client, draft):
    preview = _preview(client, draft)
    response = _post(client, "communication-publish", {"huella": preview["huella"]}, pk=draft["id"])
    assert response.status_code == 200, response.content
    return response.json(), preview


@pytest.mark.parametrize(("kind", "group", "names"), [
    ("OPERATIVA", "TODOS", {"owner_a", "employee", "manager", "dual", "customer_a"}),
    ("INTERNA", "TODOS", {"owner_a", "employee", "manager", "dual"}),
    ("OPERATIVA", "PERSONAL", {"owner_a", "employee", "manager", "dual"}),
    ("OPERATIVA", "CLIENTES", {"dual", "customer_a"}),
    ("INTERNA", "PROPIETARIOS", {"owner_a"}),
    ("INTERNA", "EMPLEADOS", {"employee", "manager", "dual"}),
])
def test_resolve_tenant_audiences_are_scoped_active_and_distinct(world, kind, group, names):
    users = list(communications.resolve(world.owner_a, world.a.pk, _payload(kind, group)))
    assert [u.pk for u in users] == sorted(getattr(world, name).pk for name in names)


def test_global_internal_excludes_tourist_with_global_cliente_role(world):
    payload = _payload("INTERNA")
    preview = _preview(_api(world.superadmin), payload)
    assert {u["id"] for u in preview["destinatarios"]} == {
        getattr(world, name).pk for name in (
            "owner_a", "owner_b", "employee", "manager", "dual", "superadmin", "global_manager",
        )
    }
    assert world.tourist.pk not in {u["id"] for u in preview["destinatarios"]}


def test_global_operational_todos_includes_active_without_profile_or_assignments(world):
    assert not CustomerProfile.objects.filter(user=world.unassigned).exists()
    assert not UserRole.objects.filter(user=world.unassigned).exists()
    assert not UserTenant.objects.filter(user=world.unassigned).exists()
    client = _api(world.superadmin)
    draft = _draft(client)
    published, preview = _publish(client, draft)
    expected = set(User.objects.filter(status=User.Status.ACTIVE).values_list("pk", flat=True))
    assert {u["id"] for u in preview["destinatarios"]} == expected
    assert set(CommunicationDelivery.objects.values_list("user_id", flat=True)) == expected
    assert published["remitente"] == "SITUR-SMART"


@pytest.mark.parametrize("endpoint", ["communications", "communication-audience", "communication-options"])
def test_anonymous_api_is_denied(endpoint):
    client = _api()
    response = (_post(client, endpoint, _payload()) if endpoint == "communication-audience"
                else client.get(reverse(endpoint)))
    assert response.status_code == 401


@pytest.mark.parametrize("actor", ["employee", "owner_a", "manager", "global_manager"])
def test_non_superadmin_cannot_use_platform_context_even_with_global_permission(world, actor):
    client = _api(getattr(world, actor))
    assert client.get(reverse("communications")).status_code == 403
    assert client.get(reverse("communication-options")).status_code == 403
    assert _post(client, "communications", _payload()).status_code == 403
    assert _post(client, "communication-audience", _payload()).status_code == 403
    assert not Communication.objects.exists()


def test_employee_denied_on_every_management_endpoint(world):
    draft = _draft(_api(world.owner_a, world.a))
    client = _api(world.employee, world.a)
    for name in ("communications", "communication-options", "communication-detail"):
        url = reverse(name, kwargs={"pk": draft["id"]} if name == "communication-detail" else None)
        assert client.get(url).status_code == 403
    for name in ("communications", "communication-audience"):
        assert _post(client, name, _payload()).status_code == 403
    assert client.patch(reverse("communication-detail", kwargs={"pk": draft["id"]}),
                        {"titulo": "Cambio"}, format="json").status_code == 403
    assert _post(client, "communication-publish", {"huella": "a" * 64}, pk=draft["id"]).status_code == 403
    assert Communication.objects.get().title == draft["titulo"]
    assert not Notification.objects.exists()


def test_explicit_permission_allows_manager_only_in_own_tenant(world):
    assert _post(_api(world.manager, world.a), "communications", _payload()).status_code == 201
    assert _post(_api(world.manager, world.b), "communications", _payload()).status_code == 403
    # Un permiso de otra empresa no alcanza aunque sea miembro de ambas.
    _member(world.manager, world.b, world.employee_role)
    assert _post(_api(world.manager, world.b), "communications", _payload()).status_code == 403


@pytest.mark.parametrize("status", [Tenant.Status.SUSPENDED, Tenant.Status.INACTIVE, Tenant.Status.PENDING])
def test_non_operational_tenant_is_denied(world, status):
    Tenant.objects.filter(pk=world.a.pk).update(status=status)
    response = _post(_api(world.owner_a, world.a), "communications", _payload())
    assert response.status_code == 403
    assert not Communication.objects.exists()


def test_communication_crud_and_publish_never_cross_contexts(world):
    client_a, client_b = _api(world.owner_a, world.a), _api(world.owner_b, world.b)
    draft_a, draft_b = _draft(client_a), _draft(client_b)
    assert [row["id"] for row in client_a.get(reverse("communications")).json()["results"]] == [draft_a["id"]]
    detail = reverse("communication-detail", kwargs={"pk": draft_b["id"]})
    assert client_a.get(detail).status_code == 404
    assert client_a.patch(detail, {"titulo": "Intrusion"}, format="json").status_code == 404
    assert _post(client_a, "communication-publish", {"huella": "a" * 64}, pk=draft_b["id"]).status_code == 404
    # Incluso SuperAdmin debe elegir el contexto correspondiente.
    assert _api(world.superadmin).get(detail).status_code == 404
    assert Communication.objects.get(pk=draft_b["id"]).title == draft_b["titulo"]


@pytest.mark.parametrize("selection", ["company", "user", "global_role", "foreign_role"])
def test_preview_and_save_reject_audience_outside_tenant(world, selection):
    audience = {
        "company": {"empresa_ids": [world.b.pk]}, "user": {"usuario_ids": [world.customer_b.pk]},
        "global_role": {"rol_ids": [world.global_role.pk]}, "foreign_role": {"rol_ids": [world.foreign_role.pk]},
    }[selection]
    client = _api(world.owner_a, world.a)
    for endpoint in ("communication-audience", "communications"):
        assert _post(client, endpoint, _payload(**audience)).status_code == 403
    assert not Communication.objects.exists()
    assert not AuditLog.objects.exists()


def test_role_filter_and_options_obey_role_and_assignment_scope(world):
    # El rol de sistema compartido se asigna en ambas empresas.
    UserRole.objects.create(user=world.owner_b, tenant=world.b, role=world.employee_role)
    client = _api(world.owner_a, world.a)
    preview = _preview(client, _payload(rol_ids=[world.employee_role.pk]))
    assert {u["id"] for u in preview["destinatarios"]} == {world.employee.pk, world.dual.pk}
    options = client.get(reverse("communication-options")).json()
    assert options["es_global"] is False
    assert [c["id"] for c in options["empresas"]] == [world.a.pk]
    assert {r["id"] for r in options["roles"]} == {world.owner_role.pk, world.employee_role.pk, world.local_role.pk}
    assert {u["id"] for u in options["usuarios"]} == {
        world.owner_a.pk, world.employee.pk, world.manager.pk, world.dual.pk, world.customer_a.pk,
    }
    searched = client.get(reverse("communication-options"), {"buscar": world.customer_a.email}).json()
    assert [u["id"] for u in searched["usuarios"]] == [world.customer_a.pk]
    assert searched["usuarios_limitados"] is False


def test_publish_is_idempotent_deduplicates_and_records_audit_without_push(world):
    client = _api(world.owner_a, world.a)
    draft = _draft(client)
    preview = _preview(client, draft)
    ids = [u["id"] for u in preview["destinatarios"]]
    assert len(ids) == len(set(ids)) == 5
    assert ids.count(world.dual.pk) == 1
    first = _post(client, "communication-publish", {"huella": preview["huella"]}, pk=draft["id"])
    assert first.status_code == 200, first.content
    initial_ids = list(Notification.objects.order_by("id").values_list("id", flat=True))
    second = _post(client, "communication-publish", {"huella": preview["huella"]}, pk=draft["id"])
    assert second.status_code == 200
    assert second.json() == first.json()
    assert list(Notification.objects.order_by("id").values_list("id", flat=True)) == initial_ids
    assert CommunicationDelivery.objects.count() == Notification.objects.count() == 5
    assert not PushAttempt.objects.exists()
    for delivery in CommunicationDelivery.objects.select_related("notification"):
        assert delivery.user_id == delivery.notification.user_id
        assert delivery.push_status == "PENDIENTE"
        assert delivery.attempts == 0
        assert delivery.notification.kind == "COMUNICACION"
        assert delivery.notification.data["remitente"] == world.a.trade_name
        assert delivery.notification.data["comunicacion_id"] == draft["id"]
    audit = AuditLog.objects.get(action="PUBLICAR", entity="comunicacion")
    assert (audit.user_id, audit.tenant_id, audit.entity_id) == (world.owner_a.pk, world.a.pk, str(draft["id"]))
    assert audit.new_data == {"destinatarios": 5, "tipo": "OPERATIVA"}
    assert first.json()["push_pendientes"] == 5
    assert first.json()["estado"] == "PUBLICADA"
    assert first.json()["publicado_en"] is not None
    assert client.patch(reverse("communication-detail", kwargs={"pk": draft["id"]}),
                        {"mensaje": "Cambiar publicado"}, format="json").status_code == 400


def test_preview_normalizes_defaults_to_match_saved_draft_and_publish(world):
    raw = {"titulo": "Defaults", "mensaje": "Prueba", "tipo": "INTERNA", "audiencia": {}}
    client = _api(world.owner_a, world.a)
    preview = _preview(client, raw)
    draft = _draft(client, raw)
    assert draft["reserva_id"] is None
    assert draft["audiencia"] == {"grupo": "TODOS", "empresa_ids": [], "rol_ids": [], "usuario_ids": []}
    assert preview == communications.preview(world.owner_a, world.a.pk, validated(raw))
    assert _post(client, "communication-publish", {"huella": preview["huella"]}, pk=draft["id"]).status_code == 200


@pytest.mark.parametrize("change", ["content", "recipient_removed", "recipient_added", "booking_cancelled"])
def test_stale_fingerprint_returns_409_and_persists_no_publication(world, change):
    client = _api(world.owner_a, world.a)
    draft = _draft(client)
    preview = _preview(client, draft)
    if change == "content":
        response = client.patch(reverse("communication-detail", kwargs={"pk": draft["id"]}),
                                {"mensaje": "Contenido nuevo"}, format="json")
        assert response.status_code == 200
    elif change == "recipient_removed":
        UserTenant.objects.filter(user=world.employee).update(status=UserTenant.Status.INACTIVE)
    elif change == "recipient_added":
        _member(world.unassigned, world.a, world.employee_role)
    else:
        Booking.objects.filter(pk=world.booking_a.pk).update(status=BookingState.CANCELLED)
    response = _post(client, "communication-publish", {"huella": preview["huella"]}, pk=draft["id"])
    assert response.status_code == 409, response.content
    item = Communication.objects.get(pk=draft["id"])
    assert item.state == Communication.State.DRAFT
    assert item.published_at is None
    assert not Notification.objects.exists()
    assert not CommunicationDelivery.objects.exists()
    assert not AuditLog.objects.filter(action="PUBLICAR").exists()
    # Una nueva revision permite publicar el contenido y la audiencia vigentes.
    fresh = client.get(reverse("communication-detail", kwargs={"pk": draft["id"]})).json()
    _publish(client, fresh)


@pytest.mark.parametrize("fingerprint", [None, "", "a" * 63, "a" * 65])
def test_publish_rejects_missing_or_malformed_fingerprint(world, fingerprint):
    client = _api(world.owner_a, world.a)
    draft = _draft(client)
    response = _post(client, "communication-publish", {} if fingerprint is None else {"huella": fingerprint}, pk=draft["id"])
    assert response.status_code == 400
    assert not Notification.objects.exists()


def test_empty_audience_cannot_publish(world):
    client = _api(world.owner_a, world.a)
    draft = _draft(client, _payload(rol_ids=[world.local_role.pk]))
    # El rol es valido; sin asignaciones activas la audiencia debe quedar vacia.
    UserRole.objects.filter(user=world.manager, role=world.local_role).delete()
    preview = _preview(client, draft)
    assert preview["total"] == 0
    assert _post(client, "communication-publish", {"huella": preview["huella"]}, pk=draft["id"]).status_code == 400
    assert Communication.objects.get().state == Communication.State.DRAFT
    assert not Notification.objects.exists()


def test_publish_rolls_back_notifications_deliveries_state_and_audit_on_failure(world, monkeypatch):
    payload = _payload()
    item = communications.save(world.owner_a, world.a.pk, payload)
    fingerprint = communications.preview(world.owner_a, world.a.pk, payload)["huella"]
    original = CommunicationDelivery.objects.bulk_create

    def partial_write_then_fail(objects, **kwargs):
        original(objects[:1], **kwargs)
        raise IntegrityError("Fallo de escritura despues del primer destinatario")

    monkeypatch.setattr(CommunicationDelivery.objects, "bulk_create", partial_write_then_fail)
    with pytest.raises(IntegrityError, match="primer destinatario"):
        communications.publish(world.owner_a, world.a.pk, item.pk, fingerprint)
    item.refresh_from_db()
    assert item.state == Communication.State.DRAFT
    assert item.published_at is None
    assert item.sender_name == ""
    assert not Notification.objects.exists()
    assert not CommunicationDelivery.objects.exists()
    assert not AuditLog.objects.filter(action="PUBLICAR").exists()
    assert AuditLog.objects.filter(action="CREAR").count() == 1


@pytest.mark.parametrize("location", ["link", "audience"])
def test_booking_link_must_belong_to_tenant_and_targets_only_its_customer(world, location):
    client = _api(world.owner_a, world.a)
    for booking, expected in ((world.booking_b, 400), (world.booking_a, 201)):
        payload = _payload()
        if location == "link":
            payload["reserva_id"] = booking.pk
        else:
            payload["audiencia"]["reserva_id"] = booking.pk
        response = _post(client, "communications", payload)
        assert response.status_code == expected, response.content
        if expected == 201:
            draft = response.json()
            _, preview = _publish(client, draft)
            assert [u["id"] for u in preview["destinatarios"]] == [world.customer_a.pk]
            if location == "link":
                assert Notification.objects.get().data["reserva_id"] == world.booking_a.pk


def test_conflicting_link_and_audience_booking_are_rejected(world):
    another = _booking(world.dual, world.a, world.currency)
    payload = _payload(reserva_id=another.pk)
    payload["reserva_id"] = world.booking_a.pk
    response = _post(_api(world.owner_a, world.a), "communications", payload)
    assert response.status_code == 400
    assert not Communication.objects.exists()


def test_departure_scope_filters_real_booking_details(world):
    country = Country.objects.create(iso_code="BOL", name="Bolivia")
    city = City.objects.create(country=country, name="Santa Cruz")
    product_type = ProductType.objects.create(code="TOUR", name="Tour")
    slots = []
    for tenant in (world.a, world.b):
        product = TourismProduct.objects.create(
            tenant=tenant, city=city, currency=world.currency, product_type=product_type,
            code="TOUR-1", name="Tour", base_price="100.00", max_capacity=10, status="PUBLICADO",
        )
        slots.append(Availability.objects.create(
            tenant=tenant, product=product, start=timezone.now() + timedelta(days=1),
            end=timezone.now() + timedelta(days=2), total_capacity=10,
        ))
    BookingDetail.objects.create(
        booking=world.booking_a, tenant=world.a, slot=slots[0], quantity=1, unit_price="100.00",
    )
    client = _api(world.owner_a, world.a)
    preview = _preview(client, _payload(salida_id=slots[0].pk))
    assert [u["id"] for u in preview["destinatarios"]] == [world.customer_a.pk]
    assert _post(client, "communication-audience", _payload(salida_id=slots[1].pk)).status_code == 403


@pytest.mark.parametrize("audience", [{"grupo": "CLIENTES"}, {"reserva_id": "booking"}])
def test_internal_notices_cannot_target_customers_or_bookings(world, audience):
    audience = {key: world.booking_a.pk if value == "booking" else value for key, value in audience.items()}
    response = _post(_api(world.owner_a, world.a), "communication-audience", _payload("INTERNA", **audience))
    assert response.status_code == 400


def test_notification_owner_only_can_list_and_mark_read_and_counts_follow(world):
    sender = _api(world.owner_a, world.a)
    draft = _draft(sender, _payload("INTERNA", "USUARIOS", usuario_ids=[world.employee.pk, world.dual.pk]))
    _publish(sender, draft)
    own = Notification.objects.get(user=world.employee)
    other = Notification.objects.get(user=world.dual)
    recipient = _api(world.employee)
    listing = recipient.get(reverse("notification-list")).json()
    assert listing["count"] == 1
    assert [row["id"] for row in listing["results"]] == [own.pk]
    assert recipient.get(reverse("notification-unread")).json() == {"no_leidas": 1}
    assert _post(recipient, "notification-read", {}, pk=other.pk).status_code == 404
    first = _post(recipient, "notification-read", {}, pk=own.pk)
    assert first.status_code == 200 and first.json()["leida"] is True
    own.refresh_from_db()
    read_at = own.read_at
    assert _post(recipient, "notification-read", {}, pk=own.pk).status_code == 200
    own.refresh_from_db()
    assert own.read_at == read_at
    assert recipient.get(reverse("notification-unread")).json() == {"no_leidas": 0}
    assert sender.get(reverse("communication-detail", kwargs={"pk": draft["id"]})).json()["leidas"] == 1
    assert _post(recipient, "notification-read-all", {}).status_code == 204
    other.refresh_from_db()
    assert other.read_at is None


def test_permission_migration_seeds_system_roles_idempotently(world):
    migration = importlib.import_module("apps.notifications.migrations.0005_communications_permission")
    executor = MigrationExecutor(connection)
    historical = executor.loader.project_state([
        ("notifications", "0005_communications_permission"),
    ]).apps
    # El escenario ya contiene un permiso delegado: no debe perderse.
    with connection.schema_editor() as editor:
        migration.seed_permission(historical, editor)
        migration.seed_permission(historical, editor)
    assert Permission.objects.filter(code=communications.PERMISSION).count() == 1
    assert set(RolePermission.objects.filter(permission=world.permission).values_list("role__code", flat=True)) == {
        "TENANT_ADMIN", "SUPER_ADMIN", "COMUNICADOR", "SOPORTE",
    }
    assert not RolePermission.objects.filter(role=world.employee_role).exists()


@pytest.mark.parametrize("configured", [False, True])
def test_public_web_push_config_exposes_only_public_values(world, monkeypatch, settings, configured):
    public = {
        "FIREBASE_WEB_API_KEY": "public-api-key", "FIREBASE_WEB_AUTH_DOMAIN": "public.example.test",
        "FIREBASE_WEB_PROJECT_ID": "public-project", "FIREBASE_WEB_MESSAGING_SENDER_ID": "123456",
        "FIREBASE_WEB_APP_ID": "public-app", "FIREBASE_WEB_VAPID_KEY": "public-vapid",
    }
    for key, value in public.items():
        setattr(settings, key, value)
    settings.FIREBASE_SERVICE_ACCOUNT_JSON = "private-service-account-must-not-leak"
    monkeypatch.setattr(push, "is_configured", lambda: configured)
    response = _api().get(reverse("web-push-config"))
    assert response.status_code == 200
    result = response.json()
    assert set(result) == {"habilitado", "firebase", "vapid_key"}
    assert result["habilitado"] is configured
    assert result["firebase"] == ({
        "apiKey": "public-api-key", "authDomain": "public.example.test", "projectId": "public-project",
        "messagingSenderId": "123456", "appId": "public-app",
    } if configured else {})
    assert result["vapid_key"] == ("public-vapid" if configured else "")
    assert "private-service-account" not in response.content.decode()


# Segunda entrega: consentimiento, cuotas y programación.

def _campaign(world, *, scheduled=False, user=None):
    payload = _payload("PROMOCIONAL", "USUARIOS", usuario_ids=[(user or world.customer_a).pk])
    payload["vence_en"] = timezone.now() + timedelta(days=2)
    if scheduled:
        payload["programado_en"] = timezone.now() + timedelta(hours=1)
    return payload


def test_promotions_require_explicit_consent_without_affecting_operational(world):
    from apps.notifications import marketing
    payload = _campaign(world)
    assert communications.preview(world.owner_a, world.a.pk, payload)["total"] == 0
    marketing.set_preference(world.customer_a, world.a.pk, True)
    assert communications.preview(world.owner_a, world.a.pk, payload)["total"] == 1
    marketing.set_preference(world.customer_a, world.a.pk, False)
    assert communications.preview(world.owner_a, world.a.pk, payload)["total"] == 0
    assert communications.preview(world.owner_a, world.a.pk, _payload("OPERATIVA", "CLIENTES"))["total"] == 2


def test_preferences_api_cannot_modify_another_user_or_subscribe_to_unrelated_company(world):
    api = _api(world.customer_a)
    response = api.patch(reverse("communication-preferences"), {"empresa_id": world.b.pk, "promociones": True}, format="json")
    assert response.status_code == 404
    response = api.patch(reverse("communication-preferences"), {"empresa_id": world.a.pk, "promociones": True, "usuario_id": world.customer_b.pk}, format="json")
    assert response.status_code == 200
    assert CommunicationPreference.objects.get(user=world.customer_a, tenant=world.a).promotions_enabled
    assert not CommunicationPreference.objects.filter(user=world.customer_b).exists()
    assert _api().get(reverse("communication-preferences")).status_code == 401


def test_promotional_frequency_budget_does_not_apply_to_operational(world):
    from apps.notifications import marketing
    marketing.set_preference(world.customer_a, world.a.pk, True)
    payload = _campaign(world)
    item = communications.save(world.owner_a, world.a.pk, payload)
    fingerprint = communications.preview(world.owner_a, world.a.pk, payload)["huella"]
    communications.publish(world.owner_a, world.a.pk, item.pk, fingerprint)
    assert Notification.objects.filter(user=world.customer_a, data__tipo_comunicacion="PROMOCIONAL").count() == 1
    assert communications.preview(world.owner_a, world.a.pk, payload)["total"] == 0
    assert communications.preview(world.owner_a, world.a.pk, _payload("OPERATIVA", "CLIENTES"))["total"] == 2


def test_global_promotions_have_separate_consent_and_shared_total_budget(world, settings):
    from apps.notifications import marketing
    settings.COMMUNICATION_PROMOTIONS_PER_DAY = 1
    marketing.set_preference(world.customer_a, world.a.pk, True)
    marketing.set_preference(world.customer_a, None, True)
    payload = _campaign(world)
    item = communications.save(world.owner_a, world.a.pk, payload)
    communications.publish(world.owner_a, world.a.pk, item.pk, communications.preview(world.owner_a, world.a.pk, payload)["huella"])
    assert communications.preview(world.superadmin, None, payload)["total"] == 0
    assert CommunicationPreference.objects.filter(user=world.customer_a).count() == 2


def test_scheduled_campaign_has_no_early_notification_and_is_idempotent(world, monkeypatch):
    from apps.notifications import campaigns, marketing
    marketing.set_preference(world.customer_a, world.a.pk, True)
    payload = _campaign(world, scheduled=True)
    item = communications.save(world.owner_a, world.a.pk, payload)
    fp = communications.preview(world.owner_a, world.a.pk, payload)["huella"]
    communications.publish(world.owner_a, world.a.pk, item.pk, fp)
    communications.publish(world.owner_a, world.a.pk, item.pk, fp)
    assert item.deliveries.get().notification_id is None
    assert campaigns.process_due_campaigns() == 0
    monkeypatch.setattr(timezone, "now", lambda: payload["programado_en"] + timedelta(seconds=1))
    assert campaigns.process_due_campaigns() == 1
    assert campaigns.process_due_campaigns() == 0
    item.refresh_from_db()
    assert item.state == "PUBLICADA"
    assert item.deliveries.get().notification.user_id == world.customer_a.pk
    assert Notification.objects.filter(user=world.customer_a).count() == 1


def test_scheduled_dispatch_respects_withdrawn_consent(world, monkeypatch):
    from apps.notifications import campaigns, marketing
    marketing.set_preference(world.customer_a, world.a.pk, True)
    payload = _campaign(world, scheduled=True)
    item = communications.save(world.owner_a, world.a.pk, payload)
    communications.publish(world.owner_a, world.a.pk, item.pk, communications.preview(world.owner_a, world.a.pk, payload)["huella"])
    marketing.set_preference(world.customer_a, world.a.pk, False)
    monkeypatch.setattr(timezone, "now", lambda: payload["programado_en"] + timedelta(seconds=1))
    campaigns.process_due_campaigns()
    assert item.deliveries.get().push_status == "OMITIDO"
    assert not Notification.objects.filter(user=world.customer_a).exists()


def test_expired_scheduled_campaign_never_creates_notifications(world, monkeypatch):
    from apps.notifications import campaigns
    payload = _payload("OPERATIVA", "CLIENTES")
    payload["programado_en"] = timezone.now() + timedelta(hours=1)
    payload["vence_en"] = timezone.now() + timedelta(hours=2)
    item = communications.save(world.owner_a, world.a.pk, payload)
    communications.publish(world.owner_a, world.a.pk, item.pk, communications.preview(world.owner_a, world.a.pk, payload)["huella"])
    monkeypatch.setattr(timezone, "now", lambda: payload["vence_en"] + timedelta(seconds=1))
    campaigns.process_due_campaigns()
    item.refresh_from_db()
    assert item.state == "VENCIDA"
    assert set(item.deliveries.values_list("push_status", flat=True)) == {"VENCIDO"}
    assert not Notification.objects.exists()


def test_cancelling_scheduled_campaign_is_scoped_and_idempotent(world, monkeypatch):
    from apps.notifications import campaigns
    payload = _payload("OPERATIVA", "CLIENTES")
    payload["programado_en"] = timezone.now() + timedelta(hours=1)
    item = communications.save(world.owner_a, world.a.pk, payload)
    communications.publish(world.owner_a, world.a.pk, item.pk, communications.preview(world.owner_a, world.a.pk, payload)["huella"])
    assert _api(world.owner_b, world.b).post(reverse("communication-cancel", kwargs={"pk": item.pk}), {}, format="json").status_code == 404
    api = _api(world.owner_a, world.a)
    for _ in range(2):
        assert api.post(reverse("communication-cancel", kwargs={"pk": item.pk}), {}, format="json").json()["estado"] == "CANCELADA"
    monkeypatch.setattr(timezone, "now", lambda: payload["programado_en"] + timedelta(seconds=1))
    assert campaigns.process_due_campaigns() == 0
    assert not Notification.objects.exists()


def test_scheduled_sender_losing_permission_requires_review(world, monkeypatch):
    from apps.notifications import campaigns
    payload = _payload("OPERATIVA", "CLIENTES")
    payload["programado_en"] = timezone.now() + timedelta(hours=1)
    item = communications.save(world.manager, world.a.pk, payload)
    communications.publish(world.manager, world.a.pk, item.pk, communications.preview(world.manager, world.a.pk, payload)["huella"])
    RolePermission.objects.filter(role=world.local_role).delete()
    monkeypatch.setattr(timezone, "now", lambda: payload["programado_en"] + timedelta(seconds=1))
    campaigns.process_due_campaigns()
    item.refresh_from_db()
    assert item.state == "REVISION"
    assert not Notification.objects.exists()


def test_unsuscribed_or_expired_queued_push_is_suppressed(world, monkeypatch):
    from apps.notifications import marketing, outbox
    marketing.set_preference(world.customer_a, world.a.pk, True)
    payload = _campaign(world)
    item = communications.save(world.owner_a, world.a.pk, payload)
    communications.publish(world.owner_a, world.a.pk, item.pk, communications.preview(world.owner_a, world.a.pk, payload)["huella"])
    marketing.set_preference(world.customer_a, world.a.pk, False)
    assert outbox.process_pending_push() == 1
    assert item.deliveries.get().push_status == "DESUSCRITO"
    assert item.deliveries.get().attempts == 1


@pytest.mark.parametrize("field,offset", [("programado_en", -1), ("vence_en", -1)])
def test_campaign_rejects_past_dates(world, field, offset):
    from rest_framework.exceptions import ValidationError
    payload = _payload("OPERATIVA")
    payload[field] = timezone.now() + timedelta(hours=offset)
    with pytest.raises(ValidationError):
        communications.save(world.owner_a, world.a.pk, payload)


def test_marketing_without_expiry_or_with_foreign_promotion_is_rejected(world):
    from rest_framework.exceptions import ValidationError
    payload = _payload("PROMOCIONAL")
    with pytest.raises(ValidationError):
        communications.save(world.owner_a, world.a.pk, payload)
    payload["vence_en"] = timezone.now() + timedelta(days=2)
    payload["promocion_id"] = 999999
    with pytest.raises(ValidationError):
        communications.save(world.owner_a, world.a.pk, payload)


def _email_campaign(world, *, promotional=False):
    client = _api(world.owner_a, world.a)
    payload = _payload("PROMOCIONAL" if promotional else "OPERATIVA", "USUARIOS", usuario_ids=[world.customer_a.pk])
    payload.update(titulo="Hola, {{nombre}}", mensaje="Tu experiencia con {{empresa}} está cerca.")
    if promotional:
        from apps.notifications.marketing import set_preference
        set_preference(world.customer_a, world.a.pk, True)
        payload["vence_en"] = (timezone.now() + timedelta(days=1)).isoformat()
    draft = _draft(client, payload)
    assert not CommunicationEmail.objects.exists()
    published, _ = _publish(client, draft)
    row = CommunicationEmail.objects.get(delivery__communication_id=published["id"])
    return client, published, row


def test_notification_and_email_are_created_together_only_when_publishing(world):
    _, published, row = _email_campaign(world)
    assert published["enviar_correo"] is True
    assert published["correos_pendientes"] == 1
    assert published["correos_aceptados"] == 0
    assert row.recipient_email == world.customer_a.email
    assert row.attempts == 0
    assert row.delivery.notification.title == "Hola, customer_a"
    assert row.delivery.notification.message == "Tu experiencia con Empresa A está cerca."


def test_legacy_clients_cannot_disable_the_email_included_in_publication(world):
    client = _api(world.owner_a, world.a)
    draft = _draft(client)
    preview = _preview(client, draft)
    changed = {**draft, "enviar_correo": False}
    response = client.patch(reverse("communication-detail", kwargs={"pk": draft["id"]}), changed, format="json")
    assert response.status_code == 200
    assert response.json()["enviar_correo"] is True
    response = _post(client, "communication-publish", {"huella": preview["huella"]}, pk=draft["id"])
    assert response.status_code == 200
    assert CommunicationEmail.objects.count() == CommunicationDelivery.objects.count() == 5


def test_old_draft_without_email_publishes_both_and_retry_does_not_duplicate(world):
    client = _api(world.owner_a, world.a)
    draft = _draft(client)
    Communication.objects.filter(pk=draft["id"]).update(email_enabled=False)
    item = client.get(reverse("communication-detail", kwargs={"pk": draft["id"]})).json()
    assert item["enviar_correo"] is True
    _publish(client, item)
    _publish(client, item)
    assert Communication.objects.get(pk=draft["id"]).email_enabled is True
    assert CommunicationEmail.objects.count() == CommunicationDelivery.objects.count() == Notification.objects.count() == 5


def test_notification_and_email_queues_rollback_together_on_failure(world, monkeypatch):
    client = _api(world.owner_a, world.a)
    draft = _draft(client)
    audience = _preview(client, draft)
    monkeypatch.setattr(CommunicationEmail.objects, "bulk_create", Mock(side_effect=IntegrityError("test failure")))
    with pytest.raises(IntegrityError):
        _post(client, "communication-publish", {"huella": audience["huella"]}, pk=draft["id"])
    assert Communication.objects.get(pk=draft["id"]).state == "BORRADOR"
    assert not Notification.objects.exists()
    assert not CommunicationDelivery.objects.exists()
    assert not CommunicationEmail.objects.exists()


def test_joint_delivery_migration_preserves_published_history_and_queues_no_email(world):
    from django.apps import apps
    migration = importlib.import_module("apps.notifications.migrations.0010_communication_joint_delivery")
    client = _api(world.owner_a, world.a)
    draft = _draft(client)
    historical = _draft(client)
    Communication.objects.filter(pk__in=[draft["id"], historical["id"]]).update(email_enabled=False)
    Communication.objects.filter(pk=historical["id"]).update(state="PUBLICADA")
    with connection.schema_editor() as editor:
        migration.enable_future_deliveries(apps, editor)
    assert Communication.objects.get(pk=draft["id"]).email_enabled is True
    old = Communication.objects.get(pk=historical["id"])
    assert old.email_enabled is False
    assert communications.as_dict(old)["enviar_correo"] is False
    assert not CommunicationEmail.objects.exists()


def test_email_preview_is_scoped_escaped_and_does_not_enqueue(world):
    client = _api(world.owner_a, world.a)
    draft = _draft(client, {**_payload(), "mensaje": '<script>alert(1)</script> {{nombre}}'})
    url = reverse("communication-email-preview", kwargs={"pk": draft["id"]})
    result = client.get(url)
    assert result.status_code == 200
    html = result.json()["html"]
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "owner_a" in html
    assert not CommunicationEmail.objects.exists()
    assert _api(world.owner_b, world.b).get(url).status_code == 404
    assert _api(world.customer_a).get(url).status_code == 403


def test_email_acceptance_is_independent_of_push_and_read(world, monkeypatch):
    from apps.notifications import email_outbox
    client, published, row = _email_campaign(world)
    sender = Mock(return_value=(None, "provider-123"))
    monkeypatch.setattr(email_outbox, "send_one", sender)
    monkeypatch.setattr(email_outbox.brevo, "is_configured", lambda: True)
    assert email_outbox.process_pending_email() == 1
    row.refresh_from_db()
    assert row.status == "ACEPTADO"
    assert row.provider_id == "provider-123"
    assert row.accepted_at is not None
    assert row.first_attempt_at is not None
    assert email_outbox.process_pending_email() == 0
    sender.assert_called_once()
    metrics = client.get(reverse("communication-detail", kwargs={"pk": published["id"]})).json()
    assert metrics["correos_aceptados"] == 1
    assert metrics["push_pendientes"] == 1
    assert metrics["leidas"] == 0


@pytest.mark.parametrize("failure", ["NOT_CONFIGURED", "CONNECTION_ERROR", "HTTP_429", "HTTP_500"])
def test_email_retries_are_bounded_and_keep_same_idempotency_key(world, monkeypatch, failure):
    from apps.notifications import email_outbox
    _, _, row = _email_campaign(world)
    sender = Mock(return_value=(failure, ""))
    monkeypatch.setattr(email_outbox, "send_one", sender)
    monkeypatch.setattr(email_outbox.brevo, "is_configured", lambda: failure != "NOT_CONFIGURED")
    clock = [timezone.now()]
    monkeypatch.setattr(email_outbox.timezone, "now", lambda: clock[0])
    key = row.idempotency_key
    for attempt in range(1, 6):
        assert email_outbox.process_pending_email() == 1
        row.refresh_from_db()
        assert row.attempts == attempt
        assert row.idempotency_key == key
        assert row.status == ("PENDIENTE" if attempt < 5 else "FALLIDO")
        assert row.accepted_at is None
        if attempt < 5:
            assert email_outbox.process_pending_email() == 0
            clock[0] = row.next_attempt_at
    assert sender.call_count == 5
    assert email_outbox.process_pending_email() == 0


@pytest.mark.parametrize("reason", ["DESUSCRITO", "VENCIDO", "RECIPIENT_CHANGED"])
def test_email_revalidates_consent_expiration_and_address_before_sending(world, monkeypatch, reason):
    from apps.notifications import email_outbox, marketing
    _, _, row = _email_campaign(world, promotional=reason == "DESUSCRITO")
    if reason == "DESUSCRITO":
        marketing.set_preference(world.customer_a, world.a.pk, False)
    elif reason == "RECIPIENT_CHANGED":
        User.objects.filter(pk=world.customer_a.pk).update(email="new@communications.test")
    else:
        notification = row.delivery.notification
        notification.data["vence_en"] = (timezone.now() - timedelta(seconds=1)).isoformat()
        notification.save(update_fields=("data",))
    sender = Mock()
    monkeypatch.setattr(email_outbox, "send_one", sender)
    email_outbox.process_pending_email()
    row.refresh_from_db()
    assert (row.status, row.last_error) == ("OMITIDO", reason)
    sender.assert_not_called()


def test_email_does_not_reclaim_live_lease_or_retry_outside_provider_window(world, monkeypatch):
    from apps.notifications import email_outbox
    _, _, row = _email_campaign(world)
    sender = Mock()
    monkeypatch.setattr(email_outbox, "send_one", sender)
    CommunicationEmail.objects.filter(pk=row.pk).update(locked_until=timezone.now() + timedelta(minutes=2))
    assert email_outbox.process_pending_email() == 0
    CommunicationEmail.objects.filter(pk=row.pk).update(locked_until=None, first_attempt_at=timezone.now() - timedelta(minutes=31))
    email_outbox.process_pending_email()
    row.refresh_from_db()
    assert (row.status, row.last_error) == ("REVISION", "PROVIDER_WINDOW_EXPIRED")
    sender.assert_not_called()


def test_email_provider_duplicate_requires_review_instead_of_claiming_delivery(world, monkeypatch):
    from apps.notifications import email_outbox
    _, _, row = _email_campaign(world)
    monkeypatch.setattr(email_outbox, "send_one", Mock(return_value=("PROVIDER_DUPLICATE", "")))
    email_outbox.process_pending_email()
    row.refresh_from_db()
    assert row.status == "REVISION"
    assert row.accepted_at is None


def test_email_html_and_plain_text_include_scoped_unsubscribe(world):
    from apps.notifications.email_content import build_email
    _, published, row = _email_campaign(world, promotional=True)
    item = Communication.objects.get(pk=published["id"])
    content = build_email(item, row.delivery.notification, world.customer_a)
    assert "Dejar de recibir promociones" in content["html"]
    assert content["unsubscribe"] in content["text"]
    assert "customer_a@" not in content["unsubscribe"]
    assert "Empresa A" in content["html"]


def test_unsubscribe_get_does_not_change_consent_and_signed_post_only_affects_sender(world):
    from urllib.parse import urlparse

    from apps.notifications import marketing
    from apps.notifications.email_content import unsubscribe_url
    marketing.set_preference(world.customer_a, world.a.pk, True)
    marketing.set_preference(world.customer_a, None, True)
    path = urlparse(unsubscribe_url(world.customer_a.pk, world.a.pk)).path
    visitor = _api()
    assert visitor.get(path).status_code == 200
    assert CommunicationPreference.objects.get(user=world.customer_a, tenant=world.a).promotions_enabled
    assert visitor.post(path).status_code == 200
    assert visitor.post(path).status_code == 200
    assert not CommunicationPreference.objects.get(user=world.customer_a, tenant=world.a).promotions_enabled
    assert CommunicationPreference.objects.get(user=world.customer_a, tenant=None).promotions_enabled
    altered = path.rstrip("/") + "tamper/"
    assert visitor.post(altered).status_code == 400


def test_filtered_options_exclude_global_and_foreign_roles_and_people(world):
    client = _api(world.superadmin)
    result = client.get(reverse("communication-options"), {"empresa_ids": str(world.a.pk), "grupo": "PERSONAL"})
    assert result.status_code == 200
    data = result.json()
    assert world.employee.pk in {u["id"] for u in data["usuarios"]}
    assert world.owner_b.pk not in {u["id"] for u in data["usuarios"]}
    assert all(r["ambito"] == "TENANT" for r in data["roles"])
    assert world.foreign_role.pk not in {r["id"] for r in data["roles"]}
    assert world.customer_a.pk not in {u["id"] for u in data["usuarios"]}


def test_list_summary_and_filters_are_scoped_to_tenant(world):
    client = _api(world.owner_a, world.a)
    draft = _draft(client)
    _draft(_api(world.owner_b, world.b))
    _draft(client, {**_payload(), "titulo": "Salida al salar"})
    result = client.get(reverse("communications"), {"buscar": "salar", "estado": "BORRADOR"}).json()
    assert result["count"] == 1
    assert result["results"][0]["titulo"] == "Salida al salar"
    assert result["resumen"]["BORRADOR"] == 2
    assert result["results"][0]["id"] != draft["id"]


def test_scheduled_email_is_only_queued_when_campaign_is_dispatched(world, monkeypatch):
    from apps.notifications import campaigns
    client = _api(world.owner_a, world.a)
    send_at = timezone.now() + timedelta(hours=1)
    draft = _draft(client, {**_payload(), "enviar_correo": True, "programado_en": send_at.isoformat()})
    published, _ = _publish(client, draft)
    assert published["estado"] == "PROGRAMADA"
    assert not CommunicationEmail.objects.exists()
    monkeypatch.setattr(campaigns.timezone, "now", lambda: send_at + timedelta(seconds=1))
    assert campaigns.process_due_campaigns() == 1
    assert CommunicationEmail.objects.count() == CommunicationDelivery.objects.filter(communication_id=draft["id"]).count()
    assert CommunicationEmail.objects.filter(delivery__notification__isnull=True).count() == 0


def test_brevo_contract_has_one_recipient_and_stable_idempotency(world, monkeypatch, settings):
    import json
    from io import BytesIO

    from apps.notifications import email_outbox
    from apps.notifications.email_content import build_email
    _, published, row = _email_campaign(world)
    settings.BREVO_API_KEY = "fake-key-test"
    settings.BREVO_SENDER_EMAIL = "sender@situr.test"
    settings.BREVO_SENDER_NAME = "SITUR"
    response = BytesIO(b'{"messageId":"accepted-id"}')
    transport = Mock(return_value=response)
    monkeypatch.setattr(email_outbox.urllib.request, "urlopen", transport)
    content = build_email(Communication.objects.get(pk=published["id"]), row.delivery.notification, world.customer_a)
    assert email_outbox.send_one(row, content, world.customer_a) == (None, "accepted-id")
    request = transport.call_args.args[0]
    payload = json.loads(request.data)
    assert len(payload["to"]) == 1
    assert payload["to"][0]["email"] == row.recipient_email
    assert payload["headers"] == {"idempotencyKey": str(row.idempotency_key)}
    assert payload["htmlContent"] == content["html"]
    assert payload["textContent"] == content["text"]
    assert transport.call_args.kwargs["timeout"] == 10


def test_unconfigured_provider_never_attempts_network(world, monkeypatch):
    from apps.notifications import email_outbox
    _, _, row = _email_campaign(world)
    monkeypatch.setattr(email_outbox.brevo, "is_configured", lambda: False)
    transport = Mock()
    monkeypatch.setattr(email_outbox.urllib.request, "urlopen", transport)
    assert email_outbox.send_one(row, {}, world.customer_a) == ("NOT_CONFIGURED", "")
    transport.assert_not_called()
