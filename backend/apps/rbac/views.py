from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Permission, Role
from .serializers import (
    PermissionSerializer,
    RoleCreateSerializer,
    RoleSerializer,
    RoleUpdateSerializer,
)
from .services import (
    create_tenant_role,
    delete_tenant_role,
    get_tenant_role,
    is_superadmin,
    require_permission,
    require_tenant_access,
    update_tenant_role,
)


def tenant_id_from_request(request, required: bool = False) -> int | None:
    raw = request.headers.get("X-Tenant-ID")
    if not raw:
        if required:
            raise ValidationError({"tenant": "Debe enviar X-Tenant-ID."})
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ValidationError({"tenant": "X-Tenant-ID debe ser numérico."}) from exc


class PermissionListView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=PermissionSerializer(many=True))
    def get(self, request):
        tenant_id = tenant_id_from_request(request)
        if tenant_id is not None:
            require_tenant_access(request.user, tenant_id)
            require_permission(request.user, "ROLES_GESTIONAR", tenant_id)
        elif not is_superadmin(request.user):
            raise PermissionDenied("Se requiere un contexto de tenant.")
        return Response(PermissionSerializer(Permission.objects.all(), many=True).data)


class RoleListCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=RoleSerializer(many=True))
    def get(self, request):
        tenant_id = tenant_id_from_request(request)
        if tenant_id is None:
            if not is_superadmin(request.user):
                raise PermissionDenied("Se requiere un contexto de tenant.")
            queryset = Role.objects.filter(
                Q(scope=Role.Scope.GLOBAL)
                | Q(scope=Role.Scope.TENANT, tenant__isnull=True)
            ).order_by("scope", "code")
        else:
            require_tenant_access(request.user, tenant_id)
            require_permission(request.user, "ROLES_GESTIONAR", tenant_id)
            queryset = Role.objects.filter(scope=Role.Scope.TENANT).filter(
                Q(tenant_id=tenant_id) | Q(tenant__isnull=True)
            )
        return Response(RoleSerializer(queryset, many=True).data)

    @extend_schema(request=RoleCreateSerializer, responses={201: RoleSerializer})
    def post(self, request):
        tenant_id = tenant_id_from_request(request, required=True)
        serializer = RoleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = create_tenant_role(
            actor=request.user,
            tenant_id=tenant_id,
            code=serializer.validated_data["code"],
            name=serializer.validated_data["name"],
            permission_codes=serializer.validated_data["permissions"],
            request=request,
        )
        return Response(RoleSerializer(role).data, status=status.HTTP_201_CREATED)


class RoleDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=RoleSerializer)
    def get(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        role = get_tenant_role(actor=request.user, tenant_id=tenant_id, role_id=pk)
        return Response(RoleSerializer(role).data)

    @extend_schema(request=RoleUpdateSerializer, responses=RoleSerializer)
    def patch(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        serializer = RoleUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        role = update_tenant_role(
            actor=request.user,
            tenant_id=tenant_id,
            role_id=pk,
            name=serializer.validated_data.get("name"),
            permission_codes=serializer.validated_data.get("permissions"),
            request=request,
        )
        return Response(RoleSerializer(role).data)

    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        delete_tenant_role(actor=request.user, tenant_id=tenant_id, role_id=pk, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)
