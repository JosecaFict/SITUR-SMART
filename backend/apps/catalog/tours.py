"""Tours y experiencias (CU20): ficha, paradas y publicacion.

Un tour es un ``producto_turistico`` de tipo TOUR o EXPERIENCIA mas su ficha en
``detalle_tour``; los servicios escriben los dos juntos, como hospedaje con su
establecimiento. Tener ficha pone al producto en "modo salidas": se reserva una
salida concreta (catalog/departures.py) y no el cupo diario automatico.

Un tour solo se publica si se puede vender: precio, punto de encuentro, al
menos una salida futura abierta y lugar en el plan de la empresa.
"""

from django.db import transaction
from django.db.models import Count, Min, Prefetch, Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.audit.services import record_audit
from apps.rbac.services import require_permission, require_tenant_access
from apps.tenancy.models import PlanLimit
from apps.tenancy.services import (
    _active_subscription_plan,
    ensure_product_quota_available,
)
from apps.tenancy.subscriptions import require_active_plan, restricted_tenant_ids

from .departures import open_future_departures
from .models import (
    TOUR_PRODUCT_CODES,
    Availability,
    ProductType,
    TourDetail,
    TourismProduct,
    TourStop,
)
from .services import (
    _normalize_coordinates,
    _relations,
    _split_specifics,
    _unique_product_code,
)

MAX_STOPS = 30

_TOUR_FIELDS = {
    "duracion_minutos": "duration_minutes",
    "idioma": "language",
    "dificultad": "difficulty",
    "edad_minima": "minimum_age",
    "punto_encuentro": "meeting_point",
    "latitud": "latitude",
    "longitud": "longitude",
    "incluye": "includes",
    "no_incluye": "excludes",
    "requisitos": "requirements",
}

_PLAN_RESOURCE = {"TOUR": PlanLimit.Resource.TOURS, "EXPERIENCIA": PlanLimit.Resource.EXPERIENCES}
_TYPE_PLURAL = {"TOUR": "tours", "EXPERIENCIA": "experiencias"}


def _tours_queryset():
    """Tours con su ficha, sus paradas y el resumen de sus proximas salidas."""
    now = timezone.now()
    upcoming = Q(availabilities__closed=False, availabilities__start__gt=now)
    return (
        TourismProduct.objects.select_related("tenant", "product_type", "city__country", "currency", "tour")
        .prefetch_related(Prefetch("stops", queryset=TourStop.objects.order_by("order", "id")))
        .filter(product_type__code__in=TOUR_PRODUCT_CODES)
        .annotate(
            upcoming_departures=Count("availabilities", filter=upcoming, distinct=True),
            next_departure=Min("availabilities__start", filter=upcoming),
        )
    )


def list_company_tours(*, actor, tenant_id: int):
    """Todos los tours y experiencias de la empresa, tengan ficha o no.

    Los que no tienen ficha vienen del catalogo generico: se ven aqui para que
    la empresa los complete y pasen a venderse por salidas.
    """
    require_tenant_access(actor, tenant_id)
    require_permission(actor, "PRODUCTOS_LEER", tenant_id)
    return _tours_queryset().filter(tenant_id=tenant_id)


def get_company_tour(*, actor, tenant_id: int, tour_id: int) -> TourismProduct:
    tour = list_company_tours(actor=actor, tenant_id=tenant_id).filter(id=tour_id).first()
    if tour is None:
        raise NotFound("Tour no encontrado en esta empresa.")
    return tour


def get_public_tour(tour_id: int) -> TourismProduct:
    tour = (
        _tours_queryset()
        .filter(id=tour_id, status=TourismProduct.Status.PUBLISHED, tenant__status="ACTIVO", tour__isnull=False)
        .exclude(tenant_id__in=restricted_tenant_ids())
        .first()
    )
    if tour is None:
        raise NotFound("Tour no encontrado.")
    return tour


def _replace_stops(product: TourismProduct, stops: list[dict]) -> None:
    """Reemplaza el recorrido completo. El orden es el de la lista."""
    if len(stops) > MAX_STOPS:
        raise ValidationError({"paradas": [f"Un recorrido admite hasta {MAX_STOPS} paradas."]})
    TourStop.objects.filter(product=product).delete()
    TourStop.objects.bulk_create(
        [
            TourStop(
                product=product,
                tenant_id=product.tenant_id,
                order=index,
                name=stop["nombre"],
                description=stop.get("descripcion") or None,
                duration_minutes=stop.get("duracion_minutos"),
            )
            for index, stop in enumerate(stops, start=1)
        ]
    )


def _save_detail(product: TourismProduct, specifics: dict) -> tuple[TourDetail, bool]:
    """Crea o actualiza la ficha. Devuelve si la creo."""
    detail = TourDetail.objects.filter(product=product).first()
    if detail is None:
        return TourDetail.objects.create(product=product, tenant_id=product.tenant_id, **specifics), True
    for field, value in specifics.items():
        setattr(detail, field, value)
    if specifics:
        detail.save(update_fields=[*specifics.keys(), "updated_at"])
    return detail, False


def _plan_limit_problem(product: TourismProduct) -> str | None:
    """Si publicar este tour pasa el tope de su tipo en el plan de la empresa."""
    type_code = product.product_type.code
    plan = _active_subscription_plan(product.tenant_id)
    if plan is None or type_code not in _PLAN_RESOURCE:
        return None
    limit = PlanLimit.objects.filter(plan=plan, resource=_PLAN_RESOURCE[type_code]).values_list("limit", flat=True).first()
    if limit is None:
        return None
    plural = _TYPE_PLURAL[type_code]
    if limit == 0:
        return f"Tu plan {plan.name} no incluye {plural}."
    published = (
        TourismProduct.objects.filter(
            tenant_id=product.tenant_id, product_type=product.product_type, status=TourismProduct.Status.PUBLISHED
        )
        .exclude(id=product.id)
        .count()
    )
    if published >= limit:
        return f"Tu plan {plan.name} permite publicar hasta {limit} {plural}. Sube de plan para publicar más."
    return None


def publish_problems(product: TourismProduct) -> list[str]:
    """Lo que le falta a un tour con ficha para publicarse. Vacio si nada."""
    problems = []
    if product.base_price is None or product.base_price <= 0:
        problems.append("Indica un precio por persona mayor a 0.")
    detail = TourDetail.objects.filter(product_id=product.id).first()
    if detail is None or not (detail.meeting_point or "").strip():
        problems.append("Indica el punto de encuentro.")
    if not open_future_departures(product).exists():
        problems.append("Programa al menos una salida futura.")
    if limit := _plan_limit_problem(product):
        problems.append(limit)
    return problems


def check_publishable(product: TourismProduct) -> None:
    if problems := publish_problems(product):
        raise ValidationError({"estado": problems})


def _close_daily_slots(product: TourismProduct) -> int:
    """Cierra los cupos diarios automaticos que el tour tenia antes de su ficha.

    Hasta tener ficha, el tour se vendia por dia con filas creadas solas a
    medianoche. Desde ahora se vende por salidas, asi que esas filas futuras
    dejan de venderse. Las reservas que ya tienen se mantienen.
    """
    return Availability.objects.filter(product=product, closed=False, start__gt=timezone.now()).update(closed=True)


@transaction.atomic
def create_tour(*, actor, tenant_id: int, request=None, **data) -> TourismProduct:
    require_tenant_access(actor, tenant_id)
    require_permission(actor, "PRODUCTOS_GESTIONAR", tenant_id)
    require_active_plan(actor, tenant_id)
    ensure_product_quota_available(tenant_id)

    stops = data.pop("paradas", None)
    type_code = data.pop("tipo_codigo", "TOUR")
    specifics = _split_specifics(data, _TOUR_FIELDS)
    _normalize_coordinates(specifics)
    requested_code = data.pop("codigo", None)

    values = _relations(data)
    values["product_type"] = ProductType.objects.get(code=type_code)
    values["code"] = _unique_product_code(tenant_id, values["name"], requested_code)
    values.setdefault("status", TourismProduct.Status.DRAFT)
    if values["status"] == TourismProduct.Status.PUBLISHED:
        raise ValidationError(
            {
                "estado": [
                    "Un tour nuevo todavía no tiene salidas, así que no puede publicarse. "
                    "Guárdalo como borrador, programa sus salidas y publícalo después."
                ]
            }
        )

    product = TourismProduct.objects.create(tenant_id=tenant_id, **values)
    TourDetail.objects.create(product=product, tenant_id=tenant_id, **specifics)
    if stops:
        _replace_stops(product, stops)
    record_audit(
        actor=actor, tenant_id=tenant_id, action="CREAR", entity="detalle_tour",
        entity_id=str(product.id),
        new_data={"producto_id": product.id, "nombre": product.name, "tipo": type_code},
        request=request,
    )
    return _tours_queryset().get(id=product.id)


@transaction.atomic
def update_tour(*, actor, tenant_id: int, tour_id: int, request=None, **data) -> TourismProduct:
    """Edita el tour, su ficha y, si vienen, sus paradas.

    Si el tour todavia no tenia ficha (venia del catalogo generico), guardarla
    lo pasa a vender por salidas: se cierran sus cupos diarios y, si estaba
    publicado sin salidas, vuelve a borrador para no quedar a la venta sin
    nada que vender. ``notice`` en el resultado lo explica.
    """
    product = get_company_tour(actor=actor, tenant_id=tenant_id, tour_id=tour_id)
    require_permission(actor, "PRODUCTOS_GESTIONAR", tenant_id)
    require_active_plan(actor, tenant_id)

    stops = data.pop("paradas", None)
    specifics = _split_specifics(data, _TOUR_FIELDS)
    _normalize_coordinates(specifics)
    data.pop("codigo", None)
    new_status = data.get("estado")
    previous = {"nombre": product.name, "estado": product.status}
    notice = None

    created_detail = False
    if specifics or stops is not None:
        _, created_detail = _save_detail(product, specifics)
    if stops is not None:
        _replace_stops(product, stops)

    product_values = _relations(data)
    for field, value in product_values.items():
        setattr(product, field, value)

    has_detail = created_detail or TourDetail.objects.filter(product_id=product.id).exists()
    if created_detail:
        _close_daily_slots(product)
    if has_detail:
        becoming_published = (
            new_status == TourismProduct.Status.PUBLISHED and previous["estado"] != TourismProduct.Status.PUBLISHED
        )
        if becoming_published:
            check_publishable(product)
        elif created_detail and product.status == TourismProduct.Status.PUBLISHED and not open_future_departures(product).exists():
            product.status = TourismProduct.Status.DRAFT
            product_values["status"] = product.status
            notice = "El tour pasó a borrador: ahora se vende por salidas. Programa sus salidas y vuelve a publicarlo."

    if product_values:
        product.save(update_fields=[*product_values.keys(), "updated_at"])

    record_audit(
        actor=actor, tenant_id=tenant_id, action="ACTUALIZAR", entity="detalle_tour",
        entity_id=str(product.id), previous_data=previous,
        new_data={
            "nombre": product.name, "estado": product.status,
            **({"paso_a_salidas": True} if created_detail else {}),
        },
        request=request,
    )
    result = _tours_queryset().get(id=product.id)
    result.notice = notice
    return result


def deactivate_tour(*, actor, tenant_id: int, tour_id: int, request=None) -> TourismProduct:
    """Saca el tour del Marketplace. Las reservas ya pagadas se mantienen."""
    return update_tour(
        actor=actor, tenant_id=tenant_id, tour_id=tour_id,
        estado=TourismProduct.Status.INACTIVE, request=request,
    )


def set_stops(*, actor, tenant_id: int, tour_id: int, stops: list[dict], request=None) -> list[TourStop]:
    """Guarda el recorrido completo. Pasa por update_tour para aplicar sus mismas reglas."""
    update_tour(actor=actor, tenant_id=tenant_id, tour_id=tour_id, paradas=stops, request=request)
    return list(TourStop.objects.filter(product_id=tour_id).order_by("order", "id"))
