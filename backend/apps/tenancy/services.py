from datetime import date

from django.db import transaction
from django.db.models import Q
from django.utils.text import slugify
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.audit.services import record_audit
from apps.rbac.models import Role, UserRole
from apps.rbac.services import (
    has_permission,
    is_superadmin,
    require_tenant_membership,
)

from .models import (
    TENANT_STATUS_TRANSITIONS,
    Plan,
    Subscription,
    Tenant,
    UserTenant,
)

DEFAULT_PLAN_CODE = "BASICO"


def _require_platform_permission(actor, code: str, message: str) -> None:
    """Exige un permiso de plataforma, no de empresa.

    ``has_permission`` con ``tenant_id=None`` solo mira asignaciones de rol sin
    tenant, es decir globales, y ``FORBIDDEN_TENANT_PERMISSIONS`` impide que
    estos tres codigos se asignen a un rol de empresa. Las dos cosas juntas son
    lo que garantiza que un administrador empresarial no pueda llegar aqui por
    mucho rol que tenga dentro de su tenant.
    """
    if is_superadmin(actor):
        return
    if not has_permission(actor, code, None):
        raise PermissionDenied(message)


def require_company_management(actor) -> None:
    """Crear, editar, cambiar estado y propietario. SUPER_ADMIN o TENANTS_GESTIONAR global.

    Antes exigia SUPER_ADMIN y nada mas, asi que ``TENANTS_GESTIONAR`` existia
    sembrado y no se verificaba en ningun sitio: un operador de plataforma con
    ese permiso no podia administrar nada. Ahora el permiso significa lo que
    dice su nombre.
    """
    _require_platform_permission(
        actor,
        "TENANTS_GESTIONAR",
        "No cuenta con permisos de plataforma para administrar empresas.",
    )


def has_company_read_access(actor) -> bool:
    """Permite consultar el padrón completo de empresas.

    No lanza excepcion porque no tenerlo no es un error: el listado y la ficha
    lo usan para decidir entre "ve todas las empresas" y "ve solo las suyas",
    que son dos vistas legitimas del mismo endpoint. Quien no lo tiene recibe
    las propias, no un 403. ``TENANTS_GESTIONAR`` implica lectura: un operador
    no podría administrar una empresa que el mismo endpoint le oculta.
    """
    return (
        is_superadmin(actor)
        or has_permission(actor, "TENANTS_LEER", None)
        or has_permission(actor, "TENANTS_GESTIONAR", None)
    )


def _unique_subdomain(trade_name: str, requested: str = "") -> str:
    base = slugify(requested or trade_name).lower()[:63].strip("-")
    if len(base) < 3:
        base = f"{base}-empresa"[:63].strip("-")
    candidate = base
    suffix = 2
    while Tenant.objects.filter(subdomain__iexact=candidate).exists():
        ending = f"-{suffix}"
        candidate = f"{base[: 63 - len(ending)].rstrip('-')}{ending}"
        suffix += 1
    return candidate


def list_companies(*, actor, search: str = "", status: str = ""):
    """Padron completo para la plataforma; solo las propias para el resto.

    No es un error que un administrador empresarial consulte este endpoint: le
    devuelve las empresas a las que pertenece, incluidas las suspendidas, que es
    como se enterara de que lo estan. La administracion global requiere
    ``TENANTS_LEER``, que un rol de empresa no puede tener.
    """
    queryset = Tenant.objects.all()
    if not has_company_read_access(actor):
        tenant_ids = UserTenant.objects.filter(
            user=actor, status=UserTenant.Status.ACTIVE
        ).values_list("tenant_id", flat=True)
        queryset = queryset.filter(id__in=tenant_ids)
    if search:
        queryset = queryset.filter(
            Q(trade_name__icontains=search)
            | Q(legal_name__icontains=search)
            | Q(tax_id__icontains=search)
        )
    if status:
        queryset = queryset.filter(status=status)
    return queryset.order_by("trade_name")


def get_company(*, actor, company_id: int) -> Tenant:
    """Ficha de una empresa.

    Usa ``require_tenant_membership`` y no ``require_tenant_access`` a
    proposito: si una empresa suspendida no se pudiera leer, su propietario no
    tendria forma de ver en que estado quedo ni por que no puede trabajar. Leer
    la ficha no es operar dentro de la empresa.
    """
    company = Tenant.objects.filter(pk=company_id).first()
    if company is None:
        raise NotFound("Empresa no encontrada.")
    if not has_company_read_access(actor):
        require_tenant_membership(actor, company.id)
    return company


def _tenant_admin_role() -> Role:
    role = Role.objects.filter(
        code="TENANT_ADMIN", scope=Role.Scope.TENANT, tenant__isnull=True
    ).first()
    if role is None:
        raise ValidationError(
            {"propietario": "No existe el rol base de Propietario. Ejecute los datos semilla."}
        )
    return role


def _resolve_owner(owner_data: dict) -> User:
    email = owner_data["email"].strip().lower()
    user = User.objects.filter(email__iexact=email).first()
    if user is not None:
        if not user.is_active:
            raise ValidationError(
                {"propietario": {"email": "La cuenta existente no está activa."}}
            )
        return user

    password = owner_data.get("password")
    if not password:
        raise ValidationError(
            {"propietario": {"password": "Debe indicar una contraseña temporal."}}
        )
    return User.objects.create_user(
        email=email,
        password=password,
        first_names=owner_data["nombres"].strip(),
        last_names=owner_data["apellidos"].strip(),
        phone=owner_data.get("telefono", "").strip() or None,
        status=User.Status.ACTIVE,
    )


def _assign_owner(*, company: Tenant, owner_data: dict) -> User:
    role = _tenant_admin_role()
    owner = _resolve_owner(owner_data)

    previous_assignments = UserRole.objects.filter(
        tenant=company,
        role__code="TENANT_ADMIN",
        role__scope=Role.Scope.TENANT,
    )
    previous_owner_ids = list(previous_assignments.values_list("user_id", flat=True))
    previous_assignments.exclude(user=owner).delete()

    membership, _ = UserTenant.objects.get_or_create(
        user=owner,
        tenant=company,
        defaults={"status": UserTenant.Status.ACTIVE},
    )
    if membership.status != UserTenant.Status.ACTIVE:
        membership.status = UserTenant.Status.ACTIVE
        membership.save(update_fields=("status",))
    UserRole.objects.get_or_create(user=owner, role=role, tenant=company)

    for previous_owner_id in previous_owner_ids:
        if previous_owner_id == owner.id:
            continue
        has_other_role = UserRole.objects.filter(
            user_id=previous_owner_id, tenant=company
        ).exists()
        if not has_other_role:
            UserTenant.objects.filter(
                user_id=previous_owner_id, tenant=company
            ).update(status=UserTenant.Status.INACTIVE)
    return owner


@transaction.atomic
def create_company(
    *,
    actor,
    razon_social: str,
    nombre_comercial: str,
    propietario: dict,
    ciudad_id: int | None = None,
    subdominio: str = "",
    nit: str = "",
    email_contacto: str = "",
    telefono: str = "",
    plan_codigo: str = DEFAULT_PLAN_CODE,
    request=None,
) -> Tenant:
    require_company_management(actor)
    tax_id = nit.strip() or None
    if tax_id and Tenant.objects.filter(tax_id__iexact=tax_id).exists():
        raise ValidationError({"nit": "Ya existe una empresa con este NIT."})
    plan = _resolve_plan(plan_codigo)

    company = Tenant.objects.create(
        legal_name=razon_social.strip(),
        trade_name=nombre_comercial.strip(),
        city_id=ciudad_id,
        subdomain=_unique_subdomain(nombre_comercial, subdominio),
        tax_id=tax_id,
        contact_email=email_contacto.strip().lower() or None,
        phone=telefono.strip() or None,
        status=Tenant.Status.ACTIVE,
    )
    owner = _assign_owner(company=company, owner_data=propietario)
    _open_subscription(tenant=company, plan=plan)
    record_audit(
        actor=actor,
        tenant_id=company.id,
        action="CREAR",
        entity="empresa",
        entity_id=str(company.id),
        new_data={
            "nombre_comercial": company.trade_name,
            "razon_social": company.legal_name,
            "propietario_id": owner.id,
            "plan": plan.code,
        },
        request=request,
    )
    return company


@transaction.atomic
def self_signup_company(
    *,
    razon_social: str,
    nombre_comercial: str,
    propietario: dict,
    plan_codigo: str,
    ciudad_id: int | None = None,
    subdominio: str = "",
    nit: str = "",
    email_contacto: str = "",
    telefono: str = "",
    request=None,
) -> Tenant:
    """Autoregistro público: una empresa se da de alta sola eligiendo un plan, sin
    intervención del SuperAdministrador (usado por la vitrina pública de planes).

    Nace PENDIENTE, no ACTIVO. Es la diferencia de fondo con el alta
    administrativa: ahi un SUPER_ADMIN responde por la empresa, aqui no hay
    nadie que la haya revisado. Hasta que la plataforma la active, su gente
    puede autenticarse y ver su perfil pero no operar, y su oferta no aparece en
    el Marketplace -- que ya filtra por ``tenant.status``.
    """
    tax_id = nit.strip() or None
    if tax_id and Tenant.objects.filter(tax_id__iexact=tax_id).exists():
        raise ValidationError({"nit": "Ya existe una empresa con este NIT."})
    plan = _resolve_plan(plan_codigo)

    company = Tenant.objects.create(
        legal_name=razon_social.strip(),
        trade_name=nombre_comercial.strip(),
        city_id=ciudad_id,
        subdomain=_unique_subdomain(nombre_comercial, subdominio),
        tax_id=tax_id,
        contact_email=email_contacto.strip().lower() or None,
        phone=telefono.strip() or None,
        status=Tenant.Status.PENDING,
    )
    owner = _assign_owner(company=company, owner_data=propietario)
    subscription = _open_subscription(tenant=company, plan=plan)
    record_audit(
        actor=owner,
        tenant_id=company.id,
        action="AUTOREGISTRO",
        entity="empresa",
        entity_id=str(company.id),
        new_data={
            "nombre_comercial": company.trade_name,
            "razon_social": company.legal_name,
            "propietario_id": owner.id,
            "plan": plan.code,
            "estado": company.status,
        },
        request=request,
    )
    return company, subscription


@transaction.atomic
def update_company(*, actor, company_id: int, request=None, **changes) -> Tenant:
    require_company_management(actor)
    company = Tenant.objects.filter(pk=company_id).first()
    if company is None:
        raise NotFound("Empresa no encontrada.")

    # El estado no se escribe aqui. Si llega en el cuerpo se delega en la
    # maquina de transiciones, que valida la transicion, exige los requisitos de
    # activacion y audita como CAMBIAR_ESTADO. Se acepta por compatibilidad con
    # el cliente actual; la via propia es POST /empresas/{id}/estado/.
    nuevo_estado = changes.pop("estado", None)

    previous_data = {
        "razon_social": company.legal_name,
        "nombre_comercial": company.trade_name,
        "estado": company.status,
    }
    field_mapping = {
        "razon_social": "legal_name",
        "nombre_comercial": "trade_name",
        "ciudad_id": "city_id",
        "nit": "tax_id",
        "email_contacto": "contact_email",
        "telefono": "phone",
    }
    update_fields = []
    for api_field, model_field in field_mapping.items():
        if api_field not in changes:
            continue
        value = changes[api_field]
        if api_field in {"nit", "email_contacto", "telefono"}:
            value = value.strip() or None
        if api_field == "email_contacto" and value:
            value = value.lower()
        setattr(company, model_field, value)
        update_fields.append(model_field)

    if "tax_id" in update_fields and company.tax_id:
        if Tenant.objects.exclude(pk=company.id).filter(tax_id__iexact=company.tax_id).exists():
            raise ValidationError({"nit": "Ya existe una empresa con este NIT."})

    if update_fields:
        update_fields.append("updated_at")
        company.save(update_fields=update_fields)
        record_audit(
            actor=actor,
            tenant_id=company.id,
            action="ACTUALIZAR",
            entity="empresa",
            entity_id=str(company.id),
            previous_data=previous_data,
            new_data=changes,
            request=request,
        )

    if nuevo_estado is not None:
        _apply_status_change(
            actor=actor, company=company, nuevo_estado=nuevo_estado, request=request
        )
    return company


def _company_owner_id(company: Tenant) -> int | None:
    return (
        UserRole.objects.filter(
            tenant=company, role__code="TENANT_ADMIN", role__scope=Role.Scope.TENANT
        )
        .values_list("user_id", flat=True)
        .first()
    )


def _check_activation_requirements(company: Tenant) -> None:
    """Una empresa no se activa a medias.

    Activar sin estas tres cosas publica una empresa que no puede operar: sin
    propietario nadie la administra, y sin suscripcion vigente de un plan activo
    no hay condiciones contratadas contra las que medir nada. Los tres errores
    se informan juntos para no obligar a descubrirlos de uno en uno.
    """
    problems = {}
    if _company_owner_id(company) is None:
        problems["propietario"] = "La empresa no tiene propietario asignado."

    subscription = (
        Subscription.objects.select_related("plan")
        .filter(tenant=company, status=Subscription.Status.ACTIVE)
        .first()
    )
    if subscription is None:
        problems["suscripcion"] = "La empresa no tiene una suscripción activa."
    elif not subscription.plan.active:
        problems["plan"] = (
            f"El plan {subscription.plan.name} ya no está disponible. "
            "Asigna un plan vigente antes de activar la empresa."
        )

    if problems:
        raise ValidationError(problems)


def _apply_status_change(*, actor, company: Tenant, nuevo_estado: str, request=None) -> Tenant:
    """Aplica una transicion validada y la audita como CAMBIAR_ESTADO.

    Vive aparte de ``update_company`` porque cambiar de estado no es editar un
    campo: tiene reglas propias, requisitos propios y una accion de bitacora
    propia. Cualquier via que cambie el estado pasa por aqui.
    """
    actual = company.status
    if nuevo_estado == actual:
        # No es un error: pedir lo que ya es cierto no cambia nada y no deja
        # una entrada de bitacora que mentiria sobre una transicion.
        return company

    permitidas = TENANT_STATUS_TRANSITIONS.get(actual, frozenset())
    if nuevo_estado not in permitidas:
        raise ValidationError(
            {
                "estado": (
                    f"No se puede pasar de {actual} a {nuevo_estado}. "
                    f"Desde {actual} solo se admite: {', '.join(sorted(permitidas)) or 'ningún estado'}."
                )
            }
        )

    if nuevo_estado == Tenant.Status.ACTIVE:
        _check_activation_requirements(company)

    company.status = nuevo_estado
    company.save(update_fields=("status", "updated_at"))
    record_audit(
        actor=actor,
        tenant_id=company.id,
        action="CAMBIAR_ESTADO",
        entity="empresa",
        entity_id=str(company.id),
        previous_data={"estado": actual},
        new_data={"estado": nuevo_estado},
        request=request,
    )
    return company


@transaction.atomic
def change_company_status(*, actor, company_id: int, estado: str, request=None) -> Tenant:
    """Punto de entrada del cambio de estado."""
    require_company_management(actor)
    company = Tenant.objects.filter(pk=company_id).first()
    if company is None:
        raise NotFound("Empresa no encontrada.")
    return _apply_status_change(
        actor=actor, company=company, nuevo_estado=estado, request=request
    )


@transaction.atomic
def assign_company_owner(
    *, actor, company_id: int, propietario: dict, request=None
) -> Tenant:
    require_company_management(actor)
    company = Tenant.objects.filter(pk=company_id).first()
    if company is None:
        raise NotFound("Empresa no encontrada.")
    previous_owner_id = (
        UserRole.objects.filter(
            tenant=company, role__code="TENANT_ADMIN", role__scope=Role.Scope.TENANT
        )
        .values_list("user_id", flat=True)
        .first()
    )
    owner = _assign_owner(company=company, owner_data=propietario)
    record_audit(
        actor=actor,
        tenant_id=company.id,
        action="ASIGNAR_PROPIETARIO",
        entity="empresa",
        entity_id=str(company.id),
        previous_data={"propietario_id": previous_owner_id},
        new_data={"propietario_id": owner.id},
        request=request,
    )
    return company


# ---------------------------------------------------------------------------
# Planes y suscripciones
# ---------------------------------------------------------------------------


def list_plans():
    # prefetch de los limites: sin esto, serializar N planes dispara N consultas
    # de plan_limite, una por plan.
    return (
        Plan.objects.filter(active=True)
        .select_related("currency")
        .prefetch_related("limits")
    )


def _resolve_plan(plan_codigo: str) -> Plan:
    plan = Plan.objects.filter(code__iexact=plan_codigo, active=True).first()
    if plan is None:
        raise ValidationError({"plan_codigo": "El plan seleccionado no existe o no está disponible."})
    return plan


def _open_subscription(*, tenant: Tenant, plan: Plan, auto_renew: bool = False) -> Subscription:
    """Abre una suscripcion congelando las condiciones vigentes del plan.

    Las tres condiciones viajan en el mismo INSERT que la fila, no en un UPDATE
    posterior: una suscripcion no puede existir ni un instante sin saber que se
    acepto pagar. El backfill de la migracion 0004 solo cubre las filas
    anteriores; de aqui en adelante toda contratacion, cambio de plan y
    renovacion copia el precio del momento.

    Cambiar despues ``plan.price`` no alcanza a esta fila: son columnas de
    tablas distintas y nada las vuelve a derivar.
    """
    Subscription.objects.filter(tenant=tenant, status=Subscription.Status.ACTIVE).update(
        status=Subscription.Status.CANCELLED, end_date=date.today()
    )
    return Subscription.objects.create(
        tenant=tenant,
        plan=plan,
        start_date=date.today(),
        status=Subscription.Status.ACTIVE,
        auto_renew=auto_renew,
        contracted_price=plan.price,
        # Por id para no disparar una consulta de moneda al crear.
        contracted_currency_id=plan.currency_id,
        contracted_periodicity=plan.periodicity,
    )


def get_company_subscription(*, actor, company_id: int) -> Subscription | None:
    """Suscripcion activa de una empresa.

    Tres caminos la autorizan: permiso global de suscripciones, permiso global
    de lectura de empresas, o pertenecer a la empresa. El ultimo usa
    ``require_tenant_membership`` y no ``require_tenant_access`` para que el
    propietario de una empresa suspendida pueda seguir viendo que plan tiene
    contratado.
    """
    if not (
        has_permission(actor, "SUSCRIPCIONES_GESTIONAR", None) or has_company_read_access(actor)
    ):
        require_tenant_membership(actor, company_id)
    return (
        Subscription.objects.select_related("plan", "plan__currency")
        .filter(tenant_id=company_id, status=Subscription.Status.ACTIVE)
        .first()
    )


def get_subscription_usage(*, tenant_id: int) -> dict:
    from apps.catalog.models import TourismProduct

    return {
        "usuarios": UserTenant.objects.filter(
            tenant_id=tenant_id, status=UserTenant.Status.ACTIVE
        ).count(),
        "productos": TourismProduct.objects.filter(tenant_id=tenant_id).count(),
    }


def require_subscription_management(actor) -> None:
    """SUPER_ADMIN o SUSCRIPCIONES_GESTIONAR global.

    No exige pertenecer a la empresa: un operador de plataforma administra
    suscripciones de empresas de las que no es miembro, que es justamente su
    trabajo. Antes el aislamiento de este camino dependia de que
    ``change_company_subscription`` consultara la suscripcion anterior, cuyo
    ``require_tenant_access`` hacia de control de acceso por efecto colateral:
    el permiso era inutilizable para cualquiera que no fuera SUPER_ADMIN, y un
    refactor que dejara de leer la suscripcion previa habria quitado la
    comprobacion sin que nada lo notara.
    """
    _require_platform_permission(
        actor,
        "SUSCRIPCIONES_GESTIONAR",
        "No cuenta con permisos de plataforma para administrar suscripciones.",
    )


@transaction.atomic
def change_company_subscription(
    *, actor, company_id: int, plan_codigo: str, auto_renew: bool = False, request=None
) -> Subscription:
    # Las tres comprobaciones son explicitas y en este orden: autorizacion de
    # plataforma, existencia de la empresa, validez del plan.
    require_subscription_management(actor)
    company = Tenant.objects.filter(pk=company_id).first()
    if company is None:
        raise NotFound("Empresa no encontrada.")
    plan = _resolve_plan(plan_codigo)
    previous = (
        Subscription.objects.select_related("plan")
        .filter(tenant_id=company_id, status=Subscription.Status.ACTIVE)
        .first()
    )
    subscription = _open_subscription(tenant=company, plan=plan, auto_renew=auto_renew)
    record_audit(
        actor=actor,
        tenant_id=company.id,
        action="CAMBIAR_PLAN",
        entity="suscripcion",
        entity_id=str(subscription.id),
        previous_data={"plan": previous.plan.code} if previous else None,
        new_data={"plan": plan.code},
        request=request,
    )
    return subscription


def _active_subscription_plan(tenant_id: int) -> Plan | None:
    subscription = (
        Subscription.objects.select_related("plan")
        .filter(tenant_id=tenant_id, status=Subscription.Status.ACTIVE)
        .first()
    )
    return subscription.plan if subscription else None


def ensure_user_quota_available(tenant_id: int) -> None:
    plan = _active_subscription_plan(tenant_id)
    if plan is None:
        return
    current = UserTenant.objects.filter(tenant_id=tenant_id, status=UserTenant.Status.ACTIVE).count()
    if current >= plan.max_users:
        raise ValidationError(
            {"plan": f"Alcanzaste el límite de {plan.max_users} usuarios del plan {plan.name}. Sube de plan para agregar más."}
        )


def ensure_product_quota_available(tenant_id: int) -> None:
    from apps.catalog.models import TourismProduct

    plan = _active_subscription_plan(tenant_id)
    if plan is None:
        return
    current = TourismProduct.objects.filter(tenant_id=tenant_id).count()
    if current >= plan.max_products:
        raise ValidationError(
            {"plan": f"Alcanzaste el límite de {plan.max_products} productos del plan {plan.name}. Sube de plan para publicar más."}
        )
