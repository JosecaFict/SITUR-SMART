"""Pruebas de los datos de ``seed_bolivia``.

La suite corre sobre SQLite sin las tablas de negocio (``managed = False``), asi
que el comando no se ejecuta aqui. Lo que si se verifica es que los datos
respeten las reglas que el backend impone al cargarlos: cupos del plan,
habitaciones publicables, capacidades y correos unicos. Si alguien agrega una
empresa que rompe una regla, falla aqui y no a mitad de la carga.
"""

from collections import Counter
from decimal import Decimal

from django.test import SimpleTestCase

from apps.catalog.seed import bolivia, credenciales

# Cupos de la migracion 0003_plan_suscripcion (max_usuarios, max_productos).
PLAN_QUOTAS = {"BASICO": (3, 15), "PROFESIONAL": (10, 60), "EMPRESARIAL": (None, None)}
SEEDED_CITIES = {
    "Santa Cruz de la Sierra", "La Paz", "Cochabamba", "Sucre", "Uyuni",
    "Samaipata", "Rurrenabaque", "Copacabana", "Potosí",
}
SIMPLE_PRODUCT_TYPES = {"RESTAURANTE", "TOUR", "EXPERIENCIA", "ATRACCION", "PAQUETE"}
STATUSES = {"BORRADOR", "PUBLICADO", "INACTIVO"}
TENANT_PERMISSIONS = {
    "USUARIOS_LEER", "USUARIOS_GESTIONAR", "ROLES_GESTIONAR", "PRODUCTOS_LEER",
    "PRODUCTOS_GESTIONAR", "DISPONIBILIDAD_GESTIONAR", "RESERVAS_LEER",
    "RESERVAS_GESTIONAR", "REPORTES_TENANT", "BITACORA_LEER",
}


def product_count(empresa: dict) -> int:
    return sum(1 + len(h["habitaciones"]) for h in empresa["hoteles"]) + len(empresa["productos"])


class SeedBoliviaDataTests(SimpleTestCase):
    def test_emails_are_unique_and_use_company_domain(self):
        emails = bolivia.todos_los_emails()
        self.assertEqual([e for e, n in Counter(emails).items() if n > 1], [])
        for empresa in bolivia.EMPRESAS:
            for cuenta in bolivia.cuentas_empresa(empresa):
                self.assertTrue(cuenta["email"].endswith("@" + empresa["dominio"]))
            self.assertTrue(empresa["dominio"].endswith(".com.bo"))

    def test_owner_account_follows_convention(self):
        for empresa in bolivia.EMPRESAS:
            owner = bolivia.cuentas_empresa(empresa)[0]
            self.assertEqual(owner["email"], f"jefeadmin@{empresa['dominio']}")
            self.assertEqual(owner["rol"], "TENANT_ADMIN")

    def test_company_names_are_unique(self):
        names = [e["nombre"] for e in bolivia.EMPRESAS]
        self.assertEqual(len(names), len(set(names)))

    def test_companies_fit_their_plan(self):
        for empresa in bolivia.EMPRESAS:
            max_users, max_products = PLAN_QUOTAS[empresa["plan"]]
            with self.subTest(empresa=empresa["nombre"]):
                if max_users is not None:
                    self.assertLessEqual(len(bolivia.cuentas_empresa(empresa)), max_users)
                if max_products is not None:
                    self.assertLessEqual(product_count(empresa), max_products)

    def test_cities_exist_or_are_created(self):
        known = SEEDED_CITIES | {c["nombre"] for c in bolivia.CIUDADES_NUEVAS}
        for empresa in bolivia.EMPRESAS:
            used = {empresa["ciudad"]}
            used |= {h["ciudad"] for h in empresa["hoteles"]}
            used |= {p["ciudad"] for p in empresa["productos"]}
            self.assertLessEqual(used, known, empresa["nombre"])

    def test_roles_exist_and_only_use_tenant_permissions(self):
        valid = set(bolivia.ROLES_PERSONALIZADOS) | set(bolivia.ROLES_SISTEMA)
        for empresa in bolivia.EMPRESAS:
            for persona in empresa["empleados"]:
                self.assertIn(persona["rol"], valid)
        for role in bolivia.ROLES_PERSONALIZADOS.values():
            self.assertLessEqual(set(role["permisos"]), TENANT_PERMISSIONS)

    def test_published_hotels_have_a_publishable_room(self):
        """El backend rechaza publicar un hotel sin habitacion publicada con precio > 0."""
        for empresa in bolivia.EMPRESAS:
            for hotel in empresa["hoteles"]:
                if hotel["estado"] != "PUBLICADO":
                    continue
                self.assertTrue(
                    any(
                        r["estado"] == "PUBLICADO" and r["precio_base"] > 0
                        for r in hotel["habitaciones"]
                    ),
                    hotel["nombre"],
                )

    def test_rooms_respect_capacity_rules(self):
        for empresa in bolivia.EMPRESAS:
            for hotel in empresa["hoteles"]:
                for room in hotel["habitaciones"]:
                    with self.subTest(hotel=hotel["nombre"], room=room["nombre"]):
                        self.assertGreater(room["capacidad_maxima"], 0)
                        self.assertGreater(room["capacidad_adultos"], 0)
                        self.assertLessEqual(room["capacidad_adultos"], room["capacidad_maxima"])
                        self.assertLessEqual(room["capacidad_ninos"], room["capacidad_maxima"])
                        self.assertGreater(room["cantidad_habitaciones"], 0)
                        self.assertIsInstance(room["precio_base"], Decimal)
                        self.assertIn(room["estado"], STATUSES)

    def test_hotels_have_complete_profile(self):
        for empresa in bolivia.EMPRESAS:
            for hotel in empresa["hoteles"]:
                with self.subTest(hotel=hotel["nombre"]):
                    self.assertTrue(1 <= hotel["estrellas"] <= 5)
                    self.assertTrue(-90 <= Decimal(hotel["latitud"]) <= 90)
                    self.assertTrue(-180 <= Decimal(hotel["longitud"]) <= 180)
                    self.assertTrue(hotel["servicios"])
                    self.assertTrue(hotel["habitaciones"])

    def test_simple_products_are_valid(self):
        for empresa in bolivia.EMPRESAS:
            names = [p["nombre"] for p in empresa["productos"]]
            self.assertEqual(len(names), len(set(names)), empresa["nombre"])
            for item in empresa["productos"]:
                with self.subTest(producto=item["nombre"]):
                    self.assertIn(item["tipo"], SIMPLE_PRODUCT_TYPES)
                    self.assertIn(item["estado"], STATUSES)
                    self.assertGreater(item["capacidad_maxima"], 0)
                    self.assertGreaterEqual(item["precio_base"], 0)

    def test_pending_company_has_nothing_to_load(self):
        """Una empresa PENDIENTE no puede operar, asi que no se le carga nada."""
        for empresa in bolivia.EMPRESAS:
            if empresa["estado"] == "PENDIENTE":
                self.assertEqual(empresa["empleados"], [])
                self.assertEqual(empresa["hoteles"], [])
                self.assertEqual(empresa["productos"], [])

    def test_all_three_plans_are_used(self):
        self.assertEqual({e["plan"] for e in bolivia.EMPRESAS}, set(PLAN_QUOTAS))

    def test_no_images_are_loaded(self):
        for empresa in bolivia.EMPRESAS:
            for item in [*empresa["hoteles"], *empresa["productos"]]:
                self.assertNotIn("imagen_url", item)


class CredentialsFileTests(SimpleTestCase):
    def test_lists_every_account_and_the_password(self):
        content = credenciales.render()
        self.assertIn(bolivia.PASSWORD, content)
        for email in bolivia.todos_los_emails():
            self.assertIn(email, content)
        for empresa in bolivia.EMPRESAS:
            self.assertIn(empresa["nombre"], content)

    def test_offer_summary(self):
        cortez = next(e for e in bolivia.EMPRESAS if e["nombre"] == "Hotel Cortez")
        self.assertEqual(credenciales.resumen_oferta(cortez), "1 hotel, 4 tipos de habitación")
        tupiza = next(e for e in bolivia.EMPRESAS if e["nombre"] == "Tupiza Tours")
        self.assertEqual(credenciales.resumen_oferta(tupiza), "Sin oferta cargada todavía")
