"""Indicadores del dashboard: ventas, reservas, ocupacion y opinion de clientes.

Un mismo calculo sirve a dos vistas:

* La empresa ve solo lo suyo (``X-Tenant-ID`` y permiso REPORTES_TENANT).
* El SuperAdmin ve toda la plataforma o las empresas que elija; con dos o mas
  recibe ademas una comparacion lado a lado.

Los importes se suman en bolivianos: es la moneda de todo el catalogo y la que
usa el resto de la plataforma (paquetes, promociones, planes). Las consultas
agrupan en la base y devuelven pocas filas; las funciones puras de abajo solo
arman la respuesta y se prueban sin base de datos.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Avg, Count, F, Max, Min, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import CustomerProfile
from apps.bookings.models import Booking, BookingDetail, BookingState, CustomerReport
from apps.catalog.models import Availability, ProductReview, TourismProduct
from apps.payments.models import Payment, Refund
from apps.promotions.models import Promotion
from apps.tenancy.models import Subscription, Tenant

from .services import report_scope

CURRENCY = "BOB"
MONTHS = 6
MAX_COMPARED = 4
ZERO = Decimal("0")
# Reservas que ocupan cupo y cuentan como venta.
SOLD = (BookingState.CONFIRMED, BookingState.PARTIAL, BookingState.COMPLETED)
STATE_ORDER = (
    (BookingState.CONFIRMED, "Confirmadas"),
    (BookingState.COMPLETED, "Completadas"),
    (BookingState.PARTIAL, "Pago parcial"),
    (BookingState.CREATED, "Pendientes de pago"),
    (BookingState.CANCELLED, "Canceladas"),
    (BookingState.EXPIRED, "Vencidas"),
)
MONTH_NAMES = ("Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")


@dataclass(frozen=True)
class Period:
    """Mes en curso, el anterior y el inicio de la serie de seis meses."""

    now: datetime
    month_start: datetime
    previous_start: datetime
    series_start: datetime

    @classmethod
    def current(cls, now: datetime | None = None) -> Period:
        now = timezone.localtime(now or timezone.now())
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return cls(
            now=now,
            month_start=month_start,
            previous_start=shift_month(month_start, -1),
            series_start=shift_month(month_start, -(MONTHS - 1)),
        )

    def months(self) -> list[datetime]:
        return [shift_month(self.series_start, step) for step in range(MONTHS)]


def shift_month(moment: datetime, months: int) -> datetime:
    index = moment.year * 12 + moment.month - 1 + months
    return moment.replace(year=index // 12, month=index % 12 + 1, day=1)


# ---------------------------------------------------------------- funciones puras


def parse_companies(raw: str | None) -> list[int]:
    """``?empresas=3,7`` -> [3, 7]. Solo el SuperAdmin la usa."""
    if not raw:
        return []
    try:
        ids = sorted({int(part) for part in raw.split(",") if part.strip()})
    except ValueError as exc:
        raise ValidationError({"empresas": "Indica las empresas por su número, separadas por coma."}) from exc
    if any(company_id <= 0 for company_id in ids):
        raise ValidationError({"empresas": "Indica las empresas por su número, separadas por coma."})
    if len(ids) > MAX_COMPARED:
        raise ValidationError({"empresas": f"Puedes comparar hasta {MAX_COMPARED} empresas a la vez."})
    return ids


def variation(current: Decimal | int, previous: Decimal | int) -> float | None:
    """Cambio porcentual respecto al mes anterior; None si no hay base."""
    if not previous:
        return None
    return round(float((Decimal(current) - Decimal(previous)) * 100 / Decimal(previous)), 1)


def percentage(part: Decimal | int, total: Decimal | int) -> float | None:
    if not total:
        return None
    return round(float(Decimal(part) * 100 / Decimal(total)), 1)


def money(value: Decimal | None) -> str:
    return f"{(value or ZERO):.2f}"


def month_key(moment: datetime | date) -> tuple[int, int]:
    return moment.year, moment.month


def month_series(months: list[datetime], charged: dict, refunded: dict, bookings: dict) -> list[dict]:
    """Une tres agrupaciones por mes en una fila por mes, con ceros donde falta."""
    rows = []
    for month in months:
        key = month_key(month)
        paid = charged.get(key, ZERO)
        returned = refunded.get(key, ZERO)
        rows.append({
            "mes": f"{month.year}-{month.month:02d}",
            "etiqueta": MONTH_NAMES[month.month - 1],
            "cobrado": money(paid),
            "reembolsado": money(returned),
            "neto": money(paid - returned),
            "reservas": bookings.get(key, 0),
        })
    return rows


def state_breakdown(counts: dict[str, int]) -> list[dict]:
    total = sum(counts.values())
    return [
        {"estado": state, "etiqueta": label, "total": counts.get(state, 0),
         "porcentaje": percentage(counts.get(state, 0), total) or 0}
        for state, label in STATE_ORDER
        if counts.get(state, 0) or state in (BookingState.CONFIRMED, BookingState.CREATED, BookingState.CANCELLED)
    ]


def short_name(first: str, last: str) -> str:
    """"María Quispe" -> "María Q.": las reseñas no exponen el apellido completo."""
    first = (first or "").split(" ")[0]
    return f"{first} {last[:1]}." if last else first or "Cliente"


# ---------------------------------------------------------------- consultas


class Scope:
    """Filtros por empresa para cada tabla; ``ids`` vacio es toda la plataforma."""

    def __init__(self, ids: list[int]):
        self.ids = ids

    def _by(self, field: str) -> Q:
        return Q(**{f"{field}__in": self.ids}) if self.ids else Q()

    @property
    def booking(self) -> Q:
        return self._by("tenant_id")

    @property
    def payment(self) -> Q:
        return self._by("booking__tenant_id")

    @property
    def refund(self) -> Q:
        return self._by("payment__booking__tenant_id")

    @property
    def product(self) -> Q:
        return self._by("tenant_id")

    @property
    def review(self) -> Q:
        return self._by("product__tenant_id")

    @property
    def detail(self) -> Q:
        return self._by("booking__tenant_id")


def approved_payments(scope: Scope):
    return Payment.objects.filter(
        scope.payment, status=Payment.State.APPROVED, currency__iso_code=CURRENCY
    ).annotate(paid_at=Coalesce("processed_at", "created_at"))


def completed_refunds(scope: Scope):
    return Refund.objects.filter(
        scope.refund, status=Refund.State.COMPLETED, currency__iso_code=CURRENCY
    ).annotate(done_at=Coalesce("processed_at", "requested_at"))


def _by_month(queryset, field: str, value) -> dict:
    tz = timezone.get_current_timezone()
    rows = (
        queryset.annotate(month=TruncMonth(field, tzinfo=tz))
        .values("month").annotate(value=value).values_list("month", "value")
    )
    return {month_key(month): amount or 0 for month, amount in rows if month}


def _sum(queryset, field: str = "amount") -> Decimal:
    return queryset.aggregate(total=Sum(field))["total"] or ZERO


def finance(scope: Scope, period: Period) -> dict:
    payments = approved_payments(scope)
    refunds = completed_refunds(scope)
    start, previous = period.month_start, period.previous_start
    charged = _sum(payments.filter(paid_at__gte=start))
    refunded = _sum(refunds.filter(done_at__gte=start))
    previous_net = _sum(payments.filter(paid_at__gte=previous, paid_at__lt=start)) - _sum(
        refunds.filter(done_at__gte=previous, done_at__lt=start)
    )
    series = month_series(
        period.months(),
        _by_month(payments.filter(paid_at__gte=period.series_start), "paid_at", Sum("amount")),
        _by_month(refunds.filter(done_at__gte=period.series_start), "done_at", Sum("amount")),
        _by_month(
            Booking.objects.filter(scope.booking, created_at__gte=period.series_start), "created_at", Count("id")
        ),
    )
    return {
        "moneda": CURRENCY,
        "cobrado": money(charged),
        "reembolsado": money(refunded),
        "neto": money(charged - refunded),
        "variacion_neto": variation(charged - refunded, previous_net),
        "serie": series,
    }


def bookings_summary(scope: Scope, period: Period) -> dict:
    bookings = Booking.objects.filter(scope.booking)
    month = dict(
        bookings.filter(created_at__gte=period.month_start)
        .values("status").annotate(total=Count("id")).values_list("status", "total")
    )
    previous = bookings.filter(created_at__gte=period.previous_start, created_at__lt=period.month_start).count()
    total = sum(month.values())
    return {
        "total": total,
        "variacion": variation(total, previous),
        "canceladas": month.get(BookingState.CANCELLED, 0),
        "por_estado": state_breakdown(month),
    }


def occupancy(scope: Scope, period: Period) -> dict:
    """Cupos vendidos sobre cupos abiertos de las salidas y noches del mes.

    Solo cuenta los cupos que existen: en habitaciones el cupo del dia nace con
    la primera reserva, asi que es la ocupacion de los dias con movimiento.
    """
    end = shift_month(period.month_start, 1)
    slots = Availability.objects.filter(
        scope.booking, closed=False, start__gte=period.month_start, start__lt=end
    )
    capacity = slots.aggregate(total=Sum("total_capacity"))["total"] or 0
    sold = (
        BookingDetail.objects.filter(
            scope.detail, booking__status__in=SOLD, slot__start__gte=period.month_start, slot__start__lt=end
        ).aggregate(total=Sum("quantity"))["total"] or 0
    )
    return {"vendidos": sold, "capacidad": capacity, "porcentaje": percentage(min(sold, capacity), capacity)}


def ratings(scope: Scope, period: Period, *, latest: int = 0) -> dict:
    reviews = ProductReview.objects.filter(scope.review)
    summary = reviews.aggregate(average=Avg("rating"), total=Count("id"))
    data = {
        "promedio": round(float(summary["average"]), 1) if summary["average"] is not None else None,
        "total": summary["total"],
        "nuevas_mes": reviews.filter(created_at__gte=period.month_start).count(),
    }
    if latest:
        data["ultimas"] = [
            {
                "autor": short_name(item.user.first_names, item.user.last_names),
                "calificacion": item.rating,
                "comentario": item.comment[:180],
                "producto": item.product.name,
                "fecha": item.created_at.isoformat(),
            }
            for item in reviews.select_related("user", "product").order_by("-created_at", "-id")[:latest]
        ]
    return data


def alerts(scope: Scope, period: Period, *, platform: bool) -> list[dict]:
    stale = period.now - timedelta(hours=24)
    items = [
        ("reembolsos_fallidos", "Reembolsos fallidos", "Revisa el detalle en Pagos.", "alta",
         Refund.objects.filter(scope.refund, status=Refund.State.FAILED).count(), "/pagos"),
        ("pagos_revision", "Pagos en revisión", "Llevan más de 24 h sin confirmarse.", "media",
         Payment.objects.filter(scope.payment, status=Payment.State.PENDING, created_at__lt=stale).count(),
         "/pagos"),
        ("reservas_pendientes", "Reservas pendientes de pago", "Se liberan solas si vencen sin pago.", "media",
         Booking.objects.filter(scope.booking, status=BookingState.CREATED).count(), "/reservas"),
    ]
    if platform:
        horizon = period.now.date() + timedelta(days=15)
        items += [
            ("clientes_reportados", "Clientes reportados", "Reportes de empresas en los últimos 30 días.", "media",
             CustomerReport.objects.filter(scope.booking, created_at__gte=period.now - timedelta(days=30)).count(),
             "/clientes"),
            ("empresas_pendientes", "Empresas pendientes", "Esperan revisión y activación.", "info",
             Tenant.objects.filter(Q(id__in=scope.ids) if scope.ids else Q(), status=Tenant.Status.PENDING).count(),
             "/empresas"),
            ("planes_por_vencer", "Planes por vencer", "Vencen en los próximos 15 días.", "info",
             Subscription.objects.filter(
                 Q(tenant_id__in=scope.ids) if scope.ids else Q(), status=Subscription.Status.ACTIVE,
                 end_date__gte=period.now.date(), end_date__lte=horizon,
             ).count(), "/empresas"),
        ]
    return [
        {"clave": key, "titulo": title, "detalle": detail, "nivel": level, "total": total, "ruta": route}
        for key, title, detail, level, total, route in items
        if total
    ]


def top_products(scope: Scope, period: Period, limit: int = 5) -> list[dict]:
    rows = (
        BookingDetail.objects.filter(
            scope.detail, booking__status__in=SOLD, booking__created_at__gte=period.month_start,
            booking__currency__iso_code=CURRENCY,
        )
        .values(product_id=F("slot__product_id"), name=F("slot__product__name"), city=F("slot__product__city__name"))
        .annotate(bookings=Count("booking_id", distinct=True), income=Sum("subtotal"), units=Sum("quantity"))
        .order_by("-income", "name")[:limit]
    )
    return [
        {"id": row["product_id"], "nombre": row["name"], "ciudad": row["city"], "reservas": row["bookings"],
         "unidades": row["units"], "ingreso": money(row["income"])}
        for row in rows
    ]


def upcoming(scope: Scope, period: Period, days: int = 7, limit: int = 6) -> list[dict]:
    rows = (
        BookingDetail.objects.filter(
            scope.detail, booking__status__in=SOLD,
            slot__start__gte=period.now, slot__start__lt=period.now + timedelta(days=days),
        )
        .values(
            "booking_id", code=F("booking__code"), state=F("booking__status"), amount=F("booking__final_amount"),
            first=F("booking__order__customer__user__first_names"),
            last=F("booking__order__customer__user__last_names"),
            product=F("slot__product__name"),
        )
        .annotate(start=Min("slot__start"), units=Max("quantity"), nights=Count("slot_id", distinct=True))
        .order_by("start", "booking_id")[:limit]
    )
    return [
        {"reserva": row["code"], "inicio": row["start"].isoformat(), "cliente": f"{row['first']} {row['last']}".strip(),
         "producto": row["product"], "cantidad": row["units"], "dias": row["nights"],
         "monto": money(row["amount"]), "estado": row["state"]}
        for row in rows
    ]


def active_promotions(scope: Scope, period: Period, limit: int = 5) -> list[dict]:
    promotions = (
        Promotion.objects.filter(
            scope.product, administrative_status=Promotion.Status.ENABLED, ends_at__gte=period.now
        )
        .annotate(uses=Count("booking_snapshots"))
        .order_by("ends_at", "id")[:limit]
    )
    return [
        {"id": item.id, "nombre": item.name, "porcentaje": f"{item.percentage:.0f}", "usos": item.uses,
         "inicia": item.starts_at.isoformat(), "vence": item.ends_at.isoformat(),
         "vigente": item.starts_at <= period.now}
        for item in promotions
    ]


def catalog(scope: Scope) -> dict:
    counts = TourismProduct.objects.filter(scope.product).aggregate(
        total=Count("id"), published=Count("id", filter=Q(status=TourismProduct.Status.PUBLISHED))
    )
    return {"publicados": counts["published"], "total": counts["total"]}


def companies_ranking(scope: Scope, period: Period, limit: int = 5) -> list[dict]:
    """Empresas con mas cobro en el mes, con sus reservas y calificacion."""
    charged = dict(
        approved_payments(scope).filter(paid_at__gte=period.month_start)
        .values("booking__tenant_id").annotate(total=Sum("amount")).values_list("booking__tenant_id", "total")
    )
    bookings = dict(
        Booking.objects.filter(scope.booking, created_at__gte=period.month_start)
        .values("tenant_id").annotate(total=Count("id")).values_list("tenant_id", "total")
    )
    ranked = sorted(set(charged) | set(bookings), key=lambda tid: (-(charged.get(tid) or ZERO), -bookings.get(tid, 0)))
    ranked = ranked[:limit]
    names = dict(Tenant.objects.filter(id__in=ranked).values_list("id", "trade_name"))
    scores = dict(
        ProductReview.objects.filter(product__tenant_id__in=ranked)
        .values("product__tenant_id").annotate(avg=Avg("rating")).values_list("product__tenant_id", "avg")
    )
    return [
        {"id": tid, "nombre": names.get(tid, f"Empresa {tid}"), "cobrado": money(charged.get(tid)),
         "reservas": bookings.get(tid, 0),
         "calificacion": round(float(scores[tid]), 1) if scores.get(tid) is not None else None}
        for tid in ranked
    ]


def platform_people(scope: Scope, period: Period) -> dict:
    tenants = Tenant.objects.filter(Q(id__in=scope.ids) if scope.ids else Q())
    counts = tenants.aggregate(total=Count("id"), active=Count("id", filter=Q(status=Tenant.Status.ACTIVE)))
    customers = CustomerProfile.objects.all()
    buyers = (
        Booking.objects.filter(scope.booking, status__in=SOLD)
        .values("order__customer_id").distinct().count()
    )
    total_customers = customers.count()
    return {
        "empresas": {"total": counts["total"], "activas": counts["active"],
                     "tasa_activacion": percentage(counts["active"], counts["total"])},
        "turistas": {"total": total_customers,
                     "nuevos_mes": customers.filter(created_at__gte=period.month_start).count(),
                     "con_compra": buyers, "porcentaje_compra": percentage(buyers, total_customers)},
    }


def subscriptions(scope: Scope) -> list[dict]:
    rows = (
        Subscription.objects.filter(
            Q(tenant_id__in=scope.ids) if scope.ids else Q(), status=Subscription.Status.ACTIVE
        )
        .values(plan_name=F("plan__name")).annotate(total=Count("tenant_id", distinct=True))
        .order_by("-total", "plan_name")
    )
    return [{"plan": row["plan_name"], "empresas": row["total"]} for row in rows]


def demand_by_city(scope: Scope, period: Period, limit: int = 5) -> list[dict]:
    rows = (
        BookingDetail.objects.filter(scope.detail, booking__created_at__gte=period.month_start)
        .values(city=F("slot__product__city__name"))
        .annotate(total=Count("booking_id", distinct=True))
        .order_by("-total", "city")[:limit]
    )
    return [{"ciudad": row["city"], "reservas": row["total"]} for row in rows]


def latest_bookings(scope: Scope, limit: int = 5) -> list[dict]:
    bookings = (
        Booking.objects.filter(scope.booking)
        .select_related("tenant", "order__customer__user", "currency")
        .order_by("-created_at", "-id")[:limit]
    )
    return [
        {"reserva": item.code, "empresa": item.tenant.trade_name,
         "cliente": item.order.customer.user.get_full_name(),
         "monto": money(item.final_amount), "moneda": item.currency.iso_code, "estado": item.status,
         "fecha": item.created_at.isoformat()}
        for item in bookings
    ]


def comparison(ids: list[int], period: Period) -> list[dict]:
    """Una fila por empresa elegida, con los mismos indicadores para comparar."""
    names = dict(Tenant.objects.filter(id__in=ids).values_list("id", "trade_name"))
    rows = []
    for tid in ids:
        scope = Scope([tid])
        money_data = finance(scope, period)
        booking_data = bookings_summary(scope, period)
        rows.append({
            "id": tid,
            "nombre": names.get(tid, f"Empresa {tid}"),
            "cobrado": money_data["cobrado"],
            "reembolsado": money_data["reembolsado"],
            "neto": money_data["neto"],
            "reservas": booking_data["total"],
            "canceladas": booking_data["canceladas"],
            "ocupacion": occupancy(scope, period)["porcentaje"],
            "calificacion": ratings(scope, period)["promedio"],
            "serie": [{"etiqueta": month["etiqueta"], "neto": month["neto"]} for month in money_data["serie"]],
        })
    return rows


# ---------------------------------------------------------------- respuesta


def build_dashboard(*, user, tenant_id: int | None, params, now: datetime | None = None) -> dict:
    global_scope, tenant_id = report_scope(user=user, tenant_id=tenant_id)
    period = Period.current(now)
    if global_scope:
        ids = parse_companies(params.get("empresas"))
        if not ids and tenant_id is not None:
            ids = [tenant_id]
    else:
        ids = [tenant_id]
    scope = Scope(ids)
    data = {
        "alcance": "plataforma" if global_scope else "empresa",
        "empresas": ids,
        "generado": period.now.isoformat(),
        "mes": f"{MONTH_NAMES[period.now.month - 1]} {period.now.year}",
        "finanzas": finance(scope, period),
        "reservas": bookings_summary(scope, period),
        "ocupacion": occupancy(scope, period),
        "calificacion": ratings(scope, period, latest=0 if global_scope else 4),
        "alertas": alerts(scope, period, platform=global_scope),
        "productos_top": top_products(scope, period),
        "catalogo": catalog(scope),
    }
    if global_scope:
        data.update(
            plataforma=platform_people(scope, period),
            ranking=companies_ranking(scope, period),
            suscripciones=subscriptions(scope),
            ciudades=demand_by_city(scope, period),
            ultimas_reservas=latest_bookings(scope),
            comparacion=comparison(ids, period) if len(ids) >= 2 else [],
        )
    else:
        data.update(
            proximas=upcoming(scope, period),
            promociones=active_promotions(scope, period),
        )
    return data
