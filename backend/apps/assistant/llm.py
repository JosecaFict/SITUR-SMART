"""Cliente de los proveedores de IA, en el formato compatible con OpenAI.

No nombra a ningun proveedor a proposito. Groq, Google Gemini, xAI (Grok) y
OpenRouter exponen ``/chat/completions`` y ``/audio/transcriptions`` con la
misma forma, asi que cambiar de uno a otro es cambiar ``IA_BASE_URL``,
``IA_API_KEY`` e ``IA_MODEL`` en el entorno, sin tocar codigo.

Hay dos proveedores: el principal (``IA_*``, Groq) y Gemini (``GEMINI_*``),
que atiende el chat de los turistas mientras tenga cupo (``quota.py``). Ambos
hablan el mismo formato; ``services.reply`` elige cual usar en cada mensaje.

Se usa ``urllib`` y no el SDK de OpenAI, igual que ``apps/catalog/geocoding.py``
y ``apps/accounts/brevo.py``: son dos llamadas y no justifican una dependencia.

Las claves solo se leen aqui. Nada de lo que se registra incluye una clave ni el
mensaje del usuario: solo el proveedor, el endpoint, el estado y, si hubo error,
el motivo que dio el proveedor, recortado.

Un 503 (proveedor saturado) suele durar segundos: el principal lo reintenta una
vez. Gemini no reintenta: si falla, el mensaje pasa al principal.
"""

import json
import logging
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field

from django.conf import settings

from .quota import QuotaGate

logger = logging.getLogger(__name__)

CHAT_PATH = "/chat/completions"
TRANSCRIPTION_PATH = "/audio/transcriptions"
REASON_LIMIT = 200


class AssistantUnavailable(Exception):
    """El proveedor no esta configurado, alcanzo su limite o no respondio.

    Se traduce a un 503 con un mensaje que no culpa al usuario. ``status`` es
    el codigo HTTP del proveedor, si lo hubo; ``daily`` indica un 429 por la
    cuota del dia.
    """

    def __init__(self, *args, status: int | None = None, daily: bool = False):
        super().__init__(*args)
        self.status = status
        self.daily = daily


class AssistantRateLimited(AssistantUnavailable):
    """El proveedor respondio 429: se agoto la cuota del plan."""


class ProviderSkipped(AssistantUnavailable):
    """No se llamo al proveedor porque no tenia cupo: no cuenta como falla."""


def _setting(name: str, default: str = "") -> str:
    return str(getattr(settings, name, default) or "").strip()


GEMINI_GATE = QuotaGate(
    per_minute=lambda: int(getattr(settings, "GEMINI_RPM_LIMIT", 14)),
    per_day=lambda: int(getattr(settings, "GEMINI_RPD_LIMIT", 490)),
)


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    api_key: str = field(repr=False)
    model: str = ""
    timeout: int = 30
    max_tokens: int = 1024
    # Gemini 3 recomienda dejar su temperatura por omision: None no la envia.
    temperature: float | None = None
    retry_503: bool = False
    gate: QuotaGate | None = field(default=None, compare=False, repr=False)

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)


def primary() -> Provider:
    """El proveedor ``IA_*`` (Groq): personal, voz y respaldo de los turistas."""
    return Provider(
        name="Groq",
        base_url=_setting("IA_BASE_URL"),
        api_key=_setting("IA_API_KEY"),
        model=_setting("IA_MODEL"),
        timeout=int(getattr(settings, "IA_TIMEOUT_SECONDS", 30)),
        max_tokens=int(getattr(settings, "IA_MAX_TOKENS", 1024)),
        temperature=0.3,
        retry_503=True,
    )


def gemini() -> Provider | None:
    """Gemini para el chat de turistas, o ``None`` si no hay clave."""
    provider = Provider(
        name="Gemini",
        base_url=_setting("GEMINI_BASE_URL"),
        api_key=_setting("GEMINI_API_KEY"),
        model=_setting("GEMINI_MODEL"),
        timeout=int(getattr(settings, "GEMINI_TIMEOUT_SECONDS", 12)),
        max_tokens=int(getattr(settings, "GEMINI_MAX_TOKENS", 2048)),
        gate=GEMINI_GATE,
    )
    return provider if provider.configured else None


def is_configured() -> bool:
    """Indica si hay algun proveedor de chat cargado, sin revelar las claves."""
    return primary().configured or gemini() is not None


def voice_configured() -> bool:
    return primary().configured and bool(_setting("IA_STT_MODEL"))


def _read_error(exc: urllib.error.HTTPError) -> tuple[str, bool]:
    """Motivo del rechazo, recortado, y si fue por la cuota del dia.

    Solo se registra ``error.message``: el cuerpo completo podria repetir lo que
    escribio el usuario. Algunos proveedores envuelven el error en una lista.
    Google indica la cuota diaria en los detalles (``...PerDay...``).
    """
    try:
        raw = exc.read().decode("utf-8", errors="replace")
        payload = json.loads(raw)
    except (OSError, ValueError, AttributeError):
        return "sin detalle", False
    daily = "perday" in raw.lower().replace(" ", "")
    if isinstance(payload, list) and payload:
        payload = payload[0]
    error = payload.get("error") if isinstance(payload, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    if not isinstance(message, str) or not message.strip():
        return "sin detalle", daily
    reason = " ".join(message.split())
    return (reason if len(reason) <= REASON_LIMIT else reason[:REASON_LIMIT] + "..."), daily


def _send(path: str, body: bytes, content_type: str, provider: Provider | None = None) -> dict:
    provider = provider or primary()
    if not provider.configured:
        logger.warning("Asistente IA solicitado sin clave, URL o modelo de %s.", provider.name)
        raise AssistantUnavailable

    request = urllib.request.Request(
        f"{provider.base_url.rstrip('/')}{path}",
        data=body,
        headers={
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": content_type,
            "Accept": "application/json",
            "User-Agent": "SITUR-SMART/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=provider.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        reason, daily = _read_error(exc)
        logger.error("%s respondio %d en %s: %s", provider.name, exc.code, path, reason)
        if exc.code == 429:
            raise AssistantRateLimited(status=429, daily=daily) from exc
        raise AssistantUnavailable(status=exc.code) from exc
    except urllib.error.URLError as exc:
        logger.error("No se pudo contactar a %s en %s: %s", provider.name, path, exc.reason)
        raise AssistantUnavailable from exc
    except (TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.error("Respuesta inutilizable de %s en %s: %s", provider.name, path, type(exc).__name__)
        raise AssistantUnavailable from exc

    if not isinstance(payload, dict):
        logger.error("%s devolvio algo que no es un objeto en %s", provider.name, path)
        raise AssistantUnavailable
    return payload


def chat(messages: list[dict], tools: list[dict] | None = None, provider: Provider | None = None) -> dict:
    """Devuelve el mensaje del asistente: ``{"content": ..., "tool_calls": [...]}``.

    Con un proveedor que tiene cupo propio (Gemini), primero se reserva un
    pedido; sin cupo se lanza ``ProviderSkipped`` sin llamar a nadie.
    """
    provider = provider or primary()
    gate = provider.gate
    if gate is not None and not gate.try_acquire():
        raise ProviderSkipped
    body: dict = {
        "model": provider.model,
        "messages": messages,
        "max_tokens": provider.max_tokens,
    }
    if provider.temperature is not None:
        body["temperature"] = provider.temperature
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"

    data = json.dumps(body).encode("utf-8")
    try:
        payload = _send(CHAT_PATH, data, "application/json", provider)
    except AssistantUnavailable as exc:
        if exc.status != 503 or not provider.retry_503:
            if gate is not None:
                gate.failure(status=exc.status, daily=exc.daily)
            raise
        delay = float(getattr(settings, "IA_RETRY_DELAY_SECONDS", 1) or 0)
        if delay > 0:
            time.sleep(delay)
        logger.warning("Asistente IA: se reintenta tras un 503.")
        payload = _send(CHAT_PATH, data, "application/json", provider)
    if gate is not None:
        gate.success()
    try:
        message = payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        logger.error("Respuesta de chat de %s sin choices[0].message", provider.name)
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
