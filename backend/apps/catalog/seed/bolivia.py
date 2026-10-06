"""Datos de demostracion de SITUR-SMART: oferta turistica de Bolivia.

Este archivo solo contiene datos; la carga la hace el comando ``seed_bolivia``.
Para agregar una empresa basta con sumar un diccionario a ``EMPRESAS``.

Convenciones:

* Toda cuenta usa la contrasena ``PASSWORD``.
* El correo se arma con el usuario y el dominio de la empresa:
  ``jefeadmin@<dominio>`` para el propietario, ``empleado1@<dominio>``,
  ``guia1@<dominio>``... para el personal. Cambiar el dominio de una empresa
  cambia todas sus cuentas.
* Los nombres de las empresas son reales; precios, habitaciones, servicios y
  coordenadas son aproximados y solo sirven para demostracion.
* No se cargan imagenes: ``imagen_url`` queda vacio y el equipo sube las fotos.
* Una agencia con "convenio" carga el hotel dentro de su propio tenant (por
  ejemplo SczTourBo con Los Tajibos). No existe relacion entre empresas.
* Todos los precios estan en bolivianos (BOB).
"""

from datetime import time
from decimal import Decimal

PASSWORD = "Admin123*"
MONEDA = "BOB"
PAIS = "BOL"

# Ciudades que no vienen en la siembra inicial (migracion 0002) y hacen falta
# para estas empresas. Se crean solo si no existen.
CIUDADES_NUEVAS = [
    {"nombre": "Tarija", "latitud": "-21.535500", "longitud": "-64.729600"},
    {"nombre": "Tupiza", "latitud": "-21.442800", "longitud": "-65.718900"},
]

SANTA_CRUZ = "Santa Cruz de la Sierra"
LA_PAZ = "La Paz"
COCHABAMBA = "Cochabamba"
SUCRE = "Sucre"
UYUNI = "Uyuni"
SAMAIPATA = "Samaipata"
RURRENABAQUE = "Rurrenabaque"
COPACABANA = "Copacabana"
POTOSI = "Potosí"
TARIJA = "Tarija"
TUPIZA = "Tupiza"

# Roles propios que crea cada empresa que los usa. Los de sistema
# (TENANT_EMPLOYEE y GUIA) ya existen y no se definen aqui.
ROLES_PERSONALIZADOS = {
    "RECEPCIONISTA": {
        "nombre": "Recepcionista",
        "permisos": [
            "PRODUCTOS_LEER", "DISPONIBILIDAD_GESTIONAR", "RESERVAS_LEER", "RESERVAS_GESTIONAR",
        ],
    },
    "ENCARGADO_CATALOGO": {
        "nombre": "Encargado de catálogo",
        "permisos": [
            "PRODUCTOS_LEER", "PRODUCTOS_GESTIONAR", "DISPONIBILIDAD_GESTIONAR", "REPORTES_TENANT",
        ],
    },
    "CAJERO": {
        "nombre": "Cajero",
        "permisos": ["PRODUCTOS_LEER", "RESERVAS_LEER", "RESERVAS_GESTIONAR"],
    },
}

ROLES_SISTEMA = {"TENANT_EMPLOYEE": "Empleado", "GUIA": "Guía turístico"}

PUBLICADO = "PUBLICADO"
BORRADOR = "BORRADOR"
INACTIVO = "INACTIVO"

# Mismos nombres que ofrece el formulario de hospedajes de la web, mas algunos
# propios. El asistente IA busca por estos textos.
WIFI = "Wi-Fi"
PISCINA = "Piscina"
DESAYUNO = "Desayuno incluido"
ESTACIONAMIENTO = "Estacionamiento"
AIRE = "Aire acondicionado"
GIMNASIO = "Gimnasio"
RESTAURANTE = "Restaurante"
SPA = "Spa"
RECEPCION_24 = "Recepción 24 h"
MASCOTAS = "Admite mascotas"
CALEFACCION = "Calefacción"
BAR = "Bar"
TRASLADO = "Traslado al aeropuerto"
LAVANDERIA = "Lavandería"
EVENTOS = "Sala de eventos"


def habitacion(
    nombre, descripcion, precio, *, capacidad, adultos=None, ninos=0, cama, cantidad,
    desayuno=True, estado=PUBLICADO,
):
    return {
        "nombre": nombre,
        "descripcion": descripcion,
        "precio_base": Decimal(precio),
        "capacidad_maxima": capacidad,
        "capacidad_adultos": capacidad if adultos is None else adultos,
        "capacidad_ninos": ninos,
        "tipo_cama": cama,
        "cantidad_habitaciones": cantidad,
        "incluye_desayuno": desayuno,
        "estado": estado,
    }


def producto(tipo, nombre, descripcion, precio, *, ciudad, localidad, capacidad, estado=PUBLICADO):
    return {
        "tipo": tipo,
        "nombre": nombre,
        "descripcion": descripcion,
        "precio_base": Decimal(precio),
        "ciudad": ciudad,
        "localidad": localidad,
        "capacidad_maxima": capacidad,
        "estado": estado,
    }


def empleado(usuario, rol):
    return {"usuario": usuario, "rol": rol}


EMPRESAS = [
    # ------------------------------------------------------------------
    # Hoteles independientes
    # ------------------------------------------------------------------
    {
        "nombre": "Hotel Cortez",
        "dominio": "hotelcortez.com.bo",
        "ciudad": SANTA_CRUZ,
        "plan": "BASICO",
        "perfil": "Solo hotel",
        "estado": "ACTIVO",
        "empleados": [empleado("empleado1", "RECEPCIONISTA"), empleado("empleado2", "TENANT_EMPLOYEE")],
        "hoteles": [
            {
                "nombre": "Hotel Cortez",
                "descripcion": (
                    "Hotel tradicional de Santa Cruz de la Sierra sobre el segundo anillo, a "
                    "pocos minutos del centro histórico y de la zona de Equipetrol. Piscina "
                    "rodeada de jardines tropicales, ideal para el clima cálido del oriente."
                ),
                "ciudad": SANTA_CRUZ,
                "localidad": "Segundo anillo",
                "direccion": "Av. Cristóbal de Mendoza 280, segundo anillo",
                "latitud": "-17.771300",
                "longitud": "-63.187300",
                "estrellas": 4,
                "check_in": time(14, 0),
                "check_out": time(12, 0),
                "servicios": [WIFI, PISCINA, DESAYUNO, ESTACIONAMIENTO, AIRE, RESTAURANTE, RECEPCION_24],
                "estado": PUBLICADO,
                "habitaciones": [
                    habitacion("Habitación Simple", "Habitación para una persona con escritorio y aire acondicionado.",
                               "350.00", capacidad=1, cama="1 cama de plaza y media", cantidad=12),
                    habitacion("Habitación Doble Estándar", "Dos camas individuales, ideal para viajes de trabajo o amigos.",
                               "480.00", capacidad=2, cama="2 camas individuales", cantidad=20),
                    habitacion("Habitación Matrimonial Superior", "Cama king, vista a los jardines y la piscina.",
                               "560.00", capacidad=3, adultos=2, ninos=1, cama="1 cama king", cantidad=15),
                    habitacion("Suite Cortez", "Suite con sala de estar independiente y minibar.",
                               "850.00", capacidad=4, adultos=2, ninos=2, cama="1 cama king y sofá cama", cantidad=4),
                ],
            }
        ],
        "productos": [],
    },
    {
        "nombre": "Hotel La Cúpula",
        "dominio": "hotelcupula.com.bo",
        "ciudad": COPACABANA,
        "plan": "BASICO",
        "perfil": "Solo hotel",
        "estado": "ACTIVO",
        "empleados": [empleado("empleado1", "RECEPCIONISTA")],
        "hoteles": [
            {
                "nombre": "Hotel La Cúpula",
                "descripcion": (
                    "Hotel de estilo mediterráneo en la ladera del cerro Calvario, con jardines "
                    "en terrazas y una de las mejores vistas al Lago Titicaca. Punto de partida "
                    "para visitar la Isla del Sol."
                ),
                "ciudad": COPACABANA,
                "localidad": "Cerro Calvario",
                "direccion": "Calle Michel Pérez 1-3",
                "latitud": "-16.164700",
                "longitud": "-69.092000",
                "estrellas": 2,
                "check_in": time(13, 0),
                "check_out": time(11, 0),
                "servicios": [WIFI, RESTAURANTE, CALEFACCION, MASCOTAS],
                "estado": PUBLICADO,
                "habitaciones": [
                    habitacion("Habitación Simple", "Habitación sencilla con baño privado.",
                               "180.00", capacidad=1, cama="1 cama individual", cantidad=4, desayuno=False),
                    habitacion("Habitación Doble", "Habitación con vista parcial al lago.",
                               "260.00", capacidad=2, cama="1 cama matrimonial", cantidad=8, desayuno=False),
                    habitacion("Suite con Vista al Lago", "Suite con cocina pequeña y ventanal al Titicaca.",
                               "380.00", capacidad=3, adultos=2, ninos=1, cama="1 cama queen y 1 individual", cantidad=3),
                ],
            }
        ],
        "productos": [],
    },
    # ------------------------------------------------------------------
    # Hoteles con restaurante
    # ------------------------------------------------------------------
    {
        "nombre": "Hoteles Rosario",
        "dominio": "hotelesrosario.com.bo",
        "ciudad": LA_PAZ,
        "plan": "PROFESIONAL",
        "perfil": "Cadena: dos hoteles y restaurante",
        "estado": "ACTIVO",
        "empleados": [
            empleado("empleado1", "RECEPCIONISTA"),
            empleado("empleado2", "RECEPCIONISTA"),
            empleado("empleado3", "TENANT_EMPLOYEE"),
        ],
        "hoteles": [
            {
                "nombre": "Hotel Rosario La Paz",
                "descripcion": (
                    "Hotel de estilo colonial a pasos de la calle Sagárnaga y el Mercado de las "
                    "Brujas. Patio interior, decoración andina y fácil acceso al casco antiguo."
                ),
                "ciudad": LA_PAZ,
                "localidad": "Centro - Calle Illampu",
                "direccion": "Av. Illampu 704",
                "latitud": "-16.496000",
                "longitud": "-68.141500",
                "estrellas": 3,
                "check_in": time(14, 0),
                "check_out": time(11, 0),
                "servicios": [WIFI, DESAYUNO, RESTAURANTE, CALEFACCION, RECEPCION_24, LAVANDERIA],
                "estado": PUBLICADO,
                "habitaciones": [
                    habitacion("Habitación Simple", "Habitación individual con calefacción.",
                               "420.00", capacidad=1, cama="1 cama individual", cantidad=10),
                    habitacion("Habitación Doble", "Habitación doble con vista al patio colonial.",
                               "560.00", capacidad=2, cama="1 cama matrimonial", cantidad=18),
                    habitacion("Habitación Triple", "Para familias o grupos pequeños.",
                               "690.00", capacidad=3, ninos=2, cama="3 camas individuales", cantidad=6),
                    habitacion("Suite Rosario", "Suite amplia con sala y bañera.",
                               "790.00", capacidad=2, cama="1 cama king", cantidad=2, estado=BORRADOR),
                ],
            },
            {
                "nombre": "Hotel Rosario del Lago",
                "descripcion": (
                    "Hotel frente al Lago Titicaca, a pocas cuadras de la Basílica de "
                    "Copacabana. Terraza con vista al lago y excursiones a la Isla del Sol."
                ),
                "ciudad": COPACABANA,
                "localidad": "Costanera",
                "direccion": "Calle Rigoberto Paredes y Av. Costanera",
                "latitud": "-16.167600",
                "longitud": "-69.091500",
                "estrellas": 3,
                "check_in": time(14, 0),
                "check_out": time(11, 0),
                "servicios": [WIFI, DESAYUNO, RESTAURANTE, CALEFACCION, ESTACIONAMIENTO],
                "estado": PUBLICADO,
                "habitaciones": [
                    habitacion("Habitación Doble Vista al Lago", "Ventanal frente al Titicaca.",
                               "600.00", capacidad=2, cama="2 camas individuales", cantidad=14),
                    habitacion("Habitación Matrimonial", "Cama queen y vista al lago.",
                               "640.00", capacidad=2, cama="1 cama queen", cantidad=10),
                    habitacion("Habitación Familiar", "Dos ambientes para familias.",
                               "820.00", capacidad=4, adultos=3, ninos=2, cama="1 cama queen y 2 individuales", cantidad=4),
                ],
            },
        ],
        "productos": [
            producto("RESTAURANTE", "Restaurante del Hotel Rosario La Paz",
                     "Cocina boliviana y del altiplano: trucha del lago, sopa de quinua y platos con "
                     "charque. Abierto también para quienes no se hospedan.",
                     "85.00", ciudad=LA_PAZ, localidad="Centro - Calle Illampu", capacidad=70),
        ],
    },
    {
        "nombre": "Hotel Palacio de Sal",
        "dominio": "palaciodesal.com.bo",
        "ciudad": UYUNI,
        "plan": "BASICO",
        "perfil": "Hotel con restaurante",
        "estado": "ACTIVO",
        "empleados": [empleado("empleado1", "RECEPCIONISTA"), empleado("empleado2", "TENANT_EMPLOYEE")],
        "hoteles": [
            {
                "nombre": "Hotel Palacio de Sal",
                "descripcion": (
                    "Hotel construido con bloques de sal a orillas del Salar de Uyuni, cerca de "
                    "Colchani. Muros, muebles y esculturas de sal, con spa y piscina temperada "
                    "para las noches frías del altiplano."
                ),
                "ciudad": UYUNI,
                "localidad": "Orillas del Salar - Colchani",
                "direccion": "Borde del Salar de Uyuni, zona Colchani",
                "latitud": "-20.332600",
                "longitud": "-66.932700",
                "estrellas": 4,
                "check_in": time(13, 0),
                "check_out": time(10, 0),
                "servicios": [WIFI, DESAYUNO, RESTAURANTE, SPA, PISCINA, CALEFACCION, ESTACIONAMIENTO, BAR],
                "estado": PUBLICADO,
                "habitaciones": [
                    habitacion("Habitación Doble", "Habitación con muros de sal y calefacción.",
                               "1100.00", capacidad=2, cama="2 camas individuales", cantidad=12),
                    habitacion("Habitación Matrimonial", "Cama queen con cabecera de sal tallada.",
                               "1150.00", capacidad=2, cama="1 cama queen", cantidad=10),
                    habitacion("Suite Salar", "Suite con vista directa al salar.",
                               "1600.00", capacidad=3, adultos=2, ninos=1, cama="1 cama king", cantidad=3),
                ],
            }
        ],
        "productos": [
            producto("RESTAURANTE", "Restaurante del Palacio de Sal",
                     "Cocina andina de autor con carne de llama, quinua real y vinos tarijeños.",
                     "120.00", ciudad=UYUNI, localidad="Orillas del Salar - Colchani", capacidad=60),
        ],
    },
    {
        "nombre": "Parador Santa María La Real",
        "dominio": "paradorsantamaria.com.bo",
        "ciudad": SUCRE,
        "plan": "BASICO",
        "perfil": "Hotel con restaurante",
        "estado": "ACTIVO",
        "empleados": [empleado("empleado1", "RECEPCIONISTA")],
        "hoteles": [
            {
                "nombre": "Parador Santa María La Real",
                "descripcion": (
                    "Casona colonial del siglo XVIII restaurada en el centro histórico de Sucre, "
                    "Patrimonio de la Humanidad. Patios, túneles históricos y terraza con vista "
                    "a los techos blancos de la ciudad."
                ),
                "ciudad": SUCRE,
                "localidad": "Centro Histórico",
                "direccion": "Calle Bolívar 625",
                "latitud": "-19.047600",
                "longitud": "-65.259000",
                "estrellas": 4,
                "check_in": time(14, 0),
                "check_out": time(12, 0),
                "servicios": [WIFI, DESAYUNO, RESTAURANTE, SPA, RECEPCION_24, BAR],
                "estado": PUBLICADO,
                "habitaciones": [
                    habitacion("Habitación Superior", "Mobiliario colonial y techos altos.",
                               "650.00", capacidad=2, cama="1 cama queen", cantidad=10),
                    habitacion("Habitación Deluxe", "Balcón hacia el patio principal.",
                               "780.00", capacidad=2, cama="1 cama king", cantidad=8),
                    habitacion("Suite Colonial", "Suite con sala y bañera de época.",
                               "980.00", capacidad=3, adultos=2, ninos=1, cama="1 cama king y sofá cama", cantidad=3),
                ],
            }
        ],
        "productos": [
            producto("RESTAURANTE", "Restaurante del Parador",
                     "Cocina chuquisaqueña en el patio colonial: chorizos chuquisaqueños, mondongo y "
                     "chocolates de Sucre.",
                     "95.00", ciudad=SUCRE, localidad="Centro Histórico", capacidad=50),
        ],
    },
    # ------------------------------------------------------------------
    # Agencia completa: hotel en convenio, tours, experiencias y paquetes
    # ------------------------------------------------------------------
    {
        "nombre": "SczTourBo",
        "dominio": "scztourbo.com.bo",
        "ciudad": SANTA_CRUZ,
        "plan": "EMPRESARIAL",
        "perfil": "Agencia completa (hotel en convenio, tours y paquetes)",
        "estado": "ACTIVO",
        "empleados": [
            empleado("empleado1", "ENCARGADO_CATALOGO"),
            empleado("empleado2", "TENANT_EMPLOYEE"),
            empleado("guia1", "GUIA"),
            empleado("guia2", "GUIA"),
        ],
        "hoteles": [
            {
                "nombre": "Hotel Los Tajibos",
                "descripcion": (
                    "Hotel de cinco estrellas en Equipetrol, rodeado de jardines tropicales con "
                    "tajibos. Piscinas, spa, gimnasio y centro de convenciones. Ofrecido por "
                    "SczTourBo mediante convenio con el hotel."
                ),
                "ciudad": SANTA_CRUZ,
                "localidad": "Equipetrol",
                "direccion": "Av. San Martín 455, Equipetrol",
                "latitud": "-17.763900",
                "longitud": "-63.195300",
                "estrellas": 5,
                "check_in": time(15, 0),
                "check_out": time(12, 0),
                "servicios": [
                    WIFI, PISCINA, DESAYUNO, ESTACIONAMIENTO, AIRE, GIMNASIO, RESTAURANTE, SPA,
                    RECEPCION_24, BAR, TRASLADO, EVENTOS,
                ],
                "estado": PUBLICADO,
                "habitaciones": [
                    habitacion("Deluxe King", "Cama king, vista a los jardines.",
                               "950.00", capacidad=3, adultos=2, ninos=1, cama="1 cama king", cantidad=60),
                    habitacion("Deluxe Twin", "Dos camas dobles, ideal para familias.",
                               "950.00", capacidad=4, adultos=3, ninos=2, cama="2 camas dobles", cantidad=50),
                    habitacion("Club King", "Acceso al lounge ejecutivo y desayuno a la carta.",
                               "1250.00", capacidad=2, cama="1 cama king", cantidad=20),
                    habitacion("Junior Suite", "Sala de estar y terraza privada.",
                               "1600.00", capacidad=3, adultos=2, ninos=1, cama="1 cama king y sofá cama", cantidad=8),
                    habitacion("Suite Presidencial", "La suite más amplia del hotel, con comedor y jacuzzi.",
                               "3500.00", capacidad=4, adultos=2, ninos=2, cama="1 cama king", cantidad=1),
                ],
            }
        ],
        "productos": [
            producto("TOUR", "City Tour Santa Cruz de la Sierra",
                     "Recorrido por la Plaza 24 de Septiembre, la Catedral, el Casco Viejo y el "
                     "Parque Urbano. Incluye transporte y guía.",
                     "180.00", ciudad=SANTA_CRUZ, localidad="Casco Viejo", capacidad=15),
            producto("TOUR", "Lomas de Arena",
                     "Excursión a las dunas del Parque Regional Lomas de Arena con lagunas y "
                     "avistamiento de aves.",
                     "250.00", ciudad=SANTA_CRUZ, localidad="Parque Regional Lomas de Arena", capacidad=12),
            producto("TOUR", "Fuerte de Samaipata y Valles",
                     "Día completo al sitio arqueológico preincaico declarado Patrimonio de la "
                     "Humanidad, con almuerzo en el pueblo de Samaipata.",
                     "420.00", ciudad=SAMAIPATA, localidad="Fuerte de Samaipata", capacidad=12),
            producto("EXPERIENCIA", "Noche Cruceña con Show Folclórico",
                     "Cena típica (majadito, locro, cuñapé) con música y danzas del oriente boliviano.",
                     "230.00", ciudad=SANTA_CRUZ, localidad="Equipetrol", capacidad=40),
            producto("EXPERIENCIA", "Avistamiento de Aves en el Jardín Botánico",
                     "Recorrido temprano con guía especializado por el Jardín Botánico de Santa Cruz.",
                     "150.00", ciudad=SANTA_CRUZ, localidad="Jardín Botánico", capacidad=10),
            producto("PAQUETE", "Santa Cruz 3D/2N con Los Tajibos",
                     "Dos noches en Hotel Los Tajibos con desayuno, City Tour y traslados "
                     "aeropuerto-hotel.",
                     "2900.00", ciudad=SANTA_CRUZ, localidad="Equipetrol", capacidad=4),
            producto("PAQUETE", "Samaipata Express 2D/1N",
                     "Transporte, una noche en Samaipata, visita al Fuerte y caminata a La Pajcha.",
                     "1100.00", ciudad=SAMAIPATA, localidad="Samaipata", capacidad=8, estado=BORRADOR),
        ],
    },
    # ------------------------------------------------------------------
    # Solo restaurantes
    # ------------------------------------------------------------------
    {
        "nombre": "Gustu",
        "dominio": "gustu.com.bo",
        "ciudad": LA_PAZ,
        "plan": "BASICO",
        "perfil": "Solo restaurante",
        "estado": "ACTIVO",
        "empleados": [empleado("empleado1", "CAJERO")],
        "hoteles": [],
        "productos": [
            producto("RESTAURANTE", "Gustu",
                     "Restaurante de alta cocina boliviana en Calacoto. Menú degustación con "
                     "ingredientes de todo el país: amazonía, valles y altiplano.",
                     "650.00", ciudad=LA_PAZ, localidad="Calacoto - Zona Sur", capacidad=45),
        ],
    },
    {
        "nombre": "Paceña La Salteña",
        "dominio": "pacenalasaltena.com.bo",
        "ciudad": LA_PAZ,
        "plan": "PROFESIONAL",
        "perfil": "Cadena gastronómica",
        "estado": "ACTIVO",
        "empleados": [empleado("empleado1", "CAJERO"), empleado("empleado2", "CAJERO")],
        "hoteles": [],
        "productos": [
            producto("RESTAURANTE", "Paceña La Salteña - Sopocachi",
                     "Salteñas jugosas de carne y pollo, recién horneadas cada mañana.",
                     "25.00", ciudad=LA_PAZ, localidad="Sopocachi", capacidad=60),
            producto("RESTAURANTE", "Paceña La Salteña - Calacoto",
                     "La salteña paceña de siempre en la Zona Sur, con postres y api.",
                     "25.00", ciudad=LA_PAZ, localidad="Calacoto - Zona Sur", capacidad=50),
            producto("RESTAURANTE", "Paceña La Salteña - Centro",
                     "Sucursal a pasos de la Plaza Murillo, ideal para el desayuno paceño.",
                     "25.00", ciudad=LA_PAZ, localidad="Centro", capacidad=40),
            producto("RESTAURANTE", "Paceña La Salteña - Miraflores",
                     "Sucursal cerrada temporalmente por remodelación.",
                     "25.00", ciudad=LA_PAZ, localidad="Miraflores", capacidad=35, estado=INACTIVO),
        ],
    },
    {
        "nombre": "Casa del Camba",
        "dominio": "casadelcamba.com.bo",
        "ciudad": SANTA_CRUZ,
        "plan": "BASICO",
        "perfil": "Solo restaurante",
        "estado": "ACTIVO",
        "empleados": [empleado("empleado1", "CAJERO")],
        "hoteles": [],
        "productos": [
            producto("RESTAURANTE", "Casa del Camba",
                     "Comida típica cruceña y parrilla en un ambiente de casona oriental, con "
                     "música en vivo los fines de semana.",
                     "90.00", ciudad=SANTA_CRUZ, localidad="Av. Cristóbal de Mendoza", capacidad=200),
        ],
    },
    {
        "nombre": "Casa de Campo",
        "dominio": "casadecampo.com.bo",
        "ciudad": COCHABAMBA,
        "plan": "BASICO",
        "perfil": "Solo restaurante",
        "estado": "ACTIVO",
        "empleados": [empleado("empleado1", "CAJERO")],
        "hoteles": [],
        "productos": [
            producto("RESTAURANTE", "Casa de Campo",
                     "Cocina cochabambina tradicional: pique macho, silpancho y chicharrón, en "
                     "patio al aire libre.",
                     "70.00", ciudad=COCHABAMBA, localidad="Recoleta", capacidad=150),
        ],
    },
    # ------------------------------------------------------------------
    # Tours y experiencias
    # ------------------------------------------------------------------
    {
        "nombre": "Gravity Bolivia",
        "dominio": "gravitybolivia.com.bo",
        "ciudad": LA_PAZ,
        "plan": "PROFESIONAL",
        "perfil": "Tours y experiencias de aventura",
        "estado": "ACTIVO",
        "empleados": [
            empleado("empleado1", "ENCARGADO_CATALOGO"),
            empleado("guia1", "GUIA"),
            empleado("guia2", "GUIA"),
        ],
        "hoteles": [],
        "productos": [
            producto("TOUR", "Descenso en Bicicleta por el Camino de la Muerte",
                     "64 km de descenso desde La Cumbre (4.700 m) hasta los Yungas. Incluye "
                     "bicicleta de doble suspensión, equipo de protección, guías y almuerzo.",
                     "850.00", ciudad=LA_PAZ, localidad="Yungas - Camino de la Muerte", capacidad=12),
            producto("TOUR", "Bici de Montaña en Chacaltaya",
                     "Ruta de descenso desde el nevado Chacaltaya con vistas a la Cordillera Real.",
                     "750.00", ciudad=LA_PAZ, localidad="Chacaltaya", capacidad=10),
            producto("TOUR", "Ruta en Bicicleta a Sorata",
                     "Dos días de pedaleo por caminos de altura hasta el valle de Sorata.",
                     "1400.00", ciudad=LA_PAZ, localidad="Sorata", capacidad=8),
            producto("EXPERIENCIA", "Tirolesa en los Yungas",
                     "Tres tramos de tirolesa sobre la selva de los Yungas, al final del Camino "
                     "de la Muerte.",
                     "320.00", ciudad=LA_PAZ, localidad="Yolosa - Yungas", capacidad=20),
        ],
    },
    {
        "nombre": "Red Cap Walking Tours",
        "dominio": "redcapwalkingtours.com.bo",
        "ciudad": LA_PAZ,
        # Queda suspendida al final de la carga para probar que su oferta
        # desaparece del Marketplace y que su gente no puede operar.
        "plan": "BASICO",
        "perfil": "Tours a pie (empresa suspendida)",
        "estado": "SUSPENDIDO",
        "empleados": [empleado("guia1", "GUIA"), empleado("guia2", "GUIA")],
        "hoteles": [],
        "productos": [
            producto("TOUR", "Walking Tour por el Centro de La Paz",
                     "Recorrido a pie por la Plaza Murillo, el Mercado Rodríguez y el Mercado de "
                     "las Brujas con historias de la ciudad.",
                     "70.00", ciudad=LA_PAZ, localidad="Centro", capacidad=25),
            producto("TOUR", "Teleférico y Mercado de El Alto",
                     "Viaje en teleférico hasta El Alto y visita a la feria 16 de Julio.",
                     "120.00", ciudad=LA_PAZ, localidad="El Alto", capacidad=20),
            producto("EXPERIENCIA", "Lucha Libre de Cholitas",
                     "Función de lucha libre de cholitas en El Alto con transporte y bocadillos.",
                     "150.00", ciudad=LA_PAZ, localidad="El Alto", capacidad=30),
        ],
    },
    {
        "nombre": "Red Planet Expedition",
        "dominio": "redplanetexpedition.com.bo",
        "ciudad": UYUNI,
        "plan": "PROFESIONAL",
        "perfil": "Tours por el salar y paquetes",
        "estado": "ACTIVO",
        "empleados": [
            empleado("empleado1", "TENANT_EMPLOYEE"),
            empleado("guia1", "GUIA"),
            empleado("guia2", "GUIA"),
        ],
        "hoteles": [],
        "productos": [
            producto("TOUR", "Salar de Uyuni Día Completo",
                     "Cementerio de trenes, Colchani, isla Incahuasi y fotos de perspectiva en el "
                     "salar. Incluye almuerzo y vehículo 4x4.",
                     "450.00", ciudad=UYUNI, localidad="Salar de Uyuni", capacidad=6),
            producto("TOUR", "Travesía 3D/2N Salar y Lagunas de Colores",
                     "Salar de Uyuni, Laguna Colorada, géiseres Sol de Mañana y Laguna Verde, con "
                     "alojamiento en refugios.",
                     "1800.00", ciudad=UYUNI, localidad="Reserva Eduardo Avaroa", capacidad=6),
            producto("TOUR", "Atardecer y Estrellas en el Salar",
                     "Salida por la tarde para ver la puesta de sol y el cielo nocturno sobre el salar.",
                     "380.00", ciudad=UYUNI, localidad="Salar de Uyuni", capacidad=6),
            producto("EXPERIENCIA", "Amanecer en el Espejo del Salar",
                     "En época de lluvias, salida antes del amanecer al efecto espejo del salar.",
                     "400.00", ciudad=UYUNI, localidad="Salar de Uyuni", capacidad=6, estado=BORRADOR),
            producto("PAQUETE", "Uyuni 3D/2N con Hotel Palacio de Sal",
                     "Dos noches en el Hotel Palacio de Sal, tour de día completo al salar y "
                     "atardecer. El hotel se reserva a través de su propia empresa.",
                     "3600.00", ciudad=UYUNI, localidad="Salar de Uyuni", capacidad=4),
        ],
    },
    {
        "nombre": "Madidi Jungle Ecolodge",
        "dominio": "madidijungle.com.bo",
        "ciudad": RURRENABAQUE,
        "plan": "PROFESIONAL",
        "perfil": "Ecolodge con tours de selva",
        "estado": "ACTIVO",
        "empleados": [empleado("empleado1", "RECEPCIONISTA"), empleado("guia1", "GUIA")],
        "hoteles": [
            {
                "nombre": "Madidi Jungle Ecolodge",
                "descripcion": (
                    "Ecolodge comunitario dentro del Parque Nacional Madidi, gestionado por la "
                    "comunidad de San José de Uchupiamonas. Se llega en bote por el río Beni y "
                    "el río Tuichi desde Rurrenabaque."
                ),
                "ciudad": RURRENABAQUE,
                "localidad": "Parque Nacional Madidi - San José de Uchupiamonas",
                "direccion": "Río Tuichi, Parque Nacional Madidi",
                "latitud": "-14.623300",
                "longitud": "-67.971900",
                "estrellas": 2,
                "check_in": time(12, 0),
                "check_out": time(10, 0),
                "servicios": [DESAYUNO, RESTAURANTE, TRASLADO],
                "estado": PUBLICADO,
                "habitaciones": [
                    habitacion("Cabaña Doble", "Cabaña de madera con mosquiteros y baño privado. Pensión completa.",
                               "900.00", capacidad=2, cama="1 cama matrimonial", cantidad=6),
                    habitacion("Cabaña Familiar", "Cabaña amplia para familias. Pensión completa.",
                               "1300.00", capacidad=4, adultos=3, ninos=2, cama="1 cama matrimonial y 2 individuales", cantidad=3),
                ],
            }
        ],
        "productos": [
            producto("TOUR", "Expedición 3D/2N en el Parque Madidi",
                     "Caminatas por la selva, collpa de guacamayos y pesca artesanal con guías de "
                     "la comunidad.",
                     "2400.00", ciudad=RURRENABAQUE, localidad="Parque Nacional Madidi", capacidad=8),
            producto("TOUR", "Pampas del Yacuma 3D/2N",
                     "Navegación por el río Yacuma para ver delfines rosados, caimanes y capibaras.",
                     "1900.00", ciudad=RURRENABAQUE, localidad="Pampas del Yacuma", capacidad=8),
            producto("EXPERIENCIA", "Caminata Nocturna en la Selva",
                     "Salida guiada al anochecer para descubrir insectos, ranas y aves nocturnas.",
                     "250.00", ciudad=RURRENABAQUE, localidad="Parque Nacional Madidi", capacidad=8),
        ],
    },
    {
        "nombre": "Bodegas Kohlberg",
        "dominio": "kohlberg.com.bo",
        "ciudad": TARIJA,
        "plan": "BASICO",
        "perfil": "Experiencias de vino y singani",
        "estado": "ACTIVO",
        "empleados": [empleado("empleado1", "TENANT_EMPLOYEE")],
        "hoteles": [],
        "productos": [
            producto("EXPERIENCIA", "Visita y Cata en Bodegas Kohlberg",
                     "Recorrido por la bodega en Santa Ana y cata de vinos de altura con quesos "
                     "tarijeños.",
                     "120.00", ciudad=TARIJA, localidad="Santa Ana", capacidad=25),
            producto("EXPERIENCIA", "Ruta del Vino y Singani",
                     "Día completo por bodegas y viñedos del Valle Central de Tarija con almuerzo "
                     "campestre.",
                     "380.00", ciudad=TARIJA, localidad="Valle Central", capacidad=15),
        ],
    },
    # ------------------------------------------------------------------
    # Atracciones
    # ------------------------------------------------------------------
    {
        "nombre": "Parque Cretácico",
        "dominio": "parquecretacico.com.bo",
        "ciudad": SUCRE,
        "plan": "BASICO",
        "perfil": "Atracción",
        "estado": "ACTIVO",
        "empleados": [empleado("empleado1", "TENANT_EMPLOYEE")],
        "hoteles": [],
        "productos": [
            producto("ATRACCION", "Parque Cretácico - Cal Orck'o",
                     "Parque temático con réplicas de dinosaurios y mirador al muro con más de "
                     "5.000 huellas del período Cretácico.",
                     "50.00", ciudad=SUCRE, localidad="Cal Orck'o", capacidad=300),
            producto("EXPERIENCIA", "Caminata Guiada al Muro de Huellas",
                     "Bajada guiada con casco hasta el pie del muro de huellas (horarios limitados).",
                     "40.00", ciudad=SUCRE, localidad="Cal Orck'o", capacidad=25),
        ],
    },
    {
        "nombre": "Casa Nacional de Moneda",
        "dominio": "casadelamoneda.com.bo",
        "ciudad": POTOSI,
        "plan": "BASICO",
        "perfil": "Atracción",
        "estado": "ACTIVO",
        "empleados": [empleado("empleado1", "TENANT_EMPLOYEE")],
        "hoteles": [],
        "productos": [
            producto("ATRACCION", "Museo Casa Nacional de Moneda",
                     "Edificio colonial donde se acuñó la plata del Cerro Rico. Visita guiada por "
                     "las salas de laminación, pintura colonial y numismática.",
                     "50.00", ciudad=POTOSI, localidad="Centro Histórico", capacidad=150),
        ],
    },
    # ------------------------------------------------------------------
    # Empresa recien registrada: pendiente de activacion por el SuperAdmin
    # ------------------------------------------------------------------
    {
        "nombre": "Tupiza Tours",
        "dominio": "tupizatours.com.bo",
        "ciudad": TUPIZA,
        "plan": "BASICO",
        "perfil": "Autorregistro pendiente de activación",
        "estado": "PENDIENTE",
        "empleados": [],
        "hoteles": [],
        "productos": [],
    },
]

# Turistas (rol CLIENTE), sin empresa.
DOMINIO_TURISTAS = "situr.com.bo"
TURISTAS = [
    {"usuario": "turista1", "nombres": "Lucía", "apellidos": "Fernández Rojas"},
    {"usuario": "turista2", "nombres": "Martín", "apellidos": "Gutiérrez Vaca"},
    {"usuario": "turista3", "nombres": "Camila", "apellidos": "Mamani Quispe"},
    {"usuario": "turista4", "nombres": "Diego", "apellidos": "Torrez Salvatierra"},
]

# Empresas ficticias que cargaba el antiguo seed_demo_data. El comando las
# desactiva con --limpiar-demo-viejo.
DEMO_VIEJO_EMPRESAS = [
    "Andes Boutique Hotels",
    "Cruceña Hospitality",
    "Kanata Turismo",
    "Sabores de Bolivia",
]
DEMO_VIEJO_EMAILS = [f"duenio{n}@situr.smart" for n in range(1, 5)]

NOMBRE_USUARIO = {
    "jefeadmin": "Jefe Admin",
    "empleado": "Empleado",
    "guia": "Guía",
}


def email(usuario: str, dominio: str) -> str:
    return f"{usuario}@{dominio}".lower()


def nombre_cuenta(usuario: str) -> str:
    """'empleado2' -> 'Empleado 2'. Las cuentas de demo usan nombres genericos
    para no atribuir personas inventadas a empresas reales."""
    for prefijo, nombre in NOMBRE_USUARIO.items():
        if usuario.startswith(prefijo):
            numero = usuario[len(prefijo):]
            return f"{nombre} {numero}".strip()
    return usuario


def cuentas_empresa(empresa: dict) -> list[dict]:
    """Cuentas de una empresa en orden: propietario primero."""
    cuentas = [{
        "email": email("jefeadmin", empresa["dominio"]),
        "nombres": nombre_cuenta("jefeadmin"),
        "apellidos": empresa["nombre"],
        "rol": "TENANT_ADMIN",
    }]
    for persona in empresa["empleados"]:
        cuentas.append({
            "email": email(persona["usuario"], empresa["dominio"]),
            "nombres": nombre_cuenta(persona["usuario"]),
            "apellidos": empresa["nombre"],
            "rol": persona["rol"],
        })
    return cuentas


def cuentas_turistas() -> list[dict]:
    return [
        {**turista, "email": email(turista["usuario"], DOMINIO_TURISTAS), "rol": "CLIENTE"}
        for turista in TURISTAS
    ]


def todos_los_emails() -> list[str]:
    emails = [c["email"] for empresa in EMPRESAS for c in cuentas_empresa(empresa)]
    return emails + [c["email"] for c in cuentas_turistas()]
