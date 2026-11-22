"""Contenido de correo sin HTML aportado por el remitente ni seguimiento oculto."""

from urllib.parse import quote, urlparse

from django.conf import settings
from django.core import signing
from django.utils import timezone
from django.utils.html import escape

SALT = "situr.comunicaciones.baja"


def personalize(text, user, sender):
    return text.replace("{{nombre}}", user.first_names.strip() or "viajero").replace("{{empresa}}", sender)


def public_url(setting, path):
    base = str(getattr(settings, setting, "")).rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("INVALID_PUBLIC_URL")
    if not settings.DEBUG and parsed.scheme != "https":
        raise ValueError("INVALID_PUBLIC_URL")
    return base + path


def unsubscribe_url(user_id, tenant_id):
    token = signing.dumps({"usuario": user_id, "empresa": tenant_id}, salt=SALT, compress=True)
    return public_url("API_PUBLIC_URL", "/api/v1/comunicaciones/baja/" + quote(token, safe="") + "/")


def build_email(item, notification, user, *, preview=False):
    sender = item.sender_name or "SITUR-SMART"
    kind = {"INTERNA": "Para nuestro equipo", "OPERATIVA": "Información para tu viaje",
            "PROMOCIONAL": "Una nueva experiencia te espera"}[item.kind]
    heading = {"INTERNA": "Un equipo conectado, una mejor experiencia.",
               "OPERATIVA": "Viaja con toda la información a mano.",
               "PROMOCIONAL": "Inspírate para tu próxima escapada."}[item.kind]
    href = public_url("WEB_APP_URL", "/notificaciones")
    action = "Abrir mi bandeja"
    if item.promotion_id:
        href, action = public_url("WEB_APP_URL", f"/marketplace/promociones/{item.promotion_id}"), "Descubrir la oferta"
    elif item.booking_id:
        href, action = public_url("WEB_APP_URL", f"/mis-viajes/{item.booking_id}"), "Consultar mi reserva"
    deadline = timezone.localtime(item.expires_at).strftime("%d/%m/%Y · %H:%M") if item.expires_at else ""
    end_note = f"Válido hasta {deadline} (hora de Bolivia)." if deadline else "Conserva este mensaje para consultarlo cuando lo necesites."
    optout = (public_url("WEB_APP_URL", "/notificaciones") if preview else unsubscribe_url(user.pk, item.tenant_id)) if item.kind == "PROMOCIONAL" else None
    foot = (f'Recibes esta oferta porque aceptaste promociones de {escape(sender)}. '
            f'<a href="{escape(optout)}" style="color:#0f766e">Dejar de recibir promociones</a>.' if optout
            else "Este aviso es informativo. Tus preferencias de publicidad no afectan los mensajes de tu reserva o equipo.")
    body = "<br>".join(str(escape(notification.message)).splitlines())
    html = f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(notification.title)}</title></head>
<body style="margin:0;background:#edf5f3;color:#193b35;font-family:Arial,Helvetica,sans-serif">
<div style="display:none;max-height:0;overflow:hidden">{escape(notification.message[:100])}</div>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr><td align="center" style="padding:32px 16px">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px;background:#fff;border:1px solid #d8e8e3;border-radius:20px;overflow:hidden">
<tr><td style="padding:30px;background:#0d4f47;color:#fff"><p style="margin:0 0 24px;font-size:18px;font-weight:bold;letter-spacing:1px">SITUR<span style="color:#5eead4">·</span>SMART</p>
<p style="margin:0 0 8px;color:#99f6e4;font-size:14px">{escape(kind)}</p><h1 style="margin:0;font-size:28px;line-height:1.25">{escape(heading)}</h1></td></tr>
<tr><td style="padding:30px"><p style="margin:0 0 12px;color:#58736c;font-size:14px">DE {escape(sender)}</p><h2 style="margin:0 0 20px;font-size:24px;line-height:1.3">{escape(notification.title)}</h2>
<p style="font-size:16px;margin:0 0 18px">Hola, {escape(user.first_names.strip() or 'viajero')}.</p>
<div style="font-size:16px;line-height:1.8;overflow-wrap:anywhere">{body}</div>
<p style="padding:16px;background:#f0fdfa;border-left:3px solid #14b8a6;font-size:14px;color:#37655b">{escape(end_note)}</p>
<table role="presentation" cellspacing="0" cellpadding="0"><tr><td style="border-radius:10px;background:#0f766e"><a href="{escape(href)}" style="display:inline-block;padding:15px 24px;color:#fff;text-decoration:none;font-size:16px;font-weight:bold">{escape(action)}</a></td></tr></table>
<p style="margin:24px 0 0;font-size:14px;color:#58736c;line-height:1.6">También encontrarás este aviso en tu bandeja de SITUR-SMART. Este correo es una notificación; no es un chat de atención.</p></td></tr>
<tr><td style="padding:24px 30px;background:#f6faf8;border-top:1px solid #e0ede8;font-size:13px;color:#58736c;line-height:1.7">{foot}<br>Enviado por SITUR-SMART en nombre de {escape(sender)}.</td></tr>
</table></td></tr></table></body></html>'''
    text = f"{sender}\n{notification.title}\n\nHola, {user.first_names}.\n\n{notification.message}\n\n{end_note}\n{action}: {href}"
    if optout:
        text += f"\nDejar de recibir promociones: {optout}"
    return {"subject": notification.title.replace("\r", " ").replace("\n", " "), "html": html,
            "text": text, "unsubscribe": optout}
