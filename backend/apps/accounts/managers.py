from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    def get_by_natural_key(self, username):
        return self.get(email__iexact=username)

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("El correo es obligatorio.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        from apps.rbac.models import Role, UserRole

        extra_fields.setdefault("status", self.model.Status.ACTIVE)
        user = self.create_user(email, password, **extra_fields)
        role = Role.objects.get(code="SUPER_ADMIN", scope=Role.Scope.GLOBAL)
        UserRole.objects.get_or_create(user=user, role=role, tenant=None)
        return user

