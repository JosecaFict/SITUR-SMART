from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Notification, PushDevice


class NotificationSerializer(serializers.ModelSerializer):
    tipo = serializers.CharField(source="kind")
    titulo = serializers.CharField(source="title")
    mensaje = serializers.CharField(source="message")
    datos = serializers.JSONField(source="data")
    leida = serializers.SerializerMethodField()
    creado_en = serializers.DateTimeField(source="created_at")

    class Meta:
        model = Notification
        fields = ("id", "tipo", "titulo", "mensaje", "datos", "leida", "creado_en")

    def get_leida(self, notification) -> bool:
        return notification.read_at is not None


class UnreadSerializer(serializers.Serializer):
    no_leidas = serializers.IntegerField()


class NotificationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50


class NotificationListView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=NotificationSerializer(many=True))
    def get(self, request):
        paginator = NotificationPagination()
        page = paginator.paginate_queryset(services.user_notifications(user=request.user), request, view=self)
        return paginator.get_paginated_response(NotificationSerializer(page, many=True).data)


class UnreadCountView(APIView):
    """Lo que consulta la campana. Barato a proposito: se llama seguido."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=UnreadSerializer)
    def get(self, request):
        return Response({"no_leidas": services.unread_count(user=request.user)})


class MarkReadView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(request=None, responses=NotificationSerializer)
    def post(self, request, pk):
        notification = services.mark_read(user=request.user, notification_id=pk)
        return Response(NotificationSerializer(notification).data)


class DeviceSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=512, trim_whitespace=True)
    plataforma = serializers.ChoiceField(choices=PushDevice.Platform.choices, default=PushDevice.Platform.ANDROID)


class DeviceTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=512, trim_whitespace=True)


class DeviceView(APIView):
    """La app registra aqui su token de Firebase al iniciar sesion y cuando Firebase lo rota."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(request=DeviceSerializer, responses={204: None})
    def post(self, request):
        serializer = DeviceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.register_device(
            user=request.user,
            token=serializer.validated_data["token"],
            platform=serializer.validated_data["plataforma"],
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class DeviceRemoveView(APIView):
    """Al cerrar sesion: ese celular deja de recibir los avisos de la cuenta."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(request=DeviceTokenSerializer, responses={204: None})
    def post(self, request):
        serializer = DeviceTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.unregister_device(user=request.user, token=serializer.validated_data["token"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class MarkAllReadView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        services.mark_all_read(user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
