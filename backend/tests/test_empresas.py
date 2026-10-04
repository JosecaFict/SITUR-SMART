"""Pruebas de la fase critica de CU8: estados, bloqueo operativo y permisos.

Tres reglas nuevas, cada una con su capa:

* la maquina de transiciones y los requisitos de activacion, en ``tenancy``;
* el bloqueo por estado, en ``rbac.require_tenant_access``;
* la semantica de los permisos de plataforma, en ``tenancy``.

Nada toca la base: los modelos son ``managed = False`` y la suite corre sobre
SQLite, asi que las consultas estan parcheadas y los objetos son instancias de
modelo sin guardar. Lo que se ejercita es la decision, no el ORM.
"""

from contextlib import ExitStack
from typing import ClassVar
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.rbac import services as rbac_services
from apps.tenancy import services as tenancy_services
from apps.tenancy.models import TENANT_STATUS_TRANSITIONS, Plan, Subscription, Tenant
from apps.tenancy.views import CompanySignupView, CompanyStatusView, SelfSignupThrottle

COMPANY_ID = 7
OTHER_COMPANY_ID = 8

TODOS = (
    Tenant.Status.PENDING,
    Tenant.Status.ACTIVE,
    Tenant.Status.INACTIVE,
    Tenant.Status.SUSPENDED,
)


def empresa(status=Tenant.Status.PENDING, pk=COMPANY_ID) -> Tenant:
    return Tenant(
        id=pk,
        legal_name="ToursBo SRL",
        trade_name="ToursBo",
        subdomain="toursbo",
        status=status,
    )


def sin_consultas_de_serializer():
    """Neutraliza las consultas que ``CompanySerializer`` hace por su cuenta.

    ``ciudad`` y ``propietario`` son ``SerializerMethodField`` que consultan la
    base al serializar, y aqui no hay base. Lo que se prueba es la vista, no la
    resolucion del propietario.
    """
    pila = ExitStack()
    propietario = pila.enter_context(
        patch("apps.tenancy.serializers.UserRole.objects.select_related")
    )
    propietario.return_value.filter.return_value.order_by.return_value.first.return_value = None
    ciudad = pila.enter_context(patch("apps.tenancy.serializers.City.objects.select_related"))
    ciudad.return_value.filter.return_value.first.return_value = None
    return pila


# ---------------------------------------------------------------------------
# A. Maquina de estados
# ---------------------------------------------------------------------------


class TransitionTableTests(SimpleTestCase):
    """La tabla es el contrato; se verifica como tal."""

    def test_the_four_states_are_covered(self):
        self.assertEqual(set(TENANT_STATUS_TRANSITIONS), set(TODOS))

    def test_the_declared_transitions(self):
        self.assertEqual(
            TENANT_STATUS_TRANSITIONS[Tenant.Status.PENDING],
            frozenset({Tenant.Status.ACTIVE, Tenant.Status.INACTIVE}),
        )
        self.assertEqual(
            TENANT_STATUS_TRANSITIONS[Tenant.Status.ACTIVE],
            frozenset({Tenant.Status.SUSPENDED, Tenant.Status.INACTIVE}),
        )
        self.assertEqual(
            TENANT_STATUS_TRANSITIONS[Tenant.Status.SUSPENDED],
            frozenset({Tenant.Status.ACTIVE, Tenant.Status.INACTIVE}),
        )
        self.assertEqual(
            TENANT_STATUS_TRANSITIONS[Tenant.Status.INACTIVE],
            frozenset({Tenant.Status.ACTIVE}),
        )

    def test_an_active_company_can_never_go_back_to_pending(self):
        """«Pendiente» es «la plataforma no la revisó»: no se vuelve cierto."""
        for origen in (Tenant.Status.ACTIVE, Tenant.Status.SUSPENDED, Tenant.Status.INACTIVE):
            with self.subTest(origen=origen):
                self.assertNotIn(Tenant.Status.PENDING, TENANT_STATUS_TRANSITIONS[origen])

    def test_no_state_declares_itself(self):
        """Pedir el estado actual se resuelve antes, no por la tabla."""
        for origen, destinos in TENANT_STATUS_TRANSITIONS.items():
            with self.subTest(origen=origen):
                self.assertNotIn(origen, destinos)


class StatusChangeTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    def setUp(self):
        self.audit = patch("apps.tenancy.services.record_audit").start()
        self.addCleanup(patch.stopall)
        # Activar exige tres cosas; se dan por cumplidas salvo donde se prueban.
        patch("apps.tenancy.services._check_activation_requirements").start()

    def _cambiar(self, desde, hasta):
        company = empresa(status=desde)
        with patch.object(Tenant, "save") as save:
            resultado = tenancy_services._apply_status_change(
                actor=MagicMock(), company=company, nuevo_estado=hasta
            )
        return resultado, save

    def test_every_valid_transition_is_applied(self):
        for desde, destinos in TENANT_STATUS_TRANSITIONS.items():
            for hasta in destinos:
                with self.subTest(transicion=f"{desde}->{hasta}"):
                    resultado, save = self._cambiar(desde, hasta)

                    self.assertEqual(resultado.status, hasta)
                    save.assert_called_once()

    def test_every_invalid_transition_is_rejected(self):
        for desde in TODOS:
            permitidas = TENANT_STATUS_TRANSITIONS[desde]
            for hasta in TODOS:
                if hasta == desde or hasta in permitidas:
                    continue
                with self.subTest(transicion=f"{desde}->{hasta}"):
                    with self.assertRaises(ValidationError) as caso:
                        self._cambiar(desde, hasta)

                    self.assertIn("estado", caso.exception.detail)

    def test_active_to_pending_is_rejected_with_a_readable_message(self):
        with self.assertRaises(ValidationError) as caso:
            self._cambiar(Tenant.Status.ACTIVE, Tenant.Status.PENDING)

        mensaje = str(caso.exception.detail["estado"])
        self.assertIn("ACTIVO", mensaje)
        self.assertIn("PENDIENTE", mensaje)

    def test_asking_for_the_current_state_changes_nothing(self):
        """Y no deja una entrada de bitácora que mentiría sobre un cambio."""
        for estado in TODOS:
            with self.subTest(estado=estado):
                resultado, save = self._cambiar(estado, estado)

                self.assertEqual(resultado.status, estado)
                save.assert_not_called()
        self.audit.assert_not_called()

    def test_the_change_is_audited_as_cambiar_estado(self):
        self._cambiar(Tenant.Status.PENDING, Tenant.Status.ACTIVE)

        kwargs = self.audit.call_args.kwargs
        self.assertEqual(kwargs["action"], "CAMBIAR_ESTADO")
        self.assertEqual(kwargs["entity"], "empresa")
        self.assertEqual(kwargs["entity_id"], str(COMPANY_ID))
        self.assertEqual(kwargs["tenant_id"], COMPANY_ID)
        self.assertEqual(kwargs["previous_data"], {"estado": Tenant.Status.PENDING})
        self.assertEqual(kwargs["new_data"], {"estado": Tenant.Status.ACTIVE})

    def test_only_the_status_column_is_written(self):
        """No se arrastra ningún otro campo del objeto en memoria."""
        _, save = self._cambiar(Tenant.Status.ACTIVE, Tenant.Status.SUSPENDED)

        self.assertEqual(save.call_args.kwargs["update_fields"], ("status", "updated_at"))


class ActivationRequirementTests(SimpleTestCase):
    """Activar exige propietario, suscripción activa y plan vigente."""

    databases: ClassVar[set[str]] = {"default"}

    @staticmethod
    def _con(owner_id=1, subscription=None):
        """Parchea las dos consultas que mira el chequeo de activación."""
        pila = ExitStack()
        pila.enter_context(
            patch("apps.tenancy.services._company_owner_id", return_value=owner_id)
        )
        consulta = pila.enter_context(
            patch("apps.tenancy.services.Subscription.objects.select_related")
        )
        consulta.return_value.filter.return_value.first.return_value = subscription
        return pila

    @staticmethod
    def _suscripcion(plan_activo=True):
        plan = Plan(id=1, code="BASICO", name="Básico", price=0, active=plan_activo)
        return Subscription(id=1, plan=plan, status=Subscription.Status.ACTIVE)

    def test_a_complete_company_can_be_activated(self):
        with self._con(owner_id=3, subscription=self._suscripcion()):
            tenancy_services._check_activation_requirements(empresa())

    def test_without_an_owner_it_cannot(self):
        with self._con(owner_id=None, subscription=self._suscripcion()):
            with self.assertRaises(ValidationError) as caso:
                tenancy_services._check_activation_requirements(empresa())

        self.assertIn("propietario", caso.exception.detail)

    def test_without_an_active_subscription_it_cannot(self):
        with self._con(owner_id=3, subscription=None):
            with self.assertRaises(ValidationError) as caso:
                tenancy_services._check_activation_requirements(empresa())

        self.assertIn("suscripcion", caso.exception.detail)

    def test_with_a_retired_plan_it_cannot(self):
        with self._con(owner_id=3, subscription=self._suscripcion(plan_activo=False)):
            with self.assertRaises(ValidationError) as caso:
                tenancy_services._check_activation_requirements(empresa())

        self.assertIn("plan", caso.exception.detail)

    def test_all_the_problems_are_reported_at_once(self):
        """Descubrirlos de uno en uno obligaría a tres intentos."""
        with self._con(owner_id=None, subscription=None):
            with self.assertRaises(ValidationError) as caso:
                tenancy_services._check_activation_requirements(empresa())

        self.assertEqual(set(caso.exception.detail), {"propietario", "suscripcion"})

    def test_activating_runs_the_check(self):
        company = empresa(status=Tenant.Status.PENDING)
        with patch(
            "apps.tenancy.services._check_activation_requirements",
            side_effect=ValidationError({"propietario": "x"}),
        ) as check, patch.object(Tenant, "save"):
            with self.assertRaises(ValidationError):
                tenancy_services._apply_status_change(
                    actor=MagicMock(), company=company, nuevo_estado=Tenant.Status.ACTIVE
                )

        check.assert_called_once()

    def test_suspending_does_not_run_the_check(self):
        """Una empresa incompleta tiene que poder suspenderse igual."""
        company = empresa(status=Tenant.Status.ACTIVE)
        with patch("apps.tenancy.services._check_activation_requirements") as check, patch.object(
            Tenant, "save"
        ), patch("apps.tenancy.services.record_audit"):
            tenancy_services._apply_status_change(
                actor=MagicMock(), company=company, nuevo_estado=Tenant.Status.SUSPENDED
            )

        check.assert_not_called()


class StatusEndpointTests(SimpleTestCase):
    """La acción propia, separada del PATCH general."""

    databases: ClassVar[set[str]] = {"default"}

    def _call(self, body, *, permitido=True):
        request = APIRequestFactory().post(
            f"/api/v1/empresas/{COMPANY_ID}/estado/", body, format="json"
        )
        force_authenticate(request, user=MagicMock(is_authenticated=True))
        gestion = patch("apps.tenancy.views.require_company_management")
        if not permitido:
            gestion = patch(
                "apps.tenancy.views.require_company_management",
                side_effect=PermissionDenied("sin permiso"),
            )
        with gestion:
            return CompanyStatusView.as_view()(request, pk=COMPANY_ID)

    def test_a_valid_change_returns_the_company(self):
        with sin_consultas_de_serializer(), patch(
            "apps.tenancy.views.change_company_status",
            return_value=empresa(status=Tenant.Status.SUSPENDED),
        ) as servicio:
            response = self._call({"estado": "SUSPENDIDO"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["estado"], "SUSPENDIDO")
        self.assertEqual(servicio.call_args.kwargs["estado"], "SUSPENDIDO")

    def test_an_unknown_state_is_a_400_before_reaching_the_service(self):
        with patch("apps.tenancy.views.change_company_status") as servicio:
            response = self._call({"estado": "ARCHIVADO"})

        self.assertEqual(response.status_code, 400)
        servicio.assert_not_called()

    def test_without_management_permission_it_is_a_403(self):
        with patch("apps.tenancy.views.change_company_status") as servicio:
            response = self._call({"estado": "SUSPENDIDO"}, permitido=False)

        self.assertEqual(response.status_code, 403)
        servicio.assert_not_called()

    def test_an_anonymous_request_is_rejected(self):
        request = APIRequestFactory().post(
            f"/api/v1/empresas/{COMPANY_ID}/estado/", {"estado": "ACTIVO"}, format="json"
        )

        response = CompanyStatusView.as_view()(request, pk=COMPANY_ID)

        self.assertEqual(response.status_code, 401)

    def test_a_missing_company_is_a_404(self):
        with patch("apps.tenancy.services.Tenant.objects.filter") as filtro, patch(
            "apps.tenancy.services.require_company_management"
        ):
            filtro.return_value.first.return_value = None
            with self.assertRaises(NotFound):
                tenancy_services.change_company_status(
                    actor=MagicMock(), company_id=999, estado="ACTIVO"
                )


class UpdateDelegatesStatusTests(SimpleTestCase):
    """El PATCH general no escribe el estado: lo delega en la máquina."""

    databases: ClassVar[set[str]] = {"default"}

    def _update(self, **changes):
        company = empresa(status=Tenant.Status.ACTIVE)
        with patch("apps.tenancy.services.require_company_management"), patch(
            "apps.tenancy.services.Tenant.objects.filter"
        ) as filtro, patch("apps.tenancy.services.record_audit"), patch(
            "apps.tenancy.services._apply_status_change"
        ) as maquina, patch.object(Tenant, "save"):
            filtro.return_value.first.return_value = company
            tenancy_services.update_company(
                actor=MagicMock(), company_id=COMPANY_ID, **changes
            )
        return maquina

    def test_a_status_in_the_body_goes_through_the_state_machine(self):
        maquina = self._update(estado="SUSPENDIDO")

        maquina.assert_called_once()
        self.assertEqual(maquina.call_args.kwargs["nuevo_estado"], "SUSPENDIDO")

    def test_without_a_status_the_machine_is_not_invoked(self):
        maquina = self._update(razon_social="Otro Nombre SRL")

        maquina.assert_not_called()

    def test_the_status_is_not_written_as_a_plain_field(self):
        """Si siguiera en el mapeo, se guardaría sin validar la transición."""
        self.assertNotIn("estado", tenancy_services.update_company.__doc__ or "")
        company = empresa(status=Tenant.Status.ACTIVE)
        with patch("apps.tenancy.services.require_company_management"), patch(
            "apps.tenancy.services.Tenant.objects.filter"
        ) as filtro, patch("apps.tenancy.services.record_audit"), patch(
            "apps.tenancy.services._apply_status_change"
        ), patch.object(Tenant, "save") as save:
            filtro.return_value.first.return_value = company
            tenancy_services.update_company(
                actor=MagicMock(), company_id=COMPANY_ID, estado="SUSPENDIDO"
            )

        # Sin otros campos que cambiar, no hay UPDATE del PATCH general.
        save.assert_not_called()


# ---------------------------------------------------------------------------
# B. Bloqueo operativo por estado
# ---------------------------------------------------------------------------


class TenantOperationBlockTests(SimpleTestCase):
    """``require_tenant_access`` ahora exige que la empresa esté operativa."""

    databases: ClassVar[set[str]] = {"default"}

    @staticmethod
    def _contexto(*, estado, es_miembro=True, superadmin=False):
        pila = ExitStack()
        pila.enter_context(
            patch("apps.rbac.services.is_superadmin", return_value=superadmin)
        )
        membresia = pila.enter_context(patch("apps.rbac.services.UserTenant.objects.filter"))
        membresia.return_value.exists.return_value = es_miembro
        empresas = pila.enter_context(patch("apps.rbac.services.Tenant.objects.filter"))
        empresas.return_value.values_list.return_value.first.return_value = estado
        return pila

    def test_an_active_company_operates(self):
        with self._contexto(estado=Tenant.Status.ACTIVE):
            rbac_services.require_tenant_access(MagicMock(), COMPANY_ID)

    def test_a_non_active_company_is_blocked(self):
        for estado in (Tenant.Status.PENDING, Tenant.Status.SUSPENDED, Tenant.Status.INACTIVE):
            with self.subTest(estado=estado):
                with self._contexto(estado=estado):
                    with self.assertRaises(PermissionDenied) as caso:
                        rbac_services.require_tenant_access(MagicMock(), COMPANY_ID)

                detalle = caso.exception.detail
                self.assertEqual(str(detalle["empresa_estado"]), estado)
                self.assertEqual(str(detalle["codigo"]), "EMPRESA_NO_OPERATIVA")

    def test_the_block_explains_itself_without_leaking_internals(self):
        with self._contexto(estado=Tenant.Status.SUSPENDED):
            with self.assertRaises(PermissionDenied) as caso:
                rbac_services.require_tenant_access(MagicMock(), COMPANY_ID)

        mensaje = str(caso.exception.detail["detail"])
        self.assertIn("suspendida", mensaje.lower())

    def test_a_superadmin_passes_whatever_the_state(self):
        """Administrar una empresa suspendida es parte de su trabajo."""
        for estado in TODOS:
            with self.subTest(estado=estado):
                with self._contexto(estado=estado, superadmin=True, es_miembro=False):
                    rbac_services.require_tenant_access(MagicMock(), COMPANY_ID)

    def test_membership_is_checked_before_the_state(self):
        """A quien no pertenece no se le cuenta en qué estado está la empresa."""
        with self._contexto(estado=Tenant.Status.ACTIVE, es_miembro=False):
            with self.assertRaises(PermissionDenied) as caso:
                rbac_services.require_tenant_access(MagicMock(), COMPANY_ID)

        self.assertNotIn("empresa_estado", str(caso.exception.detail))

    def test_a_missing_company_does_not_reveal_itself(self):
        with self._contexto(estado=None):
            with self.assertRaises(PermissionDenied) as caso:
                rbac_services.require_tenant_access(MagicMock(), COMPANY_ID)

        self.assertNotIn("empresa_estado", str(caso.exception.detail))

    def test_membership_only_does_not_look_at_the_state(self):
        """La lectura que permite enterarse del bloqueo no puede bloquearse."""
        for estado in TODOS:
            with self.subTest(estado=estado):
                with self._contexto(estado=estado):
                    rbac_services.require_tenant_membership(MagicMock(), COMPANY_ID)


class MultiTenantUserTests(SimpleTestCase):
    """Una empresa suspendida no arrastra a las demás."""

    databases: ClassVar[set[str]] = {"default"}

    def test_the_user_operates_in_the_active_one_and_not_in_the_suspended_one(self):
        estados = {COMPANY_ID: Tenant.Status.SUSPENDED, OTHER_COMPANY_ID: Tenant.Status.ACTIVE}

        def estado_de(pk):
            consulta = MagicMock()
            consulta.values_list.return_value.first.return_value = estados[pk]
            return consulta

        with patch("apps.rbac.services.is_superadmin", return_value=False), patch(
            "apps.rbac.services.UserTenant.objects.filter"
        ) as membresia, patch(
            "apps.rbac.services.Tenant.objects.filter", side_effect=lambda pk: estado_de(pk)
        ):
            membresia.return_value.exists.return_value = True
            usuario = MagicMock()

            # La activa funciona.
            rbac_services.require_tenant_access(usuario, OTHER_COMPANY_ID)

            # La suspendida no, y el error nombra solo a esa.
            with self.assertRaises(PermissionDenied) as caso:
                rbac_services.require_tenant_access(usuario, COMPANY_ID)

        self.assertEqual(str(caso.exception.detail["empresa_estado"]), Tenant.Status.SUSPENDED)


class ReadsThatSurviveTheBlockTests(SimpleTestCase):
    """Los dos consumidores que a propósito no se bloquean."""

    databases: ClassVar[set[str]] = {"default"}

    def test_the_strict_guard_is_not_even_reachable_from_tenancy(self):
        """La garantía más fuerte: el nombre estricto no está importado ahí.

        ``tenancy.services`` solo conoce ``require_tenant_membership``, así que
        ninguna de sus funciones puede bloquear por estado por descuido.
        """
        self.assertFalse(hasattr(tenancy_services, "require_tenant_access"))
        self.assertTrue(hasattr(tenancy_services, "require_tenant_membership"))

    def test_the_company_record_can_be_read_while_suspended(self):
        """Sin esto, su propietario no podría ver en qué estado quedó."""
        company = empresa(status=Tenant.Status.SUSPENDED)
        with patch("apps.tenancy.services.Tenant.objects.filter") as filtro, patch(
            "apps.tenancy.services.has_company_read_access", return_value=False
        ), patch("apps.tenancy.services.require_tenant_membership") as membresia:
            filtro.return_value.first.return_value = company
            resultado = tenancy_services.get_company(actor=MagicMock(), company_id=COMPANY_ID)

        self.assertEqual(resultado.status, Tenant.Status.SUSPENDED)
        membresia.assert_called_once()

    def test_the_subscription_can_be_read_while_suspended(self):
        with patch("apps.tenancy.services.has_permission", return_value=False), patch(
            "apps.tenancy.services.has_company_read_access", return_value=False
        ), patch("apps.tenancy.services.require_tenant_membership") as membresia, patch(
            "apps.tenancy.services.Subscription.objects.select_related"
        ) as consulta:
            consulta.return_value.filter.return_value.first.return_value = None
            tenancy_services.get_company_subscription(actor=MagicMock(), company_id=COMPANY_ID)

        membresia.assert_called_once()

    def test_a_platform_reader_needs_no_membership(self):
        with patch("apps.tenancy.services.Tenant.objects.filter") as filtro, patch(
            "apps.tenancy.services.has_company_read_access", return_value=True
        ), patch("apps.tenancy.services.require_tenant_membership") as membresia:
            filtro.return_value.first.return_value = empresa()
            tenancy_services.get_company(actor=MagicMock(), company_id=COMPANY_ID)

        membresia.assert_not_called()


# ---------------------------------------------------------------------------
# C. Permisos de plataforma
# ---------------------------------------------------------------------------


class PlatformPermissionTests(SimpleTestCase):
    """SUPER_ADMIN, los tres permisos globales, y el TENANT_ADMIN sin ninguno."""

    databases: ClassVar[set[str]] = {"default"}

    GUARDIAS = (
        ("TENANTS_GESTIONAR", tenancy_services.require_company_management),
        ("SUSCRIPCIONES_GESTIONAR", tenancy_services.require_subscription_management),
    )

    def test_a_superadmin_passes_every_guard(self):
        with patch("apps.tenancy.services.is_superadmin", return_value=True), patch(
            "apps.tenancy.services.has_permission"
        ) as permiso:
            for codigo, guardia in self.GUARDIAS:
                with self.subTest(permiso=codigo):
                    guardia(MagicMock())
            self.assertTrue(tenancy_services.has_company_read_access(MagicMock()))

        # No hace falta consultar permisos: ser SUPER_ADMIN basta.
        permiso.assert_not_called()

    def test_each_global_permission_opens_its_own_guard(self):
        for codigo, guardia in self.GUARDIAS:
            with self.subTest(permiso=codigo):
                with patch("apps.tenancy.services.is_superadmin", return_value=False), patch(
                    "apps.tenancy.services.has_permission", return_value=True
                ) as permiso:
                    guardia(MagicMock())

                self.assertEqual(permiso.call_args.args[1], codigo)
                # tenant_id None: solo cuenta un rol global.
                self.assertIsNone(permiso.call_args.args[2])

    def test_tenants_leer_opens_the_company_registry(self):
        with patch("apps.tenancy.services.is_superadmin", return_value=False), patch(
            "apps.tenancy.services.has_permission", return_value=True
        ) as permiso:
            self.assertTrue(tenancy_services.has_company_read_access(MagicMock()))

        self.assertEqual(permiso.call_args.args[1], "TENANTS_LEER")
        self.assertIsNone(permiso.call_args.args[2])

    def test_tenants_gestionar_also_opens_the_company_registry(self):
        """Administrar implica poder localizar y leer la empresa administrada."""
        def tiene_permiso(_actor, codigo, tenant_id):
            self.assertIsNone(tenant_id)
            return codigo == "TENANTS_GESTIONAR"

        with patch("apps.tenancy.services.is_superadmin", return_value=False), patch(
            "apps.tenancy.services.has_permission", side_effect=tiene_permiso
        ):
            self.assertTrue(tenancy_services.has_company_read_access(MagicMock()))

    def test_a_tenant_admin_without_global_permissions_is_rejected(self):
        """Nunca administración global, por mucho rol que tenga en su empresa."""
        with patch("apps.tenancy.services.is_superadmin", return_value=False), patch(
            "apps.tenancy.services.has_permission", return_value=False
        ):
            for codigo, guardia in self.GUARDIAS:
                with self.subTest(permiso=codigo):
                    with self.assertRaises(PermissionDenied):
                        guardia(MagicMock())
            self.assertFalse(tenancy_services.has_company_read_access(MagicMock()))

    def test_the_three_codes_cannot_be_granted_to_a_company_role(self):
        """La otra mitad del aislamiento, ya existente: se verifica que siga."""
        self.assertTrue(
            {"TENANTS_LEER", "TENANTS_GESTIONAR", "SUSCRIPCIONES_GESTIONAR"}
            <= rbac_services.FORBIDDEN_TENANT_PERMISSIONS
        )


class CompanyIsolationTests(SimpleTestCase):
    """Sin permiso de plataforma, el padrón se acota a las empresas propias."""

    databases: ClassVar[set[str]] = {"default"}

    def _listar(self, *, con_permiso):
        with patch(
            "apps.tenancy.services.has_company_read_access", return_value=con_permiso
        ), patch("apps.tenancy.services.Tenant.objects.all") as todas, patch(
            "apps.tenancy.services.UserTenant.objects.filter"
        ) as membresias:
            membresias.return_value.values_list.return_value = [COMPANY_ID]
            tenancy_services.list_companies(actor=MagicMock())
            return todas.return_value

    def test_a_platform_reader_sees_every_company(self):
        queryset = self._listar(con_permiso=True)

        queryset.filter.assert_not_called()

    def test_anyone_else_sees_only_their_own(self):
        queryset = self._listar(con_permiso=False)

        self.assertEqual(queryset.filter.call_args.kwargs["id__in"], [COMPANY_ID])

    def test_the_filter_uses_only_active_memberships(self):
        with patch("apps.tenancy.services.has_company_read_access", return_value=False), patch(
            "apps.tenancy.services.Tenant.objects.all"
        ), patch("apps.tenancy.services.UserTenant.objects.filter") as membresias:
            membresias.return_value.values_list.return_value = []
            tenancy_services.list_companies(actor=MagicMock())

        self.assertEqual(membresias.call_args.kwargs["status"], "ACTIVO")


class SubscriptionChangeAuthorizationTests(SimpleTestCase):
    """El cambio de plan ya no depende de leer la suscripción anterior."""

    databases: ClassVar[set[str]] = {"default"}

    def _cambiar(self, **patches):
        pila = ExitStack()
        pila.enter_context(patch("apps.tenancy.services.record_audit"))
        filtro = pila.enter_context(patch("apps.tenancy.services.Tenant.objects.filter"))
        filtro.return_value.first.return_value = patches.get(
            "company", empresa(status=Tenant.Status.ACTIVE)
        )
        pila.enter_context(
            patch("apps.tenancy.services._resolve_plan", return_value=Plan(id=1, code="PRO"))
        )
        pila.enter_context(
            patch("apps.tenancy.services._open_subscription", return_value=Subscription(id=2))
        )
        consulta = pila.enter_context(
            patch("apps.tenancy.services.Subscription.objects.select_related")
        )
        consulta.return_value.filter.return_value.first.return_value = None
        return pila

    def test_a_global_operator_without_membership_can_change_the_plan(self):
        """Antes esto era imposible: caía en el chequeo de pertenencia."""
        with self._cambiar(), patch(
            "apps.tenancy.services.is_superadmin", return_value=False
        ), patch("apps.tenancy.services.has_permission", return_value=True), patch(
            "apps.rbac.services.require_tenant_membership"
        ) as membresia, patch("apps.rbac.services.require_tenant_access") as estricto:
            tenancy_services.change_company_subscription(
                actor=MagicMock(), company_id=COMPANY_ID, plan_codigo="PRO"
            )

        membresia.assert_not_called()
        estricto.assert_not_called()

    def test_without_the_global_permission_it_is_rejected(self):
        with self._cambiar(), patch(
            "apps.tenancy.services.is_superadmin", return_value=False
        ), patch("apps.tenancy.services.has_permission", return_value=False):
            with self.assertRaises(PermissionDenied):
                tenancy_services.change_company_subscription(
                    actor=MagicMock(), company_id=COMPANY_ID, plan_codigo="PRO"
                )

    def test_a_missing_company_is_a_404(self):
        with self._cambiar(company=None), patch(
            "apps.tenancy.services.is_superadmin", return_value=True
        ):
            with self.assertRaises(NotFound):
                tenancy_services.change_company_subscription(
                    actor=MagicMock(), company_id=999, plan_codigo="PRO"
                )

    def test_authorization_runs_before_looking_for_the_company(self):
        """Quien no puede administrar no averigua si la empresa existe."""
        with patch("apps.tenancy.services.is_superadmin", return_value=False), patch(
            "apps.tenancy.services.has_permission", return_value=False
        ), patch("apps.tenancy.services.Tenant.objects.filter") as filtro:
            with self.assertRaises(PermissionDenied):
                tenancy_services.change_company_subscription(
                    actor=MagicMock(), company_id=COMPANY_ID, plan_codigo="PRO"
                )

        filtro.assert_not_called()


# ---------------------------------------------------------------------------
# Autoregistro publico
# ---------------------------------------------------------------------------


class SelfSignupTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    def test_a_self_registered_company_is_born_pending(self):
        """Nadie de la plataforma la revisó todavía."""
        creadas = []

        def crear(**kwargs):
            creadas.append(kwargs)
            return empresa(status=kwargs["status"])

        with patch("apps.tenancy.services.Tenant.objects.filter") as filtro, patch(
            "apps.tenancy.services.Tenant.objects.create", side_effect=crear
        ), patch("apps.tenancy.services._resolve_plan", return_value=Plan(id=1, code="BASICO")), patch(
            "apps.tenancy.services._assign_owner", return_value=MagicMock(id=4)
        ), patch(
            "apps.tenancy.services._open_subscription", return_value=Subscription(id=1)
        ), patch("apps.tenancy.services.record_audit") as audit, patch(
            "apps.tenancy.services._unique_subdomain", return_value="toursbo"
        ):
            filtro.return_value.exists.return_value = False
            company, _ = tenancy_services.self_signup_company(
                razon_social="ToursBo SRL",
                nombre_comercial="ToursBo",
                propietario={"email": "a@b.com", "nombres": "A", "apellidos": "B"},
                plan_codigo="BASICO",
            )

        self.assertEqual(creadas[0]["status"], Tenant.Status.PENDING)
        self.assertEqual(company.status, Tenant.Status.PENDING)
        self.assertEqual(audit.call_args.kwargs["new_data"]["estado"], Tenant.Status.PENDING)

    def test_the_administrative_creation_stays_active(self):
        """Ahí sí hay un SUPER_ADMIN que responde por la empresa."""
        creadas = []

        with patch("apps.tenancy.services.Tenant.objects.filter") as filtro, patch(
            "apps.tenancy.services.Tenant.objects.create",
            side_effect=lambda **kw: creadas.append(kw) or empresa(status=kw["status"]),
        ), patch("apps.tenancy.services.require_company_management"), patch(
            "apps.tenancy.services._resolve_plan", return_value=Plan(id=1, code="BASICO")
        ), patch("apps.tenancy.services._assign_owner", return_value=MagicMock(id=4)), patch(
            "apps.tenancy.services._open_subscription"
        ), patch("apps.tenancy.services.record_audit"), patch(
            "apps.tenancy.services._unique_subdomain", return_value="toursbo"
        ):
            filtro.return_value.exists.return_value = False
            tenancy_services.create_company(
                actor=MagicMock(),
                razon_social="ToursBo SRL",
                nombre_comercial="ToursBo",
                propietario={"email": "a@b.com", "nombres": "A", "apellidos": "B"},
            )

        self.assertEqual(creadas[0]["status"], Tenant.Status.ACTIVE)


@override_settings(REST_FRAMEWORK={"DEFAULT_THROTTLE_RATES": {"autoregistro": "3/hour"}})
class SelfSignupThrottleTests(SimpleTestCase):
    """Tope por IP: es el único endpoint anónimo que crea una empresa."""

    databases: ClassVar[set[str]] = {"default"}

    def setUp(self):
        # `override_settings` no alcanza: DRF copia DEFAULT_THROTTLE_RATES a
        # SimpleRateThrottle.THROTTLE_RATES al importar la clase.
        tasa = patch.dict(SelfSignupThrottle.THROTTLE_RATES, {"autoregistro": "3/hour"})
        tasa.start()
        self.addCleanup(tasa.stop)
        cache.clear()
        self.addCleanup(cache.clear)

    def _signup(self, ip="203.0.113.7", *, authenticated=False):
        request = APIRequestFactory().post(
            "/api/v1/empresas/autoregistro/",
            {
                "razon_social": "ToursBo SRL",
                "nombre_comercial": "ToursBo",
                "plan_codigo": "BASICO",
                "propietario": {
                    "email": "a@b.com",
                    "nombres": "A",
                    "apellidos": "B",
                    "password": "ContraseñaLarga123",
                },
            },
            format="json",
            REMOTE_ADDR=ip,
        )
        if authenticated:
            force_authenticate(
                request,
                user=MagicMock(pk=91, is_authenticated=True),
            )
        with patch(
            "apps.tenancy.views.self_signup_company",
            return_value=(empresa(status=Tenant.Status.PENDING), Subscription(id=1)),
        ), patch("apps.tenancy.serializers.Plan.objects.filter") as plan, patch(
            "apps.tenancy.serializers.User.objects.filter"
        ) as user, patch("apps.tenancy.views.CompanySerializer") as company_serializer, patch(
            "apps.tenancy.views.SubscriptionSerializer"
        ) as subscription_serializer:
            plan.return_value.exists.return_value = True
            user.return_value.first.return_value = None
            company_serializer.return_value.data = {}
            subscription_serializer.return_value.data = {}
            return CompanySignupView.as_view()(request)

    def test_the_fourth_signup_from_the_same_ip_is_a_429(self):
        for intento in range(3):
            self.assertEqual(self._signup().status_code, 201, f"intento {intento}")

        self.assertEqual(self._signup().status_code, 429)

    def test_the_limit_is_per_ip(self):
        for _ in range(3):
            self._signup(ip="203.0.113.7")

        self.assertEqual(self._signup(ip="198.51.100.4").status_code, 201)

    def test_authentication_does_not_bypass_the_ip_limit(self):
        for _ in range(3):
            self.assertEqual(self._signup(authenticated=True).status_code, 201)

        self.assertEqual(self._signup(authenticated=True).status_code, 429)

    def test_a_throttled_signup_creates_nothing(self):
        for _ in range(3):
            self._signup()

        with patch("apps.tenancy.views.self_signup_company") as servicio:
            request = APIRequestFactory().post(
                "/api/v1/empresas/autoregistro/", {}, format="json", REMOTE_ADDR="203.0.113.7"
            )
            response = CompanySignupView.as_view()(request)

        self.assertEqual(response.status_code, 429)
        servicio.assert_not_called()
