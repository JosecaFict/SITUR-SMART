"""Genera CREDENCIALES_DEMO.md a partir de los datos de ``bolivia.py``.

El archivo se deriva de los datos y no de la base, asi que siempre coincide con
lo que carga ``seed_bolivia`` y no cambia entre ejecuciones.
"""

from collections import Counter

from . import bolivia

PLANES = {"BASICO": "Básico", "PROFESIONAL": "Pro", "EMPRESARIAL": "Max"}
ESTADOS = {
    "ACTIVO": "Activa",
    "SUSPENDIDO": "Suspendida (su oferta no aparece en el Marketplace)",
    "PENDIENTE": "Pendiente de activación por el SuperAdmin",
}
TIPOS = {
    "RESTAURANTE": ("restaurante", "restaurantes"),
    "TOUR": ("tour", "tours"),
    "EXPERIENCIA": ("experiencia", "experiencias"),
    "ATRACCION": ("atracción", "atracciones"),
    "PAQUETE": ("paquete", "paquetes"),
}
ROLES = {
    "TENANT_ADMIN": "Propietario",
    **{codigo: datos["nombre"] for codigo, datos in bolivia.ROLES_PERSONALIZADOS.items()},
    **bolivia.ROLES_SISTEMA,
}


def _plural(cantidad: int, singular: str, plural: str) -> str:
    return f"{cantidad} {singular if cantidad == 1 else plural}"


def resumen_oferta(empresa: dict) -> str:
    partes = []
    hoteles = empresa["hoteles"]
    if hoteles:
        habitaciones = sum(len(h["habitaciones"]) for h in hoteles)
        partes.append(_plural(len(hoteles), "hotel", "hoteles"))
        partes.append(_plural(habitaciones, "tipo de habitación", "tipos de habitación"))
    por_tipo = Counter(p["tipo"] for p in empresa["productos"])
    for tipo, (singular, plural) in TIPOS.items():
        if por_tipo[tipo]:
            partes.append(_plural(por_tipo[tipo], singular, plural))
    return ", ".join(partes) or "Sin oferta cargada todavía"


def _ciudades(empresa: dict) -> str:
    ciudades = [empresa["ciudad"]]
    for item in [*empresa["hoteles"], *empresa["productos"]]:
        if item["ciudad"] not in ciudades:
            ciudades.append(item["ciudad"])
    return " / ".join(ciudades)


def render() -> str:
    empresas = bolivia.EMPRESAS
    cuentas = sum(len(bolivia.cuentas_empresa(e)) for e in empresas) + len(bolivia.TURISTAS)
    lineas = [
        "# Credenciales de demostración — SITUR-SMART",
        "",
        "> Archivo generado por `python manage.py seed_bolivia --credenciales`. No editar a mano:",
        "> los datos viven en `backend/apps/catalog/seed/bolivia.py`.",
        "",
        f"**Contraseña de todas las cuentas: `{bolivia.PASSWORD}`**",
        "",
        "Son datos de prueba. Los nombres de las empresas son reales; precios, habitaciones,",
        "servicios y coordenadas son aproximados. Las imágenes se cargan a mano desde el panel.",
        "",
        "La cuenta del **SuperAdmin** no está aquí: se crea con `python manage.py createsituradmin`.",
        "",
        "## Resumen",
        "",
        f"- {len(empresas)} empresas, {cuentas} cuentas.",
        f"- {sum(len(e['hoteles']) for e in empresas)} hoteles con "
        f"{sum(len(h['habitaciones']) for e in empresas for h in e['hoteles'])} tipos de habitación.",
        f"- {sum(len(e['productos']) for e in empresas)} productos más "
        "(restaurantes, tours, experiencias, atracciones y paquetes).",
        "- Una empresa suspendida (Red Cap Walking Tours) y una pendiente de activación (Tupiza Tours).",
        "",
        "## Cómo cargar los datos",
        "",
        "```powershell",
        "cd backend",
        "python manage.py createsituradmin        # solo si todavía no existe un SuperAdmin",
        "python manage.py seed_bolivia            # carga todo; lo que ya existe se omite",
        "python manage.py seed_bolivia --reset    # borra lo que creó el seed y lo vuelve a cargar",
        "```",
        "",
        "Sin acceso a `manage.py` (por ejemplo, la base de Railway): abrir",
        "`backend/database/seed_bolivia.sql` en el Query Tool de pgAdmin y ejecutarlo. Hace lo mismo",
        "y se puede ejecutar más de una vez.",
        "",
        "## Empresas",
        "",
        "| Empresa | Perfil | Plan | Ciudad | Estado |",
        "|---|---|---|---|---|",
    ]
    for empresa in empresas:
        lineas.append(
            f"| {empresa['nombre']} | {empresa['perfil']} | {PLANES[empresa['plan']]} | "
            f"{_ciudades(empresa)} | {ESTADOS[empresa['estado']].split(' (')[0]} |"
        )

    for empresa in empresas:
        lineas += [
            "",
            f"### {empresa['nombre']}",
            "",
            f"- **Perfil:** {empresa['perfil']}",
            f"- **Plan:** {PLANES[empresa['plan']]}",
            f"- **Estado:** {ESTADOS[empresa['estado']]}",
            f"- **Publica:** {resumen_oferta(empresa)}",
            "",
            "| Rol | Email |",
            "|---|---|",
        ]
        for cuenta in bolivia.cuentas_empresa(empresa):
            lineas.append(f"| {ROLES[cuenta['rol']]} | `{cuenta['email']}` |")

    lineas += [
        "",
        "## Turistas",
        "",
        "Cuentas con rol CLIENTE, sin empresa. Sirven para probar el Marketplace y el asistente.",
        "",
        "| Nombre | Email |",
        "|---|---|",
    ]
    for turista in bolivia.cuentas_turistas():
        lineas.append(f"| {turista['nombres']} {turista['apellidos']} | `{turista['email']}` |")

    lineas += [
        "",
        "## Roles personalizados",
        "",
        "Cada empresa que los usa los crea dentro de su tenant.",
        "",
        "| Rol | Permisos |",
        "|---|---|",
    ]
    for datos in bolivia.ROLES_PERSONALIZADOS.values():
        lineas.append(f"| {datos['nombre']} | {', '.join(datos['permisos'])} |")
    lineas.append("")
    return "\n".join(lineas)
