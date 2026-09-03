from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.rbac.views import tenant_id_from_request

from .serializers import (
    AuthResponseSerializer,
    LoginSerializer,
    RefreshSerializer,
    UserContextSerializer,
    UserCreateSerializer,
    UserSummarySerializer,
    UserUpdateSerializer,
)
from .services import (
    create_or_link_tenant_user,
    list_tenant_users,
    login_user,
    remove_tenant_user,
    revoke_refresh_token,
    rotate_refresh_token,
    update_tenant_user,
)


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


class UserListCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=UserSummarySerializer(many=True))
    def get(self, request):
        tenant_id = tenant_id_from_request(request, required=True)
        users = list_tenant_users(actor=request.user, tenant_id=tenant_id)
        return Response(
            UserSummarySerializer(users, many=True, context={"tenant_id": tenant_id}).data
        )

    @extend_schema(request=UserCreateSerializer, responses={201: UserSummarySerializer})
    def post(self, request):
        tenant_id = tenant_id_from_request(request, required=True)
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = create_or_link_tenant_user(
            actor=request.user, tenant_id=tenant_id, request=request, **serializer.validated_data
        )
        return Response(
            UserSummarySerializer(user, context={"tenant_id": tenant_id}).data,
            status=status.HTTP_201_CREATED,
        )


class UserDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=UserSummarySerializer)
    def get(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        user = list_tenant_users(actor=request.user, tenant_id=tenant_id).filter(pk=pk).first()
        if user is None:
            raise NotFound("Usuario no encontrado en esta empresa.")
        return Response(UserSummarySerializer(user, context={"tenant_id": tenant_id}).data)

    @extend_schema(request=UserUpdateSerializer, responses=UserSummarySerializer)
    def patch(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        serializer = UserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = update_tenant_user(
            actor=request.user,
            tenant_id=tenant_id,
            user_id=pk,
            request=request,
            **serializer.validated_data,
        )
        return Response(UserSummarySerializer(user, context={"tenant_id": tenant_id}).data)

    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        remove_tenant_user(actor=request.user, tenant_id=tenant_id, user_id=pk, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)
