"""Herramienta de reportes del asistente, para el personal y el SuperAdmin.

El dueño de una empresa o el SuperAdmin le pide al asistente, escrito o por
voz, "el reporte de catalogo de este mes en PDF". El modelo elige tipo, fechas
y formato; aqui se arma el reporte con los mismos permisos que la pantalla de
Reportes y se devuelve un resumen para que lo cuente. El archivo lo baja la web
con los endpoints de exportacion de siempre, que vuelven a verificar permisos y
dejan la descarga en la bitacora.

Un turista nunca ve esta herramienta: ``context_for`` devuelve None.
"""

from dataclasses import dataclass, field
from datetime import date

from rest_framework.exceptions import APIException, PermissionDenied

from apps.rbac.services import is_superadmin
from apps.reports.services import build_report, report_scope
from apps.tenancy.models import Tenant

TITLES = {
    "plataforma": "Empresas y planes",
    "catalogo": "Catálogo",
    "hospedajes": "Hospedajes",
    "actividad": "Actividad",
}
FORMATS = {"pdf", "excel"}

DEFINITION = {
    "type": "function",
    "function": {
        "name": "generar_reporte",
        "description": (
            "Genera un reporte de SITUR-SMART y, si el usuario lo pide, lo descarga en PDF o Excel. "
            "Tipos: 'plataforma' (empresas, planes y suscripciones), 'catalogo' (productos registrados "
            "y publicados), 'hospedajes' (oferta de habitaciones y capacidades), 'actividad' "
            "(movimientos de la bitacora)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tipo": {"type": "string", "enum": sorted(TITLES)},
                "desde": {"type": "string", "description": "Fecha inicial AAAA-MM-DD, opcional."},
                "hasta": {"type": "string", "description": "Fecha final AAAA-MM-DD, opcional."},
                "formato": {
                    "type": "string",
                    "enum": ["pdf", "excel", "ninguno"],
                    "description": "pdf o excel si el usuario pide el archivo; ninguno si solo pregunta.",
                },
                "empresa": {
                    "type": "string",
                    "description": "Solo SuperAdmin: nombre de una empresa para limitar el reporte.",
                },
            },
            "required": ["tipo"],
        },
    },
}


@dataclass
class ReportContext:
    """Quien pide y en nombre de que empresa; acumula los reportes generados."""

    user: object
    tenant_id: int | None
    global_scope: bool
    reports: list[dict] = field(default_factory=list)


def context_for(user, tenant_id: int | None) -> ReportContext | None:
    """El contexto si el usuario puede ver reportes; None si no (un turista)."""
    if not getattr(user, "is_authenticated", False):
        return None
    if not is_superadmin(user) and tenant_id is None:
        return None
    try:
        global_scope, effective = report_scope(user=user, tenant_id=tenant_id)
    except PermissionDenied:
        return None
    return ReportContext(user=user, tenant_id=effective, global_scope=global_scope)


def _date(value) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip()[:10]).isoformat()
    except ValueError:
        return None


def _tenant(context: ReportContext, name) -> tuple[int | None, str | None, str | None]:
    """(tenant_id, nombre, error). Solo el SuperAdmin elige empresa por nombre."""
    if not context.global_scope or not isinstance(name, str) or not name.strip():
        tenant = Tenant.objects.filter(id=context.tenant_id).first() if context.tenant_id else None
        return context.tenant_id, tenant.trade_name if tenant else None, None
    matches = list(Tenant.objects.filter(trade_name__icontains=name.strip()[:80])[:5])
    if len(matches) == 1:
        return matches[0].id, matches[0].trade_name, None
    if not matches:
        return None, None, f"No hay ninguna empresa que se llame '{name.strip()}'."
    return None, None, "Hay varias empresas con ese nombre: " + ", ".join(t.trade_name for t in matches)


def run(args: dict, context: ReportContext) -> dict:
    report_type = args.get("tipo")
    if report_type not in TITLES:
        return {"error": "Tipo de reporte no válido.", "tipos": sorted(TITLES)}
    tenant_id, tenant_name, error = _tenant(context, args.get("empresa"))
    if error:
        return {"error": error}
    params = {"tipo": report_type}
    for key in ("desde", "hasta"):
        if value := _date(args.get(key)):
            params[key] = value
    try:
        report = build_report(user=context.user, tenant_id=tenant_id, params=params)
    except APIException as exc:
        return {"error": str(exc.detail)}

    file_format = args.get("formato") if args.get("formato") in FORMATS else None
    entry = {
        "tipo": report_type,
        "titulo": TITLES[report_type],
        "formato": file_format,
        "desde": params.get("desde"),
        "hasta": params.get("hasta"),
        "empresa_id": tenant_id,
        "empresa": tenant_name,
        "filas": len(report["filas"]),
    }
    context.reports.append(entry)
    return {
        "reporte": entry["titulo"],
        "empresa": tenant_name or "Toda la plataforma",
        "desde": entry["desde"],
        "hasta": entry["hasta"],
        "filas": entry["filas"],
        "indicadores": [{"dato": m["etiqueta"], "valor": m["valor"]} for m in report.get("indicadores", [])],
        "descarga": f"La descarga en {file_format.upper()} empieza sola en la pantalla." if file_format else None,
    }
