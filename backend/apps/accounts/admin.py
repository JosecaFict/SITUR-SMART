from django.contrib import admin

from .models import PasswordResetToken, User, UserSession


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "first_names", "last_names", "status", "is_staff", "created_at")
    list_filter = ("status",)
    search_fields = ("email", "first_names", "last_names")
    ordering = ("email",)
    readonly_fields = ("last_login", "email_verified_at", "created_at", "updated_at")
    fields = (
        "email",
        "first_names",
        "last_names",
        "phone",
        "status",
        "email_verified_at",
        "last_login",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(UserSession)
class UserSessionAdmin(ReadOnlyAdmin):
    list_display = ("user", "ip", "expires_at", "revoked_at", "created_at")
    list_filter = ("revoked_at",)
    search_fields = ("user__email", "ip")


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(ReadOnlyAdmin):
    list_display = ("user", "expires_at", "used_at", "created_at")
    search_fields = ("user__email",)
