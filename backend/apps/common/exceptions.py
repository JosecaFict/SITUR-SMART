from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return response

    detail = response.data
    message = "La solicitud no pudo procesarse."
    if isinstance(detail, dict) and isinstance(detail.get("detail"), str):
        message = detail["detail"]

    response.data = {
        "error": {
            "status": response.status_code,
            "message": message,
            "details": detail,
        }
    }
    return response
