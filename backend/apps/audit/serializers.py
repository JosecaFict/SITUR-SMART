from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    empresa = serializers.SerializerMethodField()
    usuario_email = serializers.SerializerMethodField()
    usuario_nombre = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = (
            "id",
            "tenant_id",
            "empresa",
            "user_id",
            "usuario_email",
            "usuario_nombre",
            "action",
            "entity",
            "entity_id",
            "previous_data",
            "new_data",
            "ip",
            "request_id",
            "created_at",
        )

    def get_empresa(self, obj) -> str | None:
        return obj.tenant.trade_name if obj.tenant_id else None

    def get_usuario_email(self, obj) -> str | None:
        return obj.user.email if obj.user_id else None

    def get_usuario_nombre(self, obj) -> str | None:
        return f"{obj.user.first_names} {obj.user.last_names}" if obj.user_id else None
