"""Consentimiento y cuotas concurrentes contra PostgreSQL, sin Firebase real."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.db import connections
from rest_framework.exceptions import APIException

from apps.accounts.models import CustomerProfile
from apps.audit.models import AuditLog
from apps.bookings.models import Booking, Order
from apps.catalog.models import Currency
from apps.notifications import campaigns, communications, marketing, outbox
from apps.notifications.communication_views import validated
from apps.notifications.models import (
    Communication,
    CommunicationPreference,
    Notification,
)
from apps.rbac.models import UserRole

from .test_communication_push import cola_pg  # noqa: F401


@pytest.fixture
def campaign_pg(request):
    q = request.getfixturevalue("cola_pg")
    owner = UserRole.objects.select_related("user", "tenant").filter(
        role__code="TENANT_ADMIN", user__status="ACTIVO", tenant__status="ACTIVO",
    ).first()
    order = Order.objects.create(customer=CustomerProfile.objects.get(user=q.user), code=f"CAM-{uuid4().hex}")
    booking = Booking.objects.create(order=order, tenant=owner.tenant, currency=Currency.objects.first(),
                                     code=f"CAM-{uuid4().hex[:12]}", status="CONFIRMADA")
    item_ids = []
    old = CommunicationPreference.objects.filter(user=q.user, tenant=owner.tenant).first()
    old_value = old.promotions_enabled if old else None
    marketing.set_preference(q.user, owner.tenant_id, True)

    def draft(*, scheduled=False):
        payload = validated({"titulo": "Oferta PG", "mensaje": "Oferta de prueba local.", "tipo": "PROMOCIONAL",
            "audiencia": {"grupo": "USUARIOS", "usuario_ids": [q.user.pk]},
            "programado_en": q.clock[0] + timedelta(hours=1) if scheduled else None,
            "vence_en": q.clock[0] + timedelta(days=2)})
        item = communications.save(owner.user, owner.tenant_id, payload)
        item_ids.append(item.pk)
        fp = communications.preview(owner.user, owner.tenant_id, payload)["huella"]
        return item, fp

    try:
        yield SimpleNamespace(queue=q, owner=owner, draft=draft)
    finally:
        notice_ids = list(Notification.objects.filter(data__comunicacion_id__in=item_ids).values_list("pk", flat=True))
        Communication.objects.filter(pk__in=item_ids).delete()
        Notification.objects.filter(pk__in=notice_ids).delete()
        AuditLog.objects.filter(entity="comunicacion", entity_id__in=[str(pk) for pk in item_ids]).delete()
        if old_value is None:
            CommunicationPreference.objects.filter(user=q.user, tenant=owner.tenant).delete()
        else:
            CommunicationPreference.objects.filter(user=q.user, tenant=owner.tenant).update(promotions_enabled=old_value)
        booking.delete()
        order.delete()


def test_two_simultaneous_publications_cannot_exceed_sender_budget(campaign_pg):
    ctx = campaign_pg
    drafts = [ctx.draft(), ctx.draft()]
    barrier = Barrier(2)

    def publish(pair):
        try:
            barrier.wait(timeout=10)
            try:
                communications.publish(ctx.owner.user, ctx.owner.tenant_id, pair[0].pk, pair[1])
                return 200
            except APIException as exc:
                return exc.status_code
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(publish, drafts))
    assert 200 in results
    assert set(results) <= {200, 409}
    assert Notification.objects.filter(data__comunicacion_id__in=[d.pk for d, _ in drafts]).count() == 1


def test_scheduled_dispatch_rechecks_consent_and_keeps_inbox_empty(campaign_pg):
    ctx = campaign_pg
    item, fp = ctx.draft(scheduled=True)
    communications.publish(ctx.owner.user, ctx.owner.tenant_id, item.pk, fp)
    assert not Notification.objects.filter(data__comunicacion_id=item.pk).exists()
    marketing.set_preference(ctx.queue.user, ctx.owner.tenant_id, False)
    ctx.queue.clock[0] = item.scheduled_at + timedelta(seconds=1)
    assert campaigns.process_due_campaigns() == 1
    assert item.deliveries.get().push_status == "OMITIDO"
    assert not Notification.objects.filter(data__comunicacion_id=item.pk).exists()


def test_unsubscribe_before_worker_prevents_real_queued_push(campaign_pg):
    ctx = campaign_pg
    item, fp = ctx.draft()
    communications.publish(ctx.owner.user, ctx.owner.tenant_id, item.pk, fp)
    ctx.queue.device()
    marketing.set_preference(ctx.queue.user, ctx.owner.tenant_id, False)
    outbox.process_pending_push()
    assert item.deliveries.get().push_status == "DESUSCRITO"
    assert ctx.queue.firebase.enviados == []


def test_expired_push_never_reaches_firebase(campaign_pg):
    ctx = campaign_pg
    item, fp = ctx.draft()
    communications.publish(ctx.owner.user, ctx.owner.tenant_id, item.pk, fp)
    ctx.queue.device()
    ctx.queue.clock[0] = item.expires_at + timedelta(seconds=1)
    outbox.process_pending_push()
    assert item.deliveries.get().push_status == "VENCIDO"
    assert ctx.queue.firebase.enviados == []
