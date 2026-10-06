from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection, transaction

from apps.accounts.models import CustomerProfile, User
from apps.accounts.services import create_or_link_tenant_user
from apps.audit.services import record_audit
from apps.catalog.seed import bolivia, credenciales, sql
from apps.catalog.services import (
    create_lodging,
    create_product,
    create_room,
    update_lodging,
)
from apps.rbac.models import Role, UserRole
from apps.rbac.services import create_tenant_role, is_superadmin
from apps.tenancy.models import City, Country, Tenant
from apps.tenancy.services import (
    change_company_status,
    create_city,
    create_company,
    self_signup_company,
)

CREDENTIALS_PATH = Path(settings.BASE_DIR).parent / "CREDENCIALES_DEMO.md"
SQL_PATH = Path(settings.BASE_DIR) / "database" / "seed_bolivia.sql"

# Orden de borrado de --reset: primero lo que depende de otra fila. rol_permiso,
# sesion_usuario y token_recuperacion caen solos por ON DELETE CASCADE.
_RESET_STATEMENTS = (
    "DELETE FROM habitacion WHERE id_tenant = ANY(%(t)s)",
    "DELETE FROM establecimiento_hospedaje WHERE id_tenant = ANY(%(t)s)",
    "DELETE FROM disponibilidad WHERE id_tenant = ANY(%(t)s)",
    "DELETE FROM producto_turistico WHERE id_tenant = ANY(%(t)s)",
    "DELETE FROM usuario_rol WHERE id_tenant = ANY(%(t)s) OR id_usuario = ANY(%(u)s)",
    "DELETE FROM rol WHERE id_tenant = ANY(%(t)s)",
    "DELETE FROM usuario_tenant WHERE id_tenant = ANY(%(t)s) OR id_usuario = ANY(%(u)s)",
    "DELETE FROM suscripcion WHERE id_tenant = ANY(%(t)s)",
    "DELETE FROM bitacora WHERE id_tenant = ANY(%(t)s) OR id_usuario = ANY(%(u)s)",
    "DELETE FROM perfil_cliente WHERE id_usuario = ANY(%(u)s)",
    "DELETE FROM usuario WHERE id = ANY(%(u)s)",
    "DELETE FROM tenant WHERE id = ANY(%(t)s)",
)


class Command(BaseCommand):
    help = (
        "Carga empresas turísticas de Bolivia con sus hoteles, habitaciones, productos, "
        "empleados y turistas de demostración. Se puede ejecutar varias veces: una empresa "
        "que ya existe se omite. Los datos están en apps/catalog/seed/bolivia.py."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Borra todo lo que creó este seed (empresas, cuentas y oferta) y lo vuelve a cargar.",
        )
        parser.add_argument(
            "--limpiar-demo-viejo",
            action="store_true",
            help="Desactiva las empresas ficticias y las cuentas duenioN@situr.smart del seed anterior.",
        )
        parser.add_argument(
            "--credenciales",
            action="store_true",
            help="Solo regenera CREDENCIALES_DEMO.md en la raíz del repositorio; no toca la base.",
        )
        parser.add_argument(
            "--sql",
            action="store_true",
            help=(
                "Solo genera database/seed_bolivia.sql para ejecutarlo en pgAdmin (Query Tool); "
                "no toca la base. Respeta --limpiar-demo-viejo."
            ),
        )

    def handle(self, *args, **options):
        if options["credenciales"]:
            CREDENTIALS_PATH.write_text(credenciales.render(), encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Credenciales escritas en {CREDENTIALS_PATH}"))
            return
        if options["sql"]:
            SQL_PATH.write_text(
                sql.render(limpiar_demo_viejo=options["limpiar_demo_viejo"]), encoding="utf-8"
            )
            self.stdout.write(self.style.SUCCESS(f"Script SQL escrito en {SQL_PATH}"))
            return

        admin = next(
            (u for u in User.objects.filter(status=User.Status.ACTIVE) if is_superadmin(u)), None
        )
        if admin is None:
            raise CommandError(
                "No existe un SuperAdmin activo. Ejecuta antes: python manage.py createsituradmin"
            )

        with transaction.atomic():
            if options["limpiar_demo_viejo"]:
                self._deactivate_old_demo(admin)
            if options["reset"]:
                self._reset()
            cities = self._cities(admin)
            created = 0
            for empresa in bolivia.EMPRESAS:
                if Tenant.objects.filter(trade_name=empresa["nombre"]).exists():
                    self.stdout.write(f"= ya existe: {empresa['nombre']}")
                    continue
                self._load_company(admin, empresa, cities)
                created += 1
            tourists = self._load_tourists()

        self.stdout.write(
            self.style.SUCCESS(
                f"Listo: {created} empresas y {tourists} turistas creados. "
                f"Contraseña de todas las cuentas: {bolivia.PASSWORD}"
            )
        )

    # ------------------------------------------------------------------

    def _cities(self, admin) -> dict[str, int]:
        country = Country.objects.get(iso_code=bolivia.PAIS)
        for ciudad in bolivia.CIUDADES_NUEVAS:
            if not City.objects.filter(country=country, name=ciudad["nombre"]).exists():
                create_city(actor=admin, pais_id=country.id, **ciudad)
                self.stdout.write(self.style.SUCCESS(f"+ ciudad: {ciudad['nombre']}"))
        return dict(City.objects.filter(country=country).values_list("name", "id"))

    def _load_company(self, admin, empresa: dict, cities: dict[str, int]) -> None:
        owner_account, *staff = bolivia.cuentas_empresa(empresa)
        owner_data = {
            "email": owner_account["email"],
            "nombres": owner_account["nombres"],
            "apellidos": owner_account["apellidos"],
            "password": bolivia.PASSWORD,
        }
        company_data = {
            "razon_social": empresa["nombre"],
            "nombre_comercial": empresa["nombre"],
            "propietario": owner_data,
            "ciudad_id": cities[empresa["ciudad"]],
            "email_contacto": bolivia.email("contacto", empresa["dominio"]),
            "plan_codigo": empresa["plan"],
        }

        if empresa["estado"] == "PENDIENTE":
            # Igual que un autorregistro real: la empresa espera la revision del
            # SuperAdmin y su propietario todavia no puede cargar nada.
            if staff or empresa["hoteles"] or empresa["productos"]:
                raise CommandError(
                    f"{empresa['nombre']} está PENDIENTE: no puede tener empleados ni oferta."
                )
            self_signup_company(**company_data)
            self.stdout.write(self.style.SUCCESS(f"+ {empresa['nombre']} (pendiente)"))
            return

        company = create_company(actor=admin, **company_data)
        tenant_id = company.id
        # El resto lo carga el propietario, como lo haria desde el panel: el
        # SuperAdmin no administra empleados internos.
        owner = User.objects.get(email=owner_account["email"])

        for code in dict.fromkeys(c["rol"] for c in staff):
            if code in bolivia.ROLES_PERSONALIZADOS:
                role = bolivia.ROLES_PERSONALIZADOS[code]
                create_tenant_role(
                    actor=owner, tenant_id=tenant_id, code=code, name=role["nombre"],
                    permission_codes=role["permisos"],
                )
        for account in staff:
            create_or_link_tenant_user(
                actor=owner, tenant_id=tenant_id, email=account["email"],
                first_names=account["nombres"], last_names=account["apellidos"],
                role_code=account["rol"], password=bolivia.PASSWORD,
            )

        rooms = 0
        for hotel in empresa["hoteles"]:
            lodging = create_lodging(
                actor=owner, tenant_id=tenant_id,
                nombre=hotel["nombre"], descripcion=hotel["descripcion"],
                ciudad_id=cities[hotel["ciudad"]], moneda_codigo=bolivia.MONEDA,
                localidad=hotel["localidad"], direccion=hotel["direccion"],
                latitud=hotel["latitud"], longitud=hotel["longitud"],
                categoria_estrellas=hotel["estrellas"],
                hora_check_in=hotel["check_in"], hora_check_out=hotel["check_out"],
                servicios=hotel["servicios"],
                estado=bolivia.BORRADOR,
            )
            for room in hotel["habitaciones"]:
                create_room(actor=owner, tenant_id=tenant_id, lodging_id=lodging.id, **room)
                rooms += 1
            # Un hotel solo se publica cuando ya tiene habitaciones publicadas.
            if hotel["estado"] == bolivia.PUBLICADO:
                update_lodging(
                    actor=owner, tenant_id=tenant_id, lodging_id=lodging.id,
                    estado=bolivia.PUBLICADO,
                )

        for item in empresa["productos"]:
            create_product(
                actor=owner, tenant_id=tenant_id,
                tipo_codigo=item["tipo"], ciudad_id=cities[item["ciudad"]],
                moneda_codigo=bolivia.MONEDA, nombre=item["nombre"],
                descripcion=item["descripcion"], localidad=item["localidad"],
                precio_base=item["precio_base"], capacidad_maxima=item["capacidad_maxima"],
                estado=item["estado"],
            )

        if empresa["estado"] == "SUSPENDIDO":
            change_company_status(actor=admin, company_id=tenant_id, estado=Tenant.Status.SUSPENDED)

        self.stdout.write(
            self.style.SUCCESS(
                f"+ {empresa['nombre']}: {len(staff) + 1} cuentas, {len(empresa['hoteles'])} hoteles, "
                f"{rooms} habitaciones, {len(empresa['productos'])} productos"
            )
        )

    def _load_tourists(self) -> int:
        role = Role.objects.get(code="CLIENTE", scope=Role.Scope.GLOBAL)
        created = 0
        for account in bolivia.cuentas_turistas():
            if User.objects.filter(email__iexact=account["email"]).exists():
                continue
            user = User.objects.create_user(
                email=account["email"], password=bolivia.PASSWORD,
                first_names=account["nombres"], last_names=account["apellidos"],
                status=User.Status.ACTIVE,
            )
            UserRole.objects.create(user=user, role=role, tenant=None)
            CustomerProfile.objects.get_or_create(user=user)
            record_audit(
                actor=user, action="REGISTRO_CLIENTE", entity="usuario",
                entity_id=str(user.id), new_data={"email": user.email, "role": "CLIENTE"},
            )
            created += 1
        return created

    def _reset(self) -> None:
        if connection.vendor != "postgresql":
            raise CommandError("--reset solo está disponible sobre PostgreSQL.")
        tenant_ids = list(
            Tenant.objects.filter(trade_name__in=[e["nombre"] for e in bolivia.EMPRESAS])
            .values_list("id", flat=True)
        )
        user_ids = [
            user.id
            for user in User.objects.filter(email__in=bolivia.todos_los_emails())
            if not is_superadmin(user)
        ]
        try:
            with connection.cursor() as cursor:
                for statement in _RESET_STATEMENTS:
                    cursor.execute(statement, {"t": tenant_ids, "u": user_ids})
        except DatabaseError as error:
            raise CommandError(
                "No se pudo borrar lo cargado por el seed; probablemente hay datos que dependen "
                f"de estas empresas (reservas, pagos...). Detalle: {error}"
            ) from error
        self.stdout.write(
            self.style.WARNING(f"- reset: {len(tenant_ids)} empresas y {len(user_ids)} cuentas borradas")
        )

    def _deactivate_old_demo(self, admin) -> None:
        for company in Tenant.objects.filter(trade_name__in=bolivia.DEMO_VIEJO_EMPRESAS):
            if company.status != Tenant.Status.INACTIVE:
                change_company_status(actor=admin, company_id=company.id, estado=Tenant.Status.INACTIVE)
                self.stdout.write(self.style.WARNING(f"- desactivada: {company.trade_name}"))
        for user in User.objects.filter(email__in=bolivia.DEMO_VIEJO_EMAILS).exclude(
            status=User.Status.INACTIVE
        ):
            previous = user.status
            user.status = User.Status.INACTIVE
            user.save(update_fields=["status", "updated_at"])
            record_audit(
                actor=admin, action="CAMBIAR_ESTADO", entity="usuario", entity_id=str(user.id),
                previous_data={"estado": previous}, new_data={"estado": user.status},
            )
            self.stdout.write(self.style.WARNING(f"- cuenta desactivada: {user.email}"))
