"""Contacto de la empresa y boton de WhatsApp en las tarjetas del asistente."""

from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.parse import unquote

from django.test import SimpleTestCase

from apps.assistant.contact import company_contact, whatsapp_number, whatsapp_url
from apps.assistant.recommendations import as_card
from apps.assistant.schema import for_model
from apps.assistant.travel_tools import tour_card
from tests.test_asistente import lodging
from tests.test_asistente_asesor import tour


class NumeroWhatsappTests(SimpleTestCase):
    def test_celulares_bolivianos_en_distintos_formatos(self):
        for phone in ("71234567", "+591 712-34567", "00591 71234567", "591-71234567", "(7) 123 4567"):
            self.assertEqual(whatsapp_number(phone), "59171234567", phone)
        self.assertEqual(whatsapp_number("61234567"), "59161234567")

    def test_fijos_y_numeros_raros_no_tienen_whatsapp(self):
        for phone in ("3-3456789", "2 2412345", "12345678", "7123456", "712345678", "", None):
            self.assertIsNone(whatsapp_number(phone), phone)

    def test_el_mensaje_dice_que_vio_y_desde_donde(self):
        url = whatsapp_url("71234567", 'el hospedaje "Hotel Sol"')
        self.assertTrue(url.startswith("https://wa.me/59171234567?text="))
        self.assertEqual(
            unquote(url.split("text=")[1]),
            'Hola, vi el hospedaje "Hotel Sol" en SITUR-SMART y quisiera hacer una consulta.',
        )


class ContactoEmpresaTests(SimpleTestCase):
    def test_celular_y_correo(self):
        contact = company_contact(
            SimpleNamespace(phone=" 71234567 ", contact_email="info@hotel.bo"), 'el tour "X"'
        )
        self.assertEqual(contact["telefono"], "71234567")
        self.assertTrue(contact["whatsapp"])
        self.assertIn("wa.me/59171234567", contact["whatsapp_url"])
        self.assertEqual(contact["email"], "info@hotel.bo")

    def test_fijo_se_muestra_solo_para_llamar(self):
        contact = company_contact(SimpleNamespace(phone="3-3456789", contact_email=None), "x")
        self.assertEqual(contact["telefono"], "3-3456789")
        self.assertFalse(contact["whatsapp"])
        self.assertIsNone(contact["whatsapp_url"])

    def test_sin_telefono_ni_correo_no_hay_contacto(self):
        self.assertIsNone(company_contact(SimpleNamespace(phone="  ", contact_email=None), "x"))
        self.assertIsNone(company_contact(MagicMock(), "x"))


class TarjetasTests(SimpleTestCase):
    def _hotel(self):
        item = lodging()
        item.tenant.phone = "71234567"
        item.tenant.contact_email = None
        return item

    def test_la_api_publica_no_muestra_el_telefono(self):
        self.assertNotIn("contacto", as_card(self._hotel()))

    def test_el_asistente_agrega_el_contacto_a_la_tarjeta(self):
        item = self._hotel()
        card = as_card(item, contact=True)
        self.assertTrue(card["contacto"]["whatsapp"])
        self.assertIn(item.product.name.replace(" ", "%20"), card["contacto"]["whatsapp_url"])

    def test_los_tours_tambien_traen_contacto(self):
        product = tour()
        product.tenant = SimpleNamespace(trade_name="Agencia Andina", phone="77700011", contact_email=None)
        card = tour_card(product)
        self.assertIn("wa.me/59177700011", card["contacto"]["whatsapp_url"])

    def test_el_modelo_sabe_que_hay_whatsapp_pero_no_ve_el_enlace(self):
        card = as_card(self._hotel(), contact=True)
        seen = for_model(card)
        self.assertEqual(seen["contacto"]["telefono"], "71234567")
        self.assertTrue(seen["contacto"]["whatsapp"])
        self.assertNotIn("whatsapp_url", seen["contacto"])
