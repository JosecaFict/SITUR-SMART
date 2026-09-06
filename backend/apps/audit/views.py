from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.rbac.services import is_superadmin, require_permission, require_tenant_access
from apps.rbac.views import tenant_id_from_request

from .models import AuditLog
from .serializers import AuditLogSerializer

MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 50


class AuditLogListView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter("entidad", str, description="Filtra por tipo de entidad (ej. usuario, rol, empresa, producto_turistico)."),
            OpenApiParameter("accion", str, description="Filtra por accion (CREAR, ACTUALIZAR, ELIMINAR, DESACTIVAR, VINCULAR)."),
            OpenApiParameter("usuario", str, description="Filtra por nombre o correo del usuario responsable."),
            OpenApiParameter("desde", str, description="Fecha minima (AAAA-MM-DD)."),
            OpenApiParameter("hasta", str, description="Fecha maxima (AAAA-MM-DD)."),
            OpenApiParameter("limit", int, description="Cantidad de resultados (maximo 200, por defecto 50)."),
            OpenApiParameter("offset", int, description="Desde que posicion empezar."),
        ],
        responses=AuditLogSerializer(many=True),
    )
    def get(self, request):
        tenant_id = tenant_id_from_request(request)
        queryset = AuditLog.objects.select_related("tenant", "user")

        if tenant_id is not None:
            require_tenant_access(request.user, tenant_id)
            require_permission(request.user, "BITACORA_LEER", tenant_id)
            queryset = queryset.filter(tenant_id=tenant_id)
        elif not is_superadmin(request.user):
            raise PermissionDenied("Se requiere un contexto de tenant.")

        if value := request.query_params.get("entidad"):
            queryset = queryset.filter(entity=value)
        if value := request.query_params.get("accion"):
            queryset = queryset.filter(action=value)
        if value := request.query_params.get("usuario"):
            queryset = queryset.filter(
                Q(user__email__icontains=value)
                | Q(user__first_names__icontains=value)
                | Q(user__last_names__icontains=value)
            )
        if value := request.query_params.get("desde"):
            queryset = queryset.filter(created_at__date__gte=value)
        if value := request.query_params.get("hasta"):
            queryset = queryset.filter(created_at__date__lte=value)

        total = queryset.count()
        try:
            limit = min(int(request.query_params.get("limit", DEFAULT_PAGE_SIZE)), MAX_PAGE_SIZE)
            offset = max(int(request.query_params.get("offset", 0)), 0)
        except ValueError:
            limit, offset = DEFAULT_PAGE_SIZE, 0

        page = queryset[offset : offset + limit]
        return Response(
            {
                "total": total,
                "limit": limit,
                "offset": offset,
                "resultados": AuditLogSerializer(page, many=True).data,
            }
        )
