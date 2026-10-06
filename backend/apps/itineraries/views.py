from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .serializers import (
    ActivityInputSerializer,
    ActivitySerializer,
    ActivityUpdateSerializer,
    ItineraryDetailSerializer,
    ItineraryInputSerializer,
    ItinerarySummarySerializer,
)


def _detail(itinerary) -> dict:
    return ItineraryDetailSerializer(itinerary, context={"days": services.build_days(itinerary)}).data


class ItineraryListView(APIView):
    """Itinerarios del turista, del viaje mas reciente al mas viejo."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=ItinerarySummarySerializer(many=True))
    def get(self, request):
        itineraries = services.list_itineraries(user=request.user)
        return Response(ItinerarySummarySerializer(itineraries, many=True).data)

    @extend_schema(request=ItineraryInputSerializer, responses={201: ItineraryDetailSerializer})
    def post(self, request):
        serializer = ItineraryInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        itinerary = services.create_itinerary(user=request.user, **serializer.as_kwargs())
        return Response(_detail(itinerary), status=status.HTTP_201_CREATED)


class ItineraryDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=ItineraryDetailSerializer)
    def get(self, request, pk):
        return Response(_detail(services.get_itinerary(user=request.user, itinerary_id=pk)))

    @extend_schema(request=ItineraryInputSerializer, responses=ItineraryDetailSerializer)
    def patch(self, request, pk):
        serializer = ItineraryInputSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        itinerary = services.update_itinerary(
            user=request.user, itinerary_id=pk, changes=serializer.as_kwargs()
        )
        return Response(_detail(itinerary))

    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        services.delete_itinerary(user=request.user, itinerary_id=pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ActivityListView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(request=ActivityInputSerializer, responses={201: ActivitySerializer})
    def post(self, request, pk):
        serializer = ActivityInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        activity = services.add_activity(user=request.user, itinerary_id=pk, **serializer.as_kwargs())
        return Response(ActivitySerializer(activity).data, status=status.HTTP_201_CREATED)


class ActivityDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(request=ActivityUpdateSerializer, responses=ActivitySerializer)
    def patch(self, request, pk, activity_id):
        serializer = ActivityUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        activity = services.update_activity(
            user=request.user, itinerary_id=pk, activity_id=activity_id, changes=serializer.as_kwargs()
        )
        return Response(ActivitySerializer(activity).data)

    @extend_schema(responses={204: None})
    def delete(self, request, pk, activity_id):
        services.delete_activity(user=request.user, itinerary_id=pk, activity_id=activity_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
