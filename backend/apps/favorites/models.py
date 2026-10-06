from django.conf import settings
from django.db import models


class Favorite(models.Model):
    """Producto que un usuario guardo para ver despues."""

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        db_column="id_usuario",
        on_delete=models.CASCADE,
        related_name="favorites",
    )
    product = models.ForeignKey(
        "catalog.TourismProduct",
        db_column="id_producto",
        on_delete=models.CASCADE,
        related_name="favorites",
    )
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)

    class Meta:
        managed = False
        db_table = "favorito"
        ordering = ("-created_at", "-id")
