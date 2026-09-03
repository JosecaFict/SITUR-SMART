from django.db import transaction
from django.utils.text import slugify
from rest_framework.exceptions import NotFound

from apps.audit.services import record_audit
from apps.rbac.services import require_permission, require_tenant_access
from apps.tenancy.models import City

from .models import Currency, ProductType, TourismProduct


def list_company_products(*, actor, tenant_id: int):
    require_tenant_access(actor, tenant_id)
    require_permission(actor, "PRODUCTOS_LEER", tenant_id)
    return TourismProduct.objects.select_related(
        "tenant", "product_type", "city__country", "currency"
    ).filter(tenant_id=tenant_id)


def get_company_product(*, actor, tenant_id: int, product_id: int) -> TourismProduct:
    product = list_company_products(actor=actor, tenant_id=tenant_id).filter(id=product_id).first()
    if product is None:
        raise NotFound("Producto no encontrado en esta empresa.")
    return product


def _unique_product_code(tenant_id: int, name: str, requested: str | None = None) -> str:
    base = (requested or slugify(name).replace("-", "_") or "PRODUCTO").upper()[:60]
    candidate = base
    suffix = 2
    while TourismProduct.objects.filter(tenant_id=tenant_id, code__iexact=candidate).exists():
        marker = f"_{suffix}"
        candidate = f"{base[: 60 - len(marker)]}{marker}"
        suffix += 1
    return candidate


def _relations(data: dict) -> dict:
    resolved = dict(data)
    if "tipo_codigo" in resolved:
        resolved["product_type"] = ProductType.objects.get(code=resolved.pop("tipo_codigo"))
    if "ciudad_id" in resolved:
        resolved["city"] = City.objects.get(id=resolved.pop("ciudad_id"))
    if "moneda_codigo" in resolved:
        resolved["currency"] = Currency.objects.get(iso_code=resolved.pop("moneda_codigo"))
    mapping = {
        "codigo": "code", "nombre": "name", "descripcion": "description",
        "precio_base": "base_price", "capacidad_maxima": "max_capacity",
        "estado": "status", "imagen_url": "image_url", "localidad": "locality",
    }
    return {mapping.get(key, key): value for key, value in resolved.items()}


@transaction.atomic
def create_product(*, actor, tenant_id: int, request=None, **data) -> TourismProduct:
    require_tenant_access(actor, tenant_id)
    require_permission(actor, "PRODUCTOS_GESTIONAR", tenant_id)
    requested_code = data.pop("codigo", None)
    values = _relations(data)
    values["code"] = _unique_product_code(tenant_id, values["name"], requested_code)
    values.setdefault("status", TourismProduct.Status.DRAFT)
    product = TourismProduct.objects.create(tenant_id=tenant_id, **values)
    record_audit(
        actor=actor, tenant_id=tenant_id, action="CREAR", entity="producto_turistico",
        entity_id=str(product.id), new_data={"code": product.code, "name": product.name}, request=request,
    )
    return product


@transaction.atomic
def update_product(*, actor, tenant_id: int, product_id: int, request=None, **data) -> TourismProduct:
    require_tenant_access(actor, tenant_id)
    require_permission(actor, "PRODUCTOS_GESTIONAR", tenant_id)
    product = TourismProduct.objects.filter(tenant_id=tenant_id, id=product_id).first()
    if product is None:
        raise NotFound("Producto no encontrado en esta empresa.")
    data.pop("codigo", None)
    values = _relations(data)
    previous = {"name": product.name, "status": product.status}
    for field, value in values.items():
        setattr(product, field, value)
    if values:
        product.save(update_fields=[*values.keys(), "updated_at"])
    record_audit(
        actor=actor, tenant_id=tenant_id, action="ACTUALIZAR", entity="producto_turistico",
        entity_id=str(product.id), previous_data=previous,
        new_data={"name": product.name, "status": product.status}, request=request,
    )
    return product


def deactivate_product(*, actor, tenant_id: int, product_id: int, request=None) -> TourismProduct:
    return update_product(
        actor=actor, tenant_id=tenant_id, product_id=product_id,
        estado=TourismProduct.Status.INACTIVE, request=request,
    )
