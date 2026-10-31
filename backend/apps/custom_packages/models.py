from django.conf import settings
from django.db import models


class CustomPackage(models.Model):
    class Status(models.TextChoices):
        DRAFT = "BORRADOR", "Borrador"
        SAVED = "GUARDADO", "Guardado"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="custom_packages")
    name = models.CharField(max_length=120)
    city = models.ForeignKey("tenancy.City", null=True, blank=True, on_delete=models.SET_NULL)
    start_date = models.DateField()
    end_date = models.DateField()
    travelers = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "paquete_personalizado"
        ordering = ("-updated_at", "-id")


class PackageComponent(models.Model):
    package = models.ForeignKey(CustomPackage, on_delete=models.CASCADE, related_name="components")
    product = models.ForeignKey("catalog.TourismProduct", on_delete=models.PROTECT)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    quantity = models.PositiveSmallIntegerField()
    guests = models.PositiveSmallIntegerField(null=True, blank=True)
    departure = models.ForeignKey("catalog.Availability", null=True, blank=True, on_delete=models.PROTECT)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "paquete_personalizado_componente"
        ordering = ("start_date", "id")
