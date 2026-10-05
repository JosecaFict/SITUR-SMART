"""Cliente del proveedor de IA, en el formato compatible con OpenAI.

No nombra a ningun proveedor a proposito. Groq, Google Gemini, xAI (Grok) y
OpenRouter exponen ``/chat/completions`` y ``/audio/transcriptions`` con la
misma forma, asi que cambiar de uno a otro es cambiar ``IA_BASE_URL``,
``IA_API_KEY`` e ``IA_MODEL`` en el entorno, sin tocar codigo.

Se usa ``urllib`` y no el SDK de OpenAI, igual que ``apps/catalog/geocoding.py``
y ``apps/accounts/brevo.py``: son dos llamadas y no justifican una dependencia.

La clave solo se lee aqui. Nada de lo que se registra incluye la clave, el
mensaje del usuario ni el cuerpo de la respuesta: solo el endpoint y el estado.
"""

import json
import logging
import urllib.error
import urllib.request
import uuid

from django.conf import settings

logger = logging.getLogger(__name__)

CHAT_PATH = "/chat/completions"
TRANSCRIPTION_PATH = "/audio/transcriptions"


class AssistantUnavailable(Exception):
    """El proveedor no esta configurado, alcanzo su limite o no respondio.

    Se traduce a un 503 con un mensaje que no culpa al usuario.
    """


class AssistantRateLimited(AssistantUnavailable):
    """El proveedor respondio 429: se agoto la cuota del plan."""


def _setting(name: str, default: str = "") -> str:
    return str(getattr(settings, name, default) or "").strip()


def is_configured() -> bool:
    """Indica si hay proveedor cargado, sin revelar nada de la clave."""
    return bool(_setting("IA_API_KEY") and _setting("IA_BASE_URL") and _setting("IA_MODEL"))


def voice_configured() -> bool:
    return is_configured() and bool(_setting("IA_STT_MODEL"))


def _send(path: str, body: bytes, content_type: str) -> dict:
    if not is_configured():
        logger.warning("Asistente IA solicitado sin IA_API_KEY / IA_BASE_URL / IA_MODEL.")
        raise AssistantUnavailable

    request = urllib.request.Request(
        f"{_setting('IA_BASE_URL').rstrip('/')}{path}",
        data=body,
        headers={
            "Authorization": f"Bearer {_setting('IA_API_KEY')}",
            "Content-Type": content_type,
            "Accept": "application/json",
            "User-Agent": "SITUR-SMART/1.0",
        },
        method="POST",
    )
    timeout = int(getattr(settings, "IA_TIMEOUT_SECONDS", 30))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Solo el codigo: el cuerpo puede repetir el mensaje del usuario.
        logger.error("El proveedor de IA respondio %d en %s", exc.code, path)
        if exc.code == 429:
            raise AssistantRateLimited from exc
        raise AssistantUnavailable from exc
    except urllib.error.URLError as exc:
        logger.error("No se pudo contactar al proveedor de IA en %s: %s", path, exc.reason)
        raise AssistantUnavailable from exc
    except (TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.error("Respuesta inutilizable del proveedor de IA en %s: %s", path, type(exc).__name__)
        raise AssistantUnavailable from exc

    if not isinstance(payload, dict):
        logger.error("El proveedor de IA devolvio algo que no es un objeto en %s", path)
        raise AssistantUnavailable
    return payload


def chat(messages: list[dict], tools: list[dict] | None = None) -> dict:
    """Devuelve el mensaje del asistente: ``{"content": ..., "tool_calls": [...]}``."""
    body: dict = {
        "model": _setting("IA_MODEL"),
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": int(getattr(settings, "IA_MAX_TOKENS", 1024)),
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"

    payload = _send(CHAT_PATH, json.dumps(body).encode("utf-8"), "application/json")
    try:
        message = payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        logger.error("Respuesta de chat sin choices[0].message")
        raise AssistantUnavailable from exc
    if not isinstance(message, dict):
        raise AssistantUnavailable
    return message


def transcribe(*, audio: bytes, filename: str, content_type: str, language: str = "es") -> str:
    """Convierte audio en texto con el modelo de voz (Whisper en Groq)."""
    if not voice_configured():
        logger.warning("Transcripcion solicitada sin IA_STT_MODEL configurado.")
        raise AssistantUnavailable

    boundary = f"----situr{uuid.uuid4().hex}"
    fields = {"model": _setting("IA_STT_MODEL"), "language": language, "response_format": "json"}
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        )
    # El nombre del archivo lo arma el servidor; el del usuario no entra en la
    # cabecera, asi no hay forma de inyectar comillas o saltos de linea.
    safe_name = "audio" + (filename[filename.rfind("."):].lower() if "." in filename else ".webm")
    parts.append(
        (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{safe_name}\"\r\n"
            f"Content-Type: {content_type or 'application/octet-stream'}\r\n\r\n"
        ).encode()
        + audio
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())

    payload = _send(TRANSCRIPTION_PATH, b"".join(parts), f"multipart/form-data; boundary={boundary}")
    text = payload.get("text")
    if not isinstance(text, str):
        raise AssistantUnavailable
    return text.strip()
