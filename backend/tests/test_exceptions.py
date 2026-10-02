from django.test import SimpleTestCase
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.common.exceptions import api_exception_handler, first_message


def envelope(exc):
    return api_exception_handler(exc, {}).data["error"]


class FirstMessageTests(SimpleTestCase):
    def test_reads_a_plain_string(self):
        assert first_message("Algo salio mal.") == "Algo salio mal."

    def test_reads_a_list(self):
        assert first_message(["Primero.", "Segundo."]) == "Primero."

    def test_prefers_the_detail_key_over_other_fields(self):
        detail = {"campo": ["Mensaje del campo."], "detail": "Mensaje principal."}
        assert first_message(detail) == "Mensaje principal."

    def test_reads_nested_structures(self):
        assert first_message({"items": [{"nombre": ["Obligatorio."]}]}) == "Obligatorio."

    def test_returns_none_when_there_is_no_text(self):
        assert first_message({}) is None
        assert first_message([]) is None
        assert first_message("") is None


class ApiExceptionHandlerTests(SimpleTestCase):
    def test_surfaces_the_message_of_a_string_validation_error(self):
        """DRF convierte ValidationError("texto") en una lista, no en un dict.

        Es la forma que usan los servicios del proyecto (por ejemplo CloudinaryService)
        y antes caia en el mensaje genérico, dejando al frontend sin nada que mostrar.
        """
        error = envelope(ValidationError("El servicio no está configurado."))

        assert error["status"] == 400
        assert error["message"] == "El servicio no está configurado."

    def test_surfaces_the_first_field_message_of_a_validation_error(self):
        error = envelope(ValidationError({"nombre": ["Este campo es obligatorio."]}))

        assert error["message"] == "Este campo es obligatorio."

    def test_keeps_the_full_details_for_the_client(self):
        error = envelope(ValidationError({"nombre": ["Obligatorio."], "precio": ["Inválido."]}))

        assert error["details"] == {"nombre": ["Obligatorio."], "precio": ["Inválido."]}

    def test_uses_the_detail_of_single_message_exceptions(self):
        assert envelope(NotFound("Producto no encontrado."))["message"] == "Producto no encontrado."
        assert envelope(PermissionDenied())["status"] == 403

    def test_falls_back_to_a_message_for_the_status_code(self):
        error = envelope(ValidationError({}))

        assert error["status"] == 400
        assert error["message"] == "La solicitud contiene datos inválidos."
