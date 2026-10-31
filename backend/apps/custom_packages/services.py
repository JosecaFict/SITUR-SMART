"""Private travel bundles. A quote is informative: no inventory or payment is created."""

from datetime import timedelta

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound, ValidationError

from apps.bookings import services as bookings
from apps.catalog import departures
from apps.catalog.models import ROOM_PRODUCT_CODE, TourismProduct
from apps.catalog.reviews import with_review_stats
from apps.tenancy.subscriptions import restricted_tenant_ids

from .models import CustomPackage, PackageComponent, PackagePurchase

MAX_COMPONENTS = 20
COMPONENT_CODES = bookings.BOOKABLE_CODES - {"PAQUETE"}


def catalog(*, city_id=None, product_type=None, search=None):
    query = with_review_stats(
        TourismProduct.objects.select_related(
            "tenant", "product_type", "city__country", "currency",
            "room__establishment__product", "lodging",
        ).filter(
            status=TourismProduct.Status.PUBLISHED,
            tenant__status="ACTIVO",
            currency__iso_code="BOB",
            base_price__gt=0,
            product_type__code__in=COMPONENT_CODES,
        ).exclude(tenant_id__in=restricted_tenant_ids())
    ).filter(
        ~Q(product_type__code=ROOM_PRODUCT_CODE)
        | Q(room__establishment__product__status=TourismProduct.Status.PUBLISHED)
    )
    if city_id:
        query = query.filter(city_id=city_id)
    if product_type:
        query = query.filter(product_type__code=product_type)
    if search:
        query = query.filter(Q(name__icontains=search) | Q(tenant__trade_name__icontains=search))
    return query.order_by("-updated_at", "-id")


def owned_package(user, package_id, *, lock=False):
    query = CustomPackage.objects.filter(id=package_id, user=user)
    if lock:
        query = query.select_for_update()
    package = query.first()
    if package is None:
        raise NotFound("Paquete no encontrado.")
    return package


def ensure_editable(package):
    if PackagePurchase.objects.filter(package=package).exists():
        raise ValidationError("El paquete ya tiene una compra y no puede modificarse.")


def _configuration(package, values, *, exclude_id=None):
    start = values["start_date"]
    end = values.get("end_date")
    quantity = values["quantity"]
    guests = values.get("guests")
    departure_id = values.get("departure_id")
    product_id = values["product_id"]
    if start < package.start_date or start > package.end_date:
        raise ValidationError({"fecha_inicio": "La fecha debe estar dentro del viaje."})
    if end and (end <= start or end > package.end_date + timedelta(days=1)):
        raise ValidationError({"fecha_fin": "La salida debe estar dentro del viaje y después de la entrada."})
    if quantity > package.travelers and guests is None:
        raise ValidationError({"cantidad": "No puede exceder la cantidad de viajeros."})
    if guests is not None and guests > package.travelers:
        raise ValidationError({"huespedes": "No puede exceder la cantidad de viajeros."})
    product = TourismProduct.objects.select_related("product_type").filter(id=product_id).first()
    if product is None:
        raise NotFound("Producto no encontrado.")
    if product.product_type.code not in COMPONENT_CODES:
        raise ValidationError({"producto_id": "Elige un servicio individual; los paquetes de empresas se consultan por separado."})
    if product.product_type.code in departures.DEPARTURE_CODES and departure_id is None:
        day_slots = list(departures.slots_for_day(product_id, start))
        if any(not departures.is_legacy_daily(slot) for slot in day_slots):
            raise ValidationError({"salida_id": "Elige un horario concreto para este producto."})
        if not any(departures.is_legacy_daily(slot) and not slot.closed for slot in day_slots):
            raise ValidationError({"salida_id": "No hay salida ni disponibilidad diaria confirmable en esa fecha."})
    quote = bookings.build_quote(
        product_id=product_id, start=start, end=end, quantity=quantity,
        guests=guests, slot_id=departure_id,
    )
    if quote.product.currency.iso_code != "BOB":
        raise ValidationError({"producto_id": "Por ahora el paquete admite productos con precio en bolivianos."})
    if bookings.availability(quote) < quantity:
        raise ValidationError({"cantidad": "No hay cupos suficientes para esta fecha."})
    if quote.slot and quote.product.product_type.code in departures.DEPARTURE_CODES:
        others = PackageComponent.objects.filter(package=package, departure__isnull=False)
        if exclude_id:
            others = others.exclude(id=exclude_id)
        for other in others.select_related("departure"):
            if other.departure.start < quote.slot.end and quote.slot.start < other.departure.end:
                raise ValidationError({"salida_id": "Este horario se superpone con otro servicio del paquete."})
    return quote


def _values(component):
    return {
        "product_id": component.product_id,
        "start_date": component.start_date,
        "end_date": component.end_date,
        "quantity": component.quantity,
        "guests": component.guests,
        "departure_id": component.departure_id,
    }


def _message(detail):
    if isinstance(detail, dict):
        return "; ".join(_message(value) for value in detail.values())
    if isinstance(detail, list):
        return "; ".join(_message(value) for value in detail)
    return str(detail)


def evaluate(package):
    items = []
    warnings = []
    for component in package.components.select_related(
        "product__product_type", "product__tenant", "product__currency", "product__city", "departure"
    ):
        error = None
        current_total = None
        try:
            quote = _configuration(package, _values(component), exclude_id=component.id)
            current_total = quote.total
        except APIException as exc:
            error = _message(exc.detail)
            warnings.append(f"{component.product.name}: {error}")
        items.append({
            "id": component.id, "producto_id": component.product_id,
            "nombre": component.product.name, "tipo": component.product.product_type.name,
            "tipo_codigo": component.product.product_type.code,
            "empresa": component.product.tenant.trade_name,
            "ciudad": component.product.city.name,
            "imagen_url": component.product.image_url,
            "fecha_inicio": component.start_date, "fecha_fin": component.end_date,
            "cantidad": component.quantity, "huespedes": component.guests,
            "salida_id": component.departure_id,
            "inicio": component.departure.start if component.departure_id else None,
            "hora_inicio": timezone.localtime(component.departure.start).strftime("%H:%M") if component.departure_id else None,
            "precio_unitario": str(component.unit_price), "total": str(component.total),
            "total_actual": str(current_total) if current_total is not None else None,
            "disponible": error is None,
            "requiere_revalidacion": error is not None or current_total != component.total,
            "motivo": error,
        })
    return items, warnings


def package_data(package, *, detail=True):
    data = {
        "id": package.id, "nombre": package.name,
        "ciudad_id": package.city_id, "ciudad": package.city.name if package.city_id else None,
        "fecha_inicio": package.start_date, "fecha_fin": package.end_date,
        "personas": package.travelers, "estado": package.status,
        "total": str(package.total), "cantidad_servicios": package.components.count(),
        "creado_en": package.created_at, "actualizado_en": package.updated_at,
    }
    try:
        purchase = package.purchase
    except ObjectDoesNotExist:
        purchase = None
    data["compra"] = ({
        "id": purchase.id,
        "estado": purchase.status,
        "total": str(purchase.final_amount),
        "reservas": list(purchase.allocations.values_list("booking_id", flat=True)),
    } if purchase else None)
    if detail:
        components, warnings = evaluate(package)
        data.update(componentes=components, advertencias=warnings,
                    requiere_revalidacion=bool(warnings or any(c["requiere_revalidacion"] for c in components)))
    return data


@transaction.atomic
def create_package(user, data):
    return CustomPackage.objects.create(user=user, name=data["nombre"].strip(),
        city_id=data.get("ciudad_id"), start_date=data["fecha_inicio"],
        end_date=data["fecha_fin"], travelers=data["personas"])


@transaction.atomic
def update_package(user, package_id, data):
    package = owned_package(user, package_id, lock=True)
    ensure_editable(package)
    mapping = {"nombre": "name", "ciudad_id": "city_id", "fecha_inicio": "start_date",
               "fecha_fin": "end_date", "personas": "travelers"}
    for field, value in data.items():
        setattr(package, mapping[field], value.strip() if field == "nombre" else value)
    if package.end_date < package.start_date:
        raise ValidationError({"fecha_fin": "Debe ser igual o posterior a la fecha de inicio."})
    package.status = CustomPackage.Status.DRAFT
    package.save()
    _refresh_if_valid(package)
    return package


def _refresh_if_valid(package):
    """Recalcula automáticamente si todos los componentes aún son válidos."""
    quoted = []
    for component in package.components.all():
        try:
            quoted.append((component, _configuration(package, _values(component), exclude_id=component.id)))
        except APIException:
            return
    for component, quote in quoted:
        component.unit_price, component.total = quote.unit_price, quote.total
        component.save(update_fields=["unit_price", "total"])
    package.total = sum((quote.total for _, quote in quoted), 0)
    package.save(update_fields=["total", "updated_at"])


@transaction.atomic
def add_component(user, package_id, values):
    package = owned_package(user, package_id, lock=True)
    ensure_editable(package)
    if package.components.count() >= MAX_COMPONENTS:
        raise ValidationError({"componentes": f"El máximo es {MAX_COMPONENTS} servicios."})
    if package.components.filter(product_id=values["product_id"], start_date=values["start_date"],
                                 end_date=values.get("end_date"), departure_id=values.get("departure_id")).exists():
        raise ValidationError({"producto_id": "Ese servicio con las mismas fechas y horario ya está incluido."})
    quote = _configuration(package, values)
    PackageComponent.objects.create(
        package=package, product=quote.product, start_date=quote.start, end_date=quote.end if quote.is_room else None,
        quantity=quote.quantity, guests=quote.guests, departure=quote.slot,
        unit_price=quote.unit_price, total=quote.total,
    )
    package.total = sum((item.total for item in package.components.all()), 0)
    package.status = CustomPackage.Status.DRAFT
    package.save(update_fields=["total", "status", "updated_at"])
    return package


@transaction.atomic
def update_component(user, package_id, component_id, changes):
    package = owned_package(user, package_id, lock=True)
    ensure_editable(package)
    component = package.components.filter(id=component_id).first()
    if component is None:
        raise NotFound("Servicio no encontrado en este paquete.")
    values = _values(component) | changes
    quote = _configuration(package, values, exclude_id=component.id)
    duplicate = package.components.exclude(id=component.id).filter(
        product_id=values["product_id"], start_date=values["start_date"],
        end_date=values.get("end_date"), departure_id=values.get("departure_id"),
    ).exists()
    if duplicate:
        raise ValidationError({"producto_id": "Ese servicio con las mismas fechas y horario ya está incluido."})
    component.product = quote.product
    component.start_date = quote.start
    component.end_date = quote.end if quote.is_room else None
    component.quantity = quote.quantity
    component.guests = quote.guests
    component.departure = quote.slot
    component.unit_price = quote.unit_price
    component.total = quote.total
    component.save()
    package.total = sum((item.total for item in package.components.all()), 0)
    package.status = CustomPackage.Status.DRAFT
    package.save(update_fields=["total", "status", "updated_at"])
    return package


@transaction.atomic
def remove_component(user, package_id, component_id):
    package = owned_package(user, package_id, lock=True)
    ensure_editable(package)
    if not package.components.filter(id=component_id).exists():
        raise NotFound("Servicio no encontrado en este paquete.")
    package.components.filter(id=component_id).delete()
    package.total = sum((item.total for item in package.components.all()), 0)
    package.status = CustomPackage.Status.DRAFT
    package.save(update_fields=["total", "status", "updated_at"])
    return package


@transaction.atomic
def validate_package(user, package_id, *, save=False):
    package = owned_package(user, package_id, lock=True)
    components = list(package.components.all())
    if not components:
        raise ValidationError({"componentes": "Agrega al menos un servicio."})
    quotes = []
    problems = []
    for component in components:
        try:
            quotes.append((component, _configuration(package, _values(component), exclude_id=component.id)))
        except APIException as exc:
            problems.append({"componente_id": component.id, "motivo": exc.detail})
    if problems:
        raise ValidationError({"componentes": problems})
    for component, quote in quotes:
        component.unit_price, component.total = quote.unit_price, quote.total
        component.save(update_fields=["unit_price", "total"])
    package.total = sum((quote.total for _, quote in quotes), 0)
    package.status = CustomPackage.Status.SAVED if save else CustomPackage.Status.DRAFT
    package.save(update_fields=["total", "status", "updated_at"])
    return package
