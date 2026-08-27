from rest_framework import serializers

from .models import Tenant


class TenantSerializer(serializers.ModelSerializer):
    nombre_comercial = serializers.CharField(source="trade_name")
    razon_social = serializers.CharField(source="legal_name")
    estado = serializers.CharField(source="status")
    nit = serializers.CharField(source="tax_id", allow_null=True, required=False)
    email_contacto = serializers.EmailField(source="contact_email", allow_null=True, required=False)
    telefono = serializers.CharField(source="phone", allow_null=True, required=False)

    class Meta:
        model = Tenant
        fields = (
            "id",
            "nombre_comercial",
            "razon_social",
            "subdomain",
            "nit",
            "email_contacto",
            "telefono",
            "estado",
        )