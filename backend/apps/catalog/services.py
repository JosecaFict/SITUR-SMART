from django.db import transaction
from django.db.models import Count, Min, Q
from django.utils.text import slugify
from rest_framework.exceptions import NotFound, ValidationError

from apps.audit.services import record_audit
from apps.rbac.services import require_permission, require_tenant_access
from apps.tenancy.models import City
from apps.tenancy.services import ensure_product_quota_available

from .models import (
    AVAILABLE_LODGING_TYPE_CODES,
    HOTEL_PRODUCT_CODE,
    LODGING_PRODUCT_CODES,
    ROOM_PRODUCT_CODE,
    UNSUPPORTED_LODGING_TYPE_MESSAGE,
    Currency,
    LodgingEstablishment,
    LodgingType,
    ProductType,
    Room,
    TourismProduct,
)


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
    ensure_product_quota_available(tenant_id)
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
    product = (
        TourismProduct.objects.select_related("product_type")
        .filter(tenant_id=tenant_id, id=product_id)
        .first()
    )
    if product is None:
        raise NotFound("Producto no encontrado en esta empresa.")
    # El tipo no viaja en un PATCH parcial, asi que se mira el del producto: sin
    # esto se podria editar el precio de un hotel por la via generica y dejarlo
    # compitiendo con el precio "desde" calculado de sus habitaciones.
    if product.product_type.code in LODGING_PRODUCT_CODES:
        raise ValidationError(
            {
                "tipo_codigo": (
                    "Este producto es un hospedaje. Edítalo en "
                    "/api/v1/hospedajes/ o /api/v1/habitaciones/."
                )
            }
        )
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


# ============================================================
# HOSPEDAJE
# ============================================================
# Un establecimiento y una habitacion son cada uno un producto_turistico mas
# una fila en su tabla especializada. Estos servicios escriben las dos a la vez
# dentro de una transaccion, para que no quede un producto HOTEL sin
# establecimiento ni un producto HABITACION colgando de la nada.

_LODGING_FIELDS = {
    "direccion": "address",
    "categoria_estrellas": "star_rating",
    "hora_check_in": "check_in",
    "hora_check_out": "check_out",
    "servicios": "services",
}

_ROOM_FIELDS = {
    "cantidad_habitaciones": "quantity",
    "capacidad_adultos": "adults_capacity",
    "capacidad_ninos": "children_capacity",
    "tipo_cama": "bed_type",
    "incluye_desayuno": "includes_breakfast",
}

_LODGING_RELATED = (
    "lodging_type", "tenant", "product__product_type",
    "product__city__country", "product__currency",
)

_ROOM_RELATED = (
    "tenant", "establishment__product", "product__product_type",
    "product__city__country", "product__currency",
)


def _split_specifics(data: dict, mapping: dict) -> dict:
    """Separa los campos de la tabla especializada de los del producto base."""
    return {mapping[key]: data.pop(key) for key in list(data) if key in mapping}


def _lodging_type(code: str) -> LodgingType:
    """Resuelve el tipo de hospedaje reaplicando el limite de la fase.

    ``LodgingWriteSerializer`` ya lo valida, asi que en la via HTTP esto no se
    alcanza nunca. Existe para cualquier otro llamador -- un comando de gestion,
    un shell, una tarea futura -- de modo que la regla no dependa de pasar por
    un serializer.
    """
    if code not in AVAILABLE_LODGING_TYPE_CODES:
        # Lista, no cadena: asi "details" sale igual que por la via del
        # serializer y quien consume la API ve una sola forma de error.
        raise ValidationError({"tipo_hospedaje_codigo": [UNSUPPORTED_LODGING_TYPE_MESSAGE]})
    return LodgingType.objects.get(code=code)


def _check_room_capacity(*, max_capacity: int, adults: int, children: int) -> None:
    """Comprueba los topes individuales contra el tope total.

    Los tres valores son limites alternativos, no un desglose:

    * ``capacidad_maxima`` es el maximo de ocupantes de la habitacion;
    * ``capacidad_adultos`` es el maximo de adultos admitido;
    * ``capacidad_ninos`` es el maximo de ninos admitido.

    Por eso NO se exige ``adultos + ninos <= maxima``. Una habitacion con tope 4,
    hasta 4 adultos y hasta 3 ninos es valida: son combinaciones alternativas y
    nunca se ocupan las dos a la vez. La suma se valida al reservar
    (``adultos_solicitados + ninos_solicitados <= capacidad_maxima``, respetando
    ademas cada tope individual), no al configurar la habitacion.
    """
    errors = {}
    if adults > max_capacity:
        errors["capacidad_adultos"] = [
            f"No puede superar la capacidad total de la habitación ({max_capacity})."
        ]
    if children > max_capacity:
        errors["capacidad_ninos"] = [
            f"No puede superar la capacidad total de la habitación ({max_capacity})."
        ]
    if errors:
        raise ValidationError(errors)


def _check_room_price(*, status: str, price) -> None:
    """Una habitacion publicada no puede costar 0.

    El precio publico de un hotel es el menor precio positivo de sus
    habitaciones publicadas; admitir un 0 haria aparecer "Habitaciones desde
    Bs 0". En borrador si se permite, para poder guardarla a medio cargar.
    """
    if status == TourismProduct.Status.PUBLISHED and price is not None and price <= 0:
        raise ValidationError(
            {
                "precio_base": [
                    "Una habitación publicada debe tener un precio por noche mayor a 0."
                ]
            }
        )


def _has_publishable_room(lodging_id: int) -> bool:
    return Room.objects.filter(
        establishment_id=lodging_id,
        product__status=TourismProduct.Status.PUBLISHED,
        product__base_price__gt=0,
    ).exists()


def _check_lodging_publishable(lodging_id: int) -> None:
    """Un hotel solo se publica si tiene de donde sacar su precio.

    En borrador puede existir sin habitaciones; publicado, no, porque la tarjeta
    del Marketplace no tendria precio que mostrar.
    """
    if not _has_publishable_room(lodging_id):
        raise ValidationError(
            {
                "estado": [
                    "Para publicar un hospedaje necesita al menos una habitación "
                    "publicada con precio mayor a 0: su precio público se calcula "
                    "a partir de ellas."
                ]
            }
        )


def with_from_price(queryset, *, published_rooms_only: bool = True):
    """Agrega el precio "desde" de cada establecimiento y su conteo.

    Es el ``precio_base`` de su habitacion mas economica. En el Marketplace solo
    cuentan las publicadas; en el panel empresarial tambien los borradores, para
    que la empresa vea el precio de lo que todavia no publico.

    El conteo y el precio usan filtros distintos a proposito: una habitacion sin
    precio igual se cuenta (existe y la empresa debe verla), pero no puede fijar
    el precio "desde".
    """
    status_filter = (
        Q(rooms__product__status=TourismProduct.Status.PUBLISHED)
        if published_rooms_only
        else ~Q(rooms__product__status=TourismProduct.Status.INACTIVE)
    )
    return queryset.annotate(
        from_price=Min(
            "rooms__product__base_price",
            filter=status_filter & Q(rooms__product__base_price__gt=0),
        ),
        rooms_count=Count("rooms", filter=status_filter, distinct=True),
    )


def _company_lodgings(tenant_id: int):
    return with_from_price(
        LodgingEstablishment.objects.select_related(*_LODGING_RELATED).filter(tenant_id=tenant_id),
        published_rooms_only=False,
    )


def with_lodging_from_price(queryset):
    """Agrega el precio "desde" a los productos que son un establecimiento.

    Lo usa el Marketplace generico, donde un hotel aparece junto a tours y
    restaurantes: sin esto mostraria su precio_base, que en un hospedaje es 0.
    Para cualquier otro tipo de producto la anotacion queda nula.
    """
    return queryset.annotate(
        from_price=Min(
            "lodging__rooms__product__base_price",
            filter=Q(
                lodging__rooms__product__status=TourismProduct.Status.PUBLISHED,
                lodging__rooms__product__base_price__gt=0,
            ),
        )
    )


def only_complete_lodging_products(queryset):
    """Deja fuera los productos de hospedaje sin su ficha especializada.

    Antes de este modulo se podian crear productos HOTEL y HABITACION sueltos
    por /api/v1/productos/. Una habitacion asi no tiene hotel, ni empresa
    responsable que mostrar, ni ubicacion heredada, y la migracion 0005 no puede
    repararla porque no existe dato que diga a que hotel pertenecia. Tampoco
    puede repararse desde el panel. Queda fuera del Marketplace.

    Un hotel sin ficha tambien se excluye: 0005 le crea una a todos los
    existentes, asi que en la practica no deberia haber ninguno, pero el filtro
    evita que uno colado se muestre con un precio que no significa nada.

    Todas las relaciones son de un solo valor -- FK directa a tipo_producto y
    OneToOne inverso a habitacion y establecimiento -- asi que el filtro no
    multiplica filas: no hace falta distinct() y la paginacion, el orden y el
    resto de los filtros siguen funcionando igual.
    """
    return queryset.filter(
        ~Q(product_type__code__in=LODGING_PRODUCT_CODES)
        | Q(product_type__code=HOTEL_PRODUCT_CODE, lodging__isnull=False)
        | Q(
            product_type__code=ROOM_PRODUCT_CODE,
            room__isnull=False,
            room__establishment__product__status=TourismProduct.Status.PUBLISHED,
        )
    )


def list_company_lodgings(*, actor, tenant_id: int):
    require_tenant_access(actor, tenant_id)
    require_permission(actor, "PRODUCTOS_LEER", tenant_id)
    return _company_lodgings(tenant_id)


def get_company_lodging(*, actor, tenant_id: int, lodging_id: int) -> LodgingEstablishment:
    lodging = (
        list_company_lodgings(actor=actor, tenant_id=tenant_id).filter(id=lodging_id).first()
    )
    if lodging is None:
        raise NotFound("Hospedaje no encontrado en esta empresa.")
    return lodging


@transaction.atomic
def create_lodging(*, actor, tenant_id: int, request=None, **data) -> LodgingEstablishment:
    require_tenant_access(actor, tenant_id)
    require_permission(actor, "PRODUCTOS_GESTIONAR", tenant_id)
    ensure_product_quota_available(tenant_id)

    type_code = data.pop("tipo_hospedaje_codigo", LodgingType.Code.HOTEL)
    lodging_type = _lodging_type(type_code)
    specifics = _split_specifics(data, _LODGING_FIELDS)
    requested_code = data.pop("codigo", None)

    values = _relations(data)
    values["product_type"] = ProductType.objects.get(code=HOTEL_PRODUCT_CODE)
    values["code"] = _unique_product_code(tenant_id, values["name"], requested_code)
    values.setdefault("status", TourismProduct.Status.DRAFT)
    # Un hospedaje recien creado no tiene habitaciones, asi que no hay precio
    # que mostrar: no puede nacer publicado.
    if values["status"] == TourismProduct.Status.PUBLISHED:
        raise ValidationError(
            {
                "estado": [
                    "Un hospedaje nuevo todavía no tiene habitaciones, así que no "
                    "puede publicarse. Guárdalo como borrador, registra al menos "
                    "una habitación publicada con precio mayor a 0 y publícalo después."
                ]
            }
        )
    # El precio de un hotel es el de su habitacion publicada mas barata, que se
    # calcula en consulta. precio_base queda en 0 para no competir con ese dato.
    values["base_price"] = 0

    product = TourismProduct.objects.create(tenant_id=tenant_id, **values)
    lodging = LodgingEstablishment.objects.create(
        product=product, tenant_id=tenant_id, lodging_type=lodging_type, **specifics
    )
    record_audit(
        actor=actor, tenant_id=tenant_id, action="CREAR", entity="establecimiento_hospedaje",
        entity_id=str(lodging.id),
        new_data={"producto_id": product.id, "nombre": product.name, "tipo": lodging_type.code},
        request=request,
    )
    # Se relee por la consulta anotada: el serializer espera from_price y
    # rooms_count, que la instancia recien creada todavia no trae.
    return _company_lodgings(tenant_id).get(id=lodging.id)


@transaction.atomic
def update_lodging(*, actor, tenant_id: int, lodging_id: int, request=None, **data) -> LodgingEstablishment:
    lodging = get_company_lodging(actor=actor, tenant_id=tenant_id, lodging_id=lodging_id)
    require_permission(actor, "PRODUCTOS_GESTIONAR", tenant_id)

    if type_code := data.pop("tipo_hospedaje_codigo", None):
        lodging.lodging_type = _lodging_type(type_code)
    specifics = _split_specifics(data, _LODGING_FIELDS)
    data.pop("codigo", None)
    data.pop("precio_base", None)  # El hotel no fija precio propio.

    # Solo se comprueba en la transicion a publicado: un hotel ya publicado
    # puede seguir editandose aunque sus habitaciones hayan cambiado.
    nuevo_estado = data.get("estado")
    if (
        nuevo_estado == TourismProduct.Status.PUBLISHED
        and lodging.product.status != TourismProduct.Status.PUBLISHED
    ):
        _check_lodging_publishable(lodging.id)

    previous = {"nombre": lodging.product.name, "estado": lodging.product.status}
    for field, value in specifics.items():
        setattr(lodging, field, value)
    if specifics or type_code:
        lodging.save(update_fields=[*specifics.keys(), *(["lodging_type"] if type_code else [])])

    product_values = _relations(data)
    if product_values:
        for field, value in product_values.items():
            setattr(lodging.product, field, value)
        lodging.product.save(update_fields=[*product_values.keys(), "updated_at"])

    record_audit(
        actor=actor, tenant_id=tenant_id, action="ACTUALIZAR", entity="establecimiento_hospedaje",
        entity_id=str(lodging.id), previous_data=previous,
        new_data={"nombre": lodging.product.name, "estado": lodging.product.status},
        request=request,
    )
    return lodging


def deactivate_lodging(*, actor, tenant_id: int, lodging_id: int, request=None) -> LodgingEstablishment:
    """Desactiva el producto del hotel.

    No hace falta desactivar sus habitaciones: las consultas publicas exigen que
    el establecimiento este publicado, asi que dejan de aparecer solas.
    """
    return update_lodging(
        actor=actor, tenant_id=tenant_id, lodging_id=lodging_id,
        estado=TourismProduct.Status.INACTIVE, request=request,
    )


def list_lodging_rooms(*, actor, tenant_id: int, lodging_id: int):
    lodging = get_company_lodging(actor=actor, tenant_id=tenant_id, lodging_id=lodging_id)
    return Room.objects.select_related(*_ROOM_RELATED).filter(establishment=lodging)


def get_company_room(*, actor, tenant_id: int, room_id: int) -> Room:
    require_tenant_access(actor, tenant_id)
    require_permission(actor, "PRODUCTOS_LEER", tenant_id)
    room = (
        Room.objects.select_related(*_ROOM_RELATED)
        .filter(id=room_id, tenant_id=tenant_id)
        .first()
    )
    if room is None:
        raise NotFound("Habitación no encontrada en esta empresa.")
    return room


@transaction.atomic
def create_room(*, actor, tenant_id: int, lodging_id: int, request=None, **data) -> Room:
    lodging = get_company_lodging(actor=actor, tenant_id=tenant_id, lodging_id=lodging_id)
    require_permission(actor, "PRODUCTOS_GESTIONAR", tenant_id)
    ensure_product_quota_available(tenant_id)

    specifics = _split_specifics(data, _ROOM_FIELDS)
    # Los valores por omision replican los DEFAULT de la tabla habitacion.
    _check_room_capacity(
        max_capacity=data["capacidad_maxima"],
        adults=specifics.get("adults_capacity", 2),
        children=specifics.get("children_capacity", 0),
    )
    _check_room_price(
        status=data.get("estado", TourismProduct.Status.DRAFT),
        price=data.get("precio_base"),
    )
    requested_code = data.pop("codigo", None)
    data.setdefault("moneda_codigo", lodging.product.currency.iso_code)

    values = _relations(data)
    values["product_type"] = ProductType.objects.get(code=ROOM_PRODUCT_CODE)
    # La ubicacion se hereda del establecimiento y no se pide en el formulario:
    # asi una habitacion nunca puede quedar publicada en otra ciudad que su hotel.
    values["city_id"] = lodging.product.city_id
    values["locality"] = lodging.product.locality
    values["code"] = _unique_product_code(tenant_id, values["name"], requested_code)
    values.setdefault("status", TourismProduct.Status.DRAFT)

    product = TourismProduct.objects.create(tenant_id=tenant_id, **values)
    room = Room.objects.create(
        product=product, establishment=lodging, tenant_id=tenant_id, **specifics
    )
    record_audit(
        actor=actor, tenant_id=tenant_id, action="CREAR", entity="habitacion",
        entity_id=str(room.id),
        new_data={
            "producto_id": product.id, "nombre": product.name,
            "establecimiento_id": lodging.id, "precio_noche": str(product.base_price),
        },
        request=request,
    )
    return room


@transaction.atomic
def update_room(*, actor, tenant_id: int, room_id: int, request=None, **data) -> Room:
    room = get_company_room(actor=actor, tenant_id=tenant_id, room_id=room_id)
    require_permission(actor, "PRODUCTOS_GESTIONAR", tenant_id)

    specifics = _split_specifics(data, _ROOM_FIELDS)
    # Se comparan los valores ya guardados con los que llegan en el PATCH: una
    # edicion parcial tampoco puede dejar la habitacion en un estado imposible.
    _check_room_capacity(
        max_capacity=data.get("capacidad_maxima", room.product.max_capacity),
        adults=specifics.get("adults_capacity", room.adults_capacity),
        children=specifics.get("children_capacity", room.children_capacity),
    )
    _check_room_price(
        status=data.get("estado", room.product.status),
        price=data.get("precio_base", room.product.base_price),
    )
    data.pop("codigo", None)
    # Mover una habitacion de hotel cambiaria su ubicacion heredada; no se permite.
    data.pop("ciudad_id", None)
    data.pop("localidad", None)

    previous = {"nombre": room.product.name, "estado": room.product.status}
    for field, value in specifics.items():
        setattr(room, field, value)
    if specifics:
        room.save(update_fields=[*specifics.keys()])

    product_values = _relations(data)
    if product_values:
        for field, value in product_values.items():
            setattr(room.product, field, value)
        room.product.save(update_fields=[*product_values.keys(), "updated_at"])

    record_audit(
        actor=actor, tenant_id=tenant_id, action="ACTUALIZAR", entity="habitacion",
        entity_id=str(room.id), previous_data=previous,
        new_data={"nombre": room.product.name, "estado": room.product.status},
        request=request,
    )
    return room


def deactivate_room(*, actor, tenant_id: int, room_id: int, request=None) -> Room:
    return update_room(
        actor=actor, tenant_id=tenant_id, room_id=room_id,
        estado=TourismProduct.Status.INACTIVE, request=request,
    )


# ---- Consultas publicas -------------------------------------------------
# Una oferta de hospedaje se muestra solo si el producto esta publicado y la
# empresa activa. Para una habitacion se exige ademas que su establecimiento
# siga publicado, de modo que al desactivar un hotel desaparezcan con el.

def public_lodgings():
    return with_from_price(
        LodgingEstablishment.objects.select_related(*_LODGING_RELATED).filter(
            product__status=TourismProduct.Status.PUBLISHED,
            product__tenant__status="ACTIVO",
        )
    )


def get_public_lodging(lodging_id: int) -> LodgingEstablishment:
    lodging = public_lodgings().filter(id=lodging_id).first()
    if lodging is None:
        raise NotFound("Hospedaje no encontrado.")
    return lodging


def public_rooms():
    return Room.objects.select_related(*_ROOM_RELATED).filter(
        product__status=TourismProduct.Status.PUBLISHED,
        product__tenant__status="ACTIVO",
        establishment__product__status=TourismProduct.Status.PUBLISHED,
    )


def get_public_room(room_id: int) -> Room:
    room = public_rooms().filter(id=room_id).first()
    if room is None:
        raise NotFound("Habitación no encontrada.")
    return room
