from django.test import SimpleTestCase

from apps.accounts.serializers import LoginSerializer
from apps.rbac.serializers import RoleCreateSerializer


class LoginSerializerTests(SimpleTestCase):
    def test_rejects_invalid_email(self):
        serializer = LoginSerializer(data={"email": "correo-invalido", "password": "secreto"})

        assert not serializer.is_valid()
        assert "email" in serializer.errors


class RoleCreateSerializerTests(SimpleTestCase):
    def test_normal_role_payload_is_valid(self):
        serializer = RoleCreateSerializer(
            data={
                "code": "RECEPCIONISTA",
                "name": "Recepcionista",
                "permissions": ["RESERVAS_LEER"],
            }
        )

        assert serializer.is_valid(), serializer.errors

    def test_rejects_code_with_spaces(self):
        serializer = RoleCreateSerializer(data={"code": "ROL INVALIDO", "name": "Rol"})

        assert not serializer.is_valid()
        assert "code" in serializer.errors

