from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.rbac.views import tenant_id_from_request

from .models import Currency, ProductType, TourismProduct
from .serializers import (
    CurrencySerializer,
    MarketplaceQuerySerializer,
    ProductSerializer,
    ProductTypeSerializer,
    ProductWriteSerializer,
)
from .services import (
    create_product,
    deactivate_product,
    get_company_product,
    list_company_products,
    update_product,
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

        products = TourismProduct.objects.select_related(
            "tenant", "product_type", "city__country", "currency"
        ).filter(status=TourismProduct.Status.PUBLISHED, tenant__status="ACTIVO")
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
        product = TourismProduct.objects.select_related(
            "tenant", "product_type", "city__country", "currency"
        ).filter(id=pk, status=TourismProduct.Status.PUBLISHED, tenant__status="ACTIVO").first()
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
