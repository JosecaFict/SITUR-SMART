"""Pruebas del modulo de Hospedaje.

Los modelos usan ``managed = False``, asi que la suite corre sobre SQLite en
memoria sin esas tablas y las pruebas trabajan con ``SimpleTestCase`` y mocks,
igual que el resto del catalogo. Dos reglas quedan por tanto fuera de alcance
aqui porque viven en restricciones de PostgreSQL y no en codigo Python:

* la FK compuesta que impide colgar una habitacion del hotel de otro tenant;
* los CHECK de cantidad y capacidades.

Lo que si se verifica es la capa de servicio: herencia de ubicacion, tipo de
producto forzado, aislamiento por tenant, permisos, filtros publicos y calculo
del precio "desde".
"""

from decimal import Decimal
from typing import ClassVar
from unittest.mock import MagicMock, PropertyMock, patch

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, Exists, F, Min, OuterRef, Q, Sum
from django.test import SimpleTestCase
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.catalog.models import LODGING_PRODUCT_CODES
from apps.catalog.serializers import (
    LodgingSerializer,
    LodgingWriteSerializer,
    ProductSerializer,
    ProductWriteSerializer,
    PublicRoomQuerySerializer,
    RoomWriteSerializer,
)
from apps.catalog.services import (
    _check_lodging_publishable,
    _check_room_capacity,
    _check_room_price,
    _company_lodgings,
    _lodging_type,
    _publishable_room_exists,
    create_lodging,
    create_room,
    get_company_lodging,
    get_company_room,
    list_company_products,
    only_complete_lodging_products,
    public_lodgings,
    public_rooms,
    update_lodging,
    update_product,
    update_room,
    with_from_price,
    with_lodging_from_price,
)
from apps.catalog.views import CompanyLodgingListCreateView

PUBLISHED = "PUBLICADO"
ACTIVE = "ACTIVO"


class LodgingWriteSerializerTests(SimpleTestCase):
    def test_create_requires_core_fields(self):
        """No pide capacidad: se deriva de las habitaciones."""
        serializer = LodgingWriteSerializer(data={})

        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            set(serializer.errors), {"nombre", "ciudad_id", "moneda_codigo"}
        )

    def test_ignores_precio_base(self):
        """El hotel no fija precio propio: se deriva de sus habitaciones."""
        serializer = LodgingWriteSerializer(data={"precio_base": "450.00"}, partial=True)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn("precio_base", serializer.validated_data)

    def test_rejects_star_rating_out_of_range(self):
        serializer = LodgingWriteSerializer(data={"categoria_estrellas": 7}, partial=True)

        self.assertFalse(serializer.is_valid())
        self.assertIn("categoria_estrellas", serializer.errors)


class RoomWriteSerializerTests(SimpleTestCase):
    def test_create_requires_name_price_and_capacity(self):
        serializer = RoomWriteSerializer(data={})

        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            set(serializer.errors), {"nombre", "precio_base", "capacidad_maxima"}
        )

    def test_never_accepts_a_location(self):
        """La ubicacion se hereda del hotel y no puede llegar por el cuerpo."""
        serializer = RoomWriteSerializer(
            data={"ciudad_id": 99, "localidad": "Otra ciudad"}, partial=True
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn("ciudad_id", serializer.validated_data)
        self.assertNotIn("localidad", serializer.validated_data)

    def test_rejects_negative_night_price(self):
        serializer = RoomWriteSerializer(data={"precio_base": "-1"}, partial=True)

        self.assertFalse(serializer.is_valid())
        self.assertIn("precio_base", serializer.errors)


class RoomCapacityRuleTests(SimpleTestCase):
    """Los tres campos son topes alternativos, no un desglose.

    capacidad_maxima limita el total de ocupantes; capacidad_adultos y
    capacidad_ninos limitan cada grupo por separado. La suma NO se valida aqui
    sino al reservar, porque los topes describen combinaciones que nunca se dan
    al mismo tiempo.
    """

    def test_allows_individual_limits_that_exceed_the_total_when_summed(self):
        """Tope 4, hasta 4 adultos y hasta 3 ninos: valida (4+3 > 4 no importa)."""
        _check_room_capacity(max_capacity=4, adults=4, children=3)

    def test_allows_each_limit_equal_to_the_total(self):
        _check_room_capacity(max_capacity=2, adults=2, children=2)

    def test_rejects_more_adults_than_the_total(self):
        with self.assertRaises(ValidationError) as caught:
            _check_room_capacity(max_capacity=2, adults=3, children=0)

        self.assertIn("capacidad_adultos", caught.exception.detail)
        self.assertNotIn("capacidad_ninos", caught.exception.detail)

    def test_rejects_more_children_than_the_total(self):
        with self.assertRaises(ValidationError) as caught:
            _check_room_capacity(max_capacity=2, adults=1, children=5)

        self.assertIn("capacidad_ninos", caught.exception.detail)
        self.assertNotIn("capacidad_adultos", caught.exception.detail)

    def test_reports_both_limits_at_once(self):
        with self.assertRaises(ValidationError) as caught:
            _check_room_capacity(max_capacity=2, adults=3, children=4)

        self.assertEqual(
            set(caught.exception.detail), {"capacidad_adultos", "capacidad_ninos"}
        )


class LodgingPublicationRuleTests(SimpleTestCase):
    """Un hotel solo se publica si tiene de donde sacar su precio."""

    databases: ClassVar[set[str]] = {"default"}

    @patch("apps.catalog.services.Room.objects.filter")
    def test_requires_a_published_room_with_a_positive_price(self, room_filter):
        room_filter.return_value.exists.return_value = False

        with self.assertRaises(ValidationError) as caught:
            _check_lodging_publishable(11)

        self.assertIn("estado", caught.exception.detail)
        # La busqueda exige publicada Y con precio mayor a 0.
        self.assertEqual(
            room_filter.call_args.kwargs,
            {
                "establishment_id": 11,
                "product__status": PUBLISHED,
                "product__base_price__gt": 0,
            },
        )

    @patch("apps.catalog.services.Room.objects.filter")
    def test_passes_when_such_a_room_exists(self, room_filter):
        room_filter.return_value.exists.return_value = True

        _check_lodging_publishable(11)

    @patch("apps.catalog.services.Room.objects.filter")
    def test_a_draft_room_does_not_make_the_hotel_publishable(self, room_filter):
        """Solo cuentan las publicadas: el filtro ya las exige asi."""
        room_filter.return_value.exists.return_value = False

        with self.assertRaises(ValidationError):
            _check_lodging_publishable(11)

    @patch("apps.catalog.services.record_audit")
    @patch("apps.catalog.services.ensure_product_quota_available")
    @patch("apps.catalog.services.require_permission")
    @patch("apps.catalog.services.require_tenant_access")
    def test_a_brand_new_hotel_cannot_be_born_published(
        self, tenant_access, permission, quota, audit
    ):
        with (
            patch("apps.catalog.services.City.objects.get"),
            patch("apps.catalog.services.Currency.objects.get"),
            patch("apps.catalog.services.ProductType.objects.get"),
            patch("apps.catalog.services.LodgingType.objects.get"),
            patch("apps.catalog.services._unique_product_code", return_value="X"),
            patch("apps.catalog.services.TourismProduct.objects.create") as create,
        ):
            with self.assertRaises(ValidationError) as caught:
                create_lodging(
                    actor=MagicMock(), tenant_id=7, nombre="QA Hotel", ciudad_id=2,
                    moneda_codigo="BOB", capacidad_maxima=40, estado=PUBLISHED,
                )

            create.assert_not_called()
        self.assertIn("estado", caught.exception.detail)

    @patch("apps.catalog.services.record_audit")
    @patch("apps.catalog.services.require_permission")
    @patch("apps.catalog.services._check_lodging_publishable")
    @patch("apps.catalog.services.get_company_lodging")
    def test_publishing_checks_only_on_the_transition(
        self, get_lodging, publishable, permission, audit
    ):
        """Un hotel ya publicado puede seguir editandose sin revalidar."""
        lodging = MagicMock()
        lodging.product.status = PUBLISHED
        get_lodging.return_value = lodging

        update_lodging(actor=MagicMock(), tenant_id=7, lodging_id=11, estado=PUBLISHED)

        publishable.assert_not_called()

    @patch("apps.catalog.services.record_audit")
    @patch("apps.catalog.services.require_permission")
    @patch("apps.catalog.services._check_lodging_publishable")
    @patch("apps.catalog.services.get_company_lodging")
    def test_draft_to_published_is_checked(
        self, get_lodging, publishable, permission, audit
    ):
        lodging = MagicMock()
        lodging.product.status = "BORRADOR"
        lodging.id = 11
        get_lodging.return_value = lodging

        update_lodging(actor=MagicMock(), tenant_id=7, lodging_id=11, estado=PUBLISHED)

        publishable.assert_called_once_with(11)


class RoomPriceRuleTests(SimpleTestCase):
    """Una habitacion publicada no puede costar 0.

    Si pudiera, el hotel mostraria "Habitaciones desde Bs 0".
    """

    databases: ClassVar[set[str]] = {"default"}

    def test_published_room_cannot_cost_zero(self):
        with self.assertRaises(ValidationError) as caught:
            _check_room_price(status=PUBLISHED, price=Decimal("0.00"))

        self.assertIn("precio_base", caught.exception.detail)

    def test_published_room_cannot_cost_a_negative_amount(self):
        with self.assertRaises(ValidationError):
            _check_room_price(status=PUBLISHED, price=Decimal("-5.00"))

    def test_published_room_with_a_positive_price_is_fine(self):
        _check_room_price(status=PUBLISHED, price=Decimal("180.00"))

    def test_a_draft_may_cost_zero(self):
        """Se puede guardar a medio cargar; el limite aplica al publicar."""
        _check_room_price(status="BORRADOR", price=Decimal("0.00"))

    @patch("apps.catalog.services.record_audit")
    @patch("apps.catalog.services.ensure_product_quota_available")
    @patch("apps.catalog.services.require_permission")
    @patch("apps.catalog.services.get_company_lodging")
    def test_create_room_rejects_a_published_room_at_zero(
        self, get_lodging, permission, quota, audit
    ):
        lodging = MagicMock()
        lodging.product.currency.iso_code = "BOB"
        get_lodging.return_value = lodging

        with patch("apps.catalog.services.TourismProduct.objects.create") as create:
            with self.assertRaises(ValidationError) as caught:
                create_room(
                    actor=MagicMock(), tenant_id=7, lodging_id=11, nombre="Suite",
                    precio_base=Decimal("0.00"), capacidad_maxima=2, estado=PUBLISHED,
                )

            create.assert_not_called()
        self.assertIn("precio_base", caught.exception.detail)


class FromPriceAnnotationTests(SimpleTestCase):
    """precio_desde es el menor precio POSITIVO de las habitaciones publicadas."""

    def test_marketplace_requires_published_and_a_positive_price(self):
        queryset = MagicMock()

        with_from_price(queryset)

        annotations = queryset.annotate.call_args.kwargs
        self.assertEqual(
            annotations["from_price"],
            Min(
                "rooms__product__base_price",
                filter=Q(rooms__product__status=PUBLISHED)
                & Q(rooms__product__base_price__gt=0),
            ),
        )

    def test_company_panel_also_counts_drafts(self):
        """La empresa necesita ver el precio de sus borradores, no solo publicados."""
        queryset = MagicMock()

        with_from_price(queryset, published_rooms_only=False)

        annotations = queryset.annotate.call_args.kwargs
        self.assertEqual(
            annotations["from_price"],
            Min(
                "rooms__product__base_price",
                filter=~Q(rooms__product__status="INACTIVO")
                & Q(rooms__product__base_price__gt=0),
            ),
        )

    def test_the_room_count_ignores_the_price(self):
        """Una habitacion sin precio igual existe y la empresa debe verla."""
        queryset = MagicMock()

        with_from_price(queryset)

        annotations = queryset.annotate.call_args.kwargs
        self.assertEqual(
            annotations["rooms_count"],
            Count("rooms", filter=Q(rooms__product__status=PUBLISHED), distinct=True),
        )

    def test_a_hotel_without_rooms_has_no_price(self):
        """Min sobre cero filas es NULL, y el serializer lo deja pasar como null."""
        field = LodgingSerializer().fields["precio_desde"]

        self.assertEqual(field.source, "from_price")
        self.assertTrue(field.allow_null)


class PublicVisibilityTests(SimpleTestCase):
    @patch("apps.catalog.services.LodgingEstablishment.objects.select_related")
    def test_lodgings_require_published_product_and_active_company(self, select_related):
        queryset = MagicMock()
        select_related.return_value = queryset

        public_lodgings()

        queryset.filter.assert_called_once_with(
            product__status=PUBLISHED, product__tenant__status=ACTIVE
        )

    @patch("apps.catalog.services.Room.objects.select_related")
    def test_rooms_also_require_their_lodging_published(self, select_related):
        """Al desactivar un hotel, sus habitaciones dejan de aparecer solas."""
        queryset = MagicMock()
        select_related.return_value = queryset

        public_rooms()

        queryset.filter.assert_called_once_with(
            product__status=PUBLISHED,
            product__tenant__status=ACTIVE,
            establishment__product__status=PUBLISHED,
        )


class CompanyLodgingIsolationTests(SimpleTestCase):
    # Los servicios de escritura son @transaction.atomic, que abre conexion al
    # entrar. Todo el ORM esta mockeado, asi que la unica sentencia que llega a
    # SQLite es el BEGIN/COMMIT sobre una base vacia.
    databases: ClassVar[set[str]] = {"default"}

    @patch("apps.catalog.services.list_company_lodgings")
    def test_lodging_of_another_tenant_is_not_found(self, list_lodgings):
        list_lodgings.return_value.filter.return_value.first.return_value = None

        with self.assertRaises(NotFound):
            get_company_lodging(actor=MagicMock(), tenant_id=7, lodging_id=1)

    @patch("apps.catalog.services.require_permission", side_effect=PermissionDenied)
    @patch("apps.catalog.services.require_tenant_access")
    def test_create_lodging_requires_the_manage_permission(self, tenant_access, permission):
        actor = MagicMock()

        with self.assertRaises(PermissionDenied):
            create_lodging(actor=actor, tenant_id=7, nombre="Hotel Kachi Wasi")

        permission.assert_called_once_with(actor, "PRODUCTOS_GESTIONAR", 7)


@patch("apps.catalog.services.record_audit")
@patch("apps.catalog.services.ensure_product_quota_available")
@patch("apps.catalog.services.require_permission")
@patch("apps.catalog.services.require_tenant_access")
class LodgingCreationTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    @patch("apps.catalog.services._company_lodgings")
    @patch("apps.catalog.services.LodgingEstablishment.objects.create")
    @patch("apps.catalog.services.TourismProduct.objects.create")
    @patch("apps.catalog.services._unique_product_code", return_value="HOTEL_KACHI_WASI")
    @patch("apps.catalog.services.ProductType.objects.get")
    @patch("apps.catalog.services.LodgingType.objects.get")
    @patch("apps.catalog.services.Currency.objects.get")
    @patch("apps.catalog.services.City.objects.get")
    def test_company_creates_a_hotel_with_zero_base_price(
        self, city_get, currency_get, lodging_type_get, product_type_get,
        unique_code, product_create, lodging_create, company_lodgings,
        tenant_access, permission, quota, audit,
    ):
        create_lodging(
            actor=MagicMock(), tenant_id=7, nombre="Hotel Kachi Wasi",
            ciudad_id=2, moneda_codigo="BOB", capacidad_maxima=40,
            direccion="Av. Ballivian 1234", categoria_estrellas=4,
        )

        values = product_create.call_args.kwargs
        self.assertEqual(values["tenant_id"], 7)
        self.assertEqual(values["name"], "Hotel Kachi Wasi")
        self.assertEqual(values["base_price"], 0)
        self.assertEqual(values["product_type"], product_type_get.return_value)
        product_type_get.assert_called_once_with(code="HOTEL")
        # El estado por omision es borrador: nada se publica sin decirlo.
        self.assertEqual(values["status"], "BORRADOR")

        specifics = lodging_create.call_args.kwargs
        self.assertEqual(specifics["address"], "Av. Ballivian 1234")
        self.assertEqual(specifics["star_rating"], 4)
        self.assertEqual(specifics["tenant_id"], 7)

    @patch("apps.catalog.services.LodgingType.objects.get")
    def test_lodging_type_defaults_to_hotel(
        self, lodging_type_get, tenant_access, permission, quota, audit
    ):
        with (
            patch("apps.catalog.services.City.objects.get"),
            patch("apps.catalog.services.Currency.objects.get"),
            patch("apps.catalog.services.ProductType.objects.get"),
            patch("apps.catalog.services._unique_product_code", return_value="X"),
            patch("apps.catalog.services.TourismProduct.objects.create"),
            patch("apps.catalog.services.LodgingEstablishment.objects.create"),
            patch("apps.catalog.services._company_lodgings"),
        ):
            create_lodging(
                actor=MagicMock(), tenant_id=7, nombre="Hotel Kachi Wasi",
                ciudad_id=2, moneda_codigo="BOB", capacidad_maxima=40,
            )

        lodging_type_get.assert_called_once_with(code="HOTEL")


@patch("apps.catalog.services.record_audit")
@patch("apps.catalog.services.ensure_product_quota_available")
@patch("apps.catalog.services.require_permission")
class RoomCreationTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    @staticmethod
    def _lodging():
        """Hotel Kachi Wasi en La Paz (ciudad 2), Zona Sur, cobrando en BOB."""
        lodging = MagicMock()
        lodging.id = 11
        lodging.product.city_id = 2
        lodging.product.locality = "Zona Sur"
        lodging.product.currency.iso_code = "BOB"
        return lodging

    @patch("apps.catalog.services.Room.objects.create")
    @patch("apps.catalog.services.TourismProduct.objects.create")
    @patch("apps.catalog.services._unique_product_code", return_value="HABITACION_DELUXE")
    @patch("apps.catalog.services.ProductType.objects.get")
    @patch("apps.catalog.services.Currency.objects.get")
    @patch("apps.catalog.services.get_company_lodging")
    def test_room_inherits_location_and_currency_from_its_lodging(
        self, get_lodging, currency_get, product_type_get, unique_code,
        product_create, room_create, permission, quota, audit,
    ):
        lodging = self._lodging()
        get_lodging.return_value = lodging

        create_room(
            actor=MagicMock(), tenant_id=7, lodging_id=11,
            nombre="Habitacion Deluxe Vista Illimani",
            precio_base=Decimal("380.00"), capacidad_maxima=2,
            capacidad_adultos=2, capacidad_ninos=0,
        )

        values = product_create.call_args.kwargs
        self.assertEqual(values["city_id"], 2)
        self.assertEqual(values["locality"], "Zona Sur")
        currency_get.assert_called_once_with(iso_code="BOB")

        room_values = room_create.call_args.kwargs
        self.assertEqual(room_values["establishment"], lodging)
        self.assertEqual(room_values["tenant_id"], 7)
        self.assertEqual(room_values["adults_capacity"], 2)

    @patch("apps.catalog.services.Room.objects.create")
    @patch("apps.catalog.services.TourismProduct.objects.create")
    @patch("apps.catalog.services._unique_product_code", return_value="X")
    @patch("apps.catalog.services.ProductType.objects.get")
    @patch("apps.catalog.services.Currency.objects.get")
    @patch("apps.catalog.services.get_company_lodging")
    def test_room_product_is_always_of_type_habitacion(
        self, get_lodging, currency_get, product_type_get, unique_code,
        product_create, room_create, permission, quota, audit,
    ):
        get_lodging.return_value = self._lodging()

        create_room(
            actor=MagicMock(), tenant_id=7, lodging_id=11, nombre="Suite",
            precio_base=Decimal("520.00"), capacidad_maxima=3,
        )

        product_type_get.assert_called_once_with(code="HABITACION")

    @patch("apps.catalog.services.get_company_lodging")
    def test_room_of_another_tenant_lodging_is_rejected(
        self, get_lodging, permission, quota, audit
    ):
        """El aislamiento se corta antes de escribir: el hotel ni se encuentra."""
        get_lodging.side_effect = NotFound

        with self.assertRaises(NotFound):
            create_room(
                actor=MagicMock(), tenant_id=7, lodging_id=999, nombre="Suite",
                precio_base=Decimal("520.00"), capacidad_maxima=3,
            )

    @patch("apps.catalog.services.get_company_lodging")
    def test_individual_limit_above_the_total_is_rejected_before_writing(
        self, get_lodging, permission, quota, audit
    ):
        """Un tope de 4 adultos en una habitacion de 2 plazas no tiene sentido."""
        get_lodging.return_value = self._lodging()

        with self.assertRaises(ValidationError) as caught:
            create_room(
                actor=MagicMock(), tenant_id=7, lodging_id=11, nombre="Suite",
                precio_base=Decimal("520.00"), capacidad_maxima=2,
                capacidad_adultos=4, capacidad_ninos=1,
            )

        self.assertIn("capacidad_adultos", caught.exception.detail)

    @patch("apps.catalog.services.Room.objects.create")
    @patch("apps.catalog.services.TourismProduct.objects.create")
    @patch("apps.catalog.services._unique_product_code", return_value="X")
    @patch("apps.catalog.services.ProductType.objects.get")
    @patch("apps.catalog.services.Currency.objects.get")
    @patch("apps.catalog.services.get_company_lodging")
    def test_alternative_limits_are_accepted(
        self, get_lodging, currency_get, product_type_get, unique_code,
        product_create, room_create, permission, quota, audit,
    ):
        """Tope 4, hasta 4 adultos y hasta 3 ninos: combinaciones alternativas."""
        get_lodging.return_value = self._lodging()

        create_room(
            actor=MagicMock(), tenant_id=7, lodging_id=11, nombre="Familiar",
            precio_base=Decimal("280.00"), capacidad_maxima=4,
            capacidad_adultos=4, capacidad_ninos=3,
        )

        room_values = room_create.call_args.kwargs
        self.assertEqual(room_values["adults_capacity"], 4)
        self.assertEqual(room_values["children_capacity"], 3)


class GenericProductEndpointIsClosedToLodgingTests(SimpleTestCase):
    """Un hotel solo nace en /hospedajes/, nunca en /productos/.

    De lo contrario quedaria un producto HOTEL sin ficha de establecimiento:
    incapaz de tener habitaciones e invisible para el Marketplace de hospedaje.
    """

    databases: ClassVar[set[str]] = {"default"}

    def test_create_rejects_hotel(self):
        serializer = ProductWriteSerializer(data={"tipo_codigo": "HOTEL"}, partial=True)

        self.assertFalse(serializer.is_valid())
        self.assertIn("hospedajes", str(serializer.errors["tipo_codigo"]))

    def test_create_rejects_room(self):
        serializer = ProductWriteSerializer(data={"tipo_codigo": "HABITACION"}, partial=True)

        self.assertFalse(serializer.is_valid())
        self.assertIn("tipo_codigo", serializer.errors)

    def test_other_product_types_are_untouched(self):
        """Los tours y demas siguen entrando por la via generica."""
        with patch(
            "apps.catalog.serializers.ProductType.objects.filter"
        ) as product_type_filter:
            product_type_filter.return_value.exists.return_value = True
            serializer = ProductWriteSerializer(data={"tipo_codigo": "TOUR"}, partial=True)

            self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["tipo_codigo"], "TOUR")

    @patch("apps.catalog.services.TourismProduct.objects.select_related")
    @patch("apps.catalog.services.require_permission")
    @patch("apps.catalog.services.require_tenant_access")
    def test_patch_of_an_existing_hotel_is_rejected(
        self, tenant_access, permission, select_related
    ):
        """El tipo no viaja en un PATCH parcial: se mira el del producto guardado."""
        hotel = MagicMock()
        hotel.product_type.code = "HOTEL"
        select_related.return_value.filter.return_value.first.return_value = hotel

        with self.assertRaises(ValidationError) as caught:
            update_product(actor=MagicMock(), tenant_id=7, product_id=1, precio_base=200)

        self.assertIn("tipo_codigo", caught.exception.detail)


class GenericMarketplaceFromPriceTests(SimpleTestCase):
    def test_annotates_the_cheapest_published_room_with_a_positive_price(self):
        queryset = MagicMock()

        with_lodging_from_price(queryset)

        annotations = queryset.annotate.call_args.kwargs
        self.assertEqual(
            annotations["from_price"],
            Min(
                "lodging__rooms__product__base_price",
                filter=Q(
                    lodging__rooms__product__status=PUBLISHED,
                    lodging__rooms__product__base_price__gt=0,
                ),
            ),
        )


class OrphanLodgingProductsTests(SimpleTestCase):
    """Los HOTEL y HABITACION sin ficha no deben salir en el Marketplace.

    Son productos creados por /api/v1/productos/ antes de este modulo. Una
    habitacion asi no tiene hotel, ni empresa responsable, ni ubicacion heredada
    que mostrar, y 0005 no puede repararla porque no hay dato que indique a que
    hotel pertenecia.
    """

    # La condicion completa del filtro se verifica en
    # IncompleteHotelVisibilityTests.test_generic_marketplace_requires_it_for_hotels,
    # que incluye la exigencia de habitacion ofertable para los hoteles.

    def test_uses_filter_so_pagination_and_other_filters_still_chain(self):
        """Anota y filtra, sin distinct: las relaciones del OR son de un solo valor.

        El unico multivaluado (rooms) entra por una subconsulta Exists, que no
        duplica filas, asi que el count() del paginador sigue siendo exacto.
        """
        queryset = MagicMock()

        result = only_complete_lodging_products(queryset)

        annotated = queryset.annotate.return_value
        annotated.filter.assert_called_once()
        self.assertEqual(result, annotated.filter.return_value)
        result.distinct.assert_not_called()


class RoomCardInGenericMarketplaceTests(SimpleTestCase):
    """Una habitacion en la categoria "Todos" debe poder nombrar su hotel."""

    @staticmethod
    def _missing(product, *relations):
        """Simula un OneToOne inverso ausente.

        Django no devuelve None: levanta ``RelatedObjectDoesNotExist``, que
        hereda de ObjectDoesNotExist. Hay que imitar eso y no un AttributeError,
        porque es justo lo que atrapa el serializer.
        """
        for relation in relations:
            setattr(type(product), relation, PropertyMock(side_effect=ObjectDoesNotExist))

    def test_exposes_the_hotel_name_and_its_lodging_id(self):
        product = MagicMock()
        product.room.establishment_id = 11
        product.room.establishment.product.name = "Hotel Kachi Wasi"
        self._missing(product, "lodging")  # es una habitacion, no un hotel

        serializer = ProductSerializer()

        self.assertEqual(serializer.get_establecimiento(product), "Hotel Kachi Wasi")
        self.assertEqual(serializer.get_hospedaje_id(product), 11)

    def test_a_hotel_points_at_its_own_lodging_not_at_its_product_id(self):
        """El id de establecimiento_hospedaje y el del producto son distintos."""
        product = MagicMock(id=500)
        product.lodging.id = 11
        self._missing(product, "room")

        serializer = ProductSerializer()

        self.assertEqual(serializer.get_hospedaje_id(product), 11)
        self.assertIsNone(serializer.get_establecimiento(product))

    def test_a_tour_has_neither(self):
        product = MagicMock()
        self._missing(product, "room", "lodging")

        serializer = ProductSerializer()

        self.assertIsNone(serializer.get_establecimiento(product))
        self.assertIsNone(serializer.get_hospedaje_id(product))

    def test_serializer_exposes_the_annotation(self):
        product = MagicMock(from_price=Decimal("180.00"))

        self.assertEqual(ProductSerializer().get_precio_desde(product), "180.00")

    def test_serializer_is_null_without_the_annotation(self):
        """Un tour, o cualquier consulta sin anotar, no revienta."""
        product = MagicMock(spec=[])

        self.assertIsNone(ProductSerializer().get_precio_desde(product))


class LodgingTypeRestrictionTests(SimpleTestCase):
    """En esta fase solo se admite HOTEL, y el limite vive en el backend.

    Que la web deshabilite las otras opciones del desplegable no impide un POST
    directo, asi que la regla se comprueba donde no se puede eludir.
    """

    UNSUPPORTED = "En esta versión solamente se admite el tipo HOTEL."

    def _validated(self, code: str):
        """Valida el serializer con los demas campos dados por buenos."""
        with (
            patch("apps.catalog.serializers.LodgingType.objects.filter") as types,
            patch("apps.catalog.serializers.City.objects.filter") as cities,
            patch("apps.catalog.serializers.Currency.objects.filter") as currencies,
        ):
            types.return_value.exists.return_value = code in {
                "HOTEL", "HOSTAL", "CABANA", "APARTAMENTO_TURISTICO", "HOSPEDAJE_RURAL",
            }
            cities.return_value.exists.return_value = True
            currencies.return_value.exists.return_value = True
            serializer = LodgingWriteSerializer(
                data={
                    "nombre": "QA Hotel", "ciudad_id": 1, "moneda_codigo": "BOB",
                    "capacidad_maxima": 10, "tipo_hospedaje_codigo": code,
                }
            )
            valid = serializer.is_valid()
        return valid, serializer

    def _post(self, code: str):
        """POST real contra la vista, para ver el cuerpo que devuelve la API."""
        request = APIRequestFactory().post(
            "/api/v1/hospedajes/",
            {
                "nombre": "QA Hotel", "ciudad_id": 1, "moneda_codigo": "BOB",
                "capacidad_maxima": 10, "tipo_hospedaje_codigo": code,
            },
            format="json",
            HTTP_X_TENANT_ID="7",
        )
        force_authenticate(request, user=MagicMock(is_authenticated=True))
        with (
            patch("apps.catalog.serializers.LodgingType.objects.filter") as types,
            patch("apps.catalog.serializers.City.objects.filter") as cities,
            patch("apps.catalog.serializers.Currency.objects.filter") as currencies,
        ):
            types.return_value.exists.return_value = True
            cities.return_value.exists.return_value = True
            currencies.return_value.exists.return_value = True
            return CompanyLodgingListCreateView.as_view()(request)

    # ---- 1. HOTEL es aceptado ----
    def test_hotel_is_accepted(self):
        valid, serializer = self._validated("HOTEL")

        self.assertTrue(valid, serializer.errors)
        self.assertEqual(serializer.validated_data["tipo_hospedaje_codigo"], "HOTEL")

    def test_hotel_passes_the_service_guard(self):
        with patch("apps.catalog.services.LodgingType.objects.get") as get_type:
            self.assertEqual(_lodging_type("HOTEL"), get_type.return_value)
        get_type.assert_called_once_with(code="HOTEL")

    # ---- 2. HOSTAL es rechazado con 400 ----
    def test_hostal_is_rejected_with_400(self):
        response = self._post("HOSTAL")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["error"]["details"]["tipo_hospedaje_codigo"],
            [self.UNSUPPORTED],
        )

    # ---- 3. CABANA es rechazada con 400 ----
    def test_cabana_is_rejected_with_400(self):
        response = self._post("CABANA")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["error"]["details"]["tipo_hospedaje_codigo"],
            [self.UNSUPPORTED],
        )

    def test_cabana_written_with_tilde_is_also_rejected(self):
        """El codigo del catalogo es CABANA; "CABAÑA" ni existe."""
        valid, serializer = self._validated("CABAÑA")

        self.assertFalse(valid)
        self.assertIn("tipo_hospedaje_codigo", serializer.errors)

    def test_remaining_types_are_rejected_too(self):
        for code in ("APARTAMENTO_TURISTICO", "HOSPEDAJE_RURAL"):
            with self.subTest(code=code):
                valid, serializer = self._validated(code)

                self.assertFalse(valid)
                self.assertEqual(
                    serializer.errors["tipo_hospedaje_codigo"], [self.UNSUPPORTED]
                )

    def test_service_rejects_unsupported_type_without_going_through_http(self):
        """Un comando o un shell tampoco puede crear un hostal."""
        with self.assertRaises(ValidationError) as caught:
            _lodging_type("HOSTAL")

        self.assertEqual(
            caught.exception.detail["tipo_hospedaje_codigo"], [self.UNSUPPORTED]
        )


class ClientCannotSetIdentityFieldsTests(SimpleTestCase):
    """4. tenant_id, producto_id y establecimiento_id no son del cliente.

    Importa porque los servicios pasan lo que valida el serializer a
    ``setattr``: si alguno de esos campos pudiera llegar, se podria reasignar un
    producto a otra empresa. La barrera es que son ``Serializer`` planos (no
    ``ModelSerializer``), asi que DRF descarta todo lo no declarado.
    """

    FORBIDDEN = ("tenant_id", "tenant", "producto_id", "establecimiento_id", "id")

    def test_lodging_serializer_declares_no_identity_field(self):
        declared = set(LodgingWriteSerializer().fields)

        self.assertEqual(declared & set(self.FORBIDDEN), set())

    def test_room_serializer_declares_no_identity_field(self):
        declared = set(RoomWriteSerializer().fields)

        self.assertEqual(declared & set(self.FORBIDDEN), set())

    def test_lodging_serializer_drops_them_on_create(self):
        with (
            patch("apps.catalog.serializers.LodgingType.objects.filter") as types,
            patch("apps.catalog.serializers.City.objects.filter") as cities,
            patch("apps.catalog.serializers.Currency.objects.filter") as currencies,
        ):
            types.return_value.exists.return_value = True
            cities.return_value.exists.return_value = True
            currencies.return_value.exists.return_value = True
            serializer = LodgingWriteSerializer(data={
                "nombre": "QA Hotel", "ciudad_id": 1, "moneda_codigo": "BOB",
                "capacidad_maxima": 10, "tipo_hospedaje_codigo": "HOTEL",
                "tenant_id": 999, "producto_id": 999, "establecimiento_id": 999, "id": 999,
            })
            self.assertTrue(serializer.is_valid(), serializer.errors)

        for field in self.FORBIDDEN:
            self.assertNotIn(field, serializer.validated_data)

    def test_room_serializer_drops_them_on_patch(self):
        """Tampoco se pueden modificar: un PATCH con esos campos los ignora."""
        serializer = RoomWriteSerializer(
            data={
                "precio_base": "200.00",
                "tenant_id": 999, "producto_id": 999, "establecimiento_id": 999, "id": 999,
            },
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(set(serializer.validated_data), {"precio_base"})

    def test_no_writable_field_maps_to_the_lodging_or_the_tenant(self):
        """Ni siquiera por dentro hay un camino para mover una habitacion.

        ``update_room`` aplica a la fila solo las claves de ``_ROOM_FIELDS``; si
        ninguna apunta al establecimiento o al tenant, no existe payload que la
        reasigne.
        """
        from apps.catalog.services import _LODGING_FIELDS, _ROOM_FIELDS

        destinos = set(_ROOM_FIELDS.values()) | set(_LODGING_FIELDS.values())

        self.assertEqual(destinos & {"establishment", "establishment_id", "tenant", "tenant_id", "product", "product_id"}, set())


class CrossTenantAccessTests(SimpleTestCase):
    """5. Un hospedaje o habitacion de otra empresa no se alcanza."""

    databases: ClassVar[set[str]] = {"default"}

    @patch("apps.catalog.services.list_company_lodgings")
    def test_lodging_of_another_tenant_returns_not_found(self, list_lodgings):
        """El queryset ya viene filtrado por tenant: el id ajeno no aparece."""
        list_lodgings.return_value.filter.return_value.first.return_value = None

        with self.assertRaises(NotFound):
            get_company_lodging(actor=MagicMock(), tenant_id=7, lodging_id=4242)

    @patch("apps.catalog.services.Room.objects.select_related")
    @patch("apps.catalog.services.require_permission")
    @patch("apps.catalog.services.require_tenant_access")
    def test_room_of_another_tenant_returns_not_found(
        self, tenant_access, permission, select_related
    ):
        select_related.return_value.filter.return_value.first.return_value = None

        with self.assertRaises(NotFound):
            get_company_room(actor=MagicMock(), tenant_id=7, room_id=4242)

        # La consulta se acota por tenant, no solo por id.
        self.assertEqual(
            select_related.return_value.filter.call_args.kwargs,
            {"id": 4242, "tenant_id": 7},
        )

    @patch("apps.catalog.services.require_tenant_access", side_effect=PermissionDenied)
    def test_tenant_without_membership_is_denied(self, tenant_access):
        """Enviar un X-Tenant-ID ajeno corta antes de tocar datos."""
        with self.assertRaises(PermissionDenied):
            get_company_room(actor=MagicMock(), tenant_id=999, room_id=1)

    @patch("apps.catalog.services.get_company_room")
    @patch("apps.catalog.services.require_permission", side_effect=PermissionDenied)
    def test_update_room_requires_the_manage_permission(self, permission, get_room):
        actor = MagicMock()

        with self.assertRaises(PermissionDenied):
            update_room(actor=actor, tenant_id=7, room_id=1, nombre="X")

        permission.assert_called_once_with(actor, "PRODUCTOS_GESTIONAR", 7)


class DerivedHotelCapacityTests(SimpleTestCase):
    """La capacidad del hotel se deriva: SUM(cantidad x capacidad por tipo).

    producto_turistico.capacidad_maxima es NOT NULL con CHECK (> 0), asi que no
    puede guardar el 0 que corresponderia a un hotel sin habitaciones. Se guarda
    un centinela y el dato real se calcula.
    """

    databases: ClassVar[set[str]] = {"default"}

    def test_annotates_the_sum_of_units_times_capacity(self):
        queryset = MagicMock()

        with_from_price(queryset)

        annotations = queryset.annotate.call_args.kwargs
        self.assertEqual(
            annotations["total_capacity"],
            Sum(
                F("rooms__quantity") * F("rooms__product__max_capacity"),
                filter=Q(rooms__product__status=PUBLISHED),
            ),
        )

    def test_company_panel_sums_non_inactive_rooms(self):
        queryset = MagicMock()

        with_from_price(queryset, published_rooms_only=False)

        annotations = queryset.annotate.call_args.kwargs
        self.assertEqual(
            annotations["total_capacity"],
            Sum(
                F("rooms__quantity") * F("rooms__product__max_capacity"),
                filter=~Q(rooms__product__status="INACTIVO"),
            ),
        )

    def test_serializer_reports_null_while_there_is_nothing_to_sum(self):
        """Sum sobre cero filas es NULL: el hotel sin habitaciones no miente un 0."""
        field = LodgingSerializer().fields["capacidad_total"]

        self.assertEqual(field.source, "total_capacity")
        self.assertTrue(field.allow_null)

    def test_the_write_serializer_does_not_accept_a_manual_capacity(self):
        self.assertNotIn("capacidad_maxima", LodgingWriteSerializer().fields)

    def test_the_read_serializer_does_not_expose_the_sentinel(self):
        """capacidad_maxima del hotel vale 1 y no debe verse en ningun lado."""
        self.assertNotIn("capacidad_maxima", LodgingSerializer().fields)

    @patch("apps.catalog.services.record_audit")
    @patch("apps.catalog.services.ensure_product_quota_available")
    @patch("apps.catalog.services.require_permission")
    @patch("apps.catalog.services.require_tenant_access")
    def test_create_stores_the_sentinel(self, tenant_access, permission, quota, audit):
        with (
            patch("apps.catalog.services.City.objects.get"),
            patch("apps.catalog.services.Currency.objects.get"),
            patch("apps.catalog.services.ProductType.objects.get"),
            patch("apps.catalog.services.LodgingType.objects.get"),
            patch("apps.catalog.services._unique_product_code", return_value="X"),
            patch("apps.catalog.services.TourismProduct.objects.create") as create,
            patch("apps.catalog.services.LodgingEstablishment.objects.create"),
            patch("apps.catalog.services._company_lodgings"),
        ):
            create_lodging(
                actor=MagicMock(), tenant_id=7, nombre="QA Hotel",
                ciudad_id=2, moneda_codigo="BOB",
            )

            # 1 es el minimo que admite CHECK (capacidad_maxima > 0).
            self.assertEqual(create.call_args.kwargs["max_capacity"], 1)


class IncompleteHotelVisibilityTests(SimpleTestCase):
    """Un hotel sin habitacion ofertable no se muestra en el Marketplace.

    La migracion 0006 repara los heredados una vez, pero el estado se vuelve a
    alcanzar despublicando la ultima habitacion: por eso la consulta publica lo
    exige en cada pedido.
    """

    @patch("apps.catalog.services.LodgingEstablishment.objects.select_related")
    def test_public_lodgings_require_a_publishable_room(self, select_related):
        primero = MagicMock()
        select_related.return_value.filter.return_value = primero

        public_lodgings()

        # Primero el estado y la empresa, despues la existencia de habitacion.
        select_related.return_value.filter.assert_called_once_with(
            product__status=PUBLISHED, product__tenant__status=ACTIVE
        )
        primero.filter.assert_called_once()
        condition = primero.filter.call_args.args[0]
        self.assertIsInstance(condition, Exists)

    def test_the_company_panel_still_shows_them(self):
        """La empresa tiene que ver lo que le falta arreglar."""
        with patch(
            "apps.catalog.services.LodgingEstablishment.objects.select_related"
        ) as select_related:
            queryset = MagicMock()
            select_related.return_value.filter.return_value = queryset

            _company_lodgings(7)

            # Un solo filter, el del tenant: sin exigir habitacion ofertable.
            select_related.return_value.filter.assert_called_once_with(tenant_id=7)
            queryset.filter.assert_not_called()

    def test_generic_marketplace_requires_it_for_hotels(self):
        queryset = MagicMock()

        only_complete_lodging_products(queryset)

        annotated = queryset.annotate.return_value
        condition = annotated.filter.call_args.args[0]
        self.assertEqual(
            condition,
            ~Q(product_type__code__in=LODGING_PRODUCT_CODES)
            | Q(
                product_type__code="HOTEL",
                lodging__isnull=False,
                has_publishable_room=True,
            )
            | Q(
                product_type__code="HABITACION",
                room__isnull=False,
                room__establishment__product__status=PUBLISHED,
            ),
        )

    def test_the_exists_subquery_only_counts_published_priced_rooms(self):
        with patch("apps.catalog.services.Room.objects.filter") as room_filter:
            _publishable_room_exists(establishment=OuterRef("pk"))

        self.assertEqual(
            room_filter.call_args.kwargs["product__status"], PUBLISHED
        )
        self.assertEqual(room_filter.call_args.kwargs["product__base_price__gt"], 0)


class CompanyCatalogShowsLodgingTests(SimpleTestCase):
    """Catalogo es la vista general: los hospedajes vuelven a aparecer.

    Pero sin los filtros del Marketplace: la empresa debe ver sus hoteles
    incompletos y sus habitaciones huerfanas para poder arreglarlos.
    """

    @patch("apps.catalog.services.require_permission")
    @patch("apps.catalog.services.require_tenant_access")
    def test_annotates_from_price_so_a_hotel_card_has_a_price(
        self, tenant_access, permission
    ):
        with patch(
            "apps.catalog.services.TourismProduct.objects.select_related"
        ) as select_related:
            list_company_products(actor=MagicMock(), tenant_id=7)

            annotations = select_related.return_value.annotate.call_args.kwargs
            self.assertIn("from_price", annotations)
            # Y trae las relaciones para nombrar el hotel sin N+1.
            related = select_related.call_args.args
            self.assertIn("room__establishment__product", related)
            self.assertIn("lodging", related)

    @patch("apps.catalog.services.require_permission")
    @patch("apps.catalog.services.require_tenant_access")
    def test_does_not_hide_incomplete_lodging_from_the_company(
        self, tenant_access, permission
    ):
        with patch("apps.catalog.services.TourismProduct.objects.select_related") as sr:
            result = list_company_products(actor=MagicMock(), tenant_id=7)

            # Un solo filter, el del tenant. Nada de only_complete_*.
            annotated = sr.return_value.annotate.return_value
            annotated.filter.assert_called_once_with(tenant_id=7)
            self.assertEqual(result, annotated.filter.return_value)


class PublicRoomQueryTests(SimpleTestCase):
    def test_rejects_inverted_price_range(self):
        query = PublicRoomQuerySerializer(data={"precio_min": "500", "precio_max": "100"})

        self.assertFalse(query.is_valid())
        self.assertIn("precio_max", query.errors)

    def test_accepts_guest_and_lodging_filters(self):
        query = PublicRoomQuerySerializer(data={"huespedes": 2, "hospedaje": 11})

        self.assertTrue(query.is_valid(), query.errors)
        self.assertEqual(query.validated_data["huespedes"], 2)
        self.assertEqual(query.validated_data["hospedaje"], 11)
