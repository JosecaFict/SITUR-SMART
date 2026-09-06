from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import User
from apps.rbac.models import UserRole

from .models import City, Country, Plan, Subscription, Tenant


class CountrySerializer(serializers.ModelSerializer):
    codigo = serializers.CharField(source="iso_code")
    nombre = serializers.CharField(source="name")

    class Meta:
        model = Country
        fields = ("id", "codigo", "nombre")


class CitySerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(source="name")
    pais_id = serializers.IntegerField(source="country_id")
    pais = serializers.CharField(source="country.name", read_only=True)

    class Meta:
        model = City
        fields = ("id", "nombre", "pais_id", "pais")


class OwnerInputSerializer(serializers.Serializer):
    email = serializers.EmailField()
    nombres = serializers.CharField(max_length=120)
    apellidos = serializers.CharField(max_length=120)
    telefono = serializers.CharField(max_length=30, required=False, allow_blank=True)
    password = serializers.CharField(
        min_length=8,
        write_only=True,
        trim_whitespace=False,
        required=False,
        allow_blank=True,
    )

    def validate_email(self, value):
        return value.strip().lower()

    def validate(self, attrs):
        existing_user = User.objects.filter(email__iexact=attrs["email"]).first()
        password = attrs.get("password", "")
        if existing_user is None and not password:
            raise serializers.ValidationError(
                {"password": "La contraseña temporal es obligatoria para un usuario nuevo."}
            )
        if password:
            try:
                validate_password(password, user=existing_user)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs


class OwnerSummarySerializer(serializers.ModelSerializer):
    nombres = serializers.CharField(source="first_names")
    apellidos = serializers.CharField(source="last_names")
    telefono = serializers.CharField(source="phone", allow_null=True)

    class Meta:
        model = User
        fields = ("id", "email", "nombres", "apellidos", "telefono")


class CompanySerializer(serializers.ModelSerializer):
    razon_social = serializers.CharField(source="legal_name")
    nombre_comercial = serializers.CharField(source="trade_name")
    ciudad_id = serializers.IntegerField(source="city_id", allow_null=True)
    ciudad = serializers.SerializerMethodField()
    subdominio = serializers.CharField(source="subdomain")
    nit = serializers.CharField(source="tax_id", allow_null=True)
    email_contacto = serializers.EmailField(source="contact_email", allow_null=True)
    telefono = serializers.CharField(source="phone", allow_null=True)
    estado = serializers.CharField(source="status")
    propietario = serializers.SerializerMethodField()
    creado_en = serializers.DateTimeField(source="created_at")
    actualizado_en = serializers.DateTimeField(source="updated_at")

    class Meta:
        model = Tenant
        fields = (
            "id",
            "razon_social",
            "nombre_comercial",
            "ciudad_id",
            "ciudad",
            "subdominio",
            "nit",
            "email_contacto",
            "telefono",
            "estado",
            "propietario",
            "creado_en",
            "actualizado_en",
        )

    @extend_schema_field(CitySerializer(allow_null=True))
    def get_ciudad(self, company):
        if company.city_id is None:
            return None
        city = City.objects.select_related("country").filter(pk=company.city_id).first()
        return CitySerializer(city).data if city else None

    @extend_schema_field(OwnerSummarySerializer(allow_null=True))
    def get_propietario(self, company):
        assignment = (
            UserRole.objects.select_related("user")
            .filter(
                tenant_id=company.id,
                role__code="TENANT_ADMIN",
                role__scope="TENANT",
            )
            .order_by("assigned_at")
            .first()
        )
        return OwnerSummarySerializer(assignment.user).data if assignment else None


class CompanyCreateSerializer(serializers.Serializer):
    razon_social = serializers.CharField(max_length=180)
    nombre_comercial = serializers.CharField(max_length=180)
    ciudad_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    subdominio = serializers.RegexField(
        r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$", required=False, allow_blank=True
    )
    nit = serializers.CharField(max_length=30, required=False, allow_blank=True)
    email_contacto = serializers.EmailField(required=False, allow_blank=True)
    telefono = serializers.CharField(max_length=30, required=False, allow_blank=True)
    plan_codigo = serializers.CharField(max_length=50, required=False, default="BASICO")
    propietario = OwnerInputSerializer()

    def validate_ciudad_id(self, value):
        if value is not None and not City.objects.filter(pk=value).exists():
            raise serializers.ValidationError("La ciudad seleccionada no existe.")
        return value

    def validate_plan_codigo(self, value):
        if not Plan.objects.filter(code__iexact=value, active=True).exists():
            raise serializers.ValidationError("El plan seleccionado no existe o no está disponible.")
        return value


class CompanyUpdateSerializer(serializers.Serializer):
    razon_social = serializers.CharField(max_length=180, required=False)
    nombre_comercial = serializers.CharField(max_length=180, required=False)
    ciudad_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    nit = serializers.CharField(max_length=30, required=False, allow_blank=True)
    email_contacto = serializers.EmailField(required=False, allow_blank=True)
    telefono = serializers.CharField(max_length=30, required=False, allow_blank=True)
    estado = serializers.ChoiceField(choices=Tenant.Status.choices, required=False)

    def validate_ciudad_id(self, value):
        if value is not None and not City.objects.filter(pk=value).exists():
            raise serializers.ValidationError("La ciudad seleccionada no existe.")
        return value


class OwnerAssignSerializer(serializers.Serializer):
    propietario = OwnerInputSerializer()


class PlanSerializer(serializers.ModelSerializer):
    codigo = serializers.CharField(source="code")
    nombre = serializers.CharField(source="name")
    moneda = serializers.CharField(source="currency.iso_code", read_only=True)
    precio_mensual = serializers.DecimalField(source="monthly_price", max_digits=12, decimal_places=2)
    max_usuarios = serializers.IntegerField(source="max_users")
    max_productos = serializers.IntegerField(source="max_products")
    porcentaje_comision = serializers.DecimalField(
        source="commission_percentage", max_digits=5, decimal_places=2
    )
    activo = serializers.BooleanField(source="active")

    class Meta:
        model = Plan
        fields = (
            "id",
            "codigo",
            "nombre",
            "moneda",
            "precio_mensual",
            "max_usuarios",
            "max_productos",
            "porcentaje_comision",
            "activo",
        )


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    fecha_inicio = serializers.DateField(source="start_date")
    fecha_fin = serializers.DateField(source="end_date", allow_null=True)
    estado = serializers.CharField(source="status")
    renovacion_automatica = serializers.BooleanField(source="auto_renew")
    creado_en = serializers.DateTimeField(source="created_at")

    class Meta:
        model = Subscription
        fields = (
            "id",
            "plan",
            "fecha_inicio",
            "fecha_fin",
            "estado",
            "renovacion_automatica",
            "creado_en",
        )


class SubscriptionChangeSerializer(serializers.Serializer):
    plan_codigo = serializers.CharField(max_length=50)
    renovacion_automatica = serializers.BooleanField(required=False, default=False, source="auto_renew")


class CompanySelfSignupSerializer(serializers.Serializer):
    razon_social = serializers.CharField(max_length=180)
    nombre_comercial = serializers.CharField(max_length=180)
    plan_codigo = serializers.CharField(max_length=50)
    ciudad_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    subdominio = serializers.RegexField(
        r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$", required=False, allow_blank=True
    )
    nit = serializers.CharField(max_length=30, required=False, allow_blank=True)
    email_contacto = serializers.EmailField(required=False, allow_blank=True)
    telefono = serializers.CharField(max_length=30, required=False, allow_blank=True)
    propietario = OwnerInputSerializer()

    def validate_ciudad_id(self, value):
        if value is not None and not City.objects.filter(pk=value).exists():
            raise serializers.ValidationError("La ciudad seleccionada no existe.")
        return value

    def validate_plan_codigo(self, value):
        if not Plan.objects.filter(code__iexact=value, active=True).exists():
            raise serializers.ValidationError("El plan seleccionado no existe o no está disponible.")
        return value
