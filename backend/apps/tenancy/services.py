from django.db import transaction
from django.db.models import Q
from django.utils.text import slugify
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.audit.services import record_audit
from apps.rbac.models import Role, UserRole
from apps.rbac.services import is_superadmin, require_tenant_access

from .models import Tenant, UserTenant


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
    request=None,
) -> Tenant:
    require_company_management(actor)
    tax_id = nit.strip() or None
    if tax_id and Tenant.objects.filter(tax_id__iexact=tax_id).exists():
        raise ValidationError({"nit": "Ya existe una empresa con este NIT."})

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
        },
        request=request,
    )
    return company


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
