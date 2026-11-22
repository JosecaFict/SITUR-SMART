"""Gemini para el chat de turistas, con Groq de respaldo.

Ninguna prueba sale a la red: ``urlopen`` o ``llm.chat`` estan parcheados y el
cupo usa un reloj falso.
"""

import json
import urllib.error
from datetime import datetime
from io import BytesIO
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.assistant import llm, quota, services
from apps.assistant.quota import QuotaGate
from tests.test_asistente import CONFIGURADO, mensaje, respuesta

CLAVE_GEMINI = "gemini-clave-de-prueba-no-real-0123456789"
CON_GEMINI = {
    **CONFIGURADO,
    "GEMINI_API_KEY": CLAVE_GEMINI,
    "GEMINI_BASE_URL": "https://gemini.test/v1beta/openai",
    "GEMINI_MODEL": "gemini-prueba",
}
PACIFICO = quota.QUOTA_ZONE


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def gate(per_minute=3, per_day=100, now=None):
    reloj = Reloj()
    hoy = now or (lambda: datetime(2026, 11, 22, 10, 0, tzinfo=PACIFICO))
    return QuotaGate(per_minute=lambda: per_minute, per_day=lambda: per_day, clock=reloj, now=hoy), reloj


def _error(code, body=b""):
    return urllib.error.HTTPError("https://gemini.test", code, "x", {}, BytesIO(body))


# --- Cupo propio ---------------------------------------------------------------


class CupoTests(SimpleTestCase):
    def test_respeta_el_limite_por_minuto_y_libera_al_pasar_el_minuto(self):
        cupo, reloj = gate(per_minute=2)
        self.assertTrue(cupo.try_acquire())
        self.assertTrue(cupo.try_acquire())
        self.assertFalse(cupo.try_acquire())
        reloj.t += 60
        self.assertTrue(cupo.try_acquire())

    def test_al_usar_el_cupo_del_dia_pausa_hasta_el_reinicio(self):
        cupo, reloj = gate(per_minute=100, per_day=2)
        cupo.try_acquire()
        cupo.try_acquire()
        self.assertFalse(cupo.try_acquire())
        reloj.t += 3600  # una hora despues sigue sin cupo: faltan 14 h al reinicio
        self.assertFalse(cupo.try_acquire())

    def test_el_dia_nuevo_del_pacifico_reinicia_el_contador(self):
        momento = {"now": datetime(2026, 11, 22, 23, 0, tzinfo=PACIFICO)}
        cupo, reloj = gate(per_minute=100, per_day=1, now=lambda: momento["now"])
        self.assertTrue(cupo.try_acquire())
        self.assertFalse(cupo.try_acquire())  # pausa de 1 h hasta medianoche
        reloj.t += 3601
        momento["now"] = datetime(2026, 11, 23, 0, 1, tzinfo=PACIFICO)
        self.assertTrue(cupo.try_acquire())

    def test_un_429_pausa_un_minuto(self):
        cupo, reloj = gate()
        cupo.failure(status=429)
        self.assertFalse(cupo.try_acquire())
        reloj.t += 61
        self.assertTrue(cupo.try_acquire())

    def test_un_429_diario_pausa_hasta_el_reinicio(self):
        cupo, reloj = gate()
        cupo.failure(status=429, daily=True)
        reloj.t += 3600
        self.assertFalse(cupo.try_acquire())

    def test_tres_429_seguidos_se_tratan_como_cuota_diaria(self):
        cupo, reloj = gate()
        for _ in range(quota.RATE_LIMITS_BEFORE_DAY_PAUSE):
            cupo.failure(status=429)
            reloj.t += 61
        self.assertFalse(cupo.try_acquire())

    def test_clave_o_modelo_mal_pausa_diez_minutos(self):
        for status in (401, 403, 404):
            cupo, reloj = gate()
            cupo.failure(status=status)
            reloj.t += 300
            self.assertFalse(cupo.try_acquire(), status)
            reloj.t += 301
            self.assertTrue(cupo.try_acquire(), status)

    def test_un_400_no_pausa(self):
        cupo, _ = gate()
        cupo.failure(status=400)
        self.assertTrue(cupo.try_acquire())

    def test_dos_fallas_de_servicio_seguidas_pausan(self):
        cupo, _ = gate()
        cupo.failure(status=503)
        self.assertTrue(cupo.try_acquire())
        cupo.failure(status=None)
        self.assertFalse(cupo.try_acquire())

    def test_un_exito_borra_las_fallas_anteriores(self):
        cupo, _ = gate()
        cupo.failure(status=503)
        cupo.success()
        cupo.failure(status=503)
        self.assertTrue(cupo.try_acquire())


# --- Llamada a Gemini ----------------------------------------------------------


@override_settings(**CON_GEMINI)
class LlamadaGeminiTests(SimpleTestCase):
    def setUp(self):
        llm.GEMINI_GATE.reset()
        self.addCleanup(llm.GEMINI_GATE.reset)

    def test_usa_url_clave_y_modelo_de_gemini_sin_temperatura(self):
        with patch("apps.assistant.llm.urllib.request.urlopen", return_value=respuesta(mensaje("hola"))) as urlopen:
            llm.chat([{"role": "user", "content": "hola"}], provider=llm.gemini())
        request = urlopen.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(request.full_url, "https://gemini.test/v1beta/openai/chat/completions")
        self.assertEqual(request.get_header("Authorization"), f"Bearer {CLAVE_GEMINI}")
        self.assertEqual(body["model"], "gemini-prueba")
        self.assertNotIn("temperature", body)

    def test_el_principal_sigue_con_groq(self):
        with patch("apps.assistant.llm.urllib.request.urlopen", return_value=respuesta(mensaje("hola"))) as urlopen:
            llm.chat([{"role": "user", "content": "hola"}])
        request = urlopen.call_args.args[0]
        self.assertTrue(request.full_url.startswith("https://proveedor.test/v1"))
        self.assertEqual(json.loads(request.data)["model"], "modelo-prueba")

    @override_settings(IA_RETRY_DELAY_SECONDS=0)
    def test_gemini_no_reintenta_un_503(self):
        with patch("apps.assistant.llm.urllib.request.urlopen", side_effect=_error(503)) as urlopen:
            with self.assertLogs("apps.assistant", level="ERROR"):
                with self.assertRaises(llm.AssistantUnavailable):
                    llm.chat([{"role": "user", "content": "hola"}], provider=llm.gemini())
        self.assertEqual(urlopen.call_count, 1)

    @override_settings(GEMINI_RPM_LIMIT=1)
    def test_sin_cupo_no_llama_a_google(self):
        with patch("apps.assistant.llm.urllib.request.urlopen", return_value=respuesta(mensaje("hola"))) as urlopen:
            llm.chat([{"role": "user", "content": "hola"}], provider=llm.gemini())
            with self.assertRaises(llm.ProviderSkipped):
                llm.chat([{"role": "user", "content": "hola"}], provider=llm.gemini())
        self.assertEqual(urlopen.call_count, 1)

    def test_un_429_diario_de_google_pausa_a_gemini(self):
        body = json.dumps(
            [{"error": {"code": 429, "message": "Quota exceeded", "details": [
                {"violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}
            ]}}]
        ).encode()
        with patch("apps.assistant.llm.urllib.request.urlopen", side_effect=_error(429, body)):
            with self.assertLogs("apps.assistant", level="WARNING") as logs:
                with self.assertRaises(llm.AssistantRateLimited) as caught:
                    llm.chat([{"role": "user", "content": "hola"}], provider=llm.gemini())
        self.assertTrue(caught.exception.daily)
        self.assertFalse(llm.GEMINI_GATE.try_acquire())
        self.assertNotIn(CLAVE_GEMINI, "\n".join(logs.output))

    def test_sin_clave_de_gemini_no_hay_proveedor(self):
        with override_settings(GEMINI_API_KEY=""):
            self.assertIsNone(llm.gemini())

    def test_el_chat_se_muestra_con_solo_gemini_pero_la_voz_necesita_groq(self):
        with override_settings(IA_API_KEY=""):
            self.assertTrue(llm.is_configured())
            self.assertFalse(llm.voice_configured())


# --- Eleccion de proveedor por mensaje -----------------------------------------


def _por_proveedor(respuestas):
    """``llm.chat`` falso: responde segun el proveedor y guarda cada pedido."""
    pedidos = []

    def chat(messages, tools=None, provider=None):
        nombre = provider.name if provider is not None else "Groq"
        pedidos.append((nombre, [dict(m) for m in messages]))
        resultado = respuestas[nombre].pop(0)
        if isinstance(resultado, Exception):
            raise resultado
        return resultado

    return chat, pedidos


@override_settings(**CON_GEMINI)
class EleccionTests(SimpleTestCase):
    def setUp(self):
        llm.GEMINI_GATE.reset()
        self.addCleanup(llm.GEMINI_GATE.reset)

    def test_el_turista_conversa_con_gemini(self):
        chat, pedidos = _por_proveedor({"Gemini": [{"content": "Hola desde Gemini"}], "Groq": []})
        with patch("apps.assistant.services.llm.chat", side_effect=chat):
            result = services.reply(message="hola", history=[])
        self.assertEqual(result["respuesta"], "Hola desde Gemini")
        self.assertEqual([nombre for nombre, _ in pedidos], ["Gemini"])

    def test_si_gemini_falla_a_mitad_el_mensaje_entero_pasa_a_groq(self):
        call = {"id": "g1", "function": {"name": "listar_ciudades", "arguments": "{}"}}
        chat, pedidos = _por_proveedor({
            "Gemini": [{"content": None, "tool_calls": [call]}, llm.AssistantUnavailable(status=503)],
            "Groq": [{"content": "Hola desde Groq"}],
        })
        with (
            patch("apps.assistant.services.llm.chat", side_effect=chat),
            patch("apps.assistant.tools.run", return_value="{}"),
            self.assertLogs("apps.assistant.services", level="WARNING") as logs,
        ):
            result = services.reply(message="ciudades", history=[])
        self.assertEqual(result["respuesta"], "Hola desde Groq")
        self.assertEqual([nombre for nombre, _ in pedidos], ["Gemini", "Gemini", "Groq"])
        # Groq empieza de cero: sin la llamada a herramienta firmada por Gemini.
        self.assertEqual([m["role"] for m in pedidos[2][1]], ["system", "user"])
        self.assertIn("Gemini no atendio (503); el mensaje pasa a Groq", logs.output[0])

    def test_sin_cupo_de_gemini_va_directo_a_groq(self):
        chat, pedidos = _por_proveedor({"Gemini": [llm.ProviderSkipped()], "Groq": [{"content": "ok"}]})
        with (
            patch("apps.assistant.services.llm.chat", side_effect=chat),
            self.assertLogs("apps.assistant.services", level="WARNING") as logs,
        ):
            services.reply(message="hola", history=[])
        self.assertEqual([nombre for nombre, _ in pedidos], ["Gemini", "Groq"])
        self.assertIn("sin cupo", logs.output[0])

    def test_si_los_dos_fallan_se_avisa_al_turista(self):
        chat, _ = _por_proveedor({
            "Gemini": [llm.AssistantRateLimited(status=429)],
            "Groq": [llm.AssistantRateLimited(status=429)],
        })
        with (
            patch("apps.assistant.services.llm.chat", side_effect=chat),
            self.assertLogs("apps.assistant.services", level="WARNING"),
            self.assertRaises(llm.AssistantRateLimited),
        ):
            services.reply(message="hola", history=[])

    def test_el_personal_sigue_con_groq(self):
        reports = type("Ctx", (), {"global_scope": True, "reports": []})()
        chat, pedidos = _por_proveedor({"Gemini": [], "Groq": [{"content": "Reporte listo"}]})
        with (
            patch("apps.assistant.services.report_tool.context_for", return_value=reports),
            patch("apps.assistant.services.llm.chat", side_effect=chat),
        ):
            services.reply(message="ventas del mes", history=[], user=object())
        self.assertEqual([nombre for nombre, _ in pedidos], ["Groq"])

    def test_sin_groq_gemini_atiende_solo(self):
        chat, pedidos = _por_proveedor({"Gemini": [llm.AssistantUnavailable(status=503)], "Groq": []})
        with (
            override_settings(IA_API_KEY=""),
            patch("apps.assistant.services.llm.chat", side_effect=chat),
            self.assertRaises(llm.AssistantUnavailable),
        ):
            services.reply(message="hola", history=[])
        self.assertEqual([nombre for nombre, _ in pedidos], ["Gemini"])


class LimitePorTuristaTests(SimpleTestCase):
    def test_el_limite_por_turista_alcanza_para_una_demo(self):
        from django.conf import settings

        rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
        self.assertEqual(rates["asistente"], "20/min")
        self.assertEqual(rates["asistente_voz"], "10/min")
