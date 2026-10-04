"""Pruebas de la geocodificacion de direcciones.

Ninguna sale a la red: ``urlopen`` esta parcheado en todas, igual que en las
pruebas de Brevo. Lo que se verifica es nuestro lado del contrato -- que
parametros se mandan, como se traduce la respuesta, que pasa cuando el proveedor
falla y que la clave no se filtra por ningun sitio.
"""

import json
import urllib.error
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from io import BytesIO
from typing import ClassVar
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.catalog import geocoding
from apps.catalog.serializers import LodgingWriteSerializer
from apps.catalog.views import (
    GeocodingReverseView,
    GeocodingSearchView,
    GeocodingThrottle,
)

TENANT_ID = 2
CLAVE = "clave-de-prueba-no-real-0123456789"

# Un Feature de Pelias tal como llega: coordenadas en [lon, lat].
FEATURE_UYUNI = {
    "geometry": {"type": "Point", "coordinates": [-66.825320, -20.460350]},
    "properties": {
        "label": "Avenida Ferroviaria, Uyuni, Bolivia",
        "name": "Avenida Ferroviaria",
        "locality": "Uyuni",
        "region": "Potosí",
        "country": "Bolivia",
        "confidence": 0.9,
        "layer": "street",
    },
}


def respuesta(payload: dict):
    """Imita el gestor de contexto que devuelve ``urlopen``."""
    cuerpo = BytesIO(json.dumps(payload).encode("utf-8"))
    contexto = MagicMock()
    contexto.__enter__.return_value = cuerpo
    contexto.__exit__.return_value = False
    return contexto


class _GeocodingCase(SimpleTestCase):
    """Pedidos autenticados, con X-Tenant-ID y permisos concedidos."""

    databases: ClassVar[set[str]] = {"default"}

    def _call(self, view, params, *, tenant=str(TENANT_ID), permitido=True):
        request = APIRequestFactory().get(
            "/api/v1/geo/", params, **({"HTTP_X_TENANT_ID": tenant} if tenant else {})
        )
        force_authenticate(request, user=MagicMock(is_authenticated=True))

        permisos = patch("apps.catalog.views.require_permission")
        if not permitido:
            permisos = patch(
                "apps.catalog.views.require_permission",
                side_effect=PermissionDenied("No cuenta con el permiso requerido."),
            )
        with permisos, patch("apps.catalog.views.require_tenant_access"):
            return view.as_view()(request)


@override_settings(OPENROUTESERVICE_API_KEY=CLAVE)
class SearchRequestTests(_GeocodingCase):
    """Que se le pide al proveedor."""

    def test_search_returns_translated_places(self):
        with patch(
            "apps.catalog.geocoding.urllib.request.urlopen",
            return_value=respuesta({"features": [FEATURE_UYUNI]}),
        ):
            response = self._call(GeocodingSearchView, {"texto": "avenida ferroviaria"})

        self.assertEqual(response.status_code, 200)
        resultado = response.data["resultados"][0]
        self.assertEqual(resultado["etiqueta"], "Avenida Ferroviaria, Uyuni, Bolivia")
        self.assertEqual(resultado["localidad"], "Uyuni")
        self.assertEqual(resultado["capa"], "street")

    def test_longitude_and_latitude_are_not_swapped(self):
        """Pelias entrega [lon, lat]; el error clasico es creerlo [lat, lon]."""
        with patch(
            "apps.catalog.geocoding.urllib.request.urlopen",
            return_value=respuesta({"features": [FEATURE_UYUNI]}),
        ):
            response = self._call(GeocodingSearchView, {"texto": "avenida ferroviaria"})

        resultado = response.data["resultados"][0]
        self.assertEqual(resultado["latitud"], Decimal("-20.460350"))
        self.assertEqual(resultado["longitud"], Decimal("-66.825320"))

    def test_search_is_always_restricted_to_bolivia(self):
        with patch(
            "apps.catalog.geocoding.urllib.request.urlopen",
            return_value=respuesta({"features": []}),
        ) as urlopen:
            self._call(GeocodingSearchView, {"texto": "plaza murillo"})

        url = urlopen.call_args.args[0].full_url
        self.assertIn("boundary.country=BOL", url)

    def test_the_key_travels_in_the_header_never_in_the_url(self):
        with patch(
            "apps.catalog.geocoding.urllib.request.urlopen",
            return_value=respuesta({"features": []}),
        ) as urlopen:
            self._call(GeocodingSearchView, {"texto": "plaza murillo"})

        peticion = urlopen.call_args.args[0]
        self.assertNotIn(CLAVE, peticion.full_url)
        # urllib normaliza los nombres de cabecera a Capitalizado.
        self.assertEqual(peticion.get_header("Authorization"), CLAVE)

    def test_city_biases_the_ranking_without_the_client_sending_a_center(self):
        with patch(
            "apps.catalog.geocoding.urllib.request.urlopen",
            return_value=respuesta({"features": []}),
        ) as urlopen, patch(
            "apps.catalog.views._city_center",
            return_value=(Decimal("-20.460350"), Decimal("-66.825320")),
        ):
            self._call(GeocodingSearchView, {"texto": "mercado", "ciudad_id": "5"})

        url = urlopen.call_args.args[0].full_url
        self.assertIn("focus.point.lat=-20.460350", url)
        self.assertIn("focus.point.lon=-66.825320", url)

    def test_without_a_city_there_is_no_focus_point(self):
        with patch(
            "apps.catalog.geocoding.urllib.request.urlopen",
            return_value=respuesta({"features": []}),
        ) as urlopen:
            self._call(GeocodingSearchView, {"texto": "mercado"})

        self.assertNotIn("focus.point", urlopen.call_args.args[0].full_url)

    def test_a_city_without_coordinates_is_not_an_error(self):
        """No hay sesgo, pero la busqueda sigue limitada al pais."""
        with patch(
            "apps.catalog.geocoding.urllib.request.urlopen",
            return_value=respuesta({"features": []}),
        ) as urlopen, patch("apps.catalog.views._city_center", return_value=None):
            response = self._call(GeocodingSearchView, {"texto": "mercado", "ciudad_id": "5"})

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("focus.point", urlopen.call_args.args[0].full_url)

    def test_the_result_limit_is_capped(self):
        with patch("apps.catalog.geocoding.urllib.request.urlopen") as urlopen:
            response = self._call(GeocodingSearchView, {"texto": "mercado", "limite": "500"})

        self.assertEqual(response.status_code, 400)
        urlopen.assert_not_called()

    def test_extra_results_are_trimmed(self):
        """Si el proveedor ignora `size`, se recorta igual."""
        with patch(
            "apps.catalog.geocoding.urllib.request.urlopen",
            return_value=respuesta({"features": [FEATURE_UYUNI] * 9}),
        ):
            response = self._call(GeocodingSearchView, {"texto": "mercado", "limite": "3"})

        self.assertEqual(len(response.data["resultados"]), 3)

    def test_short_text_is_rejected_before_calling_out(self):
        with patch("apps.catalog.geocoding.urllib.request.urlopen") as urlopen:
            response = self._call(GeocodingSearchView, {"texto": "av"})

        self.assertEqual(response.status_code, 400)
        urlopen.assert_not_called()


@override_settings(OPENROUTESERVICE_API_KEY=CLAVE)
class ReverseRequestTests(_GeocodingCase):
    def test_reverse_returns_the_place(self):
        with patch(
            "apps.catalog.geocoding.urllib.request.urlopen",
            return_value=respuesta({"features": [FEATURE_UYUNI]}),
        ) as urlopen:
            response = self._call(
                GeocodingReverseView, {"latitud": "-20.460350", "longitud": "-66.825320"}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["resultado"]["localidad"], "Uyuni")
        url = urlopen.call_args.args[0].full_url
        self.assertIn("point.lat=-20.460350", url)
        self.assertIn("point.lon=-66.825320", url)

    def test_no_place_nearby_is_a_200_with_null(self):
        """En el altiplano es la respuesta habitual, no un error."""
        with patch(
            "apps.catalog.geocoding.urllib.request.urlopen",
            return_value=respuesta({"features": []}),
        ):
            response = self._call(
                GeocodingReverseView, {"latitud": "-20.460350", "longitud": "-66.825320"}
            )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["resultado"])

    def test_reverse_rounds_gps_precision_instead_of_rejecting_it(self):
        with patch(
            "apps.catalog.geocoding.urllib.request.urlopen",
            return_value=respuesta({"features": []}),
        ) as urlopen:
            response = self._call(
                GeocodingReverseView,
                {"latitud": "-20.4603501234567", "longitud": "-66.8253209876"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("point.lat=-20.460350", urlopen.call_args.args[0].full_url)

    def test_out_of_range_point_is_rejected_before_calling_out(self):
        with patch("apps.catalog.geocoding.urllib.request.urlopen") as urlopen:
            response = self._call(GeocodingReverseView, {"latitud": "-91", "longitud": "0"})

        self.assertEqual(response.status_code, 400)
        urlopen.assert_not_called()

    def test_half_a_pair_is_rejected(self):
        with patch("apps.catalog.geocoding.urllib.request.urlopen") as urlopen:
            response = self._call(GeocodingReverseView, {"latitud": "-20.460350"})

        self.assertEqual(response.status_code, 400)
        urlopen.assert_not_called()


@override_settings(OPENROUTESERVICE_API_KEY=CLAVE)
class ProviderFailureTests(_GeocodingCase):
    """Nada de lo que falle del lado del proveedor rompe el panel."""

    def _assert_unavailable(self, error):
        with patch("apps.catalog.geocoding.urllib.request.urlopen", side_effect=error):
            response = self._call(GeocodingSearchView, {"texto": "plaza murillo"})

        self.assertEqual(response.status_code, 503)
        # El mensaje tiene que decirle a la persona que puede seguir.
        self.assertIn("manualmente", response.data["error"]["message"])
        return response

    def test_timeout_is_a_503(self):
        self._assert_unavailable(TimeoutError())

    def test_connection_error_is_a_503(self):
        self._assert_unavailable(urllib.error.URLError("sin red"))

    def test_provider_quota_exceeded_is_a_503(self):
        self._assert_unavailable(
            urllib.error.HTTPError("https://api.heigit.org/pelias/v1/search", 429, "Too Many Requests", {}, None)
        )

    def test_provider_server_error_is_a_503(self):
        self._assert_unavailable(
            urllib.error.HTTPError("https://api.heigit.org/pelias/v1/search", 500, "Server Error", {}, None)
        )

    def test_unparseable_body_is_a_503(self):
        cuerpo = BytesIO(b"no soy json")
        contexto = MagicMock()
        contexto.__enter__.return_value = cuerpo
        contexto.__exit__.return_value = False

        with patch("apps.catalog.geocoding.urllib.request.urlopen", return_value=contexto):
            response = self._call(GeocodingSearchView, {"texto": "plaza murillo"})

        self.assertEqual(response.status_code, 503)

    def test_a_feature_without_a_usable_point_is_discarded(self):
        roto = {"geometry": {"coordinates": []}, "properties": {"label": "sin punto"}}
        fuera_de_rango = {
            "geometry": {"coordinates": [-999, -20.46]},
            "properties": {"label": "imposible"},
        }

        with patch(
            "apps.catalog.geocoding.urllib.request.urlopen",
            return_value=respuesta({"features": [roto, fuera_de_rango, FEATURE_UYUNI]}),
        ):
            response = self._call(GeocodingSearchView, {"texto": "plaza murillo"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["resultados"]), 1)
        self.assertEqual(response.data["resultados"][0]["localidad"], "Uyuni")

    def test_a_body_with_invalid_utf8_bytes_is_a_503(self):
        """Un cuerpo que no es UTF-8 es tan inutilizable como un JSON roto.

        Sin capturar ``UnicodeDecodeError`` escaparia como 500. Es un caso real:
        basta un proxy que reescriba la respuesta con otra codificacion.
        """
        cuerpo = BytesIO(b'{"features": [{"properties": {"label": "\xff\xfe no es utf-8"}}]}')
        contexto = MagicMock()
        contexto.__enter__.return_value = cuerpo
        contexto.__exit__.return_value = False

        with patch("apps.catalog.geocoding.urllib.request.urlopen", return_value=contexto):
            response = self._call(GeocodingSearchView, {"texto": "plaza murillo"})

        self.assertEqual(response.status_code, 503)
        self.assertIn("manualmente", response.data["error"]["message"])


@override_settings(OPENROUTESERVICE_API_KEY=CLAVE)
class CoordinateRoundingStrategyTests(_GeocodingCase):
    """Una sola estrategia de redondeo en todo el sistema: ROUND_HALF_UP.

    Importa que sea la misma en los tres sitios --el serializer de escritura, la
    guardia de servicio y la traduccion de la respuesta del proveedor--. Si aqui
    se dejara el contexto por omision de ``decimal``, que es ROUND_HALF_EVEN, el
    mismo punto podria guardarse con un ultimo decimal distinto segun si se
    eligio en el buscador o se coloco a mano en el mapa.
    """

    # Valor elegido justo porque las dos estrategias no coinciden:
    #   ROUND_HALF_UP   -> -20.460353   (se aleja del cero)
    #   ROUND_HALF_EVEN -> -20.460352   (busca el digito par)
    SIETE_DECIMALES = "-20.4603525"
    ESPERADO_HALF_UP = Decimal("-20.460353")
    HABRIA_DADO_HALF_EVEN = Decimal("-20.460352")

    def test_the_two_strategies_really_differ_for_this_value(self):
        """Si no difirieran, la prueba de abajo no probaria nada."""
        valor = Decimal(self.SIETE_DECIMALES)
        precision = Decimal("0.000001")

        self.assertEqual(
            valor.quantize(precision, rounding=ROUND_HALF_UP), self.ESPERADO_HALF_UP
        )
        self.assertEqual(
            valor.quantize(precision, rounding=ROUND_HALF_EVEN), self.HABRIA_DADO_HALF_EVEN
        )

    def test_the_provider_response_is_rounded_half_up(self):
        self.assertEqual(
            geocoding._coordinate(self.SIETE_DECIMALES), self.ESPERADO_HALF_UP
        )
        self.assertNotEqual(
            geocoding._coordinate(self.SIETE_DECIMALES), self.HABRIA_DADO_HALF_EVEN
        )

    def test_half_up_applies_end_to_end_through_the_endpoint(self):
        feature = {
            "geometry": {"coordinates": [-66.8253145, -20.4603525]},
            "properties": {"label": "Punto de prueba"},
        }

        with patch(
            "apps.catalog.geocoding.urllib.request.urlopen",
            return_value=respuesta({"features": [feature]}),
        ):
            response = self._call(GeocodingSearchView, {"texto": "punto de prueba"})

        resultado = response.data["resultados"][0]
        self.assertEqual(resultado["latitud"], Decimal("-20.460353"))
        self.assertEqual(resultado["longitud"], Decimal("-66.825315"))

    def test_the_rounding_is_symmetric_around_zero(self):
        """ROUND_HALF_UP es "medio se aleja del cero", no "medio hacia arriba"."""
        self.assertEqual(geocoding._coordinate("16.1234565"), Decimal("16.123457"))
        self.assertEqual(geocoding._coordinate("-16.1234565"), Decimal("-16.123457"))

    def test_the_same_value_rounds_the_same_by_both_paths(self):
        """El buscador y la escritura tienen que coincidir digito a digito.

        Es la razon de ser del redondeo explicito: un punto elegido en la lista
        de resultados y el mismo punto colocado a mano deben guardar lo mismo.
        """
        del_proveedor = geocoding._coordinate(self.SIETE_DECIMALES)

        serializer = LodgingWriteSerializer(
            data={"latitud": self.SIETE_DECIMALES, "longitud": "-66.8253145"}, partial=True
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["latitud"], del_proveedor)


class MissingKeyTests(_GeocodingCase):
    """Sin clave configurada el servicio degrada, no explota."""

    @override_settings(OPENROUTESERVICE_API_KEY="")
    def test_search_without_key_is_a_503_and_never_calls_out(self):
        with patch("apps.catalog.geocoding.urllib.request.urlopen") as urlopen:
            response = self._call(GeocodingSearchView, {"texto": "plaza murillo"})

        self.assertEqual(response.status_code, 503)
        urlopen.assert_not_called()

    @override_settings(OPENROUTESERVICE_API_KEY="")
    def test_reverse_without_key_is_a_503_and_never_calls_out(self):
        with patch("apps.catalog.geocoding.urllib.request.urlopen") as urlopen:
            response = self._call(
                GeocodingReverseView, {"latitud": "-20.460350", "longitud": "-66.825320"}
            )

        self.assertEqual(response.status_code, 503)
        urlopen.assert_not_called()

    @override_settings(OPENROUTESERVICE_API_KEY="")
    def test_health_reports_the_integration_as_unconfigured(self):
        self.assertFalse(geocoding.is_configured())

    @override_settings(OPENROUTESERVICE_API_KEY="   ")
    def test_a_blank_key_counts_as_unconfigured(self):
        self.assertFalse(geocoding.is_configured())

    @override_settings(OPENROUTESERVICE_API_KEY=CLAVE)
    def test_health_reports_the_integration_as_configured(self):
        self.assertTrue(geocoding.is_configured())


@override_settings(OPENROUTESERVICE_API_KEY=CLAVE)
class KeyIsNeverLoggedTests(_GeocodingCase):
    """La clave no puede aparecer en ningun registro, ni en un fallo."""

    def test_nothing_is_logged_with_the_key_on_an_http_error(self):
        error = urllib.error.HTTPError(
            f"https://api.heigit.org/pelias/v1/search?api_key={CLAVE}", 403, "Forbidden", {}, None
        )
        with patch("apps.catalog.geocoding.urllib.request.urlopen", side_effect=error):
            with self.assertLogs("apps.catalog.geocoding", level="ERROR") as registros:
                self._call(GeocodingSearchView, {"texto": "plaza murillo"})

        registrado = "\n".join(registros.output)
        self.assertNotIn(CLAVE, registrado)
        self.assertIn("403", registrado)

    def test_the_provider_error_body_is_not_logged(self):
        """Puede repetir el texto consultado, que es entrada del usuario."""
        error = urllib.error.HTTPError(
            "https://api.heigit.org/pelias/v1/search",
            400,
            "Bad Request",
            {},
            BytesIO(b"texto invalido: <script>alert(1)</script>"),
        )
        with patch("apps.catalog.geocoding.urllib.request.urlopen", side_effect=error):
            with self.assertLogs("apps.catalog.geocoding", level="ERROR") as registros:
                self._call(GeocodingSearchView, {"texto": "plaza murillo"})

        self.assertNotIn("script", "\n".join(registros.output))

    def test_the_missing_key_warning_does_not_name_a_value(self):
        with override_settings(OPENROUTESERVICE_API_KEY=""):
            with self.assertLogs("apps.catalog.geocoding", level="WARNING") as registros:
                self._call(GeocodingSearchView, {"texto": "plaza murillo"})

        self.assertNotIn(CLAVE, "\n".join(registros.output))

    def test_no_failure_whatsoever_logs_key_url_or_body(self):
        """Barrido sobre todos los modos de fallo, no solo uno.

        Tres cosas no pueden aparecer en ningun registro: la clave, la URL
        completa --que lleva el texto consultado y llevaria la clave si alguna
        vez viajara por query-- y el cuerpo de la respuesta del proveedor, que
        puede repetir lo que escribio el usuario.
        """
        texto_del_usuario = "casa de la senora Perez 4321"
        cuerpo_delator = b"rechazado: casa de la senora Perez 4321 <script>"
        url_con_clave = f"https://api.heigit.org/pelias/v1/search?api_key={CLAVE}&text=x"

        fallos = {
            "HTTPError 403 con la clave en su propia URL": urllib.error.HTTPError(
                url_con_clave, 403, "Forbidden", {}, BytesIO(cuerpo_delator)
            ),
            "HTTPError 429": urllib.error.HTTPError(
                url_con_clave, 429, "Too Many Requests", {}, BytesIO(cuerpo_delator)
            ),
            "HTTPError 500": urllib.error.HTTPError(
                url_con_clave, 500, "Server Error", {}, BytesIO(cuerpo_delator)
            ),
            "URLError": urllib.error.URLError("sin red"),
            "TimeoutError": TimeoutError(),
        }

        for nombre, error in fallos.items():
            with self.subTest(fallo=nombre):
                with patch("apps.catalog.geocoding.urllib.request.urlopen", side_effect=error):
                    with self.assertLogs("apps.catalog.geocoding", level="ERROR") as registros:
                        response = self._call(
                            GeocodingSearchView, {"texto": texto_del_usuario}
                        )

                registrado = "\n".join(registros.output)
                self.assertEqual(response.status_code, 503)
                self.assertNotIn(CLAVE, registrado)
                self.assertNotIn("api_key", registrado)
                self.assertNotIn(texto_del_usuario, registrado)
                self.assertNotIn("script", registrado)
                self.assertNotIn("api.heigit.org", registrado)

    def test_an_unusable_body_is_logged_by_type_only(self):
        """Ni el JSON roto ni los bytes invalidos se vuelcan al log."""
        for nombre, crudo in (
            ("json roto", b"no soy json: calle Murillo 123"),
            ("utf-8 invalido", b'{"a": "\xff\xfe calle Murillo 123"}'),
        ):
            with self.subTest(cuerpo=nombre):
                contexto = MagicMock()
                contexto.__enter__.return_value = BytesIO(crudo)
                contexto.__exit__.return_value = False

                with patch(
                    "apps.catalog.geocoding.urllib.request.urlopen", return_value=contexto
                ):
                    with self.assertLogs("apps.catalog.geocoding", level="ERROR") as registros:
                        response = self._call(GeocodingSearchView, {"texto": "plaza murillo"})

                registrado = "\n".join(registros.output)
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("Murillo 123", registrado)
                self.assertNotIn(CLAVE, registrado)
                # Solo el tipo de excepcion y la ruta relativa.
                self.assertIn("/search", registrado)

    def test_a_successful_call_logs_nothing_at_all(self):
        """El camino feliz no deja rastro: nada que filtrar."""
        with patch(
            "apps.catalog.geocoding.urllib.request.urlopen",
            return_value=respuesta({"features": [FEATURE_UYUNI]}),
        ):
            with self.assertNoLogs("apps.catalog.geocoding"):
                response = self._call(GeocodingSearchView, {"texto": "avenida ferroviaria"})

        self.assertEqual(response.status_code, 200)


@override_settings(OPENROUTESERVICE_API_KEY=CLAVE)
class ThrottleTests(_GeocodingCase):
    """El limite por usuario, con su salvedad documentada."""

    def setUp(self):
        # `urlopen` se parchea para toda la clase, no por prueba: olvidarlo en
        # una sola haria que esa prueba saliera de verdad a internet.
        # `side_effect` y no `return_value`: el cuerpo es un BytesIO que se
        # agota al leerlo, asi que cada llamada necesita una respuesta nueva.
        salida = patch(
            "apps.catalog.geocoding.urllib.request.urlopen",
            side_effect=lambda *_, **__: respuesta({"features": []}),
        )
        self.urlopen = salida.start()
        self.addCleanup(salida.stop)

        # `override_settings` no sirve para la tasa: DRF copia
        # DEFAULT_THROTTLE_RATES a SimpleRateThrottle.THROTTLE_RATES cuando se
        # importa la clase, asi que hay que tocar ese diccionario.
        tasa = patch.dict(GeocodingThrottle.THROTTLE_RATES, {"geocodificacion": "3/min"})
        tasa.start()
        self.addCleanup(tasa.stop)

        # La cache es memoria del proceso y sobrevive entre pruebas: sin
        # limpiarla el resultado dependeria del orden de ejecucion.
        cache.clear()
        self.addCleanup(cache.clear)

    def _search_as(self, usuario_id):
        """Como ``_call`` pero con una identidad estable para el throttle."""
        return self._authenticated_call(
            GeocodingSearchView, "/api/v1/geo/buscar/", {"texto": "plaza murillo"}, usuario_id
        )

    def _reverse_as(self, usuario_id):
        return self._authenticated_call(
            GeocodingReverseView,
            "/api/v1/geo/inverso/",
            {"latitud": "-20.460350", "longitud": "-66.825320"},
            usuario_id,
        )

    @staticmethod
    def _authenticated_call(view, path, params, usuario_id):
        request = APIRequestFactory().get(path, params, HTTP_X_TENANT_ID=str(TENANT_ID))
        force_authenticate(request, user=MagicMock(is_authenticated=True, pk=usuario_id))
        with patch("apps.catalog.views.require_permission"), patch(
            "apps.catalog.views.require_tenant_access"
        ):
            return view.as_view()(request)

    def test_the_fourth_call_in_a_minute_is_a_429(self):
        for intento in range(3):
            self.assertEqual(self._search_as(77).status_code, 200, f"intento {intento}")

        self.assertEqual(self._search_as(77).status_code, 429)

    def test_a_throttled_call_does_not_reach_the_provider(self):
        """Lo que importa del limite: que no gaste cuota."""
        for _ in range(3):
            self._search_as(81)
        self.assertEqual(self.urlopen.call_count, 3)

        self._search_as(81)

        self.assertEqual(self.urlopen.call_count, 3)

    def test_the_limit_is_per_user_not_global(self):
        for _ in range(3):
            self._search_as(77)

        self.assertEqual(self._search_as(78).status_code, 200)

    def test_search_and_reverse_share_the_same_budget(self):
        """Un solo cupo para las dos: la cuota del proveedor es una sola."""
        for _ in range(3):
            self._search_as(79)

        self.assertEqual(self._reverse_as(79).status_code, 429)


@override_settings(OPENROUTESERVICE_API_KEY=CLAVE)
class GeocodingSecurityTests(_GeocodingCase):
    """Decision D3: sesion, X-Tenant-ID, acceso al tenant y permiso."""

    def test_anonymous_request_is_rejected(self):
        request = APIRequestFactory().get(
            "/api/v1/geo/buscar/", {"texto": "plaza murillo"}, HTTP_X_TENANT_ID=str(TENANT_ID)
        )

        with patch("apps.catalog.geocoding.urllib.request.urlopen") as urlopen:
            response = GeocodingSearchView.as_view()(request)

        self.assertEqual(response.status_code, 401)
        urlopen.assert_not_called()

    def test_missing_tenant_header_is_rejected(self):
        with patch("apps.catalog.geocoding.urllib.request.urlopen") as urlopen:
            response = self._call(GeocodingSearchView, {"texto": "plaza murillo"}, tenant=None)

        self.assertEqual(response.status_code, 400)
        urlopen.assert_not_called()

    def test_non_numeric_tenant_header_is_rejected(self):
        with patch("apps.catalog.geocoding.urllib.request.urlopen") as urlopen:
            response = self._call(
                GeocodingSearchView, {"texto": "plaza murillo"}, tenant="dos"
            )

        self.assertEqual(response.status_code, 400)
        urlopen.assert_not_called()

    def test_without_the_manage_permission_it_is_a_403(self):
        with patch("apps.catalog.geocoding.urllib.request.urlopen") as urlopen:
            response = self._call(
                GeocodingSearchView, {"texto": "plaza murillo"}, permitido=False
            )

        self.assertEqual(response.status_code, 403)
        urlopen.assert_not_called()

    def test_reverse_is_protected_the_same_way(self):
        with patch("apps.catalog.geocoding.urllib.request.urlopen") as urlopen:
            response = self._call(
                GeocodingReverseView,
                {"latitud": "-20.460350", "longitud": "-66.825320"},
                permitido=False,
            )

        self.assertEqual(response.status_code, 403)
        urlopen.assert_not_called()

    def test_authorization_runs_before_spending_quota(self):
        """El orden importa: primero los permisos, despues la llamada."""
        with patch("apps.catalog.geocoding.urllib.request.urlopen") as urlopen:
            self._call(GeocodingSearchView, {"texto": "plaza murillo"}, permitido=False)

        urlopen.assert_not_called()

    def test_the_url_is_a_module_constant(self):
        """El texto del usuario nunca se concatena al host ni a la ruta."""
        self.assertEqual(geocoding.PELIAS_BASE_URL, "https://api.heigit.org/pelias/v1")

        with patch(
            "apps.catalog.geocoding.urllib.request.urlopen",
            return_value=respuesta({"features": []}),
        ) as urlopen:
            self._call(GeocodingSearchView, {"texto": "https://evil.example/?a=b"})

        url = urlopen.call_args.args[0].full_url
        self.assertTrue(url.startswith("https://api.heigit.org/pelias/v1/search?"))
