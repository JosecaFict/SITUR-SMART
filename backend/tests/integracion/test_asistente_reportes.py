"""El asistente arma reportes para el personal y el SuperAdmin, contra PostgreSQL real.

El proveedor de IA se reemplaza por respuestas fijas: se prueba quien recibe la
herramienta, con que alcance se arma el reporte y que le llega a la web.
"""

import json
from unittest.mock import patch

import pytest

from apps.tenancy.models import Tenant, UserTenant

from .datos import TURISTA, cliente

pytestmark = pytest.mark.django_db(transaction=False)

SUPERADMIN = "superadmin@situr.com.bo"
DUENO = "jefeadmin@hotelcortez.com.bo"
URL = "/api/v1/asistente/chat/"


def _empresa_de(email: str) -> Tenant:
    return UserTenant.objects.select_related("tenant").get(user__email=email).tenant


def _pedir(email, argumentos, *, tenant_id=None, respuesta="Listo, aquí está tu reporte."):
    """Simula que el modelo pide generar_reporte y despues contesta."""
    llamada = {
        "id": "r1",
        "type": "function",
        "function": {"name": "generar_reporte", "arguments": json.dumps(argumentos)},
    }
    with patch(
        "apps.assistant.services.llm.chat",
        side_effect=[{"content": None, "tool_calls": [llamada]}, {"content": respuesta}],
    ) as chat:
        headers = {"HTTP_X_TENANT_ID": str(tenant_id)} if tenant_id else {}
        response = cliente(email).post(URL, {"mensaje": "reporte"}, format="json", **headers)
    return response, chat


def _herramientas(chat) -> list[str]:
    return [tool["function"]["name"] for tool in chat.call_args_list[0].kwargs["tools"]]


def _resultado_de_la_herramienta(chat) -> dict:
    return json.loads(chat.call_args_list[1].args[0][-1]["content"])


def test_el_dueno_pide_el_catalogo_de_su_empresa_en_pdf():
    empresa = _empresa_de(DUENO)
    response, chat = _pedir(
        DUENO, {"tipo": "catalogo", "formato": "pdf", "desde": "2026-01-01"}, tenant_id=empresa.id
    )

    assert response.status_code == 200
    assert "generar_reporte" in _herramientas(chat)
    [reporte] = response.json()["reportes"]
    assert reporte["tipo"] == "catalogo"
    assert reporte["formato"] == "pdf"
    assert reporte["desde"] == "2026-01-01"
    assert reporte["empresa_id"] == empresa.id
    resultado = _resultado_de_la_herramienta(chat)
    assert resultado["empresa"] == empresa.trade_name
    assert resultado["filas"] == reporte["filas"]
    assert resultado["indicadores"]


def test_el_dueno_no_puede_pedir_otra_empresa():
    empresa = _empresa_de(DUENO)
    otra = Tenant.objects.exclude(id=empresa.id).first()
    response, _ = _pedir(
        DUENO, {"tipo": "catalogo", "empresa": otra.trade_name, "formato": "ninguno"}, tenant_id=empresa.id
    )

    [reporte] = response.json()["reportes"]
    assert reporte["empresa_id"] == empresa.id
    assert reporte["formato"] is None


def test_el_superadmin_ve_toda_la_plataforma_o_una_empresa_por_nombre():
    response, chat = _pedir(SUPERADMIN, {"tipo": "plataforma", "formato": "excel"})
    [reporte] = response.json()["reportes"]
    assert reporte["empresa_id"] is None
    assert reporte["formato"] == "excel"
    assert _resultado_de_la_herramienta(chat)["empresa"] == "Toda la plataforma"

    empresa = _empresa_de(DUENO)
    response, _ = _pedir(SUPERADMIN, {"tipo": "hospedajes", "empresa": empresa.trade_name})
    assert response.json()["reportes"][0]["empresa_id"] == empresa.id


def test_un_nombre_de_empresa_que_no_existe_se_le_explica_al_modelo():
    response, chat = _pedir(SUPERADMIN, {"tipo": "catalogo", "empresa": "Empresa Inexistente XYZ"})
    assert response.json()["reportes"] == []
    assert "No hay ninguna empresa" in _resultado_de_la_herramienta(chat)["error"]


def test_el_turista_no_recibe_la_herramienta_ni_puede_forzarla():
    response, chat = _pedir(TURISTA, {"tipo": "plataforma", "formato": "pdf"})

    assert "generar_reporte" not in _herramientas(chat)
    assert response.json()["reportes"] == []
    assert _resultado_de_la_herramienta(chat) == {"error": "No tienes acceso a reportes."}


def test_el_personal_sin_empresa_elegida_no_recibe_la_herramienta():
    _, chat = _pedir(DUENO, {"tipo": "catalogo"})
    assert "generar_reporte" not in _herramientas(chat)
