from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse


class HealthViewTests(SimpleTestCase):
    @patch("apps.common.views.HealthView.database_is_available", return_value=True)
    def test_health_reports_database_available(self, database_is_available):
        response = self.client.get(reverse("health"))
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["database"] == "ok"
        assert set(payload["integraciones"]) == {"cloudinary", "brevo"}

    @patch("apps.common.views.HealthView.database_is_available", return_value=True)
    def test_health_reports_integrations_as_booleans(self, database_is_available):
        with (
            patch("apps.common.views.CloudinaryService.is_configured", return_value=True),
            patch("apps.common.views.brevo_is_configured", return_value=False),
        ):
            response = self.client.get(reverse("health"))

        assert response.status_code == 200
        assert response.json()["integraciones"] == {"cloudinary": True, "brevo": False}

    @patch("apps.common.views.HealthView.database_is_available", return_value=True)
    def test_health_never_exposes_credential_values(self, database_is_available):
        """El endpoint es publico: solo puede informar presencia, nunca valores."""
        response = self.client.get(reverse("health"))

        assert all(isinstance(value, bool) for value in response.json()["integraciones"].values())

    @patch("apps.common.views.HealthView.database_is_available", return_value=False)
    def test_health_degraded_when_database_is_down(self, database_is_available):
        response = self.client.get(reverse("health"))

        assert response.status_code == 503
        assert response.json()["status"] == "degraded"
        assert response.json()["database"] == "error"


class ApiRootViewTests(SimpleTestCase):
    def test_root_exposes_service_links(self):
        response = self.client.get(reverse("api-root"), HTTP_ACCEPT="application/json")

        assert response.status_code == 200
        assert response.json()["name"] == "SITUR-SMART API"
        assert response.json()["health"].endswith("/api/v1/health/")
