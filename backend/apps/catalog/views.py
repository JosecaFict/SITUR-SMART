from django.db.models import F, Q
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.rbac.services import require_permission, require_tenant_access
from apps.rbac.views import tenant_id_from_request
from apps.tenancy.models import City
from apps.tenancy.subscriptions import restricted_tenant_ids

from .geocoding import GeocodingUnavailable, reverse_geocode, search_places
from .models import Currency, LodgingType, ProductType, TourismProduct
from .serializers import (
    CurrencySerializer,
    GeocodingPlaceSerializer,
    GeocodingReverseQuerySerializer,
    GeocodingSearchQuerySerializer,
    LodgingSerializer,
    LodgingTypeSerializer,
    LodgingWriteSerializer,
    MarketplaceQuerySerializer,
    ProductSerializer,
    ProductTypeSerializer,
    ProductWriteSerializer,
    PublicLodgingQuerySerializer,
    PublicRoomQuerySerializer,
    RoomSerializer,
    RoomWriteSerializer,
)
from .services import (
    create_lodging,
    create_product,
    create_room,
    deactivate_lodging,
    deactivate_product,
    deactivate_room,
    get_company_lodging,
    get_company_product,
    get_company_room,
    get_public_lodging,
    get_public_room,
    list_company_lodgings,
    list_company_products,
    list_lodging_rooms,
    marketplace_visible_products,
    public_lodgings,
    public_rooms,
    update_lodging,
    update_product,
    update_room,
    with_lodging_from_price,
)


class MarketplacePagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 50


class ProductTypeListView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(responses=ProductTypeSerializer(many=True))
    def get(self, request):
        return Response(ProductTypeSerializer(ProductType.objects.all(), many=True).data)


class CurrencyListView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(responses=CurrencySerializer(many=True))
    def get(self, request):
        return Response(CurrencySerializer(Currency.objects.all(), many=True).data)


class PublicProductListView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(parameters=[MarketplaceQuerySerializer], responses=ProductSerializer(many=True))
    def get(self, request):
        query = MarketplaceQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        filters = query.validated_data

        products = marketplace_visible_products(
            with_lodging_from_price(
                TourismProduct.objects.select_related(
                    "tenant", "product_type", "city__country", "currency",
                    # Para que la tarjeta de una habitacion pueda nombrar su
                    # hotel sin una consulta por fila.
                    "room__establishment__product", "lodging",
                )
            ).filter(status=TourismProduct.Status.PUBLISHED, tenant__status="ACTIVO")
            .exclude(tenant_id__in=restricted_tenant_ids())
        )
        if value := filters.get("pais"):
            products = products.filter(city__country_id=value)
        if value := filters.get("ciudad"):
            products = products.filter(city_id=value)
        if value := filters.get("localidad"):
            products = products.filter(locality__icontains=value)
        if value := filters.get("tipo"):
            products = products.filter(product_type__code=value.upper())
        if value := filters.get("buscar"):
            products = products.filter(
                Q(name__icontains=value) | Q(description__icontains=value) | Q(tenant__trade_name__icontains=value)
            )
        if selected_date := filters.get("fecha"):
            products = products.filter(
                availabilities__start__date__lte=selected_date,
                availabilities__end__date__gte=selected_date,
                availabilities__closed=False,
                availabilities__total_capacity__gt=0,
            ).distinct()
        minimum = filters.get("precio_min")
        if minimum is not None:
            products = products.filter(base_price__gte=minimum)
        maximum = filters.get("precio_max")
        if maximum is not None:
            products = products.filter(base_price__lte=maximum)

        ordering = {
            "recientes": ("-updated_at", "-id"),
            "precio_asc": ("base_price", "id"),
            "precio_desc": ("-base_price", "id"),
            "nombre": ("name", "id"),
        }[filters.get("orden", "recientes")]
        products = products.order_by(*ordering)

        paginator = MarketplacePagination()
        page = paginator.paginate_queryset(products, request, view=self)
        return paginator.get_paginated_response(ProductSerializer(page, many=True).data)


class PublicProductDetailView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(responses=ProductSerializer)
    def get(self, request, pk):
        product = (
            marketplace_visible_products(
                with_lodging_from_price(
                    TourismProduct.objects.select_related(
                        "tenant", "product_type", "city__country", "currency",
                        "room__establishment__product", "lodging",
                    )
                )
            )
            .filter(id=pk, status=TourismProduct.Status.PUBLISHED, tenant__status="ACTIVO")
            .exclude(tenant_id__in=restricted_tenant_ids())
            .first()
        )
        if product is None:
            raise NotFound("Producto no encontrado.")
        return Response(ProductSerializer(product).data)


class CompanyProductListCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=ProductSerializer(many=True))
    def get(self, request):
        tenant_id = tenant_id_from_request(request, required=True)
        products = list_company_products(actor=request.user, tenant_id=tenant_id)
        return Response(ProductSerializer(products, many=True).data)

    @extend_schema(request=ProductWriteSerializer, responses={201: ProductSerializer})
    def post(self, request):
        tenant_id = tenant_id_from_request(request, required=True)
        serializer = ProductWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = create_product(
            actor=request.user, tenant_id=tenant_id, request=request, **serializer.validated_data
        )
        return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)


class CompanyProductDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=ProductSerializer)
    def get(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        return Response(ProductSerializer(get_company_product(actor=request.user, tenant_id=tenant_id, product_id=pk)).data)

    @extend_schema(request=ProductWriteSerializer, responses=ProductSerializer)
    def patch(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        serializer = ProductWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        product = update_product(
            actor=request.user, tenant_id=tenant_id, product_id=pk,
            request=request, **serializer.validated_data,
        )
        return Response(ProductSerializer(product).data)

    @extend_schema(responses=ProductSerializer)
    def delete(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        product = deactivate_product(
            actor=request.user, tenant_id=tenant_id, product_id=pk, request=request
        )
        return Response(ProductSerializer(product).data)


# ============================================================
# HOSPEDAJE - CATALOGO
# ============================================================


class LodgingTypeListView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(responses=LodgingTypeSerializer(many=True))
    def get(self, request):
        return Response(LodgingTypeSerializer(LodgingType.objects.all(), many=True).data)


# ============================================================
# HOSPEDAJE - API EMPRESARIAL
# ============================================================
# Todas exigen autenticacion y X-Tenant-ID; la verificacion de membresia,
# permisos y aislamiento entre tenants vive en los servicios, igual que en el
# resto del modulo de catalogo.


class CompanyLodgingListCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=LodgingSerializer(many=True))
    def get(self, request):
        tenant_id = tenant_id_from_request(request, required=True)
        lodgings = list_company_lodgings(actor=request.user, tenant_id=tenant_id)
        return Response(LodgingSerializer(lodgings, many=True).data)

    @extend_schema(request=LodgingWriteSerializer, responses={201: LodgingSerializer})
    def post(self, request):
        tenant_id = tenant_id_from_request(request, required=True)
        serializer = LodgingWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lodging = create_lodging(
            actor=request.user, tenant_id=tenant_id, request=request, **serializer.validated_data
        )
        return Response(LodgingSerializer(lodging).data, status=status.HTTP_201_CREATED)


class CompanyLodgingDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=LodgingSerializer)
    def get(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        lodging = get_company_lodging(actor=request.user, tenant_id=tenant_id, lodging_id=pk)
        return Response(LodgingSerializer(lodging).data)

    @extend_schema(request=LodgingWriteSerializer, responses=LodgingSerializer)
    def patch(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        serializer = LodgingWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        lodging = update_lodging(
            actor=request.user, tenant_id=tenant_id, lodging_id=pk,
            request=request, **serializer.validated_data,
        )
        return Response(LodgingSerializer(lodging).data)

    @extend_schema(responses=LodgingSerializer)
    def delete(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        lodging = deactivate_lodging(
            actor=request.user, tenant_id=tenant_id, lodging_id=pk, request=request
        )
        return Response(LodgingSerializer(lodging).data)


class CompanyLodgingRoomListCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=RoomSerializer(many=True))
    def get(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        rooms = list_lodging_rooms(actor=request.user, tenant_id=tenant_id, lodging_id=pk)
        return Response(RoomSerializer(rooms, many=True).data)

    @extend_schema(request=RoomWriteSerializer, responses={201: RoomSerializer})
    def post(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        serializer = RoomWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        room = create_room(
            actor=request.user, tenant_id=tenant_id, lodging_id=pk,
            request=request, **serializer.validated_data,
        )
        return Response(RoomSerializer(room).data, status=status.HTTP_201_CREATED)


class CompanyRoomDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=RoomSerializer)
    def get(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        room = get_company_room(actor=request.user, tenant_id=tenant_id, room_id=pk)
        return Response(RoomSerializer(room).data)

    @extend_schema(request=RoomWriteSerializer, responses=RoomSerializer)
    def patch(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        serializer = RoomWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        room = update_room(
            actor=request.user, tenant_id=tenant_id, room_id=pk,
            request=request, **serializer.validated_data,
        )
        return Response(RoomSerializer(room).data)

    @extend_schema(responses=RoomSerializer)
    def delete(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        room = deactivate_room(
            actor=request.user, tenant_id=tenant_id, room_id=pk, request=request
        )
        return Response(RoomSerializer(room).data)


# ============================================================
# HOSPEDAJE - API PUBLICA
# ============================================================


class PublicLodgingListView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(parameters=[PublicLodgingQuerySerializer], responses=LodgingSerializer(many=True))
    def get(self, request):
        query = PublicLodgingQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        filters = query.validated_data

        lodgings = public_lodgings()
        if value := filters.get("pais"):
            lodgings = lodgings.filter(product__city__country_id=value)
        if value := filters.get("ciudad"):
            lodgings = lodgings.filter(product__city_id=value)
        if value := filters.get("localidad"):
            lodgings = lodgings.filter(product__locality__icontains=value)
        if value := filters.get("tipo_hospedaje"):
            lodgings = lodgings.filter(lodging_type__code=value.upper())
        if value := filters.get("estrellas"):
            lodgings = lodgings.filter(star_rating__gte=value)
        if value := filters.get("buscar"):
            lodgings = lodgings.filter(
                Q(product__name__icontains=value)
                | Q(product__description__icontains=value)
                | Q(product__tenant__trade_name__icontains=value)
                | Q(address__icontains=value)
            )
        # El precio filtrado es el "desde", no el precio_base del hotel (que es 0).
        minimum = filters.get("precio_min")
        if minimum is not None:
            lodgings = lodgings.filter(from_price__gte=minimum)
        maximum = filters.get("precio_max")
        if maximum is not None:
            lodgings = lodgings.filter(from_price__lte=maximum)

        # nulls_last mantiene al final los hoteles sin habitaciones publicadas,
        # que no tienen precio "desde" que mostrar.
        ordering = {
            "recientes": (F("product__updated_at").desc(), F("id").desc()),
            "precio_asc": (F("from_price").asc(nulls_last=True), F("id").asc()),
            "precio_desc": (F("from_price").desc(nulls_last=True), F("id").asc()),
            "nombre": (F("product__name").asc(), F("id").asc()),
        }[filters.get("orden", "recientes")]
        lodgings = lodgings.order_by(*ordering)

        paginator = MarketplacePagination()
        page = paginator.paginate_queryset(lodgings, request, view=self)
        return paginator.get_paginated_response(LodgingSerializer(page, many=True).data)


class PublicLodgingDetailView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(responses=LodgingSerializer)
    def get(self, request, pk):
        return Response(LodgingSerializer(get_public_lodging(pk)).data)


class PublicLodgingRoomListView(APIView):
    """Habitaciones publicadas de un establecimiento, de la mas economica a la mas cara."""

    permission_classes = (AllowAny,)

    @extend_schema(responses=RoomSerializer(many=True))
    def get(self, request, pk):
        lodging = get_public_lodging(pk)
        rooms = public_rooms().filter(establishment=lodging).order_by("product__base_price", "id")
        return Response(RoomSerializer(rooms, many=True).data)


class PublicRoomListView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(parameters=[PublicRoomQuerySerializer], responses=RoomSerializer(many=True))
    def get(self, request):
        query = PublicRoomQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        filters = query.validated_data

        rooms = public_rooms()
        if value := filters.get("hospedaje"):
            rooms = rooms.filter(establishment_id=value)
        if value := filters.get("pais"):
            rooms = rooms.filter(product__city__country_id=value)
        if value := filters.get("ciudad"):
            rooms = rooms.filter(product__city_id=value)
        if value := filters.get("localidad"):
            rooms = rooms.filter(product__locality__icontains=value)
        if value := filters.get("huespedes"):
            rooms = rooms.filter(product__max_capacity__gte=value)
        if value := filters.get("buscar"):
            rooms = rooms.filter(
                Q(product__name__icontains=value)
                | Q(product__description__icontains=value)
                | Q(establishment__product__name__icontains=value)
                | Q(product__tenant__trade_name__icontains=value)
            )
        minimum = filters.get("precio_min")
        if minimum is not None:
            rooms = rooms.filter(product__base_price__gte=minimum)
        maximum = filters.get("precio_max")
        if maximum is not None:
            rooms = rooms.filter(product__base_price__lte=maximum)

        ordering = {
            "recientes": ("-product__updated_at", "-id"),
            "precio_asc": ("product__base_price", "id"),
            "precio_desc": ("-product__base_price", "id"),
            "nombre": ("product__name", "id"),
        }[filters.get("orden", "recientes")]
        rooms = rooms.order_by(*ordering)

        paginator = MarketplacePagination()
        page = paginator.paginate_queryset(rooms, request, view=self)
        return paginator.get_paginated_response(RoomSerializer(page, many=True).data)


class PublicRoomDetailView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(responses=RoomSerializer)
    def get(self, request, pk):
        return Response(RoomSerializer(get_public_room(pk)).data)


# --- Geocodificacion ---------------------------------------------------------


class GeocodingUnavailableError(APIException):
    """503 con un mensaje que no culpa al usuario ni delata al proveedor.

    El texto importa: quien lo lea tiene que entender que puede seguir
    trabajando. Ubicar el pin a mano no pasa por aqui, asi que un
    geocodificador caido no bloquea guardar una ubicacion.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = (
        "El buscador de direcciones no está disponible en este momento. "
        "Puedes ubicar el punto en el mapa manualmente y guardar igual."
    )


class GeocodingThrottle(UserRateThrottle):
    """Limite por usuario para no quemar la cuota del proveedor.

    ADVERTENCIA documentada a proposito: usa la cache por omision de Django,
    que es ``LocMemCache``, es decir memoria del proceso. Eso significa que
    **no es un limite global ni durable**: se reinicia en cada despliegue y se
    multiplicaria por la cantidad de workers si alguna vez se arranca gunicorn
    con mas de uno (hoy arranca con el valor por omision, que es uno). Para el
    piloto alcanza; si hace falta un limite real habra que respaldarlo con una
    cache compartida.

    La defensa que si es durable no depende de esta clase: ``limite`` tiene un
    tope por peticion en el serializer, y el cliente solo consulta cuando la
    persona pulsa un boton.
    """

    scope = "geocodificacion"


class _GeocodingView(APIView):
    """Base de los endpoints de geocodificacion.

    La clave del proveedor no sale del servidor, asi que estos endpoints son el
    unico camino del navegador hacia el geocodificador y conviene que esten tan
    cerrados como el panel que los usa: sesion valida, ``X-Tenant-ID``, acceso a
    esa empresa y permiso de gestion de productos. Buscar una direccion es parte
    de cargar un hospedaje, no una utilidad publica.
    """

    permission_classes = (IsAuthenticated,)
    throttle_classes = (GeocodingThrottle,)

    @staticmethod
    def _authorize(request) -> None:
        tenant_id = tenant_id_from_request(request, required=True)
        require_tenant_access(request.user, tenant_id)
        require_permission(request.user, "PRODUCTOS_GESTIONAR", tenant_id)


class GeocodingSearchView(_GeocodingView):
    @extend_schema(
        parameters=[GeocodingSearchQuerySerializer],
        responses=inline_serializer(
            name="GeocodingSearchResponse",
            fields={"resultados": GeocodingPlaceSerializer(many=True)},
        ),
    )
    def get(self, request):
        self._authorize(request)
        query = GeocodingSearchQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data

        try:
            places = search_places(
                text=data["texto"],
                limit=data["limite"],
                center=_city_center(data.get("ciudad_id")),
            )
        except GeocodingUnavailable as exc:
            raise GeocodingUnavailableError from exc
        return Response({"resultados": places})


class GeocodingReverseView(_GeocodingView):
    @extend_schema(
        parameters=[GeocodingReverseQuerySerializer],
        responses=inline_serializer(
            name="GeocodingReverseResponse",
            fields={"resultado": GeocodingPlaceSerializer(allow_null=True)},
        ),
    )
    def get(self, request):
        self._authorize(request)
        query = GeocodingReverseQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data

        try:
            place = reverse_geocode(latitude=data["latitud"], longitude=data["longitud"])
        except GeocodingUnavailable as exc:
            raise GeocodingUnavailableError from exc
        # 200 con null, no 404: "no hay calle registrada en ese punto" es una
        # respuesta valida, y en el altiplano es la respuesta habitual.
        return Response({"resultado": place})


def _city_center(city_id: int | None) -> tuple | None:
    """Centro de la ciudad para sesgar el ranking.

    El cliente manda ``ciudad_id`` y no un centro: asi no puede apuntar la
    busqueda a cualquier parte del mundo. Las coordenadas salen de ``ciudad``,
    que ya las trae sembradas desde ``0002_seed_bolivia_cities``.

    Una ciudad sin coordenadas no es un error: simplemente no hay sesgo y la
    busqueda sigue restringida al pais.
    """
    if city_id is None:
        return None
    center = City.objects.filter(id=city_id).values_list("latitude", "longitude").first()
    if center is None:
        raise ValidationError({"ciudad_id": "La ciudad no existe."})
    latitude, longitude = center
    if latitude is None or longitude is None:
        return None
    return latitude, longitude
