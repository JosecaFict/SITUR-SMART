"""SQL legacy + migraciones 0004/0005: ACL, deduplicacion y atomicidad reales.

Usa exclusivamente django_db_setup de integracion/conftest.py, que crea una
base nueva situr_smart_pruebas*. No ejecuta migrate contra la base principal.
"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.recorder import MigrationRecorder
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.accounts.models import CustomerProfile, User
from apps.audit.models import AuditLog
from apps.bookings.models import Booking, BookingState, Order
from apps.notifications import communications, push
from apps.notifications.communication_views import validated
from apps.notifications.models import (
    Communication,
    CommunicationDelivery,
    Notification,
    PushDevice,
)
from apps.rbac.models import Permission, Role, RolePermission, UserRole
from apps.tenancy.models import UserTenant

from .datos import TURISTA, cliente, tour_publicado

pytestmark = pytest.mark.django_db(transaction=False)


@pytest.fixture(autouse=True)
def no_external_push(monkeypatch):
    guards = []
    for name in ("push_notification", "send_one", "_session"):
        guard = Mock(side_effect=AssertionError(f"Publicar no debe llamar push.{name}"))
        monkeypatch.setattr(push, name, guard)
        guards.append(guard)
    yield
    for guard in guards:
        guard.assert_not_called()


@pytest.fixture
def context():
    product = tour_publicado()
    assert product is not None, "seed_bolivia debe proporcionar un tour activo"
    assignment = UserRole.objects.select_related("user", "tenant").get(
        tenant_id=product.tenant_id, role__code="TENANT_ADMIN",
    )
    other = UserRole.objects.select_related("user", "tenant").filter(
        role__code="TENANT_ADMIN", tenant__status="ACTIVO",
    ).exclude(tenant_id=product.tenant_id).first()
    assert other is not None, "seed_bolivia debe proporcionar una segunda empresa"
    tourist = User.objects.get(email=TURISTA)
    staff_role = Role.objects.get(code="TENANT_EMPLOYEE", scope=Role.Scope.TENANT, tenant__isnull=True)
    UserTenant.objects.get_or_create(
        user=tourist, tenant=assignment.tenant, defaults={"status": UserTenant.Status.ACTIVE},
    )
    UserRole.objects.create(user=tourist, tenant=assignment.tenant, role=staff_role)
    # Misma persona: personal + cliente de dos reservas. Todas las FK y
    # restricciones corresponden al SQL legacy; no hay schema_editor auxiliar.
    profile = CustomerProfile.objects.get(user=tourist)
    bookings = []
    for index in range(2):
        order = Order.objects.create(customer=profile, code=f"COM-PG-ORDER-{index}")
        bookings.append(Booking.objects.create(
            order=order, tenant=assignment.tenant, currency=product.currency,
            code=f"COM-PG-BOOKING-{index}", status=BookingState.CONFIRMED,
        ))
    api = cliente(assignment.user.email)
    api.credentials(HTTP_X_TENANT_ID=str(assignment.tenant_id))
    other_api = cliente(other.user.email)
    other_api.credentials(HTTP_X_TENANT_ID=str(other.tenant_id))
    payload = validated({
        "titulo": "Aviso PostgreSQL", "mensaje": "Destinatario compartido sin duplicados",
        "tipo": "OPERATIVA", "audiencia": {"grupo": "USUARIOS", "usuario_ids": [tourist.pk]},
        "reserva_id": None,
    })
    return SimpleNamespace(
        actor=assignment.user, tenant=assignment.tenant, other=other, api=api, other_api=other_api,
        tourist=tourist, staff_role=staff_role, payload=payload, bookings=bookings,
    )


def _draft(ctx):
    response = ctx.api.post(reverse("communications"), ctx.payload, format="json")
    assert response.status_code == 201, response.content
    return response.json()


def _preview(ctx):
    response = ctx.api.post(reverse("communication-audience"), ctx.payload, format="json")
    assert response.status_code == 200, response.content
    assert response.json()["total"] == 1
    return response.json()


def test_legacy_schema_and_0004_0005_permission_seed_are_present(context):
    assert connection.vendor == "postgresql"
    assert connection.settings_dict["NAME"].startswith("situr_smart_pruebas")
    applied = MigrationRecorder(connection).applied_migrations()
    assert ("notifications", "0004_communication_communicationdelivery_pushattempt_and_more") in applied
    assert ("notifications", "0005_communications_permission") in applied
    assert {"usuario", "reserva", "notificacion", "comunicacion", "comunicacion_destinatario"} <= set(
        connection.introspection.table_names()
    )
    # Se consulta lo aplicado por migrate, sin volver a ejecutar el seed aqui.
    permission = Permission.objects.get(code=communications.PERMISSION)
    system_roles = Role.objects.filter(code__in=("TENANT_ADMIN", "SUPER_ADMIN"), is_system=True)
    assert set(system_roles.values_list("code", flat=True)) == {"TENANT_ADMIN", "SUPER_ADMIN"}
    assert set(RolePermission.objects.filter(permission=permission).values_list("role_id", flat=True)) == set(
        system_roles.values_list("pk", flat=True)
    )
    assert not RolePermission.objects.filter(role=context.staff_role, permission=permission).exists()


def test_publish_deduplicates_staff_customer_and_retry_with_legacy_foreign_keys(
    context, django_capture_on_commit_callbacks,
):
    ctx = context
    draft, preview = _draft(ctx), _preview(ctx)
    url = reverse("communication-publish", kwargs={"pk": draft["id"]})
    with django_capture_on_commit_callbacks(execute=True), CaptureQueriesContext(connection) as queries:
        first = ctx.api.post(url, {"huella": preview["huella"]}, format="json")
        second = ctx.api.post(url, {"huella": preview["huella"]}, format="json")
    assert first.status_code == second.status_code == 200, (first.content, second.content)
    assert any('FROM "comunicacion"' in query["sql"] and "FOR UPDATE" in query["sql"] for query in queries)
    assert first.json() == second.json()
    item = Communication.objects.get(pk=draft["id"])
    delivery = CommunicationDelivery.objects.select_related("notification").get(communication=item)
    assert item.state == Communication.State.PUBLISHED
    assert delivery.user_id == delivery.notification.user_id == ctx.tourist.pk
    assert delivery.push_status == "PENDIENTE" and delivery.attempts == 0
    assert delivery.notification.data["comunicacion_id"] == item.pk
    assert Notification.objects.filter(data__comunicacion_id=item.pk).count() == 1
    assert AuditLog.objects.filter(entity="comunicacion", entity_id=str(item.pk), action="PUBLICAR").count() == 1
    # La restriccion de la 0004 existe realmente, ademas de la deduplicacion Python.
    with pytest.raises(IntegrityError), transaction.atomic():
        CommunicationDelivery.objects.create(communication=item, user=ctx.tourist)


def test_employee_permission_and_cross_tenant_communication_acl(context):
    ctx = context
    draft = _draft(ctx)
    detail = reverse("communication-detail", kwargs={"pk": draft["id"]})
    publish = reverse("communication-publish", kwargs={"pk": draft["id"]})
    assert ctx.other_api.get(detail).status_code == 404
    assert ctx.other_api.patch(detail, {"titulo": "Otra empresa"}, format="json").status_code == 404
    assert ctx.other_api.post(publish, {"huella": "a" * 64}, format="json").status_code == 404
    employee = cliente(TURISTA)
    employee.credentials(HTTP_X_TENANT_ID=str(ctx.tenant.pk))
    assert employee.get(reverse("communications")).status_code == 403
    assert employee.post(reverse("communication-audience"), ctx.payload, format="json").status_code == 403
    # Delegacion real mediante rol_permiso: al concederlo puede trabajar aqui.
    RolePermission.objects.create(
        role=ctx.staff_role, permission=Permission.objects.get(code=communications.PERMISSION),
    )
    assert employee.post(reverse("communication-audience"), ctx.payload, format="json").status_code == 200
    employee.credentials()  # Quitar tenant no convierte el permiso en global.
    assert employee.get(reverse("communications")).status_code == 403


def test_publish_atomic_rollback_after_actual_postgresql_unique_violation(context, monkeypatch):
    ctx = context
    item = communications.save(ctx.actor, ctx.tenant.pk, ctx.payload)
    fingerprint = communications.preview(ctx.actor, ctx.tenant.pk, ctx.payload)["huella"]
    original = CommunicationDelivery.objects.bulk_create

    def duplicate_after_first_write(objects, **kwargs):
        original(objects[:1], **kwargs)
        # Primera entrega ya escrita; la segunda falla en la restriccion real
        # de PostgreSQL. La publicacion debe revertir tambien las notificaciones.
        CommunicationDelivery.objects.create(communication=item, user=ctx.tourist)

    monkeypatch.setattr(CommunicationDelivery.objects, "bulk_create", duplicate_after_first_write)
    with pytest.raises(IntegrityError):
        communications.publish(ctx.actor, ctx.tenant.pk, item.pk, fingerprint)
    item.refresh_from_db()
    assert item.state == Communication.State.DRAFT
    assert item.published_at is None
    assert item.sender_name == ""
    assert not CommunicationDelivery.objects.filter(communication=item).exists()
    assert not Notification.objects.filter(data__comunicacion_id=item.pk).exists()
    assert not AuditLog.objects.filter(entity="comunicacion", entity_id=str(item.pk), action="PUBLICAR").exists()
    assert AuditLog.objects.filter(entity="comunicacion", entity_id=str(item.pk), action="CREAR").count() == 1


def test_web_device_passes_real_0006_platform_check(context):
    response = cliente(TURISTA).post(
        reverse("push-device"), {"token": "comunicaciones-web-pg", "plataforma": "WEB"}, format="json",
    )
    assert response.status_code == 204, response.content
    assert PushDevice.objects.get(token="comunicaciones-web-pg").platform == "WEB"
