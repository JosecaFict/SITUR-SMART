from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Permission, Role


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ("id", "code", "module", "name")


class RoleSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ("id", "tenant_id", "code", "name", "scope", "is_system", "permissions")

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_permissions(self, role):
        return list(
            role.role_permissions.order_by("permission__code").values_list("permission__code", flat=True)
        )


class RoleCreateSerializer(serializers.Serializer):
    code = serializers.RegexField(r"^[A-Za-z][A-Za-z0-9_]{2,59}$")
    name = serializers.CharField(max_length=120)
    permissions = serializers.ListField(
        child=serializers.CharField(max_length=100), allow_empty=True, default=list
    )
