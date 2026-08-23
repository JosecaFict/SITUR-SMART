from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    AuthResponseSerializer,
    LoginSerializer,
    RefreshSerializer,
    UserContextSerializer,
)
from .services import login_user, revoke_refresh_token, rotate_refresh_token


class LoginView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(request=LoginSerializer, responses=AuthResponseSerializer)
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, tokens = login_user(request=request, **serializer.validated_data)
        return Response({**tokens, "user": UserContextSerializer(user).data})


class RefreshView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(request=RefreshSerializer, responses=AuthResponseSerializer)
    def post(self, request):
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, tokens = rotate_refresh_token(
            raw_refresh=serializer.validated_data["refresh"], request=request
        )
        return Response({**tokens, "user": UserContextSerializer(user).data})


class LogoutView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(request=RefreshSerializer, responses={204: None})
    def post(self, request):
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        revoke_refresh_token(serializer.validated_data["refresh"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=UserContextSerializer)
    def get(self, request):
        return Response(UserContextSerializer(request.user).data)
