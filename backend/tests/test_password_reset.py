from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.brevo import build_otp_email_html, send_password_reset_otp_email
from apps.accounts.models import PasswordResetToken, User, UserSession
from apps.accounts.serializers import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PasswordResetVerifySerializer,
)
from apps.accounts.services import (
    confirm_password_reset,
    generate_otp_code,
    request_password_reset_otp,
    token_hash,
    verify_password_reset_otp,
)


class PasswordResetSerializersTests(SimpleTestCase):
    def test_request_serializer_validates_email(self):
        valid = PasswordResetRequestSerializer(data={"email": "usuario@situr.smart"})
        assert valid.is_valid()

        invalid = PasswordResetRequestSerializer(data={"email": "no-es-correo"})
        assert not invalid.is_valid()
        assert "email" in invalid.errors

    def test_verify_serializer_validates_code_format(self):
        valid = PasswordResetVerifySerializer(data={"email": "user@situr.smart", "code": "123456"})
        assert valid.is_valid()

        invalid_alpha = PasswordResetVerifySerializer(data={"email": "user@situr.smart", "code": "12A456"})
        assert not invalid_alpha.is_valid()
        assert "code" in invalid_alpha.errors

        invalid_len = PasswordResetVerifySerializer(data={"email": "user@situr.smart", "code": "123"})
        assert not invalid_len.is_valid()
        assert "code" in invalid_len.errors

    def test_confirm_serializer_validates_password_match(self):
        valid = PasswordResetConfirmSerializer(
            data={
                "email": "user@situr.smart",
                "code": "123456",
                "new_password": "NewSecurePassword123!",
                "new_password_confirm": "NewSecurePassword123!",
            }
        )
        assert valid.is_valid(), valid.errors

        mismatch = PasswordResetConfirmSerializer(
            data={
                "email": "user@situr.smart",
                "code": "123456",
                "new_password": "NewSecurePassword123!",
                "new_password_confirm": "DifferentPassword123!",
            }
        )
        assert not mismatch.is_valid()
        assert "new_password_confirm" in mismatch.errors


class BrevoEmailTests(SimpleTestCase):
    def test_build_otp_email_html_contains_code_and_branding(self):
        html = build_otp_email_html(recipient_name="Juan Perez", otp_code="789012", expiration_minutes=15)
        assert "789012" in html
        assert "Juan Perez" in html
        assert "SITUR-SMART" in html
        assert "15 minutos" in html

    def test_send_email_fallback_when_no_api_key(self):
        with patch("apps.accounts.brevo.settings.BREVO_API_KEY", ""):
            sent = send_password_reset_otp_email(
                to_email="test@situr.smart",
                recipient_name="Test",
                otp_code="123456",
            )
            assert sent is True


class PasswordResetServicesTests(TestCase):
    def test_generate_otp_code_is_6_digits(self):
        code = generate_otp_code()
        assert len(code) == 6
        assert code.isdigit()

    @patch("apps.accounts.services.User.objects.filter")
    @patch("apps.accounts.services.send_password_reset_otp_email")
    def test_request_otp_for_non_existing_user_returns_generic_message(self, mock_send, mock_user_filter):
        mock_user_filter.return_value.first.return_value = None
        result = request_password_reset_otp(email="noexiste@situr.smart")
        assert "detail" in result
        mock_send.assert_not_called()

    @patch("apps.accounts.services.send_password_reset_otp_email")
    @patch("apps.accounts.services.PasswordResetToken.objects.create")
    @patch("apps.accounts.services.PasswordResetToken.objects.filter")
    @patch("apps.accounts.services.User.objects.filter")
    def test_request_otp_for_active_user_creates_token_and_calls_email(
        self, mock_user_filter, mock_token_filter, mock_token_create, mock_send
    ):
        fake_user = MagicMock()
        fake_user.id = 42
        fake_user.email = "activo@situr.smart"
        fake_user.is_active = True
        fake_user.get_full_name.return_value = "Usuario Activo"

        mock_user_filter.return_value.first.return_value = fake_user
        mock_token_filter.return_value.first.return_value = None  # No recent token (rate limit ok)

        result = request_password_reset_otp(email="activo@situr.smart")
        assert "detail" in result
        mock_token_create.assert_called_once()
        mock_send.assert_called_once()

    @patch("apps.accounts.services.PasswordResetToken.objects.filter")
    @patch("apps.accounts.services.User.objects.filter")
    def test_request_otp_rate_limiting(self, mock_user_filter, mock_token_filter):
        fake_user = MagicMock()
        fake_user.id = 42
        fake_user.is_active = True
        mock_user_filter.return_value.first.return_value = fake_user

        # Token created recently
        mock_token_filter.return_value.first.return_value = MagicMock()

        with self.assertRaises(ValidationError):
            request_password_reset_otp(email="activo@situr.smart")

    @patch("apps.accounts.services.PasswordResetToken.objects.filter")
    @patch("apps.accounts.services.User.objects.filter")
    def test_verify_otp_success_and_failure(self, mock_user_filter, mock_token_filter):
        fake_user = MagicMock()
        fake_user.id = 1
        fake_user.is_active = True
        mock_user_filter.return_value.first.return_value = fake_user

        # Valid token
        mock_token_filter.return_value.first.return_value = MagicMock()
        assert verify_password_reset_otp(email="user@situr.smart", code="123456") is True

        # Invalid token
        mock_token_filter.return_value.first.return_value = None
        with self.assertRaises(ValidationError):
            verify_password_reset_otp(email="user@situr.smart", code="999999")

    @patch("apps.accounts.services.record_audit")
    @patch("apps.accounts.services.UserSession.objects.filter")
    @patch("apps.accounts.services.validate_password")
    @patch("apps.accounts.services.PasswordResetToken.objects.select_for_update")
    @patch("apps.accounts.services.User.objects.filter")
    def test_confirm_password_reset_updates_user_and_revokes_sessions(
        self, mock_user_filter, mock_token_update, mock_val_pwd, mock_session_filter, mock_audit
    ):
        fake_user = MagicMock()
        fake_user.id = 10
        fake_user.is_active = True
        mock_user_filter.return_value.first.return_value = fake_user

        fake_token = MagicMock()
        mock_token_update.return_value.filter.return_value.first.return_value = fake_token

        user = confirm_password_reset(
            email="user@situr.smart",
            code="123456",
            new_password="NewSecurePassword2026!",
        )

        fake_user.set_password.assert_called_once_with("NewSecurePassword2026!")
        fake_user.save.assert_called_once()
        assert fake_token.used_at is not None
        mock_session_filter.return_value.update.assert_called_once()
        mock_audit.assert_called_once()
