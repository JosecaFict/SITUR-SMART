"""Ciclo de vida del plan de una empresa (SaaS), contra PostgreSQL real.

Stripe y Brevo se reemplazan: se prueba la vigencia, los avisos, la renovacion,
el vencimiento con su restriccion y el pago de la renovacion.
"""

import hashlib
import hmac
import json
import time
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.catalog import services as catalog
from apps.catalog.models import TourismProduct
from apps.tenancy import subscriptions
from apps.tenancy.models import Plan, Subscription, SubscriptionPayment, UserTenant
from apps.tenancy.services import change_company_subscription

from .datos import WEBHOOK_SECRET, cliente

pytestmark = pytest.mark.django_db(transaction=False)

SUPERADMIN = "superadmin@situr.com.bo"
DUENO = "jefeadmin@hotelcortez.com.bo"
EMPLEADO = "empleado1@hotelcortez.com.bo"
URL = "/api/v1/empresa/mi-plan/"


@pytest.fixture
def correos(monkeypatch):
    enviados = []
    monkeypatch.setattr(subscriptions, "send_email", lambda **kwargs: enviados.append(kwargs) or True)
    return enviados


def _empresa():
    return UserTenant.objects.select_related("tenant").get(user__email=DUENO).tenant


def _plan_activo(tenant) -> Subscription:
    return Subscription.objects.select_related("plan").get(tenant=tenant, status="ACTIVA")


def _vence_en(dias: int, *, automatica=False) -> Subscription:
    suscripcion = _plan_activo(_empresa())
    suscripcion.end_date = timezone.localdate() + timedelta(days=dias)
    suscripcion.auto_renew = automatica
    suscripcion.save(update_fields=["end_date", "auto_renew"])
    return suscripcion


def _api(email=DUENO):
    api = cliente(email)
    api.credentials(HTTP_X_TENANT_ID=str(_empresa().id))
    return api


def _webhook_plan(session_id: str):
    payload = json.dumps({
        "id": "evt_plan",
        "object": "event",
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": session_id, "object": "checkout.session", "payment_status": "paid",
            "metadata": {"tipo": "SUSCRIPCION"},
        }},
    })
    timestamp = int(time.time())
    firma = hmac.new(WEBHOOK_SECRET.encode(), f"{timestamp}.{payload}".encode(), hashlib.sha256).hexdigest()
    return APIClient().post(
        "/api/v1/pagos/stripe/webhook/", data=payload, content_type="application/json",
        HTTP_STRIPE_SIGNATURE=f"t={timestamp},v1={firma}",
    )


def test_las_suscripciones_existentes_recibieron_su_fecha_de_fin():
    activas = Subscription.objects.filter(status="ACTIVA")
    assert activas.exists()
    assert not activas.filter(end_date=None).exists()
    assert not activas.filter(end_date__lte=timezone.localdate()).exists()


def test_un_plan_nuevo_vence_segun_su_periodicidad():
    superadmin = User.objects.get(email=SUPERADMIN)
    empresa = _empresa()
    mensual = Plan.objects.filter(periodicity="MENSUAL", active=True).first()
    suscripcion = change_company_subscription(actor=superadmin, company_id=empresa.id, plan_codigo=mensual.code)
    assert suscripcion.end_date == subscriptions.add_months(timezone.localdate(), 1)
    assert subscriptions.add_months(timezone.localdate().replace(month=1, day=31), 1).day in (28, 29)


def test_avisa_siete_dias_antes_y_una_sola_vez(correos):
    _vence_en(7)
    assert subscriptions.process_due()["avisos"] == 1
    assert subscriptions.process_due()["avisos"] == 0
    [correo] = correos
    assert correo["to_email"] == DUENO
    assert "vence en 7 días" in correo["subject"]


def test_al_vencer_la_empresa_queda_restringida(correos, stripe):
    empresa = _empresa()
    # El hotel (no una habitacion: esas no salen solas en el Marketplace).
    producto = TourismProduct.objects.filter(tenant=empresa, status="PUBLICADO", product_type__code="HOTEL").first()
    assert cliente().get(f"/api/v1/marketplace/productos/{producto.id}/").status_code == 200

    _vence_en(0)
    assert subscriptions.process_due()["vencidas"] == 1
    assert subscriptions.is_restricted(empresa.id)
    assert "venció" in correos[0]["subject"]

    # Fuera del Marketplace y sin poder reservar.
    assert cliente().get(f"/api/v1/marketplace/productos/{producto.id}/").status_code == 404
    assert not catalog.public_lodgings().filter(tenant=empresa).exists()

    # El personal entra y ve su plan, pero no puede editar oferta.
    plan = _api(EMPLEADO).get(URL).json()
    assert plan["estado"] == "VENCIDA"
    assert plan["restringida"] is True
    dueno = UserTenant.objects.get(user__email=DUENO).user
    with pytest.raises(subscriptions.PlanExpired):
        catalog.update_product(actor=dueno, tenant_id=empresa.id, product_id=producto.id, name="Otro nombre")


def test_con_renovacion_automatica_se_extiende_un_periodo(correos):
    suscripcion = _vence_en(0, automatica=True)
    assert subscriptions.process_due()["renovadas"] == 1

    suscripcion.refresh_from_db()
    assert suscripcion.status == "ACTIVA"
    assert suscripcion.end_date > timezone.localdate()
    assert not subscriptions.is_restricted(suscripcion.tenant_id)
    assert "se renovó" in correos[0]["subject"]


def test_el_dueno_paga_la_renovacion_y_la_empresa_vuelve_a_vender(correos, stripe, django_capture_on_commit_callbacks):
    empresa = _empresa()
    _vence_en(0)
    subscriptions.process_due()
    assert subscriptions.is_restricted(empresa.id)

    respuesta = _api().post(f"{URL}pagar/", {}, format="json")
    assert respuesta.status_code == 201
    assert respuesta.json()["checkout_url"].startswith("https://checkout.stripe.test/")
    [creada] = stripe.created
    assert creada["metadata"]["tipo"] == "SUSCRIPCION"
    session_id = SubscriptionPayment.objects.get(tenant=empresa).reference

    with django_capture_on_commit_callbacks(execute=True):
        assert _webhook_plan(session_id).status_code == 200
        assert _webhook_plan(session_id).status_code == 200  # el reintento de Stripe no duplica

    pago = SubscriptionPayment.objects.get(tenant=empresa)
    assert pago.status == "APROBADO"
    nueva = _plan_activo(empresa)
    assert nueva.end_date > timezone.localdate()
    assert not subscriptions.is_restricted(empresa.id)
    assert "Recibimos el pago" in correos[-1]["subject"]


def test_si_el_webhook_no_llega_mi_plan_concilia_con_stripe(stripe):
    empresa = _empresa()
    _vence_en(3)
    antes = _plan_activo(empresa).end_date
    _api().post(f"{URL}pagar/", {}, format="json")
    stripe.pay(SubscriptionPayment.objects.get(tenant=empresa).reference)

    plan = _api().get(URL).json()
    assert plan["estado"] == "ACTIVA"
    assert _plan_activo(empresa).end_date > antes
    assert plan["pagos"][0]["estado"] == "APROBADO"


def test_mi_plan_muestra_uso_y_solo_el_dueno_gestiona(stripe):
    plan = _api().get(URL).json()
    assert plan["es_propietario"] is True
    assert plan["puede_pagar"] is True
    assert {uso["recurso"] for uso in plan["uso"]} == {"usuarios", "productos"}

    empleado = _api(EMPLEADO)
    assert empleado.get(URL).json()["es_propietario"] is False
    assert empleado.patch(URL, {"renovacion_automatica": True}, format="json").status_code == 403
    assert empleado.post(f"{URL}pagar/", {}, format="json").status_code == 403

    assert _api().patch(URL, {"renovacion_automatica": True}, format="json").json()["renovacion_automatica"] is True
    assert cliente("turista1@situr.com.bo").get(URL, HTTP_X_TENANT_ID=str(_empresa().id)).status_code == 403


def test_el_cron_incluye_los_planes(correos, stripe, monkeypatch):
    monkeypatch.setattr("apps.backups.scheduled.run_if_due", lambda: None)
    monkeypatch.setattr(
        "apps.backups.management.commands.tareas_programadas.run_if_due", lambda: None
    )
    _vence_en(0)
    salida = StringIO()
    call_command("tareas_programadas", stdout=salida)
    assert "1 vencidos" in salida.getvalue()
