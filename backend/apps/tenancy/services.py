from datetime import date

from django.db import transaction
from django.db.models import Q
from django.utils.text import slugify
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.audit.services import record_audit
from apps.rbac.models import Role, UserRole
from apps.rbac.services import is_superadmin, require_permission, require_tenant_access

from .models import Plan, Subscription, Tenant, UserTenant

DEFAULT_PLAN_CODE = "BASICO"


def require_company_management(actor) -> None:
    if not is_superadmin(actor):
        raise PermissionDenied("Solo el SuperAdministrador puede administrar empresas.")


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
    queryset = Tenant.objects.all()
    if not is_superadmin(actor):
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
    company = Tenant.objects.filter(pk=company_id).first()
    if company is None:
        raise NotFound("Empresa no encontrada.")
    require_tenant_access(actor, company.id)
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
    intervención del SuperAdministrador (usado por la vitrina pública de planes)."""
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
        "estado": "status",
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
    return company


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
    return Plan.objects.filter(active=True).select_related("currency")


def _resolve_plan(plan_codigo: str) -> Plan:
    plan = Plan.objects.filter(code__iexact=plan_codigo, active=True).first()
    if plan is None:
        raise ValidationError({"plan_codigo": "El plan seleccionado no existe o no está disponible."})
    return plan


def _open_subscription(*, tenant: Tenant, plan: Plan, auto_renew: bool = False) -> Subscription:
    Subscription.objects.filter(tenant=tenant, status=Subscription.Status.ACTIVE).update(
        status=Subscription.Status.CANCELLED, end_date=date.today()
    )
    return Subscription.objects.create(
        tenant=tenant,
        plan=plan,
        start_date=date.today(),
        status=Subscription.Status.ACTIVE,
        auto_renew=auto_renew,
    )


def get_company_subscription(*, actor, company_id: int) -> Subscription | None:
    require_tenant_access(actor, company_id)
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
    require_permission(actor, "SUSCRIPCIONES_GESTIONAR")


@transaction.atomic
def change_company_subscription(
    *, actor, company_id: int, plan_codigo: str, auto_renew: bool = False, request=None
) -> Subscription:
    require_subscription_management(actor)
    company = Tenant.objects.filter(pk=company_id).first()
    if company is None:
        raise NotFound("Empresa no encontrada.")
    plan = _resolve_plan(plan_codigo)
    previous = get_company_subscription(actor=actor, company_id=company_id)
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
