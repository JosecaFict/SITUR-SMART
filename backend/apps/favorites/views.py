from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.serializers import ProductSerializer

from . import services


class FavoriteStateSerializer(serializers.Serializer):
    producto_id = serializers.IntegerField()
    favorito = serializers.BooleanField()


class FavoriteListView(APIView):
    """Favoritos del usuario con sesion, como tarjetas del Marketplace."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=ProductSerializer(many=True))
    def get(self, request):
        products = services.list_favorites(user=request.user)
        return Response(ProductSerializer(products, many=True).data)


class FavoriteDetailView(APIView):
    """PUT marca y DELETE desmarca. Las dos son idempotentes."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(request=None, responses={200: FavoriteStateSerializer, 201: FavoriteStateSerializer})
    def put(self, request, producto_id):
        created = services.add_favorite(user=request.user, product_id=producto_id)
        return Response(
            {"producto_id": producto_id, "favorito": True},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @extend_schema(responses={204: None})
    def delete(self, request, producto_id):
        services.remove_favorite(user=request.user, product_id=producto_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
