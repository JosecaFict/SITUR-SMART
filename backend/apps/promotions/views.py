from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.serializers import ProductSerializer
from apps.catalog.services import with_lodging_from_price
from apps.rbac.views import tenant_id_from_request

from . import services
from .serializers import (
    ComponentWriteSerializer,
    EligibleQuerySerializer,
    EvaluationSerializer,
    PromotionPageSerializer,
    PromotionReadSerializer,
    PromotionWriteSerializer,
    PublicQuerySerializer,
)


class PromotionPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50


def _validated(serializer_class, data, *, partial=False):
    serializer = serializer_class(data=data, partial=partial)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def _result(promotion):
    return services.promotion_data(services.queryset().get(id=promotion.id))


@extend_schema(
    tags=["Promociones"],
    parameters=[
        OpenApiParameter(
            "X-Tenant-ID",
            int,
            OpenApiParameter.HEADER,
            required=True,
            description="Empresa activa del usuario. Requiere PRODUCTOS_LEER o PRODUCTOS_GESTIONAR según la operación.",
        )
    ],
)
class CompanyView(APIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = PromotionReadSerializer

    def scope(self, request):
        return request.user, tenant_id_from_request(request, required=True)


class PromotionListView(CompanyView):
    @extend_schema(operation_id="promotions_list", responses=PromotionPageSerializer)
    def get(self, request):
        pagination = PromotionPagination()
        page = pagination.paginate_queryset(
            services.company_promotions(*self.scope(request)), request
        )
        return pagination.get_paginated_response(
            [services.promotion_data(promotion) for promotion in page]
        )

    @extend_schema(
        request=PromotionWriteSerializer, responses={201: PromotionReadSerializer}
    )
    def post(self, request):
        values = _validated(PromotionWriteSerializer, request.data)
        promotion = services.create(*self.scope(request), values, request=request)
        return Response(_result(promotion), status=201)


class PromotionDetailView(CompanyView):
    def get(self, request, pk):
        return Response(_result(services.owned(*self.scope(request), pk)))

    @extend_schema(request=PromotionWriteSerializer)
    def patch(self, request, pk):
        values = _validated(PromotionWriteSerializer, request.data, partial=True)
        promotion = services.update(*self.scope(request), pk, values, request=request)
        return Response(_result(promotion))


class PromotionPublishView(CompanyView):
    enabled = True

    @extend_schema(request=None)
    def post(self, request, pk):
        return Response(
            _result(
                services.set_enabled(
                    *self.scope(request), pk, self.enabled, request=request
                )
            )
        )


class PromotionDisableView(PromotionPublishView):
    enabled = False


class EligibleProductsView(CompanyView):
    @extend_schema(
        parameters=[EligibleQuerySerializer],
        responses=inline_serializer(
            name="PromotionEligiblePage",
            fields={
                "count": serializers.IntegerField(),
                "next": serializers.URLField(allow_null=True),
                "previous": serializers.URLField(allow_null=True),
                "results": ProductSerializer(many=True),
            },
        ),
    )
    def get(self, request):
        query = _validated(EligibleQuerySerializer, request.query_params)
        products = with_lodging_from_price(
            services.eligible_products(*self.scope(request), query["modalidad"])
        )
        pagination = PromotionPagination()
        page = pagination.paginate_queryset(products, request)
        return pagination.get_paginated_response(
            ProductSerializer(page, many=True).data
        )


class PreviewView(CompanyView):
    @extend_schema(request=PromotionWriteSerializer, responses=EvaluationSerializer)
    def post(self, request):
        return Response(
            services.preview(
                *self.scope(request), _validated(PromotionWriteSerializer, request.data)
            )
        )


class RecalculateView(CompanyView):
    def get(self, request, pk):
        return Response(_result(services.owned(*self.scope(request), pk)))


class ComponentListView(CompanyView):
    @extend_schema(
        responses={
            200: {
                "type": "array",
                "items": {"type": "object", "additionalProperties": True},
            }
        }
    )
    def get(self, request, pk):
        return Response(
            _result(services.owned(*self.scope(request), pk))["componentes"]
        )

    @extend_schema(
        request=ComponentWriteSerializer, responses={201: PromotionReadSerializer}
    )
    def post(self, request, pk):
        values = _validated(ComponentWriteSerializer, request.data)
        promotion = services.change_component(
            *self.scope(request), pk, values, request=request
        )
        return Response(_result(promotion), status=201)


class ComponentDetailView(CompanyView):
    @extend_schema(request=ComponentWriteSerializer)
    def patch(self, request, pk, component_id):
        values = _validated(ComponentWriteSerializer, request.data, partial=True)
        promotion = services.change_component(
            *self.scope(request), pk, values, component_id, request=request
        )
        return Response(_result(promotion))

    @extend_schema(responses={200: PromotionReadSerializer})
    def delete(self, request, pk, component_id):
        promotion = services.change_component(
            *self.scope(request),
            pk,
            component_id=component_id,
            delete=True,
            request=request,
        )
        return Response(_result(promotion))


class PublicPromotionListView(APIView):
    permission_classes = (AllowAny,)
    serializer_class = PromotionPageSerializer

    @extend_schema(
        operation_id="public_promotions_list",
        tags=["Promociones"],
        parameters=[PublicQuerySerializer],
    )
    def get(self, request):
        query = _validated(PublicQuerySerializer, request.query_params)
        # Las condiciones de los componentes pueden cambiar sin editar la oferta.
        # Nunca se publica un total parcial ni disponibilidad de servicios retirados.
        results = [
            services.promotion_data(
                promotion, start=query.get("fecha"), quantity=query["cantidad"]
            )
            for promotion in services.public_promotions()
        ]
        results = [data for data in results if data["valida"]]
        pagination = PromotionPagination()
        return pagination.get_paginated_response(
            pagination.paginate_queryset(results, request)
        )


class PublicPromotionDetailView(APIView):
    permission_classes = (AllowAny,)
    serializer_class = PromotionReadSerializer

    @extend_schema(tags=["Promociones"], parameters=[PublicQuerySerializer])
    def get(self, request, pk):
        query = _validated(PublicQuerySerializer, request.query_params)
        promotion = services.public_promotions().filter(id=pk).first()
        if promotion is None:
            raise NotFound("Promoción no disponible.")
        data = services.promotion_data(
            promotion, start=query.get("fecha"), quantity=query["cantidad"]
        )
        if not data["valida"]:
            raise NotFound(
                "La promoción dejó de cumplir las condiciones de sus productos."
            )
        return Response(data)
