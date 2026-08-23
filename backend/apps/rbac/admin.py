from django.contrib import admin

from .models import Permission, Role, UserRole


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "module")
    list_filter = ("module",)
    search_fields = ("code", "name", "module")
    ordering = ("module", "code")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "scope", "tenant", "is_system")
    list_filter = ("scope", "is_system")
    search_fields = ("code", "name", "tenant__trade_name")
    ordering = ("scope", "code")


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "tenant", "assigned_at")
    list_filter = ("role__scope",)
    search_fields = ("user__email", "role__code", "tenant__trade_name")
    readonly_fields = ("assigned_at",)
