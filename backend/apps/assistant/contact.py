"""Contacto de la empresa para que el viajero consulte lo que no figura.

Se usa el telefono y el correo que la empresa registro. Si el telefono es un
celular boliviano (8 digitos que empiezan con 6 o 7), se arma un enlace de
WhatsApp (``wa.me``) con un mensaje ya escrito que dice desde donde llega el
cliente. Un fijo se muestra solo para llamar: WhatsApp no lo abriria.

No se puede saber si el celular tiene WhatsApp; si no lo tiene, WhatsApp se lo
avisa al viajero.

Solo lo usa el asistente (viajero con sesion iniciada); la API publica de
recomendaciones no expone el telefono.
"""

import re
from urllib.parse import quote

COUNTRY_CODE = "591"
BOLIVIAN_MOBILE = re.compile(r"[67]\d{7}")


def _digits(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("00"):
        digits = digits[2:]
    return digits


def whatsapp_number(phone: str | None) -> str | None:
    """Numero internacional para wa.me, solo si es un celular boliviano."""
    digits = _digits(phone or "")
    if digits.startswith(COUNTRY_CODE) and len(digits) == len(COUNTRY_CODE) + 8:
        digits = digits[len(COUNTRY_CODE):]
    return COUNTRY_CODE + digits if BOLIVIAN_MOBILE.fullmatch(digits) else None


def whatsapp_url(phone: str | None, subject: str) -> str | None:
    number = whatsapp_number(phone)
    if number is None:
        return None
    text = f"Hola, vi {subject} en SITUR-SMART y quisiera hacer una consulta."
    return f"https://wa.me/{number}?text={quote(text)}"


def _text(value) -> str | None:
    return value.strip() or None if isinstance(value, str) else None


def company_contact(tenant, subject: str) -> dict | None:
    """Telefono, WhatsApp y correo de la empresa, o ``None`` si no dejo nada.

    ``subject`` describe lo que vio el viajero, p. ej. 'el hospedaje "Hotel X"'.
    ``whatsapp`` le dice al modelo si hay boton; el enlace solo va a la tarjeta.
    """
    phone = _text(getattr(tenant, "phone", None))
    email = _text(getattr(tenant, "contact_email", None))
    if not phone and not email:
        return None
    link = whatsapp_url(phone, subject)
    return {"telefono": phone, "whatsapp": link is not None, "whatsapp_url": link, "email": email}
