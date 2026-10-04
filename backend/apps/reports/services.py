from __future__ import annotations

from datetime import date

from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.models import AuditLog
from apps.catalog.models import Room, TourismProduct
from apps.rbac.services import is_superadmin, require_permission, require_tenant_access
from apps.tenancy.models import City, Subscription, Tenant

REPORT_TYPES = {"plataforma", "catalogo", "hospedajes", "actividad"}


def report_scope(*, user, tenant_id: int | None) -> tuple[bool, int | None]:
    global_scope = is_superadmin(user)
    if global_scope:
        require_permission(user, "REPORTES_GLOBALES")
        return True, tenant_id
    if tenant_id is None:
        raise PermissionDenied("Se requiere un contexto de empresa para consultar reportes.")
    require_tenant_access(user, tenant_id)
    require_permission(user, "REPORTES_TENANT", tenant_id)
    return False, tenant_id


def parse_filters(params) -> dict:
    report_type = params.get("tipo", "plataforma")
    if report_type not in REPORT_TYPES:
        raise ValidationError({"tipo": "El tipo de reporte no es válido."})
    values = {"tipo": report_type, "estado": params.get("estado", "")}
    for key in ("desde", "hasta"):
        raw = params.get(key)
        if not raw:
            values[key] = None
            continue
        try:
            values[key] = date.fromisoformat(raw)
        except ValueError as exc:
            raise ValidationError({key: "Use el formato AAAA-MM-DD."}) from exc
    if values["desde"] and values["hasta"] and values["desde"] > values["hasta"]:
        raise ValidationError({"hasta": "La fecha final no puede ser anterior a la inicial."})
    return values


def _date_filter(queryset, filters, field="created_at"):
    if filters["desde"]:
        queryset = queryset.filter(**{f"{field}__date__gte": filters["desde"]})
    if filters["hasta"]:
        queryset = queryset.filter(**{f"{field}__date__lte": filters["hasta"]})
    return queryset


def _metric(key, label, value, detail=""):
    return {"clave": key, "etiqueta": label, "valor": value, "detalle": detail}


def _city_names(ids):
    return dict(City.objects.filter(id__in=set(ids)).values_list("id", "name"))


def platform_report(*, tenant_id, filters):
    tenants = Tenant.objects.all()
    if tenant_id is not None:
        tenants = tenants.filter(id=tenant_id)
    tenants = _date_filter(tenants, filters)
    if filters["estado"]:
        tenants = tenants.filter(status=filters["estado"])
    tenant_rows = list(tenants.values("id", "trade_name", "city_id", "status", "created_at"))
    ids = [row["id"] for row in tenant_rows]
    cities = _city_names(row["city_id"] for row in tenant_rows if row["city_id"])
    active_subscriptions = {
        row["tenant_id"]: row
        for row in Subscription.objects.filter(
            tenant_id__in=ids, status=Subscription.Status.ACTIVE
        )
        .select_related("plan", "contracted_currency")
        .values(
            "tenant_id", "plan__name", "contracted_price",
            "contracted_currency__iso_code", "contracted_periodicity",
        )
    }
    rows = []
    for tenant in tenant_rows:
        subscription = active_subscriptions.get(tenant["id"], {})
        price = subscription.get("contracted_price")
        currency = subscription.get("contracted_currency__iso_code") or ""
        rows.append({
            "empresa": tenant["trade_name"],
            "ciudad": cities.get(tenant["city_id"], "Sin registrar"),
            "estado": tenant["status"],
            "plan": subscription.get("plan__name") or "Sin plan activo",
            "importe_contratado": f"{currency} {price:.2f}" if price is not None else "—",
            "periodicidad": subscription.get("contracted_periodicity") or "—",
            "registro": tenant["created_at"].isoformat(),
        })
    return {
        "indicadores": [
            _metric("empresas", "Empresas", len(rows)),
            _metric("activas", "Empresas activas", sum(r["estado"] == Tenant.Status.ACTIVE for r in rows)),
            _metric("suscritas", "Con plan activo", sum(r["plan"] != "Sin plan activo" for r in rows)),
        ],
        "columnas": [
            ["empresa", "Empresa"], ["ciudad", "Ciudad"], ["estado", "Estado"],
            ["plan", "Plan"], ["importe_contratado", "Importe contratado"],
            ["periodicidad", "Periodicidad"], ["registro", "Registro"],
        ],
        "filas": rows,
        "nota": "Los importes corresponden a condiciones contratadas; no representan pagos cobrados.",
    }


def catalog_report(*, tenant_id, filters):
    products = TourismProduct.objects.select_related("tenant", "product_type", "city", "currency")
    if tenant_id is not None:
        products = products.filter(tenant_id=tenant_id)
    products = _date_filter(products, filters)
    if filters["estado"]:
        products = products.filter(status=filters["estado"])
    rows = [{
        "producto": product.name,
        "empresa": product.tenant.trade_name,
        "tipo": product.product_type.name,
        "ciudad": product.city.name,
        "estado": product.status,
        "precio_base": f"{product.currency.iso_code} {product.base_price:.2f}",
        "registro": product.created_at.isoformat(),
    } for product in products]
    return {
        "indicadores": [
            _metric("productos", "Productos", len(rows)),
            _metric("publicados", "Publicados", sum(r["estado"] == TourismProduct.Status.PUBLISHED for r in rows)),
            _metric("borradores", "Borradores", sum(r["estado"] == TourismProduct.Status.DRAFT for r in rows)),
        ],
        "columnas": [["producto", "Producto"], ["empresa", "Empresa"], ["tipo", "Tipo"], ["ciudad", "Ciudad"], ["estado", "Estado"], ["precio_base", "Precio base"], ["registro", "Registro"]],
        "filas": rows,
        "nota": "El precio base es informativo y no representa ingresos ni pagos.",
    }


def lodging_report(*, tenant_id, filters):
    rooms = Room.objects.select_related(
        "tenant", "product", "product__currency", "establishment__product"
    )
    if tenant_id is not None:
        rooms = rooms.filter(tenant_id=tenant_id)
    rooms = _date_filter(rooms, filters)
    if filters["estado"]:
        rooms = rooms.filter(product__status=filters["estado"])
    rows = [{
        "hospedaje": room.establishment.product.name,
        "empresa": room.tenant.trade_name,
        "tipo_habitacion": room.product.name,
        "estado": room.product.status,
        "unidades": room.quantity,
        "huespedes_unidad": room.product.max_capacity,
        "capacidad_total": room.quantity * room.product.max_capacity,
        "precio_noche": f"{room.product.currency.iso_code} {room.product.base_price:.2f}",
        "desayuno": "Incluido" if room.includes_breakfast else "No incluido",
    } for room in rooms]
    hotel_ids = {room.establishment_id for room in rooms}
    return {
        "indicadores": [
            _metric("hospedajes", "Hospedajes", len(hotel_ids)),
            _metric("tipos_habitacion", "Tipos de habitación", len(rows)),
            _metric("unidades", "Habitaciones ofertadas", sum(r["unidades"] for r in rows)),
            _metric("capacidad", "Capacidad total", sum(r["capacidad_total"] for r in rows), "huéspedes"),
        ],
        "columnas": [["hospedaje", "Hospedaje"], ["empresa", "Empresa"], ["tipo_habitacion", "Tipo de habitación"], ["estado", "Estado"], ["unidades", "Unidades"], ["huespedes_unidad", "Huéspedes/unidad"], ["capacidad_total", "Capacidad total"], ["precio_noche", "Precio/noche"], ["desayuno", "Desayuno"]],
        "filas": rows,
        "nota": "Las unidades son la cantidad declarada de cada tipo, no disponibilidad en tiempo real.",
    }


def activity_report(*, tenant_id, filters):
    logs = AuditLog.objects.select_related("tenant", "user")
    if tenant_id is not None:
        logs = logs.filter(tenant_id=tenant_id)
    logs = _date_filter(logs, filters)
    if filters["estado"]:
        logs = logs.filter(action=filters["estado"])
    rows = [{
        "fecha": log.created_at.isoformat(),
        "empresa": log.tenant.trade_name if log.tenant_id else "Plataforma",
        "usuario": log.user.get_full_name() if log.user_id else "Sistema",
        "accion": log.action,
        "entidad": log.entity,
        "identificador": log.entity_id or "—",
    } for log in logs[:1000]]
    return {
        "indicadores": [
            _metric("movimientos", "Movimientos", len(rows)),
            _metric("creaciones", "Creaciones", sum(r["accion"] == "CREAR" for r in rows)),
            _metric("actualizaciones", "Actualizaciones", sum(r["accion"] == "ACTUALIZAR" for r in rows)),
        ],
        "columnas": [["fecha", "Fecha"], ["empresa", "Empresa"], ["usuario", "Usuario"], ["accion", "Acción"], ["entidad", "Entidad"], ["identificador", "Identificador"]],
        "filas": rows,
        "nota": "Se muestran hasta 1.000 movimientos por consulta.",
    }


BUILDERS = {
    "plataforma": platform_report,
    "catalogo": catalog_report,
    "hospedajes": lodging_report,
    "actividad": activity_report,
}


def build_report(*, user, tenant_id, params):
    global_scope, effective_tenant_id = report_scope(user=user, tenant_id=tenant_id)
    filters = parse_filters(params)
    result = BUILDERS[filters["tipo"]](tenant_id=effective_tenant_id, filters=filters)
    tenant = Tenant.objects.filter(id=effective_tenant_id).first() if effective_tenant_id else None
    return {
        "tipo": filters["tipo"],
        "alcance": "GLOBAL" if global_scope and effective_tenant_id is None else "EMPRESA",
        "empresa": {"id": tenant.id, "nombre": tenant.trade_name} if tenant else None,
        **result,
    }
