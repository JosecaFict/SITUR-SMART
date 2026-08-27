from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.rbac.models import UserRole
from apps.tenancy.models import UserTenant

from .models import User


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField(write_only=True, trim_whitespace=False)


class TenantContextSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    subdomain = serializers.CharField()


class UserContextSerializer(serializers.ModelSerializer):
    nombres = serializers.CharField(source="first_names")
    apellidos = serializers.CharField(source="last_names")
    roles = serializers.SerializerMethodField()
    permisos = serializers.SerializerMethodField()
    tenants = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "email", "nombres", "apellidos", "estado", "roles", "permisos", "tenants")

    estado = serializers.CharField(source="status")

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_roles(self, user):
        return list(
            UserRole.objects.filter(user=user)
            .order_by("role__code")
            .values_list("role__code", flat=True)
            .distinct()
        )

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_permisos(self, user):
        return list(
            UserRole.objects.filter(user=user)
            .order_by("role__role_permissions__permission__code")
            .values_list("role__role_permissions__permission__code", flat=True)
            .exclude(role__role_permissions__permission__code__isnull=True)
            .distinct()
        )

    @extend_schema_field(TenantContextSerializer(many=True))
    def get_tenants(self, user):
        memberships = UserTenant.objects.select_related("tenant").filter(
            user=user, status=UserTenant.Status.ACTIVE
        )
        return [
            {
                "id": membership.tenant_id,
                "name": membership.tenant.trade_name,
                "subdomain": membership.tenant.subdomain,
            }
            for membership in memberships
        ]


class AuthResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserContextSerializer()

class UserManagementSerializer(serializers.ModelSerializer):

    nombres = serializers.CharField(
        source="first_names"
    )

    apellidos = serializers.CharField(
        source="last_names"
    )

    telefono = serializers.CharField(
        source="phone",
        allow_blank=True,
        required=False,
    )

    estado = serializers.CharField(
        source="status"
    )


    class Meta:
        model = User

        fields = (
            "id",
            "email",
            "nombres",
            "apellidos",
            "telefono",
            "estado",
        )