from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.rbac.views import tenant_id_from_request

from .serializers import (
    AuthResponseSerializer,
    CustomerProfileUpdateSerializer,
    CustomerRegisterSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PasswordResetVerifySerializer,
    RefreshSerializer,
    UserContextSerializer,
    UserCreateSerializer,
    UserSummarySerializer,
    UserUpdateSerializer,
)
from .services import (
    confirm_password_reset,
    create_or_link_tenant_user,
    list_tenant_users,
    login_user,
    register_customer,
    remove_tenant_user,
    request_password_reset_otp,
    revoke_refresh_token,
    rotate_refresh_token,
    update_customer_profile,
    update_tenant_user,
    verify_password_reset_otp,
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


class CustomerRegisterView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        request=CustomerRegisterSerializer,
        responses={201: AuthResponseSerializer},
        description="Auto-registro público de cliente/turista.",
    )
    def post(self, request):
        serializer = CustomerRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, tokens = register_customer(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
            first_names=serializer.validated_data["nombres"],
            last_names=serializer.validated_data["apellidos"],
            phone=serializer.validated_data.get("telefono"),
            request=request,
        )
        return Response(
            {**tokens, "user": UserContextSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


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

    @extend_schema(request=CustomerProfileUpdateSerializer, responses=UserContextSerializer)
    def patch(self, request):
        serializer = CustomerProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated_user = update_customer_profile(
            user=request.user, data=serializer.validated_data, request=request
        )
        return Response(UserContextSerializer(updated_user).data)



class PasswordResetRequestView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        request=PasswordResetRequestSerializer,
        responses={200: dict},
        description="Solicita el envío de un código OTP de 6 dígitos al correo electrónico para recuperación de contraseña.",
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = request_password_reset_otp(
            email=serializer.validated_data["email"], request=request
        )
        return Response(result, status=status.HTTP_200_OK)


class PasswordResetVerifyView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        request=PasswordResetVerifySerializer,
        responses={200: dict},
        description="Verifica si el código OTP de 6 dígitos ingresado es válido y no ha expirado.",
    )
    def post(self, request):
        serializer = PasswordResetVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        verify_password_reset_otp(
            email=serializer.validated_data["email"],
            code=serializer.validated_data["code"],
        )
        return Response(
            {"valid": True, "detail": "Código verificado correctamente."},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        request=PasswordResetConfirmSerializer,
        responses={200: dict},
        description="Establece la nueva contraseña utilizando el código OTP verificado.",
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        confirm_password_reset(
            email=serializer.validated_data["email"],
            code=serializer.validated_data["code"],
            new_password=serializer.validated_data["new_password"],
            request=request,
        )
        return Response(
            {
                "detail": "Tu contraseña ha sido restablecida exitosamente. Ya puedes iniciar sesión con tu nueva clave."
            },
            status=status.HTTP_200_OK,
        )


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
