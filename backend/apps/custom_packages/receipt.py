"""Comprobante PDF consolidado de una compra de paquete."""

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import PackagePurchase


def build(purchase: PackagePurchase) -> bytes:
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("SITUR-SMART", styles["Title"]),
        Paragraph("Comprobante de paquete turístico", styles["Heading2"]),
        Paragraph(f"{purchase.package.name} · Orden {purchase.order.code}", styles["Normal"]),
        Spacer(1, 8 * mm),
    ]
    rows = [["Reserva", "Empresa", "Servicio", "Importe"]]
    for allocation in purchase.allocations.select_related("booking__tenant").prefetch_related(
        "booking__details__slot__product"
    ):
        booking = allocation.booking
        detail = booking.details.first()
        rows.append([
            booking.code,
            booking.tenant.trade_name,
            detail.slot.product.name if detail else "Servicio",
            f"{purchase.currency.symbol} {allocation.final_amount:.2f}",
        ])
    table = Table(rows, colWidths=[35 * mm, 48 * mm, 62 * mm, 28 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    story += [table, Spacer(1, 7 * mm),
              Paragraph(f"Total pagado: {purchase.currency.symbol} {purchase.final_amount:.2f}", styles["Heading2"]),
              Paragraph("Conserva los códigos de reserva para presentarlos en cada servicio.", styles["Normal"])]
    doc.build(story)
    return output.getvalue()
