"""Gestión comercial CU51. No modifica paquetes privados, pagos ni inventario."""

from decimal import Decimal

from django.db import transaction
from django.db.models import Exists, OuterRef, Prefetch, Q
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound, ValidationError

from apps.audit.services import record_audit
from apps.bookings import services as bookings
from apps.catalog import departures
from apps.catalog.models import ROOM_PRODUCT_CODE, TourismProduct
from apps.rbac.services import require_permission, require_tenant_access
from apps.tenancy.subscriptions import require_active_plan, restricted_tenant_ids

from .models import Promotion, PromotionComponent
from .pricing import EXISTING_PRODUCT_CODES, current_promotions, discounted_price

COMPONENT_CODES = bookings.BOOKABLE_CODES - {"PAQUETE"}
MAX_COMPONENTS = 20
COMBINED_REASON = "El checkout conjunto y el bloqueo atómico de todos los componentes están pendientes. No se puede reservar esta oferta todavía."
COMPONENT_FIELDS = (
    "product_id",
    "start_date",
    "end_date",
    "quantity",
    "guests",
    "departure_id",
)


def access(actor, tenant_id, *, write=False):
    require_tenant_access(actor, tenant_id)
    require_permission(
        actor, "PRODUCTOS_GESTIONAR" if write else "PRODUCTOS_LEER", tenant_id
    )
    if write:
        require_active_plan(actor, tenant_id)


def queryset():
    return (
        Promotion.objects.annotate(
            tenant_restricted=Exists(
                restricted_tenant_ids().filter(tenant_id=OuterRef("tenant_id"))
            )
        )
        .select_related("tenant", "product__product_type", "product__currency")
        .prefetch_related(
            Prefetch(
                "components",
                queryset=PromotionComponent.objects.select_related(
                    "product__product_type",
                    "product__currency",
                    "product__tenant",
                    "departure",
                ),
            )
        )
    )


def company_promotions(actor, tenant_id):
    access(actor, tenant_id)
    return queryset().filter(tenant_id=tenant_id)


def owned(actor, tenant_id, promotion_id, *, lock=False):
    access(actor, tenant_id, write=lock)
    promotion = Promotion.objects.filter(id=promotion_id, tenant_id=tenant_id).first()
    if promotion is None:
        raise NotFound("Promoción no encontrada en esta empresa.")
    if lock:
        # Mismo orden que checkout: producto antes de promoción. Modalidad y
        # producto son inmutables para que este bloqueo siga siendo válido.
        if promotion.product_id:
            TourismProduct.objects.select_for_update().get(id=promotion.product_id)
        promotion = Promotion.objects.select_for_update().get(id=promotion.id)
    return promotion


def eligible_products(actor, tenant_id, mode):
    access(actor, tenant_id)
    codes = EXISTING_PRODUCT_CODES if mode == Promotion.Mode.EXISTING else COMPONENT_CODES
    return (
        TourismProduct.objects.select_related(
            "tenant", "product_type", "currency", "city__country"
        )
        .filter(
            tenant_id=tenant_id,
            tenant__status="ACTIVO",
            status=TourismProduct.Status.PUBLISHED,
            product_type__code__in=codes,
            base_price__gt=0,
        )
        .exclude(tenant_id__in=restricted_tenant_ids())
        .filter(
            ~Q(product_type__code=ROOM_PRODUCT_CODE)
            | Q(room__establishment__product__status=TourismProduct.Status.PUBLISHED)
        )
        .order_by("name", "id")
    )


def _product(promotion):
    if hasattr(promotion, "tenant_restricted"):
        product = promotion.product
        if (
            promotion.tenant_restricted
            or promotion.tenant.status != "ACTIVO"
            or (product is None or product.status != TourismProduct.Status.PUBLISHED)
        ):
            raise ValidationError({"producto_id": "Este producto no se puede ofertar."})
    else:
        product = bookings._bookable_product(promotion.product_id)
    if (
        product.tenant_id != promotion.tenant_id
        or product.product_type.code not in EXISTING_PRODUCT_CODES
    ):
        raise ValidationError(
            {"producto_id": "Selecciona un producto publicado y reservable de esta empresa."}
        )
    discounted_price(product.base_price, promotion.percentage, product.currency)
    return product


def _validate(promotion, *, publication=False):
    if not Decimal(0) < promotion.percentage < Decimal(100):
        raise ValidationError(
            {"porcentaje_descuento": "Debe ser mayor que 0 y menor que 100."}
        )
    if promotion.starts_at >= promotion.ends_at:
        raise ValidationError({"fin": "El fin debe ser posterior al inicio."})
    if promotion.ends_at <= timezone.now():
        raise ValidationError({"fin": "La promoción debe finalizar en el futuro."})
    if promotion.mode == Promotion.Mode.EXISTING:
        if not promotion.product_id:
            raise ValidationError({"producto_id": "Selecciona un producto."})
        _product(promotion)
        if (
            publication
            and Promotion.objects.filter(
                product_id=promotion.product_id,
                administrative_status=Promotion.Status.ENABLED,
                starts_at__lt=promotion.ends_at,
                ends_at__gt=promotion.starts_at,
            )
            .exclude(id=promotion.pk)
            .exists()
        ):
            raise ValidationError(
                {
                    "inicio": "Ya existe una promoción habilitada con vigencia superpuesta para este producto."
                }
            )
    elif promotion.product_id is not None:
        raise ValidationError(
            {
                "producto_id": "Una oferta combinada utiliza componentes, no un producto original."
            }
        )


def _component_quote(promotion, values):
    product = bookings._bookable_product(values["product_id"])
    if product.tenant_id != promotion.tenant_id:
        raise ValidationError(
            {"producto_id": "El servicio no pertenece a esta empresa."}
        )
    if product.product_type.code not in COMPONENT_CODES:
        raise ValidationError(
            {
                "producto_id": "Selecciona un servicio individual; hospedajes por habitación y sin paquetes anidados."
            }
        )
    start = values["start_date"]
    if start < timezone.localtime(promotion.starts_at).date():
        raise ValidationError(
            {
                "fecha_inicio": "El servicio no puede comenzar antes de la vigencia de la oferta."
            }
        )
    quantity = values["quantity"]
    if not 1 <= quantity <= 500:
        raise ValidationError({"cantidad": "Indica entre 1 y 500 unidades."})
    if product.product_type.code != ROOM_PRODUCT_CODE:
        if values.get("end_date") is not None or values.get("guests") is not None:
            raise ValidationError(
                {
                    "fecha_fin": "Fecha de salida y huéspedes se usan solo para habitaciones."
                }
            )
    if (
        product.product_type.code in departures.DEPARTURE_CODES
        and values.get("departure_id") is None
    ):
        slots = list(departures.slots_for_day(product.id, start))
        if any(not departures.is_legacy_daily(slot) for slot in slots):
            raise ValidationError(
                {"salida_id": "Selecciona explícitamente una salida horaria."}
            )
        if not any(
            departures.is_legacy_daily(slot) and not slot.closed for slot in slots
        ):
            raise ValidationError(
                {"salida_id": "No existe salida ni disponibilidad diaria confirmable."}
            )
    quote = bookings.build_quote(
        product_id=product.id,
        start=start,
        end=values.get("end_date"),
        quantity=quantity,
        guests=values.get("guests"),
        slot_id=values.get("departure_id"),
    )
    if bookings.availability(quote) < quantity:
        raise ValidationError(
            {"cantidad": "No hay disponibilidad suficiente para este componente."}
        )
    return quote


def _compatible(quotes):
    if len({quote.product.currency_id for quote in quotes}) > 1:
        raise ValidationError(
            {"componentes": "Todos los servicios deben tener la misma moneda."}
        )
    for i, quote in enumerate(quotes):
        for other in quotes[:i]:
            if quote.product.id == other.product.id and set(quote.days) & set(
                other.days
            ):
                raise ValidationError(
                    {
                        "componentes": "No repitas el mismo servicio en fechas superpuestas; edita su cantidad."
                    }
                )
            if (
                quote.slot
                and other.slot
                and quote.slot.start < other.slot.end
                and other.slot.start < quote.slot.end
            ):
                raise ValidationError(
                    {"componentes": "Los horarios de los servicios se superponen."}
                )


def _values(component):
    return {name: getattr(component, name) for name in COMPONENT_FIELDS}


def _message(detail):
    if isinstance(detail, dict):
        return "; ".join(_message(value) for value in detail.values())
    if isinstance(detail, (list, tuple)):
        return "; ".join(_message(value) for value in detail)
    return str(detail)


def evaluate(promotion, *, component_values=None):
    """Relee precios, publicación y cupos. No usa los precios guardados como verdad."""
    issues, items, quotes = [], [], []
    currency, original, final, image = None, None, None, None
    if promotion.mode == Promotion.Mode.EXISTING:
        try:
            product = _product(promotion)
            currency, image = product.currency, product.image_url
            original, final = discounted_price(
                product.base_price, promotion.percentage, currency
            )
        except APIException as exc:
            issues.append(_message(exc.detail))
    else:
        components = (
            component_values
            if component_values is not None
            else list(promotion.components.all())
        )
        if not 2 <= len(components) <= MAX_COMPONENTS:
            issues.append(
                f"La oferta debe incluir entre 2 y {MAX_COMPONENTS} componentes."
            )
        for component in components:
            values = component if isinstance(component, dict) else _values(component)
            item = {
                "id": getattr(component, "id", None),
                "producto_id": values["product_id"],
                "fecha_inicio": values["start_date"],
                "fecha_fin": values.get("end_date"),
                "cantidad": values["quantity"],
                "huespedes": values.get("guests"),
                "salida_id": values.get("departure_id"),
                "disponible": False,
                "motivo": None,
                "precio_unitario": None,
                "total": None,
                "precio_cambio": False,
            }
            product = getattr(component, "product", None)
            if product:
                item.update(
                    nombre=product.name,
                    tipo_codigo=product.product_type.code,
                    imagen_url=product.image_url,
                )
            try:
                quote = _component_quote(promotion, values)
                quotes.append(quote)
                currency = quote.product.currency
                image = image or quote.product.image_url
                item.update(
                    nombre=quote.product.name,
                    tipo_codigo=quote.product.product_type.code,
                    imagen_url=quote.product.image_url,
                    disponible=True,
                    precio_unitario=str(quote.unit_price),
                    total=str(quote.total),
                    inicio=quote.slot.start if quote.slot else None,
                    fin=quote.slot.end if quote.slot else None,
                    precio_cambio=getattr(component, "reference_total", quote.total)
                    != quote.total,
                )
            except APIException as exc:
                item["motivo"] = _message(exc.detail)
                issues.append(item["motivo"])
            items.append(item)
        try:
            _compatible(quotes)
            if currency and len(quotes) == len(components):
                original, final = discounted_price(
                    sum((quote.total for quote in quotes), Decimal(0)),
                    promotion.percentage,
                    currency,
                )
                if original >= Decimal("1000000000000"):
                    raise ValidationError(
                        "El importe excede la precisión admitida para una oferta."
                    )
        except APIException as exc:
            issues.append(_message(exc.detail))
    return {
        "valida": not issues,
        "advertencias": issues,
        "componentes": items,
        "precio_original": str(original) if original is not None else None,
        "precio_final": str(final) if final is not None else None,
        "monto_descuento": str(original - final)
        if original is not None and final is not None
        else None,
        "moneda_codigo": currency.iso_code if currency else None,
        "moneda_simbolo": currency.symbol if currency else None,
        "imagen_url": image,
        "requiere_revalidacion": bool(issues)
        or any(item["precio_cambio"] for item in items),
    }


def promotion_data(promotion, *, start=None, quantity=1):
    data = evaluate(promotion)
    active = promotion.state_at() == "VIGENTE" and data["valida"]
    reservable = active and promotion.mode == Promotion.Mode.EXISTING
    data.update(
        id=promotion.id,
        empresa_id=promotion.tenant_id,
        empresa=promotion.tenant.trade_name,
        modalidad=promotion.mode,
        producto_id=promotion.product_id,
        nombre=promotion.name,
        descripcion=promotion.description,
        porcentaje_descuento=str(promotion.percentage),
        inicio=promotion.starts_at,
        fin=promotion.ends_at,
        estado=promotion.state_at(),
        estado_administrativo=promotion.administrative_status,
        publicado=active,
        admite_reservas=reservable,
        reservable=False,
        disponible=None,
        cupos_restantes=None,
        motivo_no_reservable=COMBINED_REASON
        if promotion.mode == Promotion.Mode.COMBINED
        else "Selecciona fecha y cantidad para comprobar los cupos."
        if reservable
        else "La promoción no está disponible para reservar.",
        requiere_fecha=promotion.mode == Promotion.Mode.EXISTING,
        creado_en=promotion.created_at,
        actualizado_en=promotion.updated_at,
    )
    if promotion.mode == Promotion.Mode.COMBINED:
        data["disponible"] = data["valida"]
    elif reservable and start is not None:
        try:
            quote = bookings.build_quote(
                product_id=promotion.product_id,
                start=start,
                end=None,
                quantity=quantity,
                guests=None,
                promotion_id=promotion.id,
            )
            remaining = bookings.availability(quote)
            data.update(
                cupos_restantes=remaining,
                disponible=remaining >= quantity,
                reservable=remaining >= quantity,
                requiere_fecha=False,
                cotizacion=quote.promotion_discount.data(quantity),
                motivo_no_reservable=None
                if remaining >= quantity
                else "No hay cupos suficientes para esta fecha.",
            )
        except APIException as exc:
            data.update(
                disponible=False,
                reservable=False,
                motivo_no_reservable=_message(exc.detail),
            )
    return data


def _audit(actor, promotion, action, request=None):
    record_audit(
        actor=actor,
        action=action,
        entity="promocion_comercial",
        entity_id=str(promotion.id),
        tenant_id=promotion.tenant_id,
        request=request,
        new_data={
            "estado": promotion.administrative_status,
            "porcentaje": str(promotion.percentage),
            "inicio": promotion.starts_at.isoformat(),
            "fin": promotion.ends_at.isoformat(),
        },
    )


@transaction.atomic
def create(actor, tenant_id, values, request=None):
    access(actor, tenant_id, write=True)
    values = dict(values)
    components = values.pop("components", [])
    promotion = Promotion(tenant_id=tenant_id, created_by=actor, **values)
    if promotion.product_id:
        TourismProduct.objects.select_for_update().filter(
            id=promotion.product_id
        ).first()
    _validate(promotion)
    promotion.save()
    for component in components:
        _save_component(promotion, component)
    _audit(actor, promotion, "PROMOCION_CREAR", request)
    return promotion


@transaction.atomic
def update(actor, tenant_id, promotion_id, values, request=None):
    promotion = owned(actor, tenant_id, promotion_id, lock=True)
    for key in ("mode", "product_id", "components"):
        if key in values:
            raise ValidationError(
                {
                    key: "Este campo no se modifica aquí. Usa la gestión de componentes o crea otra promoción."
                }
            )
    for key, value in values.items():
        setattr(promotion, key, value)
    _validate(
        promotion,
        publication=promotion.administrative_status == Promotion.Status.ENABLED,
    )
    if promotion.administrative_status == Promotion.Status.ENABLED:
        result = evaluate(promotion)
        if not result["valida"]:
            raise ValidationError({"componentes": result["advertencias"]})
    promotion.save()
    _audit(actor, promotion, "PROMOCION_EDITAR", request)
    return promotion


@transaction.atomic
def set_enabled(actor, tenant_id, promotion_id, enabled, request=None):
    promotion = owned(actor, tenant_id, promotion_id, lock=True)
    if enabled:
        _validate(promotion, publication=True)
        result = evaluate(promotion)
        if not result["valida"]:
            raise ValidationError({"componentes": result["advertencias"]})
    promotion.administrative_status = (
        Promotion.Status.ENABLED if enabled else Promotion.Status.DISABLED
    )
    promotion.save(update_fields=["administrative_status", "updated_at"])
    _audit(
        actor,
        promotion,
        "PROMOCION_PUBLICAR" if enabled else "PROMOCION_DESACTIVAR",
        request,
    )
    return promotion


def _save_component(promotion, values, component=None):
    if promotion.mode != Promotion.Mode.COMBINED:
        raise ValidationError(
            {"modalidad": "Solo las ofertas combinadas admiten componentes."}
        )
    if promotion.administrative_status == Promotion.Status.ENABLED:
        raise ValidationError(
            {
                "estado": "Desactiva la oferta antes de cambiar sus componentes y vuelve a publicarla al terminar."
            }
        )
    others = list(promotion.components.exclude(id=component.id if component else None))
    if len(others) >= MAX_COMPONENTS:
        raise ValidationError(
            {"componentes": f"El máximo es {MAX_COMPONENTS} servicios."}
        )
    config = _values(component) if component else {}
    config.update(values)
    quote = _component_quote(promotion, config)
    quotes = [_component_quote(promotion, _values(other)) for other in others]
    _compatible([*quotes, quote])
    # Valida también precisión y ahorro, incluso al guardar un borrador.
    discounted_price(
        sum((q.total for q in [*quotes, quote]), Decimal(0)),
        promotion.percentage,
        quote.product.currency,
    )
    component = component or PromotionComponent(promotion=promotion)
    for key in COMPONENT_FIELDS:
        setattr(component, key, config.get(key))
    component.reference_unit_price, component.reference_total = (
        quote.unit_price,
        quote.total,
    )
    component.save()
    return component


@transaction.atomic
def change_component(
    actor,
    tenant_id,
    promotion_id,
    values=None,
    component_id=None,
    *,
    delete=False,
    request=None,
):
    promotion = owned(actor, tenant_id, promotion_id, lock=True)
    component = None
    if component_id is not None:
        component = promotion.components.filter(id=component_id).first()
        if component is None:
            raise NotFound("Componente no encontrado en esta promoción.")
    if delete:
        if promotion.administrative_status == Promotion.Status.ENABLED:
            raise ValidationError(
                {"estado": "Desactiva la oferta antes de quitar componentes."}
            )
        component.delete()
    else:
        _save_component(promotion, values, component)
    promotion.save(update_fields=["updated_at"])
    _audit(actor, promotion, "PROMOCION_COMPONENTES", request)
    return promotion


def preview(actor, tenant_id, values):
    access(actor, tenant_id)
    values = dict(values)
    components = values.pop("components", [])
    promotion = Promotion(tenant_id=tenant_id, created_by=actor, **values)
    _validate(promotion)
    if components and promotion.mode != Promotion.Mode.COMBINED:
        raise ValidationError(
            {"componentes": "Solo las ofertas combinadas admiten componentes."}
        )
    return evaluate(promotion, component_values=components)


def public_promotions():
    return queryset().filter(id__in=current_promotions().values("id"))
