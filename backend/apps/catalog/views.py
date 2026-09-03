from datetime import date
from decimal import Decimal, InvalidOperation

from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.rbac.views import tenant_id_from_request

from .models import Currency, ProductType, TourismProduct
from .serializers import (
    CurrencySerializer,
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

    @extend_schema(responses=ProductSerializer(many=True))
    def get(self, request):
        products = TourismProduct.objects.select_related(
            "tenant", "product_type", "city__country", "currency"
        ).filter(status=TourismProduct.Status.PUBLISHED, tenant__status="ACTIVO")
        if value := request.query_params.get("pais"):
            products = products.filter(city__country_id=value)
        if value := request.query_params.get("ciudad"):
            products = products.filter(city_id=value)
        if value := request.query_params.get("localidad"):
            products = products.filter(locality__icontains=value)
        if value := request.query_params.get("tipo"):
            products = products.filter(product_type__code=value.upper())
        if value := request.query_params.get("buscar"):
            products = products.filter(
                Q(name__icontains=value) | Q(description__icontains=value) | Q(tenant__trade_name__icontains=value)
            )
        if value := request.query_params.get("fecha"):
            try:
                selected_date = date.fromisoformat(value)
            except ValueError as exc:
                raise ValidationError({"fecha": "Usa el formato AAAA-MM-DD."}) from exc
            products = products.filter(
                availabilities__start__date__lte=selected_date,
                availabilities__end__date__gte=selected_date,
                availabilities__closed=False,
                availabilities__total_capacity__gt=0,
            ).distinct()
        for parameter, lookup in (("precio_min", "base_price__gte"), ("precio_max", "base_price__lte")):
            if value := request.query_params.get(parameter):
                try:
                    parsed = Decimal(value)
                except InvalidOperation as exc:
                    raise ValidationError({parameter: "Debe ser un número válido."}) from exc
                if parsed < 0:
                    raise ValidationError({parameter: "No puede ser negativo."})
                products = products.filter(**{lookup: parsed})
        return Response(ProductSerializer(products, many=True).data)


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
