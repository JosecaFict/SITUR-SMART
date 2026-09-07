import io
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.media.services import CloudinaryService


class MediaUploadSecurityTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    def test_upload_requires_authentication(self):
        """Verifica que el endpoint de subida esté protegido contra accesos anónimos."""
        url = reverse("media-upload")
        fake_file = SimpleUploadedFile("test.jpg", b"fake image content", content_type="image/jpeg")
        response = self.client.post(url, {"file": fake_file}, format="multipart")
        self.assertEqual(response.status_code, 401)


class MediaUploadServiceTests(SimpleTestCase):
    def test_is_configured_returns_false_when_settings_empty(self):
        with patch("apps.media.services.settings") as mock_settings:
            mock_settings.CLOUDINARY_CLOUD_NAME = ""
            mock_settings.CLOUDINARY_API_KEY = ""
            mock_settings.CLOUDINARY_API_SECRET = ""
            self.assertFalse(CloudinaryService.is_configured())

    def test_is_configured_returns_true_when_settings_present(self):
        with patch("apps.media.services.settings") as mock_settings:
            mock_settings.CLOUDINARY_CLOUD_NAME = "demo-cloud"
            mock_settings.CLOUDINARY_API_KEY = "12345"
            mock_settings.CLOUDINARY_API_SECRET = "secret"
            self.assertTrue(CloudinaryService.is_configured())

    @patch("apps.media.services.cloudinary.uploader.upload")
    @patch.object(CloudinaryService, "is_configured", return_value=True)
    def test_upload_image_success(self, mock_is_configured, mock_uploader_upload):
        mock_uploader_upload.return_value = {
            "secure_url": "https://res.cloudinary.com/demo/image/upload/v123/situr-smart/productos/sample.webp",
            "public_id": "situr-smart/productos/sample",
            "format": "webp",
            "bytes": 20480,
            "width": 800,
            "height": 600,
        }

        fake_file = SimpleUploadedFile("sample.webp", b"\x00\x01\x02", content_type="image/webp")
        result = CloudinaryService.upload_image(fake_file, folder="productos")

        self.assertEqual(
            result["url"],
            "https://res.cloudinary.com/demo/image/upload/v123/situr-smart/productos/sample.webp",
        )
        self.assertEqual(result["public_id"], "situr-smart/productos/sample")
        self.assertEqual(result["format"], "webp")
        self.assertEqual(result["bytes"], 20480)
        self.assertEqual(result["width"], 800)
        self.assertEqual(result["height"], 600)
