from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.rbac.services import require_permission

from .models import Tenant
from .serializers import TenantSerializer


class TenantListCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=TenantSerializer(many=True))
    def get(self, request):
        tenants = Tenant.objects.all().order_by("trade_name")

        return Response(
            TenantSerializer(tenants, many=True).data
        )

    @extend_schema(
        request=TenantSerializer,
        responses={201: TenantSerializer},
    )
    def post(self, request):
        require_permission(
            request.user,
            "TENANTS_GESTIONAR"
        )

        serializer = TenantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tenant = serializer.save()

        return Response(
            TenantSerializer(tenant).data,
            status=status.HTTP_201_CREATED
        )


class TenantDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    def get_object(self, pk):
        try:
            return Tenant.objects.get(pk=pk)
        except Tenant.DoesNotExist:
            raise NotFound("La empresa no existe.")

    @extend_schema(responses=TenantSerializer)
    def get(self, request, pk):
        tenant = self.get_object(pk)

        return Response(
            TenantSerializer(tenant).data
        )