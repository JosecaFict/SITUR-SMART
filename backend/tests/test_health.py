from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse


class HealthViewTests(SimpleTestCase):
    @patch("apps.common.views.HealthView.database_is_available", return_value=True)
    def test_health_reports_database_available(self, database_is_available):
        response = self.client.get(reverse("health"))
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "database": "ok"}


class ApiRootViewTests(SimpleTestCase):
    def test_root_exposes_service_links(self):
        response = self.client.get(reverse("api-root"), HTTP_ACCEPT="application/json")

        assert response.status_code == 200
        assert response.json()["name"] == "SITUR-SMART API"
        assert response.json()["health"].endswith("/api/v1/health/")
