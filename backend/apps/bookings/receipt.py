"""Comprobante en PDF de una reserva pagada.

Va adjunto al correo de reserva confirmada y se baja desde la app con un enlace
firmado (``receipt_url``): el turista lo abre en el navegador del celular sin
mandar su sesion. El QR es el mismo del voucher de la app, firmado, asi una
copia editada no pasa por valida al llegar.
"""

from datetime import datetime
from functools import lru_cache
from io import BytesIO

from django.conf import settings
from django.core import signing
from django.urls import reverse
from django.utils import timezone
from PIL import Image as PILImage
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from apps.reports.exporters import logo_path

from .models import Booking

RECEIPT_SALT = "situr.comprobante"
# Lo que dura el enlace del correo. La app pide uno nuevo cada vez.
RECEIPT_LINK_DAYS = 90

BRAND = colors.HexColor("#0F766E")
INK = colors.HexColor("#10233F")
MUTED = colors.HexColor("#64748B")
LIGHT = colors.HexColor("#EAF8F6")

MONTHS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def receipt_token(booking: Booking) -> str:
    return signing.dumps({"r": booking.id, "c": booking.code}, salt=RECEIPT_SALT, compress=True)


def read_receipt_token(token: str) -> int:
    """Id de la reserva del enlace. Levanta signing.BadSignature si no es valido o vencio."""
    data = signing.loads(token, salt=RECEIPT_SALT, max_age=RECEIPT_LINK_DAYS * 24 * 3600)
    return int(data["r"])


def receipt_url(booking: Booking) -> str:
    """Enlace publico y firmado al PDF; no necesita sesion."""
    path = reverse("booking-receipt-public", kwargs={"token": receipt_token(booking)})
    return f"{settings.API_PUBLIC_URL.rstrip('/')}{path}"


def _day(value: str | None) -> str:
    if not value:
        return ""
    year, month, day = (int(part) for part in value.split("-"))
    return f"{day} {MONTHS[month - 1]} {year}"


@lru_cache(maxsize=1)
def _logo_bytes() -> bytes | None:
    """El logo de los reportes, achicado: tal cual haria pesar el PDF casi 500 KB."""
    path = logo_path()
    if path is None:
        return None
    with PILImage.open(path) as image:
        image.thumbnail((700, 700))
        out = BytesIO()
        image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _logo() -> BytesIO | None:
    data = _logo_bytes()
    return BytesIO(data) if data else None


def _qr(content: str, size: float) -> Drawing:
    widget = QrCodeWidget(content, barLevel="M")
    left, bottom, right, top = widget.getBounds()
    drawing = Drawing(size, size, transform=[size / (right - left), 0, 0, size / (top - bottom), 0, 0])
    drawing.add(widget)
    return drawing


def build_receipt_pdf(booking: Booking) -> bytes:
    # Import diferido: el serializer importa los servicios, que importan este modulo.
    from .serializers import BookingSerializer
    from .services import voucher_token

    data = BookingSerializer(booking).data
    product = data["producto"] or {}
    dates = data["fechas"] or {}
    amount = data["importe"]
    payment = data["pago"] or {}
    customer = booking.order.customer.user

    stream = BytesIO()
    document = SimpleDocTemplate(
        stream, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        title=f"Comprobante {booking.code}", author="SITUR-SMART",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("t", parent=styles["Heading1"], fontSize=18, leading=22, textColor=INK, spaceAfter=0)
    muted = ParagraphStyle("m", parent=styles["Normal"], fontSize=9, leading=12, textColor=MUTED)
    label = ParagraphStyle("l", parent=muted, fontSize=8.5)
    value = ParagraphStyle("v", parent=styles["Normal"], fontSize=10.5, leading=14, textColor=INK)
    code = ParagraphStyle("c", parent=styles["Normal"], fontName="Courier-Bold", fontSize=16, leading=20, textColor=BRAND)

    story = []
    logo = _logo()
    header = [
        Image(logo, width=58 * mm, height=19 * mm) if logo else Paragraph("SITUR-SMART", title),
        Paragraph(
            f"<b>COMPROBANTE DE RESERVA</b><br/>Emitido el {timezone.localtime().strftime('%d/%m/%Y %H:%M')}",
            ParagraphStyle("h", parent=muted, alignment=2),
        ),
    ]
    head = Table([header], colWidths=[90 * mm, 84 * mm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story += [head, Spacer(1, 8 * mm)]

    place = product.get("establecimiento") or product.get("nombre") or "Reserva"
    subtitle = product.get("nombre") if product.get("establecimiento") else product.get("tipo")
    if dates.get("noches"):
        nights = dates["noches"]
        when = f"{_day(dates['inicio'])} al {_day(dates['fin'])} ({nights} {'noche' if nights == 1 else 'noches'})"
    else:
        when = _day(dates.get("inicio"))

    summary = [
        Paragraph(place, title),
        Paragraph(subtitle or "", muted),
        Spacer(1, 4 * mm),
        Paragraph("Código de reserva", label),
        Paragraph(data["codigo"], code),
        Spacer(1, 2 * mm),
        Paragraph(f"Estado: <b>{data['estado_nombre']}</b>", value),
    ]
    qr_block = [_qr(voucher_token(booking), 46 * mm), Paragraph("Presenta este QR al llegar", ParagraphStyle("q", parent=muted, alignment=1))]
    top = Table([[summary, qr_block]], colWidths=[118 * mm, 56 * mm])
    top.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.6, BRAND),
        ("LEFTPADDING", (0, 0), (-1, -1), 6 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm),
    ]))
    story += [top, Spacer(1, 7 * mm)]

    city = ", ".join(part for part in (product.get("localidad"), product.get("ciudad")) if part)
    rows = [
        ("Titular", f"{customer.get_full_name()} · {customer.email}"),
        ("Fechas", when),
        ("Cantidad", f"{amount['cantidad']} {amount['unidad']}"),
    ]
    if data.get("huespedes"):
        guests = data["huespedes"]
        rows.append(("Huéspedes", f"{guests} {'huésped' if guests == 1 else 'huéspedes'}"))
    rows += [
        ("Lugar", city),
        ("Ofrecido por", data["empresa"]),
        ("Orden", data["orden"]),
        ("Precio unitario", f"{data['moneda_simbolo']} {amount['precio_unitario']}"),
    ]
    if payment:
        processed = payment.get("procesado_en")
        paid_on = timezone.localtime(datetime.fromisoformat(processed)).strftime("%d/%m/%Y %H:%M") if processed else ""
        rows.append(("Pago", f"Tarjeta vía {payment.get('proveedor', '').title()} · {paid_on}".strip(" ·")))
    rows.append(("Total pagado", f"<b>{data['moneda_simbolo']} {amount['total']}</b>"))

    details = Table(
        [[Paragraph(name, label), Paragraph(text, value)] for name, text in rows if text],
        colWidths=[40 * mm, 134 * mm],
    )
    details.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#DDE4EA")),
        ("LINEABOVE", (0, -1), (-1, -1), 1, BRAND),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story += [details, Spacer(1, 10 * mm)]
    story.append(Paragraph(
        "Este comprobante confirma tu reserva en SITUR-SMART. Muestra el código o el QR al llegar. "
        "También lo encuentras en la app, en Mis viajes. Para cambios o cancelaciones de una reserva pagada, "
        "comunícate con la empresa que ofrece el servicio.",
        muted,
    ))
    document.build(story)
    return stream.getvalue()
