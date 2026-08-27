from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from apps.rbac.models import Role, UserRole
from apps.tenancy.models import Tenant

from .models import User
from .serializers import UserManagementSerializer

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

class UserListCreateView(ListCreateAPIView):

    permission_classes = (IsAuthenticated,)

    queryset = User.objects.all()

    serializer_class = UserManagementSerializer

    def perform_create(self, serializer):

        data = serializer.validated_data

        user = User.objects.create_user(
            email=data["email"],
            password=self.request.data.get("password"),
            first_names=data["first_names"],
            last_names=data["last_names"],
            phone=data.get("phone"),
            status=data.get(
                "status",
                User.Status.ACTIVE,
            ),
        )


        role_id = self.request.data.get("role_id")

        tenant_id = self.request.data.get("tenant_id")


        if role_id:

            role = Role.objects.get(
                id=role_id
            )


            tenant = None

            if tenant_id:

                tenant = Tenant.objects.get(
                    id=tenant_id
                )


            UserRole.objects.create(
                user=user,
                role=role,
                tenant=tenant,
            )



class UserDetailView(RetrieveUpdateDestroyAPIView):

    permission_classes = (IsAuthenticated,)

    queryset = User.objects.all()

    serializer_class = UserManagementSerializer