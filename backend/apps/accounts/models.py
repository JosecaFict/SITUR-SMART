from django.contrib.auth.base_user import AbstractBaseUser
from django.db import models

from .managers import UserManager


class User(AbstractBaseUser):
    class Status(models.TextChoices):
        PENDING = "PENDIENTE", "Pendiente"
        ACTIVE = "ACTIVO", "Activo"
        INACTIVE = "INACTIVO", "Inactivo"
        BLOCKED = "BLOQUEADO", "Bloqueado"

    id = models.BigAutoField(primary_key=True)
    email = models.EmailField(max_length=255, unique=True)
    password = models.TextField(db_column="password_hash")
    first_names = models.CharField(db_column="nombres", max_length=120)
    last_names = models.CharField(db_column="apellidos", max_length=120)
    phone = models.CharField(db_column="telefono", max_length=30, null=True, blank=True)
    status = models.CharField(db_column="estado", max_length=20, choices=Status.choices)
    email_verified_at = models.DateTimeField(db_column="email_verificado_en", null=True, blank=True)
    last_login = models.DateTimeField(db_column="ultimo_acceso_en", null=True, blank=True)
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="actualizado_en", auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ("first_names", "last_names")

    class Meta:
        managed = False
        db_table = "usuario"
        ordering = ("email",)

    @property
    def is_active(self) -> bool:
        return self.status == self.Status.ACTIVE

    @property
    def is_staff(self) -> bool:
        return self.user_roles.filter(role__code="SUPER_ADMIN", tenant__isnull=True).exists()

    @property
    def is_superuser(self) -> bool:
        return self.is_staff

    def has_perm(self, perm, obj=None) -> bool:
        if self.is_superuser:
            return True
        return self.user_roles.filter(role__role_permissions__permission__code=perm).exists()

    def has_module_perms(self, app_label) -> bool:
        return self.is_superuser

    def get_full_name(self) -> str:
        return f"{self.first_names} {self.last_names}".strip()

    def get_short_name(self) -> str:
        return self.first_names

    def __str__(self) -> str:
        return self.email


class UserSession(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, db_column="id_usuario", on_delete=models.DO_NOTHING, related_name="sessions")
    refresh_token_hash = models.TextField(unique=True)
    user_agent = models.TextField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    expires_at = models.DateTimeField(db_column="expira_en")
    revoked_at = models.DateTimeField(db_column="revocada_en", null=True, blank=True)
    created_at = models.DateTimeField(db_column="creada_en", auto_now_add=True)

    class Meta:
        managed = False
        db_table = "sesion_usuario"


class PasswordResetToken(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, db_column="id_usuario", on_delete=models.DO_NOTHING)
    token_hash = models.TextField(unique=True)
    expires_at = models.DateTimeField(db_column="expira_en")
    used_at = models.DateTimeField(db_column="usado_en", null=True, blank=True)
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)

    class Meta:
        managed = False
        db_table = "token_recuperacion"


class CustomerProfile(models.Model):
    user = models.OneToOneField(
        User,
        db_column="id_usuario",
        primary_key=True,
        on_delete=models.DO_NOTHING,
        related_name="customer_profile",
    )
    document_type = models.CharField(db_column="tipo_documento", max_length=30, null=True, blank=True)
    document_number = models.CharField(db_column="numero_documento", max_length=50, null=True, blank=True)
    birth_date = models.DateField(db_column="fecha_nacimiento", null=True, blank=True)
    preferences = models.JSONField(db_column="preferencias", default=dict)
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)

    class Meta:
        managed = False
        db_table = "perfil_cliente"

