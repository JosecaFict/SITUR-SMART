from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from apps.catalog.serializers import ProductWriteSerializer
from apps.catalog.services import _unique_product_code
from apps.catalog.views import PublicProductListView


class ProductWriteSerializerTests(SimpleTestCase):
    def test_create_requires_core_product_fields(self):
        serializer = ProductWriteSerializer(data={})

        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            set(serializer.errors),
            {
                "tipo_codigo",
                "ciudad_id",
                "moneda_codigo",
                "nombre",
                "precio_base",
                "capacidad_maxima",
            },
        )

    def test_rejects_negative_price(self):
        serializer = ProductWriteSerializer(data={"precio_base": "-1"}, partial=True)

        self.assertFalse(serializer.is_valid())
        self.assertIn("precio_base", serializer.errors)


class ProductServiceTests(SimpleTestCase):
    @patch("apps.catalog.services.TourismProduct.objects.filter")
    def test_unique_code_adds_suffix_when_code_exists(self, product_filter):
        product_filter.side_effect = [
            MagicMock(exists=MagicMock(return_value=True)),
            MagicMock(exists=MagicMock(return_value=False)),
        ]

        self.assertEqual(_unique_product_code(7, "Tour Samaipata"), "TOUR_SAMAIPATA_2")


class PublicMarketplaceValidationTests(SimpleTestCase):
    @patch("apps.catalog.views.TourismProduct.objects.select_related")
    def test_rejects_invalid_price_filter(self, select_related):
        products = MagicMock()
        products.filter.return_value = products
        select_related.return_value = products
        request = APIRequestFactory().get("/api/v1/marketplace/productos/?precio_min=gratis")

        response = PublicProductListView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn("precio_min", response.data["error"]["details"])

    @patch("apps.catalog.views.TourismProduct.objects.select_related")
    def test_rejects_invalid_date_filter(self, select_related):
        products = MagicMock()
        products.filter.return_value = products
        select_related.return_value = products
        request = APIRequestFactory().get("/api/v1/marketplace/productos/?fecha=mañana")

        response = PublicProductListView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn("fecha", response.data["error"]["details"])
