from getpass import getpass

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.rbac.models import Role, UserRole


class Command(BaseCommand):
    help = "Crea el primer SuperAdmin global de SITUR-SMART."

    def add_arguments(self, parser):
        parser.add_argument("--email")
        parser.add_argument("--nombres")
        parser.add_argument("--apellidos")
        parser.add_argument("--password")

    @transaction.atomic
    def handle(self, *args, **options):
        email = options["email"] or input("Correo: ").strip()
        first_names = options["nombres"] or input("Nombres: ").strip()
        last_names = options["apellidos"] or input("Apellidos: ").strip()
        password = options["password"] or getpass("Contraseña: ")

        if User.objects.filter(email__iexact=email).exists():
            raise CommandError("Ya existe un usuario con ese correo.")
        if len(password) < 8:
            raise CommandError("La contraseña debe tener al menos 8 caracteres.")

        try:
            role = Role.objects.get(code="SUPER_ADMIN", scope=Role.Scope.GLOBAL)
        except Role.DoesNotExist as exc:
            raise CommandError("No existe el rol SUPER_ADMIN. Ejecuta los datos semilla.") from exc

        user = User.objects.create_user(
            email=email,
            password=password,
            first_names=first_names,
            last_names=last_names,
            status=User.Status.ACTIVE,
        )
        UserRole.objects.create(user=user, role=role, tenant=None)
        self.stdout.write(self.style.SUCCESS(f"SuperAdmin creado: {user.email}"))

