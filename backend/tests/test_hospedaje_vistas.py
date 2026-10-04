"""Pruebas de integracion de las vistas empresariales de hospedaje.

Llegan hasta el codigo de estado y el cuerpo serializado, que es donde
``test_hospedaje.py`` no entra: ese cubre la capa de servicio con mocks.

Los objetos de prueba se arman con **instancias de modelo sin guardar**, no con
``MagicMock``, para que la serializacion se ejercite de verdad: un mock pasa
cualquier campo y oculta errores de tipo en los decimales y las fechas. Nada
toca la base -- los servicios estan mockeados y los modelos son
``managed = False``.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import ClassVar
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.catalog.models import (
    Currency,
    LodgingEstablishment,
    LodgingType,
    ProductType,
    Room,
    TourismProduct,
)
from apps.catalog.views import (
    CompanyLodgingDetailView,
    CompanyLodgingListCreateView,
    CompanyLodgingRoomListCreateView,
    CompanyRoomDetailView,
)
from apps.tenancy.models import City, Country, Tenant

AHORA = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
TENANT_ID = 2
LODGING_ID = 11
ROOM_ID = 6


def _graph():
    """Catalogos compartidos: pais, ciudad, moneda, empresa y tipos."""
    country = Country(id=1, iso_code="BOL", name="Bolivia")
    city = City(id=5, country=country, name="Uyuni")
    currency = Currency(id=1, iso_code="BOB", name="Boliviano", symbol="Bs", decimals=2)
    tenant = Tenant(
        id=TENANT_ID, legal_name="ToursBo SRL", trade_name="ToursBo",
        subdomain="toursbo", status="ACTIVO",
    )
    return country, city, currency, tenant


def fake_lodging(status="BORRADOR", from_price=None, rooms_count=0, total_capacity=None):
    _, city, currency, tenant = _graph()
    product = TourismProduct(
        id=2, tenant=tenant, product_type=ProductType(id=1, code="HOTEL", name="Hotel"),
        city=city, currency=currency, code="HOTEL_X", name="Hotel de prueba",
        description=None, locality="Potosi", base_price=Decimal("0.00"),
        max_capacity=1, status=status, image_url=None,
        created_at=AHORA, updated_at=AHORA,
    )
    lodging = LodgingEstablishment(
        id=LODGING_ID, product=product, tenant=tenant,
        lodging_type=LodgingType(id=1, code="HOTEL", name="Hotel"),
        address=None, star_rating=None, check_in=None, check_out=None,
        services=[], created_at=AHORA, updated_at=AHORA,
    )
    # Anotaciones de services.with_from_price.
    lodging.from_price = from_price
    lodging.rooms_count = rooms_count
    lodging.total_capacity = total_capacity
    return lodging


def fake_room(status="BORRADOR"):
    _, city, currency, tenant = _graph()
    product = TourismProduct(
        id=8, tenant=tenant,
        product_type=ProductType(id=2, code="HABITACION", name="Habitación"),
        city=city, currency=currency, code="HAB_X", name="Habitación Familiar",
        description=None, locality="Potosi", base_price=Decimal("700.00"),
        max_capacity=6, status=status, image_url=None,
        created_at=AHORA, updated_at=AHORA,
    )
    return Room(
        id=ROOM_ID, product=product, establishment=fake_lodging(), tenant=tenant,
        quantity=5, adults_capacity=4, children_capacity=2,
        bed_type="Queen", includes_breakfast=True,
        created_at=AHORA, updated_at=AHORA,
    )


class _ViewCase(SimpleTestCase):
    """Base con el armado de pedidos autenticados y con X-Tenant-ID."""

    databases: ClassVar[set[str]] = {"default"}

    @staticmethod
    def _valid_catalogs():
        """Da por buenos ciudad, moneda y tipo de hospedaje.

        Los validadores del serializer los consultan en la base, que aqui no
        existe (``managed = False`` sobre SQLite). Lo que se prueba es la vista,
        no la existencia de los catalogos.
        """
        from contextlib import ExitStack

        pila = ExitStack()
        for modelo in ("City", "Currency", "LodgingType"):
            consulta = pila.enter_context(
                patch(f"apps.catalog.serializers.{modelo}.objects.filter")
            )
            consulta.return_value.exists.return_value = True
        return pila

    def _call(self, view, method, path, body=None, tenant=str(TENANT_ID), **kwargs):
        factory = APIRequestFactory()
        request = getattr(factory, method)(
            path, body, format="json", **({"HTTP_X_TENANT_ID": tenant} if tenant else {})
        )
        from unittest.mock import MagicMock

        force_authenticate(request, user=MagicMock(is_authenticated=True))
        return view.as_view()(request, **kwargs)


class LodgingViewTests(_ViewCase):
    LODGING_BODY: ClassVar[dict] = {
        "nombre": "Hotel de prueba",
        "ciudad_id": 5,
        "moneda_codigo": "BOB",
    }

    # ---- POST ----

    @patch("apps.catalog.views.create_lodging")
    def test_post_creates_and_returns_201(self, create):
        create.return_value = fake_lodging()

        with self._valid_catalogs():
            response = self._call(
                CompanyLodgingListCreateView, "post", "/api/v1/hospedajes/", self.LODGING_BODY
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["estado"], "BORRADOR")
        self.assertEqual(response.data["id"], LODGING_ID)
        # El hotel nace sin precio: lo dan sus habitaciones.
        self.assertIsNone(response.data["precio_desde"])
        self.assertIsNone(response.data["capacidad_total"])
        self.assertEqual(create.call_args.kwargs["tenant_id"], TENANT_ID)

    @patch("apps.catalog.views.create_lodging", side_effect=PermissionDenied)
    def test_post_without_the_manage_permission_returns_403(self, create):
        with self._valid_catalogs():
            response = self._call(
                CompanyLodgingListCreateView, "post", "/api/v1/hospedajes/", self.LODGING_BODY
            )

        self.assertEqual(response.status_code, 403)

    def test_post_without_the_tenant_header_returns_400(self):
        response = self._call(
            CompanyLodgingListCreateView, "post", "/api/v1/hospedajes/",
            self.LODGING_BODY, tenant=None,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("tenant", response.data["error"]["details"])

    def test_post_with_a_non_numeric_tenant_returns_400(self):
        response = self._call(
            CompanyLodgingListCreateView, "post", "/api/v1/hospedajes/",
            self.LODGING_BODY, tenant="abc",
        )

        self.assertEqual(response.status_code, 400)

    # ---- GET ----

    @patch("apps.catalog.views.list_company_lodgings")
    def test_get_list_returns_a_plain_array(self, listar):
        """No pagina: solo los tres endpoints publicos del Marketplace lo hacen."""
        listar.return_value = [fake_lodging()]

        response = self._call(CompanyLodgingListCreateView, "get", "/api/v1/hospedajes/")

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)

    @patch("apps.catalog.views.get_company_lodging", side_effect=NotFound)
    def test_get_detail_of_another_tenant_returns_404(self, get_lodging):
        """404, no 403: un 403 confirmaria que el hospedaje existe."""
        response = self._call(
            CompanyLodgingDetailView, "get", "/api/v1/hospedajes/999/", pk=999
        )

        self.assertEqual(response.status_code, 404)

    # ---- PATCH ----

    @patch("apps.catalog.views.update_lodging")
    def test_patch_returns_200_with_the_updated_object(self, update):
        update.return_value = fake_lodging(status="PUBLICADO", from_price=Decimal("700.00"))

        response = self._call(
            CompanyLodgingDetailView, "patch", f"/api/v1/hospedajes/{LODGING_ID}/",
            {"estado": "PUBLICADO"}, pk=LODGING_ID,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["estado"], "PUBLICADO")
        self.assertEqual(response.data["precio_desde"], "700.00")

    @patch("apps.catalog.views.update_lodging", side_effect=NotFound)
    def test_patch_of_another_tenant_returns_404(self, update):
        response = self._call(
            CompanyLodgingDetailView, "patch", "/api/v1/hospedajes/999/",
            {"nombre": "Intento"}, pk=999,
        )

        self.assertEqual(response.status_code, 404)

    @patch("apps.catalog.views.update_lodging", side_effect=PermissionDenied)
    def test_patch_without_permission_returns_403(self, update):
        response = self._call(
            CompanyLodgingDetailView, "patch", f"/api/v1/hospedajes/{LODGING_ID}/",
            {"nombre": "Otro"}, pk=LODGING_ID,
        )

        self.assertEqual(response.status_code, 403)

    def test_patch_rejects_a_lodging_type_other_than_hotel(self):
        with (
            patch("apps.catalog.serializers.LodgingType.objects.filter") as tipos,
            patch("apps.catalog.serializers.City.objects.filter") as ciudades,
            patch("apps.catalog.serializers.Currency.objects.filter") as monedas,
        ):
            tipos.return_value.exists.return_value = True
            ciudades.return_value.exists.return_value = True
            monedas.return_value.exists.return_value = True
            response = self._call(
                CompanyLodgingDetailView, "patch", f"/api/v1/hospedajes/{LODGING_ID}/",
                {"tipo_hospedaje_codigo": "CABANA"}, pk=LODGING_ID,
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("tipo_hospedaje_codigo", response.data["error"]["details"])

    # ---- DELETE ----

    @patch("apps.catalog.views.deactivate_lodging")
    def test_delete_returns_200_and_the_object_inactive(self, deactivate):
        """Desactivacion, no borrado: 200 con el objeto, nunca 204."""
        deactivate.return_value = fake_lodging(status="INACTIVO")

        response = self._call(
            CompanyLodgingDetailView, "delete", f"/api/v1/hospedajes/{LODGING_ID}/",
            pk=LODGING_ID,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["estado"], "INACTIVO")
        self.assertEqual(response.data["id"], LODGING_ID)

    @patch("apps.catalog.views.deactivate_lodging", side_effect=NotFound)
    def test_delete_of_another_tenant_returns_404(self, deactivate):
        response = self._call(
            CompanyLodgingDetailView, "delete", "/api/v1/hospedajes/999/", pk=999
        )

        self.assertEqual(response.status_code, 404)


class RoomViewTests(_ViewCase):
    ROOM_BODY: ClassVar[dict] = {
        "nombre": "Habitación Familiar",
        "precio_base": "700.00",
        "capacidad_maxima": 6,
        "capacidad_adultos": 4,
        "capacidad_ninos": 2,
        "cantidad_habitaciones": 5,
    }

    @patch("apps.catalog.views.create_room")
    def test_post_creates_and_returns_201(self, create):
        create.return_value = fake_room()

        response = self._call(
            CompanyLodgingRoomListCreateView, "post",
            f"/api/v1/hospedajes/{LODGING_ID}/habitaciones/", self.ROOM_BODY, pk=LODGING_ID,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["precio_noche"], "700.00")
        self.assertEqual(response.data["cantidad_habitaciones"], 5)
        # La ubicacion viene heredada del hotel, no del cuerpo del pedido.
        self.assertEqual(response.data["ciudad"], "Uyuni")
        self.assertEqual(response.data["localidad"], "Potosi")
        self.assertEqual(create.call_args.kwargs["lodging_id"], LODGING_ID)

    @patch("apps.catalog.views.create_room", side_effect=PermissionDenied)
    def test_post_without_permission_returns_403(self, create):
        response = self._call(
            CompanyLodgingRoomListCreateView, "post",
            f"/api/v1/hospedajes/{LODGING_ID}/habitaciones/", self.ROOM_BODY, pk=LODGING_ID,
        )

        self.assertEqual(response.status_code, 403)

    @patch("apps.catalog.views.create_room", side_effect=NotFound)
    def test_post_under_a_lodging_of_another_tenant_returns_404(self, create):
        response = self._call(
            CompanyLodgingRoomListCreateView, "post",
            "/api/v1/hospedajes/999/habitaciones/", self.ROOM_BODY, pk=999,
        )

        self.assertEqual(response.status_code, 404)

    def test_post_never_accepts_a_location_from_the_body(self):
        """Mandar ciudad se descarta: la ubicacion la fija el hotel."""
        with patch("apps.catalog.views.create_room") as create:
            create.return_value = fake_room()
            self._call(
                CompanyLodgingRoomListCreateView, "post",
                f"/api/v1/hospedajes/{LODGING_ID}/habitaciones/",
                {**self.ROOM_BODY, "ciudad_id": 99, "localidad": "Otra ciudad"},
                pk=LODGING_ID,
            )

        enviado = create.call_args.kwargs
        self.assertNotIn("ciudad_id", enviado)
        self.assertNotIn("localidad", enviado)

    @patch("apps.catalog.views.list_lodging_rooms")
    def test_get_list_returns_a_plain_array(self, listar):
        listar.return_value = [fake_room()]

        response = self._call(
            CompanyLodgingRoomListCreateView, "get",
            f"/api/v1/hospedajes/{LODGING_ID}/habitaciones/", pk=LODGING_ID,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)

    @patch("apps.catalog.views.update_room")
    def test_patch_publishes_and_returns_200(self, update):
        update.return_value = fake_room(status="PUBLICADO")

        response = self._call(
            CompanyRoomDetailView, "patch", f"/api/v1/habitaciones/{ROOM_ID}/",
            {"estado": "PUBLICADO"}, pk=ROOM_ID,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["estado"], "PUBLICADO")

    @patch("apps.catalog.views.update_room", side_effect=NotFound)
    def test_patch_of_another_tenant_returns_404(self, update):
        response = self._call(
            CompanyRoomDetailView, "patch", "/api/v1/habitaciones/999/",
            {"estado": "PUBLICADO"}, pk=999,
        )

        self.assertEqual(response.status_code, 404)

    @patch("apps.catalog.views.update_room", side_effect=PermissionDenied)
    def test_patch_without_permission_returns_403(self, update):
        response = self._call(
            CompanyRoomDetailView, "patch", f"/api/v1/habitaciones/{ROOM_ID}/",
            {"estado": "PUBLICADO"}, pk=ROOM_ID,
        )

        self.assertEqual(response.status_code, 403)

    @patch("apps.catalog.views.deactivate_room")
    def test_delete_returns_200_and_the_object_inactive(self, deactivate):
        deactivate.return_value = fake_room(status="INACTIVO")

        response = self._call(
            CompanyRoomDetailView, "delete", f"/api/v1/habitaciones/{ROOM_ID}/", pk=ROOM_ID
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["estado"], "INACTIVO")

    @patch("apps.catalog.views.get_company_room", side_effect=NotFound)
    def test_get_detail_of_another_tenant_returns_404(self, get_room):
        response = self._call(
            CompanyRoomDetailView, "get", "/api/v1/habitaciones/999/", pk=999
        )

        self.assertEqual(response.status_code, 404)


class ReactivationRuleTests(_ViewCase):
    """Reactivar de INACTIVO a PUBLICADO revalida las reglas de publicacion."""

    @patch("apps.catalog.views.update_lodging")
    def test_reactivating_a_lodging_goes_through_the_service(self, update):
        update.return_value = fake_lodging(status="PUBLICADO", from_price=Decimal("700.00"))

        response = self._call(
            CompanyLodgingDetailView, "patch", f"/api/v1/hospedajes/{LODGING_ID}/",
            {"estado": "PUBLICADO"}, pk=LODGING_ID,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(update.call_args.kwargs["estado"], "PUBLICADO")

    @patch("apps.catalog.views.update_lodging")
    def test_reactivating_a_lodging_without_offerable_rooms_returns_400(self, update):
        """El servicio exige una habitacion ofertable incluso viniendo de INACTIVO."""
        from rest_framework.exceptions import ValidationError

        update.side_effect = ValidationError({"estado": ["Para publicar un hospedaje…"]})

        response = self._call(
            CompanyLodgingDetailView, "patch", f"/api/v1/hospedajes/{LODGING_ID}/",
            {"estado": "PUBLICADO"}, pk=LODGING_ID,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("estado", response.data["error"]["details"])

    @patch("apps.catalog.views.update_room")
    def test_republishing_a_room_at_zero_returns_400(self, update):
        from rest_framework.exceptions import ValidationError

        update.side_effect = ValidationError(
            {"precio_base": ["Una habitación publicada debe tener un precio…"]}
        )

        response = self._call(
            CompanyRoomDetailView, "patch", f"/api/v1/habitaciones/{ROOM_ID}/",
            {"estado": "PUBLICADO"}, pk=ROOM_ID,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("precio_base", response.data["error"]["details"])
