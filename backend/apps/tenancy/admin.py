from django.contrib import admin

from .models import City, Country, Tenant


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("iso_code", "name")
    search_fields = ("iso_code", "name")
    ordering = ("name",)


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "timezone")
    list_filter = ("country",)
    search_fields = ("name", "country__name")
    ordering = ("name",)


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("trade_name", "legal_name", "subdomain", "status", "contact_email", "created_at")
    list_filter = ("status",)
    search_fields = ("trade_name", "legal_name", "subdomain", "tax_id", "contact_email")
    ordering = ("trade_name",)
    readonly_fields = ("created_at", "updated_at")
