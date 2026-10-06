import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse

from corsheaders.defaults import default_headers
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def database_config() -> dict[str, object]:
    raw_url = os.getenv("DATABASE_URL")
    if not raw_url:
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "situr_smart"),
            "USER": os.getenv("POSTGRES_USER", "postgres"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
        }

    parsed = urlparse(raw_url.replace("postgresql+psycopg://", "postgresql://", 1))
    options: dict[str, str] = {}
    if "sslmode=require" in parsed.query:
        options["sslmode"] = "require"
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or 5432),
        "OPTIONS": options,
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-development-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "apps.common",
    "apps.accounts",
    "apps.tenancy",
    "apps.rbac",
    "apps.audit",
    "apps.backups",
    "apps.reports",
    "apps.catalog",
    "apps.media",
    "apps.assistant",
    "apps.favorites",
    "apps.bookings",
    "apps.payments",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "apps.audit.middleware.RequestIdMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {"default": database_config()}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

LANGUAGE_CODE = "es-bo"
TIME_ZONE = "America/La_Paz"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:4200,http://localhost:8080,https://situr-smart-web.vercel.app",
)
CORS_ALLOW_CREDENTIALS = False
CORS_ALLOW_HEADERS = (*default_headers, "x-tenant-id")
CORS_EXPOSE_HEADERS = ("Content-Disposition", "X-Backup-SHA256")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
    # Solo la geocodificacion esta limitada: es la unica ruta que consume cuota
    # de un proveedor externo. No hay limite por omision para el resto.
    #
    # El respaldo es la cache por omision de Django (LocMemCache, memoria del
    # proceso), asi que NO es un limite global ni durable: se reinicia en cada
    # despliegue y se multiplicaria por la cantidad de workers de gunicorn, que
    # hoy es uno. Alcanza para el piloto; un limite real necesita cache
    # compartida.
    "DEFAULT_THROTTLE_RATES": {
        "geocodificacion": os.getenv("GEOCODING_THROTTLE_RATE", "30/min"),
        # Autoregistro publico de empresas: el unico endpoint anonimo que crea
        # empresa, usuario, rol y suscripcion de una sola llamada. Por IP.
        "autoregistro": os.getenv("SELF_SIGNUP_THROTTLE_RATE", "5/hour"),
        # Una copia ejecuta pg_dump sobre toda la base. El límite evita que
        # varios clics consecutivos compitan por CPU, disco y conexiones.
        "backup": os.getenv("BACKUP_THROTTLE_RATE", "3/hour"),
        # Asistente IA (CU36): cada mensaje consume cuota del proveedor.
        "asistente": os.getenv("IA_THROTTLE_RATE", "10/min"),
        "asistente_voz": os.getenv("IA_VOICE_THROTTLE_RATE", "6/min"),
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("ACCESS_TOKEN_MINUTES", "15"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("REFRESH_TOKEN_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "SITUR-SMART API",
    "DESCRIPTION": "API compartida para Angular y Flutter.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Varios serializers comparten el estado de producto_turistico. Sin un
    # nombre fijo, drf-spectacular genera uno con hash (Estado9dbEnum) que
    # cambia al agregar otro serializer y rompe los clientes generados.
    "ENUM_NAME_OVERRIDES": {
        "EstadoProductoEnum": "apps.catalog.models.TourismProduct.Status",
    },
}

# Brevo (Sendinblue) Email & OTP Recovery
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL", "jcvillarroeld126@ficct.uagrm.edu.bo")
BREVO_SENDER_NAME = os.getenv("BREVO_SENDER_NAME", "SITUR-SMART")
PASSWORD_RESET_OTP_MINUTES = int(os.getenv("PASSWORD_RESET_OTP_MINUTES", "15"))
PASSWORD_RESET_RATE_LIMIT_SECONDS = int(os.getenv("PASSWORD_RESET_RATE_LIMIT_SECONDS", "60"))

# Cloudinary Media Storage
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "")

# openrouteservice / HeiGIT -- geocodificacion de direcciones
#
# La clave se lee unicamente aqui y solo la usa apps/catalog/geocoding.py. No
# viaja a Angular ni a Flutter, no aparece en el esquema de OpenAPI y no se
# registra en ningun log: el navegador habla con nuestra API, nunca con el
# proveedor.
#
# Sin clave, la busqueda responde 503 y el mapa sigue funcionando: ubicar el pin
# a mano no depende de este servicio.
OPENROUTESERVICE_API_KEY = os.getenv("OPENROUTESERVICE_API_KEY", "")
# Mas corto que el de Brevo (10 s) porque esto esta en el camino interactivo de
# quien carga un hotel, no en el envio de un correo.
OPENROUTESERVICE_TIMEOUT_SECONDS = int(os.getenv("OPENROUTESERVICE_TIMEOUT_SECONDS", "6"))
# Recorte duro de la busqueda. En esta fase la plataforma solo opera en Bolivia.
GEOCODING_COUNTRY = os.getenv("GEOCODING_COUNTRY", "BOL")


# Asistente virtual IA (CU36)
#
# Cualquier proveedor con API compatible con OpenAI: Groq, Google Gemini,
# xAI (Grok) u OpenRouter. Cambiar de proveedor es cambiar estas variables.
# La clave solo la lee apps/assistant/llm.py y nunca viaja a Angular ni Flutter.
# Sin clave, /asistente/estado/ responde chat=false y la web oculta el chat.
IA_BASE_URL = os.getenv("IA_BASE_URL", "https://api.groq.com/openai/v1")
IA_API_KEY = os.getenv("IA_API_KEY", "")
IA_MODEL = os.getenv("IA_MODEL", "openai/gpt-oss-120b")
# Modelo de voz a texto. Vacio desactiva el boton de voz.
IA_STT_MODEL = os.getenv("IA_STT_MODEL", "whisper-large-v3-turbo")
IA_TIMEOUT_SECONDS = int(os.getenv("IA_TIMEOUT_SECONDS", "30"))
IA_MAX_TOKENS = int(os.getenv("IA_MAX_TOKENS", "1024"))

# Pagos con Stripe Checkout (reservas del turista)
#
# Solo el backend habla con Stripe: la app abre la pagina de pago que devuelve
# la API y la confirmacion llega por webhook. Sin STRIPE_SECRET_KEY no se puede
# reservar (la API responde 503). STRIPE_WEBHOOK_SECRET es el "Signing secret"
# del endpoint /api/v1/pagos/stripe/webhook/ creado en el panel de Stripe.
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
# Minutos que el cupo queda apartado mientras el turista paga. Stripe exige
# que la sesion de Checkout dure al menos 30 minutos y vence a la vez.
RESERVA_MINUTOS_PAGO = max(31, int(os.getenv("RESERVA_MINUTOS_PAGO", "35")))
