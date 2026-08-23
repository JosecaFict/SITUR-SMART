from django.contrib import admin

from .models import Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("trade_name", "legal_name", "subdomain", "status", "contact_email", "created_at")
    list_filter = ("status",)
    search_fields = ("trade_name", "legal_name", "subdomain", "tax_id", "contact_email")
    ordering = ("trade_name",)
    readonly_fields = ("created_at", "updated_at")
