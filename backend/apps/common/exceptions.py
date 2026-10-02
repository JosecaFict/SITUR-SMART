from rest_framework.views import exception_handler

FALLBACK_MESSAGE = "La solicitud no pudo procesarse."

STATUS_MESSAGES = {
    400: "La solicitud contiene datos inválidos.",
    401: "Tu sesión no es válida o ha expirado.",
    403: "No tienes permisos para realizar esta acción.",
    404: "El recurso solicitado no existe.",
    405: "El método no está permitido para este recurso.",
    413: "El archivo enviado es demasiado grande.",
    429: "Demasiadas solicitudes. Inténtalo de nuevo en unos minutos.",
    503: "El servicio no está disponible en este momento.",
}


def first_message(detail) -> str | None:
    """Extrae el primer texto legible de un detalle de DRF.

    DRF entrega el detalle en formas distintas segun como se levanto la excepcion:
    una cadena, una lista (``raise ValidationError("texto")``) o un diccionario
    por campo (``raise ValidationError({"campo": [...]})``), que a su vez puede
    anidar listas y diccionarios. Se recorre cualquiera de esas formas.
    """
    if isinstance(detail, str):
        return detail or None
    if isinstance(detail, (list, tuple)):
        for item in detail:
            if message := first_message(item):
                return message
        return None
    if isinstance(detail, dict):
        # "detail" es la clave que usa DRF para los errores de un solo mensaje.
        ordered_keys = ["detail", *(key for key in detail if key != "detail")]
        for key in ordered_keys:
            if key in detail and (message := first_message(detail[key])):
                return message
    return None


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return response

    detail = response.data
    message = (
        first_message(detail)
        or STATUS_MESSAGES.get(response.status_code)
        or FALLBACK_MESSAGE
    )

    response.data = {
        "error": {
            "status": response.status_code,
            "message": message,
            "details": detail,
        }
    }
    return response
