from django.db import models


class AuditLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    tenant = models.ForeignKey(
        "tenancy.Tenant", db_column="id_tenant", null=True, blank=True, on_delete=models.DO_NOTHING
    )
    user = models.ForeignKey(
        "accounts.User", db_column="id_usuario", null=True, blank=True, on_delete=models.DO_NOTHING
    )
    action = models.CharField(db_column="accion", max_length=50)
    entity = models.CharField(db_column="entidad", max_length=100)
    entity_id = models.CharField(db_column="entidad_id",max_length=100,null=True,blank=True,)
    previous_data = models.JSONField(db_column="datos_anteriores", null=True, blank=True)
    new_data = models.JSONField(db_column="datos_nuevos", null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    request_id = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)

    class Meta:
        managed = False
        db_table = "bitacora"
        ordering = ("-created_at",)

