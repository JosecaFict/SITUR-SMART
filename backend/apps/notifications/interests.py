"""Notificaciones inteligentes de ofertas segun los intereses del turista.

Los intereses se detectan con lo que el turista ya hizo en la plataforma:
favoritos, reservas y resenas bien calificadas. No hay tabla propia: el perfil
se calcula al momento, asi siempre refleja lo ultimo que hizo.

Es un recomendador basado en contenido. Cada accion del turista es una senal
sobre un producto, y ese producto tiene ciudad y tipo (hotel, tour,
experiencia...). Cuando una empresa publica una promocion, se compara la
promocion con las senales de cada turista y se calcula una afinidad:

- misma oferta (el mismo producto)      -> peso de la senal + bono
- misma ciudad y mismo tipo             -> peso completo
- misma ciudad                          -> mitad del peso
- mismo tipo, otra ciudad               -> un tercio del peso

Solo se avisa a quien supera MIN_SCORE, y cada aviso lleva el motivo mas
fuerte para que el turista entienda por que le llego.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.accounts.models import User
from apps.bookings.models import BookingDetail, BookingState
from apps.bookings.services import OCCUPYING_STATES
from apps.catalog.models import ROOM_PRODUCT_CODE, ProductReview
from apps.favorites.models import Favorite

from . import marketing
from .models import Notification
from .services import notify

OFFER_KIND = "OFERTA_INTERES"

# Cuanto vale cada accion. Guardar en favoritos es la senal mas directa.
WEIGHTS = {"favorito": 3.0, "reserva": 2.0, "resena": 1.5}
SAME_PRODUCT_BONUS = 2.0
MIN_SCORE = 2.0
DAILY_LIMIT = 3
GOOD_RATING = 4

# Reservas que cuentan como interes real (no las vencidas ni canceladas).
INTEREST_BOOKING_STATES = (*OCCUPYING_STATES,)
# Reservas activas: quien ya tiene una del producto en oferta no recibe el aviso.
ACTIVE_BOOKING_STATES = (BookingState.CREATED, *OCCUPYING_STATES)

PRODUCT_RELATED = (
    "product_type",
    "city",
    "room__establishment__product__product_type",
    "room__establishment__product__city",
)


@dataclass(frozen=True)
class Item:
    """Un producto visto como interes: una habitacion cuenta como su hotel."""

    id: int
    name: str
    city_id: int
    city: str
    type_id: int
    type_name: str


@dataclass(frozen=True)
class Signal:
    user_id: int
    source: str  # favorito | reserva | resena
    item: Item


def _item(product) -> Item:
    if product.product_type.code == ROOM_PRODUCT_CODE:
        product = product.room.establishment.product
    return Item(
        id=product.id,
        name=product.name,
        city_id=product.city_id,
        city=product.city.name,
        type_id=product.product_type_id,
        type_name=product.product_type.name,
    )


def _related(prefix: str) -> list[str]:
    return [f"{prefix}__{path}" for path in PRODUCT_RELATED]


def _signals(*, user_id: int | None = None, product_filter: Q | None = None) -> list[Signal]:
    """Lee las senales de favoritos, reservas y resenas.

    ``product_filter`` usa rutas relativas al producto (city_id__in=...), asi la
    misma condicion sirve para las tres fuentes.
    """

    def scoped(queryset, user_field: str, product_prefix: str):
        if user_id is not None:
            queryset = queryset.filter(**{user_field: user_id})
        if product_filter is not None:
            queryset = queryset.filter(_prefixed(product_filter, product_prefix))
        return queryset

    signals: list[Signal] = []

    favorites = scoped(Favorite.objects.select_related(*_related("product")), "user_id", "product")
    signals += [Signal(row.user_id, "favorito", _item(row.product)) for row in favorites]

    details = scoped(
        BookingDetail.objects.filter(booking__status__in=INTEREST_BOOKING_STATES).select_related(
            "booking__order__customer", *_related("slot__product")
        ),
        "booking__order__customer__user_id",
        "slot__product",
    )
    signals += [
        Signal(row.booking.order.customer.user_id, "reserva", _item(row.slot.product)) for row in details
    ]

    reviews = scoped(
        ProductReview.objects.filter(rating__gte=GOOD_RATING).select_related(*_related("product")),
        "user_id",
        "product",
    )
    signals += [Signal(row.user_id, "resena", _item(row.product)) for row in reviews]
    return signals


def _prefixed(condition: Q, prefix: str) -> Q:
    """Copia un Q anteponiendo ``prefix__`` a cada campo."""
    copy = Q()
    copy.connector = condition.connector
    copy.negated = condition.negated
    for child in condition.children:
        if isinstance(child, Q):
            copy.children.append(_prefixed(child, prefix))
        else:
            field, value = child
            copy.children.append((f"{prefix}__{field}", value))
    return copy


# --- Perfil del turista (lo que ve en "Mis intereses") -------------------------


def customer_interests(user) -> dict:
    """Ciudades y tipos que le interesan al turista, con puntaje de 0 a 100."""
    signals = _signals(user_id=user.id)
    cities: dict[str, float] = defaultdict(float)
    types: dict[str, float] = defaultdict(float)
    counts = {"favoritos": 0, "reservas": 0, "resenas": 0}
    seen: set[tuple[str, int]] = set()
    for signal in signals:
        weight = WEIGHTS[signal.source]
        cities[signal.item.city] += weight
        types[signal.item.type_name] += weight
        key = (signal.source, signal.item.id)
        if key not in seen:
            seen.add(key)
            counts[{"favorito": "favoritos", "reserva": "reservas", "resena": "resenas"}[signal.source]] += 1

    def ranked(scores: dict[str, float]) -> list[dict]:
        if not scores:
            return []
        top = max(scores.values())
        ordered = sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))[:5]
        return [{"nombre": name, "puntaje": round(score * 100 / top)} for name, score in ordered]

    return {"ciudades": ranked(cities), "tipos": ranked(types), "basado_en": counts}


# --- Emparejar una promocion con los turistas ----------------------------------


def _promotion_items(promotion) -> list[Item]:
    if promotion.product_id:
        products = [promotion.product]
    else:
        products = [component.product for component in promotion.components.all()]
    items: dict[int, Item] = {}
    for product in products:
        item = _item(product)
        items[item.id] = item
    return list(items.values())


def _affinity(signal: Signal, targets: list[Item]) -> tuple[float, str] | None:
    """Puntaje de una senal contra la oferta y el motivo para mostrar."""
    weight = WEIGHTS[signal.source]
    best: tuple[float, str] | None = None
    for target in targets:
        same_city = signal.item.city_id == target.city_id
        same_type = signal.item.type_id == target.type_id
        if signal.item.id == target.id:
            score = weight + SAME_PRODUCT_BONUS
        elif same_city and same_type:
            score = weight
        elif same_city:
            score = weight / 2
        elif same_type:
            score = weight / 3
        else:
            continue
        if best is None or score > best[0]:
            best = (score, _reason(signal, target, same_product=signal.item.id == target.id))
    return best


def _reason(signal: Signal, target: Item, *, same_product: bool) -> str:
    item = signal.item
    if signal.source == "favorito":
        return f"guardaste {item.name} en favoritos" if same_product else f"tienes {item.name} ({item.city}) en favoritos"
    if signal.source == "reserva":
        return f"ya reservaste {item.name}" if same_product else f"reservaste {item.name} en {item.city}"
    return f"calificaste bien {item.name}"


def _excluded_users(promotion, targets: list[Item], candidate_ids: set[int]) -> set[int]:
    now = timezone.now()
    already = set(
        Notification.objects.filter(
            kind=OFFER_KIND, data__promocion_id=promotion.id, user_id__in=candidate_ids
        ).values_list("user_id", flat=True)
    )
    over_limit = set(
        Notification.objects.filter(
            kind=OFFER_KIND, created_at__gte=now - timedelta(days=1), user_id__in=candidate_ids
        )
        .values("user_id")
        .annotate(total=Count("id"))
        .filter(total__gte=DAILY_LIMIT)
        .values_list("user_id", flat=True)
    )
    target_ids = [item.id for item in targets]
    booked = set(
        BookingDetail.objects.filter(
            Q(slot__product_id__in=target_ids) | Q(slot__product__room__establishment__product_id__in=target_ids),
            booking__status__in=ACTIVE_BOOKING_STATES,
            slot__start__gte=now,
            booking__order__customer__user_id__in=candidate_ids,
        ).values_list("booking__order__customer__user_id", flat=True)
    )
    return already | over_limit | booked


def _eligible_users(promotion, user_ids: set[int]) -> dict[int, User]:
    """Turistas activos; nunca el personal de la empresa que publica."""
    users = (
        User.objects.filter(id__in=user_ids, status=User.Status.ACTIVE, customer_profile__isnull=False)
        .exclude(user_roles__tenant_id=promotion.tenant_id)
        .distinct()
    )
    return {user.id: user for user in users}


def notify_interested(promotion) -> int:
    """Avisa a los turistas a los que les encaja la promocion. Devuelve cuantos."""
    if promotion.state_at() not in ("VIGENTE", "PROGRAMADA"):
        return 0
    targets = _promotion_items(promotion)
    if not targets:
        return 0

    city_ids = {item.city_id for item in targets}
    type_ids = {item.type_id for item in targets}
    target_ids = {item.id for item in targets}
    product_filter = (
        Q(city_id__in=city_ids)
        | Q(product_type_id__in=type_ids)
        | Q(id__in=target_ids)
        | Q(room__establishment__product_id__in=target_ids)
    )

    scores: dict[int, float] = defaultdict(float)
    reasons: dict[int, tuple[float, str]] = {}
    for signal in _signals(product_filter=product_filter):
        result = _affinity(signal, targets)
        if result is None:
            continue
        score, reason = result
        scores[signal.user_id] += score
        if signal.user_id not in reasons or score > reasons[signal.user_id][0]:
            reasons[signal.user_id] = (score, reason)

    candidates = {user_id for user_id, score in scores.items() if score >= MIN_SCORE}
    if not candidates:
        return 0
    candidates -= _excluded_users(promotion, targets, candidates)
    users = _eligible_users(promotion, candidates)

    percentage = f"{promotion.percentage.normalize():f}"
    until = timezone.localtime(promotion.ends_at).strftime("%d/%m/%Y")
    sent = 0
    for user_id, user in users.items():
        reason = reasons[user_id][1]
        with transaction.atomic():
            User.objects.select_for_update().get(pk=user_id)
            if user_id not in marketing.eligible_ids([user_id], promotion.tenant_id):
                continue
            if Notification.objects.filter(user_id=user_id, kind=OFFER_KIND, data__promocion_id=promotion.id).exists():
                continue
            notify(
                user=user, kind=OFFER_KIND,
                title=f"{percentage}% de descuento en {promotion.name}"[:150],
                message=f"Te avisamos porque {reason}. Válido hasta el {until}.",
                data={"promocion_id": promotion.id, "empresa_id": promotion.tenant_id,
                      "remitente": promotion.tenant.trade_name,
                      "vence_en": promotion.ends_at.isoformat(), "tipo_comunicacion": "PROMOCIONAL",
                      "afinidad": round(scores[user_id], 2), "motivo": reason},
            )
            sent += 1
    return sent
