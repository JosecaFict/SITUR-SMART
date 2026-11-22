from .base import *  # noqa: F403

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
# Un .env local con claves reales no debe hacer que los tests llamen a la IA.
IA_API_KEY = ""
GEMINI_API_KEY = ""
