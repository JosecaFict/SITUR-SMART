from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.catalog.models import TourismProduct
from apps.catalog.services import create_product
from apps.rbac.services import is_superadmin
from apps.tenancy.models import Tenant
from apps.tenancy.services import create_company

IMAGES = [
    "/images/auth-carousel/Hotel1.jpg",
    "/images/auth-carousel/Hotel2-mejorada.png",
    "/images/auth-carousel/Hotel3-mejorada.png",
    "/images/auth-carousel/Hotel4.webp",
    "/images/auth-carousel/Imagen1-mejorada.png",
    "/images/auth-carousel/Imagen2-mejorada.png",
    "/images/auth-carousel/Imagen3-mejorada.png",
    "/images/auth-carousel/Imagen4-mejorada.png",
    "/images/auth-carousel/Imagen5-mejorada.png",
    "/images/auth-carousel/Imagen6-mejorada.png",
    "/images/auth-carousel/Imagen7-mejorada.png",
]

# Empresas de ejemplo. La contrasena de cada propietario es "Empresa1234".
COMPANIES = [
    {
        "razon_social": "Andes Boutique Hotels SRL",
        "nombre_comercial": "Andes Boutique Hotels",
        "ciudad_id": 2,
        "email_contacto": "contacto@andesboutique.com",
        "plan_codigo": "PROFESIONAL",
        "propietario": {
            "email": "duenio1@situr.smart", "nombres": "Marisol", "apellidos": "Quispe",
            "password": "Empresa1234",
        },
    },
    {
        "razon_social": "Crucena Hospitality SA",
        "nombre_comercial": "Cruceña Hospitality",
        "ciudad_id": 1,
        "email_contacto": "contacto@crucenahospitality.com",
        "plan_codigo": "PROFESIONAL",
        "propietario": {
            "email": "duenio2@situr.smart", "nombres": "Ronald", "apellidos": "Vaca",
            "password": "Empresa1234",
        },
    },
    {
        "razon_social": "Kanata Turismo SRL",
        "nombre_comercial": "Kanata Turismo",
        "ciudad_id": 2,
        "email_contacto": "contacto@kanataturismo.com",
        "plan_codigo": "BASICO",
        "propietario": {
            "email": "duenio3@situr.smart", "nombres": "Elena", "apellidos": "Mamani",
            "password": "Empresa1234",
        },
    },
    {
        "razon_social": "Sabores de Bolivia SRL",
        "nombre_comercial": "Sabores de Bolivia",
        "ciudad_id": 3,
        "email_contacto": "contacto@saboresdebolivia.com",
        "plan_codigo": "BASICO",
        "propietario": {
            "email": "duenio4@situr.smart", "nombres": "Freddy", "apellidos": "Rojas",
            "password": "Empresa1234",
        },
    },
]

# (empresa, tipo_codigo, ciudad_id, nombre, descripcion, localidad, precio_base, capacidad_maxima)
PRODUCTS = [
    ("Andes Boutique Hotels", "HOTEL", 2, "Hotel Kachi Wasi", "Hotel boutique con piscina interior y vista a la ciudad de La Paz.", "Zona Sur", "450.00", 40),
    ("Cruceña Hospitality", "HOTEL", 1, "Resort Laguna Urubo", "Resort con piscina de olas artificiales y areas verdes en Urubo.", "Urubo", "620.00", 80),
    ("Kanata Turismo", "TOUR", 2, "Teleferico y Miradores de La Paz", "Recorrido por las lineas del teleferico con miradores panoramicos de la ciudad.", "Centro", "120.00", 15),
    ("Cruceña Hospitality", "EXPERIENCIA", 1, "Catedral y Casco Viejo al Atardecer", "Recorrido guiado por el casco historico de Santa Cruz de la Sierra.", "Casco Viejo", "80.00", 20),

    ("Kanata Turismo", "TOUR", 5, "Salar de Uyuni al Amanecer", "Excursion de un dia al salar mas grande del mundo, con salida antes del amanecer.", "Salar de Uyuni", "250.00", 12),
    ("Kanata Turismo", "TOUR", 7, "Selva y Pampas de Rurrenabaque", "Expedicion de tres dias por la selva amazonica y las pampas bolivianas.", "Rio Beni", "780.00", 10),
    ("Kanata Turismo", "EXPERIENCIA", 6, "Ruinas del Fuerte de Samaipata", "Visita guiada al sitio arqueologico preincaico declarado Patrimonio de la Humanidad.", "Fuerte de Samaipata", "90.00", 20),
    ("Kanata Turismo", "TOUR", 8, "Peregrinacion al Lago Titicaca", "Recorrido en bote por el lago navegable mas alto del mundo, con parada en la Isla del Sol.", "Copacabana", "180.00", 15),
    ("Kanata Turismo", "EXPERIENCIA", 9, "Minas de Plata de Potosi", "Ingreso guiado a las minas historicas del Cerro Rico con equipo de seguridad incluido.", "Cerro Rico", "110.00", 12),

    ("Andes Boutique Hotels", "HABITACION", 2, "Habitacion Deluxe Vista Illimani", "Habitacion con balcon y vista directa al nevado Illimani.", "Zona Sur", "380.00", 2),
    ("Andes Boutique Hotels", "HABITACION", 2, "Habitacion Suite Ejecutiva", "Suite con sala de estar independiente, ideal para viajes de negocio.", "Zona Sur", "520.00", 3),
    ("Andes Boutique Hotels", "HOTEL", 4, "Hotel Wayra Sucre", "Hotel colonial restaurado en pleno centro historico de Sucre.", "Centro Historico", "410.00", 45),
    ("Andes Boutique Hotels", "HABITACION", 4, "Habitacion Doble Superior Sucre", "Habitacion doble con patio colonial y desayuno incluido.", "Centro Historico", "220.00", 2),
    ("Andes Boutique Hotels", "HOTEL", 3, "Hotel Amanecer Cochabamba", "Hotel familiar cerca de la plaza principal de Cochabamba.", "Centro", "320.00", 50),
    ("Andes Boutique Hotels", "HABITACION", 3, "Habitacion Familiar Cochabamba", "Habitacion para hasta 4 personas con dos camas queen.", "Centro", "280.00", 4),
    ("Andes Boutique Hotels", "HOTEL", 5, "Hotel Refugio Uyuni", "Hotel de paredes de sal a minutos del Salar de Uyuni.", "Cerca del Salar", "450.00", 35),
    ("Andes Boutique Hotels", "HABITACION", 5, "Habitacion Estandar Uyuni", "Habitacion con calefaccion para las noches frias del altiplano.", "Cerca del Salar", "190.00", 2),
    ("Andes Boutique Hotels", "HOTEL", 8, "Hotel Mirador Copacabana", "Hotel con vista panoramica al Lago Titicaca.", "Malecon", "360.00", 40),
    ("Andes Boutique Hotels", "HABITACION", 8, "Habitacion Vista al Lago Copacabana", "Habitacion con ventanal frente al lago.", "Malecon", "210.00", 2),
    ("Andes Boutique Hotels", "HOTEL", 9, "Hotel Colonial Potosi", "Hotel boutique en una casona colonial restaurada.", "Centro Historico", "300.00", 30),
    ("Andes Boutique Hotels", "HABITACION", 9, "Habitacion Superior Potosi", "Habitacion con chimenea y vista a los tejados coloniales.", "Centro Historico", "170.00", 2),
    ("Andes Boutique Hotels", "HABITACION", 2, "Habitacion Junior Suite La Paz", "Habitacion amplia con zona de trabajo y minibar.", "Zona Sur", "460.00", 3),

    ("Cruceña Hospitality", "HABITACION", 1, "Habitacion Ejecutiva Urubo", "Habitacion con acceso a piscina y areas verdes en Urubo.", "Urubo", "340.00", 2),
    ("Cruceña Hospitality", "HABITACION", 1, "Habitacion Doble Estandar", "Habitacion doble con aire acondicionado, ideal para el clima cruceno.", "Equipetrol", "260.00", 2),
    ("Cruceña Hospitality", "EXPERIENCIA", 1, "Tour Jardin Botanico de Santa Cruz", "Recorrido guiado por la reserva de flora nativa cruceña.", "Jardin Botanico", "60.00", 25),
    ("Cruceña Hospitality", "ATRACCION", 1, "Bioparque Ovis y Reserva Natural", "Visita al bioparque con especies nativas de la region.", "Km 7 doble via a la Guardia", "45.00", 100),
    ("Cruceña Hospitality", "ATRACCION", 6, "Fuerte de Samaipata (Sitio UNESCO)", "Sitio arqueologico preincaico con la roca tallada mas grande de Sudamerica.", "Samaipata", "60.00", 80),
    ("Cruceña Hospitality", "EXPERIENCIA", 6, "Ruta del Vino en los Valles", "Degustacion de vinos y singanis en las bodegas de los valles cruceños.", "Valles Cruceños", "140.00", 18),
    ("Cruceña Hospitality", "HOTEL", 1, "Hotel Jardines del Urubo", "Hotel con jardines tropicales y piscina infinita.", "Urubo", "480.00", 60),
    ("Cruceña Hospitality", "HABITACION", 1, "Habitacion Suite Presidencial", "La suite mas exclusiva del hotel, con jacuzzi privado.", "Urubo", "890.00", 2),
    ("Cruceña Hospitality", "ATRACCION", 1, "Museo de Historia Natural Noel Kempff", "Coleccion de fauna y flora del oriente boliviano.", "Centro", "35.00", 150),
    ("Cruceña Hospitality", "EXPERIENCIA", 1, "Tour Gastronomico Cruceño", "Recorrido por los sabores tipicos del oriente boliviano.", "Casco Viejo", "95.00", 16),
    ("Cruceña Hospitality", "ATRACCION", 6, "Laguna Volcan Aventura", "Actividades de aventura y senderismo en la laguna volcanica.", "Samaipata", "70.00", 40),
    ("Cruceña Hospitality", "HOTEL", 1, "Hotel Boutique Casco Viejo", "Hotel pequeño y acogedor en el centro historico cruceño.", "Casco Viejo", "390.00", 25),

    ("Andes Boutique Hotels", "HOTEL", 2, "Hotel Illimani Suites", "Suites modernas con vista al nevado Illimani.", "Zona Sur", "540.00", 40),
    ("Andes Boutique Hotels", "HOTEL", 4, "Hotel Valle Encantado", "Hotel rodeado de jardines en las afueras de Sucre.", "Valle de Sucre", "390.00", 35),
    ("Andes Boutique Hotels", "HOTEL", 2, "Hotel Altiplano Boutique", "Hotel boutique de diseño andino contemporaneo.", "San Miguel", "470.00", 28),
    ("Andes Boutique Hotels", "HOTEL", 5, "Hotel Salar Blanco", "Construccion de bloques de sal a orillas del Salar de Uyuni.", "Salar de Uyuni", "500.00", 32),
    ("Andes Boutique Hotels", "HOTEL", 8, "Hotel Titicaca Sunset", "Hotel con terraza para ver el atardecer sobre el lago.", "Copacabana", "410.00", 38),

    ("Andes Boutique Hotels", "HABITACION", 2, "Habitacion Twin Vista Ciudad", "Dos camas individuales con vista a la ciudad de La Paz.", "Zona Sur", "240.00", 2),
    ("Andes Boutique Hotels", "HABITACION", 4, "Habitacion Matrimonial Colonial", "Habitacion con mobiliario colonial restaurado.", "Centro Historico", "230.00", 2),
    ("Andes Boutique Hotels", "HABITACION", 2, "Habitacion Individual Ejecutiva", "Habitacion compacta pensada para viajeros de negocio.", "San Miguel", "180.00", 1),
    ("Andes Boutique Hotels", "HABITACION", 5, "Habitacion Panoramica Salar", "Ventanal de piso a techo frente al salar.", "Salar de Uyuni", "310.00", 2),
    ("Andes Boutique Hotels", "HABITACION", 8, "Habitacion Romantica Lago", "Habitacion con jacuzzi y vista al Lago Titicaca.", "Copacabana", "350.00", 2),

    ("Kanata Turismo", "TOUR", 3, "Excursion a las Cavernas del Repechon", "Recorrido de un dia por las cavernas naturales cerca de Cochabamba.", "Repechon", "130.00", 14),
    ("Kanata Turismo", "TOUR", 2, "City Tour La Paz Historica", "Recorrido por el centro historico y los mercados tradicionales de La Paz.", "Centro", "70.00", 20),
    ("Kanata Turismo", "TOUR", 2, "Aventura en Bicicleta Camino de la Muerte", "Descenso en bicicleta por la carretera mas famosa de Bolivia.", "Yungas", "220.00", 10),
    ("Kanata Turismo", "TOUR", 2, "Tour Nocturno Valle de la Luna", "Recorrido nocturno por las formaciones rocosas del Valle de la Luna.", "Valle de la Luna", "85.00", 18),
    ("Kanata Turismo", "TOUR", 5, "Travesia por el Desierto de Siloli", "Expedicion de varios dias por los desiertos altoandinos del suroeste.", "Desierto de Siloli", "690.00", 8),

    ("Cruceña Hospitality", "EXPERIENCIA", 1, "Taller de Cocina Cruceña", "Clase practica de platos tipicos del oriente boliviano.", "Equipetrol", "120.00", 12),
    ("Cruceña Hospitality", "EXPERIENCIA", 6, "Cabalgata en los Valles", "Paseo a caballo por los valles mesotermicos de Samaipata.", "Valles de Samaipata", "150.00", 10),
    ("Cruceña Hospitality", "EXPERIENCIA", 1, "Observacion de Aves en la Reserva", "Recorrido guiado de avistamiento de aves nativas.", "Reserva Natural", "100.00", 14),
    ("Cruceña Hospitality", "EXPERIENCIA", 1, "Noche de Folklore Oriental", "Cena show con musica y danzas tradicionales cruceñas.", "Casco Viejo", "160.00", 60),
    ("Cruceña Hospitality", "EXPERIENCIA", 6, "Caminata Nocturna Samaipata", "Caminata guiada bajo las estrellas por senderos de Samaipata.", "Samaipata", "90.00", 15),

    ("Cruceña Hospitality", "ATRACCION", 1, "Parque Urbano Arenal", "Parque central con laguna artificial en pleno centro de Santa Cruz.", "Centro", "0.00", 500),
    ("Cruceña Hospitality", "ATRACCION", 6, "Mirador El Mechero", "Formacion rocosa con vista panoramica de los valles de Samaipata.", "Samaipata", "20.00", 60),
    ("Cruceña Hospitality", "ATRACCION", 1, "Catedral Metropolitana de Santa Cruz", "Visita guiada a la catedral y su museo de arte sacro.", "Plaza 24 de Septiembre", "15.00", 100),
    ("Cruceña Hospitality", "ATRACCION", 1, "Zoologico Municipal Fauna Sudamericana", "Zoologico con especies representativas de Sudamerica.", "Zona Norte", "30.00", 200),
    ("Cruceña Hospitality", "ATRACCION", 6, "Cueva de los Minerales", "Formaciones minerales naturales dentro de una cueva accesible.", "Samaipata", "25.00", 40),

    ("Cruceña Hospitality", "PAQUETE", 1, "Paquete Santa Cruz + Samaipata 3 Dias", "Paquete combinado de hotel, transporte y tour al Fuerte de Samaipata.", "Santa Cruz - Samaipata", "980.00", 6),
    ("Cruceña Hospitality", "PAQUETE", 1, "Paquete Fin de Semana en Urubo", "Dos noches de hotel con acceso a piscina y desayuno incluido.", "Urubo", "760.00", 8),
    ("Cruceña Hospitality", "PAQUETE", 6, "Paquete Ruta del Vino Completo", "Transporte, degustacion y almuerzo incluido en los valles cruceños.", "Valles Cruceños", "420.00", 12),
    ("Cruceña Hospitality", "PAQUETE", 6, "Paquete Aventura y Naturaleza", "Cabalgata, caminata nocturna y visita al Fuerte de Samaipata.", "Samaipata", "540.00", 10),
    ("Cruceña Hospitality", "PAQUETE", 1, "Paquete Gastronomico Cruceño", "Taller de cocina, cena show y tour gastronomico en dos dias.", "Santa Cruz", "610.00", 12),

    ("Sabores de Bolivia", "RESTAURANTE", 3, "Picanteria La Cochabambina", "Comida tipica cochabambina, famosa por su picante de pollo.", "La Cancha", "45.00", 80),
    ("Sabores de Bolivia", "RESTAURANTE", 2, "Restaurante Mirador Paceño", "Cocina altiplanica con vista panoramica de La Paz.", "San Jorge", "60.00", 50),
    ("Sabores de Bolivia", "RESTAURANTE", 1, "Parrilla Cruceña Camba", "Parrilla de carnes con acompañamientos del oriente boliviano.", "Equipetrol", "70.00", 65),
    ("Sabores de Bolivia", "RESTAURANTE", 4, "Comedor Colonial Sucre", "Cocina chuquisaqueña en un patio colonial restaurado.", "Centro Historico", "50.00", 45),
    ("Sabores de Bolivia", "RESTAURANTE", 9, "Fonda Minera Potosina", "Platos andinos de altura en un ambiente tradicional potosino.", "Centro Historico", "40.00", 35),
]


class Command(BaseCommand):
    help = (
        "Puebla la base de datos local con empresas y productos de ejemplo para "
        "pruebas y demostraciones. Es seguro volver a ejecutarlo: omite lo que ya exista."
    )

    def handle(self, *args, **options):
        admin = next((u for u in User.objects.filter(status=User.Status.ACTIVE) if is_superadmin(u)), None)
        if admin is None:
            raise CommandError(
                "No existe un SuperAdmin activo. Ejecuta antes: python manage.py createsituradmin"
            )

        tenant_by_name: dict[str, int] = {}

        with transaction.atomic():
            for data in COMPANIES:
                existing = Tenant.objects.filter(trade_name=data["nombre_comercial"]).first()
                if existing:
                    self.stdout.write(f"= empresa ya existe: {data['nombre_comercial']} (id={existing.id})")
                    tenant_by_name[data["nombre_comercial"]] = existing.id
                    continue
                company = create_company(actor=admin, **data)
                tenant_by_name[data["nombre_comercial"]] = company.id
                self.stdout.write(
                    self.style.SUCCESS(f"+ empresa creada: {company.trade_name} (id={company.id})")
                )

            created, skipped = 0, 0
            for i, (empresa, tipo, ciudad_id, nombre, descripcion, localidad, precio, capacidad) in enumerate(
                PRODUCTS
            ):
                tenant_id = tenant_by_name[empresa]
                if TourismProduct.objects.filter(tenant_id=tenant_id, name=nombre).exists():
                    skipped += 1
                    continue
                create_product(
                    actor=admin,
                    tenant_id=tenant_id,
                    tipo_codigo=tipo,
                    ciudad_id=ciudad_id,
                    moneda_codigo="BOB",
                    nombre=nombre,
                    descripcion=descripcion,
                    localidad=localidad,
                    precio_base=precio,
                    capacidad_maxima=capacidad,
                    estado="PUBLICADO",
                    imagen_url=IMAGES[i % len(IMAGES)],
                )
                created += 1

        self.stdout.write(self.style.SUCCESS(f"Listo: {created} productos creados, {skipped} ya existian."))
