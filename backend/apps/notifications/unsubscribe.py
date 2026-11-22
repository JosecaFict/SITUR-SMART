from django.core import signing
from django.http import HttpResponse
from django.utils.html import escape
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.accounts.models import User

from .email_content import SALT
from .marketing import set_preference


def page(title, body, status=200):
    return HttpResponse(f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)} · SITUR-SMART</title><body style="margin:0;padding:48px 20px;background:#edf5f3;font-family:Arial,sans-serif;color:#163e35">
<main style="max-width:500px;margin:auto;padding:32px;background:white;border-radius:20px;border:1px solid #d4e5de"><p style="color:#0f766e;font-weight:bold">SITUR·SMART</p><h1>{escape(title)}</h1>{body}</main></body></html>''', status=status)


class UnsubscribeView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    schema = None

    def _target(self, token):
        try:
            target = signing.loads(token, salt=SALT, max_age=90 * 86400)
            if type(target.get("usuario")) is not int or target["usuario"] <= 0:
                return None
            if target.get("empresa") is not None and (type(target["empresa"]) is not int or target["empresa"] <= 0):
                return None
            user = User.objects.filter(pk=target["usuario"]).first()
            return (user, target.get("empresa")) if user else None
        except (signing.BadSignature, ValueError, TypeError, AttributeError):
            return None

    def get(self, request, token):
        if self._target(token) is None:
            return page("Enlace no disponible", "<p>Este enlace no es válido o venció. Puedes gestionar tus preferencias desde tu cuenta.</p>", 400)
        return page("¿Dejar de recibir estas promociones?", f'''<p style="line-height:1.7">Solo se desactivarán las promociones de este remitente. Seguirás recibiendo los avisos operativos de tus reservas y de tu equipo.</p>
<form method="post" action="{escape(request.path)}"><button style="border:0;border-radius:10px;padding:14px 20px;background:#0f766e;color:white;font-size:16px;cursor:pointer">Confirmar baja de promociones</button></form>''')

    def post(self, request, token):
        target = self._target(token)
        if target is None:
            return page("Enlace no disponible", "<p>Gestiona tus preferencias desde tu cuenta.</p>", 400)
        set_preference(target[0], target[1], False)
        return page("Tu preferencia quedó guardada", "<p style='line-height:1.7'>Ya no recibirás nuevas promociones de este remitente. Los avisos de reservas y equipo seguirán disponibles.</p>")
