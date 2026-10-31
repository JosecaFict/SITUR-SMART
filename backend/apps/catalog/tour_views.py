"""API de tours, salidas y guias (CU20).

Las vistas de empresa exigen sesion y X-Tenant-ID; permisos, aislamiento entre
empresas y reglas viven en los servicios, igual que en el resto del catalogo.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.rbac.views import tenant_id_from_request

from . import departures, guides, tours
from .tour_serializers import (
    DepartureRangeQuerySerializer,
    DepartureSerializer,
    DepartureWriteSerializer,
    GuideSerializer,
    GuideWriteSerializer,
    PublicDepartureSerializer,
    RecurringDepartureSerializer,
    RecurringResultSerializer,
    TourSerializer,
    TourStopSerializer,
    TourStopsWriteSerializer,
    TourWriteSerializer,
)

# --- Tours ---------------------------------------------------------------------


class CompanyTourListCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=TourSerializer(many=True))
    def get(self, request):
        tenant_id = tenant_id_from_request(request, required=True)
        return Response(TourSerializer(tours.list_company_tours(actor=request.user, tenant_id=tenant_id), many=True).data)

    @extend_schema(request=TourWriteSerializer, responses={201: TourSerializer})
    def post(self, request):
        tenant_id = tenant_id_from_request(request, required=True)
        serializer = TourWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tour = tours.create_tour(actor=request.user, tenant_id=tenant_id, request=request, **serializer.validated_data)
        return Response(TourSerializer(tour).data, status=status.HTTP_201_CREATED)


class CompanyTourDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=TourSerializer)
    def get(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        return Response(TourSerializer(tours.get_company_tour(actor=request.user, tenant_id=tenant_id, tour_id=pk)).data)

    @extend_schema(request=TourWriteSerializer, responses=TourSerializer)
    def patch(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        serializer = TourWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        tour = tours.update_tour(
            actor=request.user, tenant_id=tenant_id, tour_id=pk, request=request, **serializer.validated_data
        )
        return Response(TourSerializer(tour).data)

    @extend_schema(responses=TourSerializer)
    def delete(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        tour = tours.deactivate_tour(actor=request.user, tenant_id=tenant_id, tour_id=pk, request=request)
        return Response(TourSerializer(tour).data)


class TourStopsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=TourStopSerializer(many=True))
    def get(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        tour = tours.get_company_tour(actor=request.user, tenant_id=tenant_id, tour_id=pk)
        return Response(TourStopSerializer(tour.stops.all(), many=True).data)

    @extend_schema(request=TourStopsWriteSerializer, responses=TourStopSerializer(many=True))
    def put(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        serializer = TourStopsWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        stops = tours.set_stops(
            actor=request.user, tenant_id=tenant_id, tour_id=pk,
            stops=serializer.validated_data["paradas"], request=request,
        )
        return Response(TourStopSerializer(stops, many=True).data)


class PublicTourDetailView(APIView):
    """Ficha publica del tour: datos, recorrido y resumen de salidas."""

    permission_classes = (AllowAny,)

    @extend_schema(responses=TourSerializer)
    def get(self, request, pk):
        return Response(TourSerializer(tours.get_public_tour(pk)).data)


# --- Salidas -------------------------------------------------------------------


class TourDepartureListCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(parameters=[DepartureRangeQuerySerializer], responses=DepartureSerializer(many=True))
    def get(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        query = DepartureRangeQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        result = departures.list_departures(
            actor=request.user, tenant_id=tenant_id, tour_id=pk,
            date_from=query.validated_data.get("desde"), date_to=query.validated_data.get("hasta"),
        )
        return Response(DepartureSerializer(result, many=True).data)

    @extend_schema(
        request=DepartureWriteSerializer,
        responses={201: DepartureSerializer},
        description=(
            "Crea una salida (inicio, fin, cupo, guia_id) o varias repetidas "
            "(dias_semana, hora_inicio, hora_fin, desde, hasta, cupo, guia_id)."
        ),
    )
    def post(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        if "dias_semana" in request.data:
            serializer = RecurringDepartureSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            result = departures.create_recurring(
                actor=request.user, tenant_id=tenant_id, tour_id=pk, request=request,
                weekdays=data["dias_semana"], start_time=data["hora_inicio"], end_time=data.get("hora_fin"),
                date_from=data["desde"], date_to=data["hasta"], capacity=data.get("cupo"),
                guide_id=data.get("guia_id"),
            )
            body = RecurringResultSerializer({"creadas": result["created"], "omitidas": result["skipped"]}).data
            return Response(body, status=status.HTTP_201_CREATED)

        serializer = DepartureWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        departure = departures.create_departure(
            actor=request.user, tenant_id=tenant_id, tour_id=pk, request=request,
            start=data["inicio"], end=data.get("fin"), capacity=data.get("cupo"), guide_id=data.get("guia_id"),
        )
        return Response(DepartureSerializer(departure).data, status=status.HTTP_201_CREATED)


class DepartureDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(request=DepartureWriteSerializer, responses=DepartureSerializer)
    def patch(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        serializer = DepartureWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        departure = departures.update_departure(
            actor=request.user, tenant_id=tenant_id, departure_id=pk, request=request, **serializer.validated_data
        )
        return Response(DepartureSerializer(departure).data)

    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        departures.delete_departure(actor=request.user, tenant_id=tenant_id, departure_id=pk, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DepartureCloseView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(request=None, responses=DepartureSerializer)
    def post(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        departure = departures.close_departure(actor=request.user, tenant_id=tenant_id, departure_id=pk, request=request)
        return Response(DepartureSerializer(departure).data)


class PublicTourDeparturesView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(responses=PublicDepartureSerializer(many=True))
    def get(self, request, pk):
        return Response(PublicDepartureSerializer(departures.list_public_departures(pk), many=True).data)


# --- Guias ---------------------------------------------------------------------


class GuideListCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=GuideSerializer(many=True))
    def get(self, request):
        tenant_id = tenant_id_from_request(request, required=True)
        return Response(GuideSerializer(guides.list_guides(actor=request.user, tenant_id=tenant_id), many=True).data)

    @extend_schema(request=GuideWriteSerializer, responses={201: GuideSerializer})
    def post(self, request):
        tenant_id = tenant_id_from_request(request, required=True)
        serializer = GuideWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        guide = guides.create_guide(actor=request.user, tenant_id=tenant_id, request=request, **serializer.validated_data)
        return Response(GuideSerializer(guide).data, status=status.HTTP_201_CREATED)


class GuideDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(request=GuideWriteSerializer, responses=GuideSerializer)
    def patch(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        serializer = GuideWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        guide = guides.update_guide(
            actor=request.user, tenant_id=tenant_id, guide_id=pk, request=request, **serializer.validated_data
        )
        return Response(GuideSerializer(guide).data)

    @extend_schema(responses=GuideSerializer)
    def delete(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        guide = guides.deactivate_guide(actor=request.user, tenant_id=tenant_id, guide_id=pk, request=request)
        return Response(GuideSerializer(guide).data)
