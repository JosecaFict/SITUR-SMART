from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.rbac.models import UserRole
from apps.tenancy.models import UserTenant

from .models import CustomerProfile, User


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
    telefono = serializers.CharField(source="phone", allow_null=True, required=False)
    roles = serializers.SerializerMethodField()
    permisos = serializers.SerializerMethodField()
    tenants = serializers.SerializerMethodField()
    perfil = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "nombres",
            "apellidos",
            "telefono",
            "estado",
            "roles",
            "permisos",
            "tenants",
            "perfil",
        )

    estado = serializers.CharField(source="status")

    @extend_schema_field(serializers.DictField())
    def get_perfil(self, user):
        profile = getattr(user, "customer_profile", None)
        if profile is None:
            try:
                profile = CustomerProfile.objects.filter(user=user).first()
            except Exception:
                profile = None
        if profile is None:
            return None
        return {
            "tipo_documento": profile.document_type,
            "numero_documento": profile.document_number,
            "fecha_nacimiento": profile.birth_date.isoformat() if profile.birth_date else None,
        }


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


class UserSummarySerializer(serializers.ModelSerializer):
    nombres = serializers.CharField(source="first_names")
    apellidos = serializers.CharField(source="last_names")
    telefono = serializers.CharField(source="phone", allow_null=True, required=False)
    estado = serializers.CharField(source="status")
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "email", "nombres", "apellidos", "telefono", "estado", "roles")

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_roles(self, user):
        tenant_id = self.context.get("tenant_id")
        queryset = UserRole.objects.filter(user=user)
        if tenant_id is not None:
            queryset = queryset.filter(tenant_id=tenant_id)
        return list(
            queryset.order_by("role__code").values_list("role__code", flat=True).distinct()
        )


class UserCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    first_names = serializers.CharField(max_length=120)
    last_names = serializers.CharField(max_length=120)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True, allow_null=True)
    password = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False, write_only=True
    )
    role_code = serializers.RegexField(r"^[A-Za-z][A-Za-z0-9_]{2,59}$")


class UserUpdateSerializer(serializers.Serializer):
    first_names = serializers.CharField(max_length=120, required=False)
    last_names = serializers.CharField(max_length=120, required=False)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True, allow_null=True)
    role_code = serializers.RegexField(r"^[A-Za-z][A-Za-z0-9_]{2,59}$", required=False)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.RegexField(
        r"^\d{6}$",
        error_messages={"invalid": "El código debe contener exactamente 6 dígitos numéricos."},
    )


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.RegexField(
        r"^\d{6}$",
        error_messages={"invalid": "El código debe contener exactamente 6 dígitos numéricos."},
    )
    new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
    )
    new_password_confirm = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
    )

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "Las contraseñas no coinciden."}
            )
        return attrs


class CustomerRegisterSerializer(serializers.Serializer):
    nombres = serializers.CharField(max_length=120)
    apellidos = serializers.CharField(max_length=120)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)
    telefono = serializers.CharField(max_length=30, required=False, allow_blank=True, allow_null=True)


class CustomerProfileUpdateSerializer(serializers.Serializer):
    nombres = serializers.CharField(max_length=120, required=False)
    apellidos = serializers.CharField(max_length=120, required=False)
    telefono = serializers.CharField(max_length=30, required=False, allow_blank=True, allow_null=True)
    tipo_documento = serializers.CharField(max_length=30, required=False, allow_blank=True, allow_null=True)
    numero_documento = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    fecha_nacimiento = serializers.DateField(required=False, allow_null=True)


