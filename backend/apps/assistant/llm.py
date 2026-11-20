"""Cliente de los proveedores de IA, en el formato compatible con OpenAI.

Groq, Google Gemini, xAI y OpenRouter exponen ``/chat/completions`` con la
misma forma, asi que un proveedor es solo una URL, una clave y un modelo.

Hay dos perfiles:

- ``cliente``: el turista. Usa ``IA_CLIENTE_*`` (Gemini).
- ``empresa``: el personal de empresas y el SuperAdmin. Usa ``IA_EMPRESA_*``
  (Groq), o las ``IA_*`` de siempre si no se definieron.

Cada perfil tiene al otro como respaldo: si su proveedor responde 429 (cuota
agotada) o falla, se reintenta con el otro. El que respondio 429 queda en pausa
``IA_COOLDOWN_SECONDS`` para no gastar un intento fallido en cada mensaje. Un
503 (proveedor saturado) se reintenta una vez antes de pasar al respaldo.

Un mensaje del turista puede necesitar varias llamadas (pedir una herramienta,
recibir su resultado, responder). ``Session`` fija el proveedor que respondio
la primera llamada para el resto del mensaje: Gemini 3 rechaza (400) una
llamada a herramienta que no pidio el mismo, porque le falta su firma.

La voz (``/audio/transcriptions``) usa siempre el proveedor de empresa: Whisper
de Groq.

Se usa ``urllib`` y no el SDK de OpenAI, igual que ``apps/catalog/geocoding.py``
y ``apps/accounts/brevo.py``: son dos llamadas y no justifican una dependencia.

Las claves solo se leen aqui. Nada de lo que se registra incluye la clave ni el
mensaje del usuario: solo el proveedor, el endpoint, el estado y, si hubo error,
el motivo que dio el proveedor, recortado.
"""

import json
import logging
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

CHAT_PATH = "/chat/completions"
TRANSCRIPTION_PATH = "/audio/transcriptions"

CLIENTE = "cliente"
EMPRESA = "empresa"
PROFILES = (CLIENTE, EMPRESA)


REASON_LIMIT = 200


class AssistantUnavailable(Exception):
    """El proveedor no esta configurado, alcanzo su limite o no respondio.

    Se traduce a un 503 con un mensaje que no culpa al usuario. ``status`` es
    el codigo HTTP del proveedor, si lo hubo.
    """

    def __init__(self, *args, status: int | None = None):
        super().__init__(*args)
        self.status = status


class AssistantRateLimited(AssistantUnavailable):
    """El proveedor respondio 429: se agoto la cuota del plan."""


@dataclass(frozen=True)
class Provider:
    profile: str
    base_url: str
    api_key: str
    model: str
    max_tokens: int
    reasoning_effort: str

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    @property
    def cooldown_key(self) -> str:
        # Sin la clave: la cache puede ser compartida y no debe guardar secretos.
        return f"asistente:pausa:{self.base_url}|{self.model}"


def _setting(name: str, default: str = "") -> str:
    return str(getattr(settings, name, default) or "").strip()


def _int_setting(name: str, default: int) -> int:
    try:
        return int(getattr(settings, name, default))
    except (TypeError, ValueError):
        return default


def provider(profile: str) -> Provider:
    """Lee la configuracion de un perfil. ``empresa`` cae en las ``IA_*`` de siempre."""
    prefix = f"IA_{profile.upper()}_"
    fallback = profile == EMPRESA

    def value(name: str) -> str:
        own = _setting(prefix + name)
        return own or (_setting(f"IA_{name}") if fallback else "")

    return Provider(
        profile=profile,
        base_url=value("BASE_URL").rstrip("/"),
        api_key=value("API_KEY"),
        model=value("MODEL"),
        max_tokens=_int_setting(prefix + "MAX_TOKENS", _int_setting("IA_MAX_TOKENS", 1024)),
        reasoning_effort=_setting(prefix + "REASONING_EFFORT"),
    )


def _candidates(profile: str) -> list[Provider]:
    """Proveedores a probar, en orden: el del perfil y luego el otro."""
    if profile not in PROFILES:
        profile = CLIENTE
    order = [profile, *(p for p in PROFILES if p != profile)]
    result: list[Provider] = []
    seen: set[tuple[str, str, str]] = set()
    for item in (provider(p) for p in order):
        identity = (item.base_url, item.api_key, item.model)
        if item.configured and identity not in seen:
            seen.add(identity)
            result.append(item)
    return result


def is_configured() -> bool:
    """Indica si hay algun proveedor cargado, sin revelar nada de la clave."""
    return bool(_candidates(CLIENTE))


def voice_configured() -> bool:
    return provider(EMPRESA).configured and bool(_setting("IA_STT_MODEL"))


def _error_reason(exc: urllib.error.HTTPError) -> str:
    """Solo ``error.message`` del proveedor, recortado: explica el rechazo.

    No se registra el cuerpo completo porque podria repetir lo que escribio el
    usuario. Gemini a veces envuelve el error en una lista.
    """
    try:
        payload = json.loads(exc.read().decode("utf-8", errors="replace"))
    except (OSError, ValueError, AttributeError):
        return "sin detalle"
    if isinstance(payload, list) and payload:
        payload = payload[0]
    error = payload.get("error") if isinstance(payload, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    if not isinstance(message, str) or not message.strip():
        return "sin detalle"
    reason = " ".join(message.split())
    return reason if len(reason) <= REASON_LIMIT else reason[:REASON_LIMIT] + "..."


def _send(target: Provider, path: str, body: bytes, content_type: str) -> dict:
    request = urllib.request.Request(
        f"{target.base_url}{path}",
        data=body,
        headers={
            "Authorization": f"Bearer {target.api_key}",
            "Content-Type": content_type,
            "Accept": "application/json",
            "User-Agent": "SITUR-SMART/1.0",
        },
        method="POST",
    )
    timeout = _int_setting("IA_TIMEOUT_SECONDS", 30)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        logger.error(
            "El proveedor de IA (%s) respondio %d en %s: %s",
            target.profile,
            exc.code,
            path,
            _error_reason(exc),
        )
        if exc.code == 429:
            raise AssistantRateLimited(status=429) from exc
        raise AssistantUnavailable(status=exc.code) from exc
    except urllib.error.URLError as exc:
        logger.error(
            "No se pudo contactar al proveedor de IA (%s) en %s: %s", target.profile, path, exc.reason
        )
        raise AssistantUnavailable from exc
    except (TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.error(
            "Respuesta inutilizable del proveedor de IA (%s) en %s: %s",
            target.profile,
            path,
            type(exc).__name__,
        )
        raise AssistantUnavailable from exc

    if not isinstance(payload, dict):
        logger.error("El proveedor de IA (%s) devolvio algo que no es un objeto en %s", target.profile, path)
        raise AssistantUnavailable
    return payload


def _chat_once(target: Provider, messages: list[dict], tools: list[dict] | None) -> dict:
    body: dict = {
        "model": target.model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": target.max_tokens,
    }
    if target.reasoning_effort:
        body["reasoning_effort"] = target.reasoning_effort
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"

    payload = _send(target, CHAT_PATH, json.dumps(body).encode("utf-8"), "application/json")
    try:
        message = payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        logger.error("Respuesta de chat sin choices[0].message (%s)", target.profile)
        raise AssistantUnavailable from exc
    if not isinstance(message, dict):
        raise AssistantUnavailable
    return message


def _chat_with_retry(target: Provider, messages: list[dict], tools: list[dict] | None) -> dict:
    """Un 503 suele ser una saturacion de segundos: se reintenta una vez."""
    try:
        return _chat_once(target, messages, tools)
    except AssistantUnavailable as exc:
        if exc.status != 503:
            raise
    delay = float(getattr(settings, "IA_RETRY_DELAY_SECONDS", 1) or 0)
    if delay > 0:
        time.sleep(delay)
    logger.warning("Asistente IA (%s): se reintenta tras un 503.", target.profile)
    return _chat_once(target, messages, tools)


class Session:
    """Llamadas de un mismo mensaje, todas con el mismo proveedor.

    La primera llamada elige proveedor (el del perfil o, si falla, el de
    respaldo) y las siguientes lo reutilizan. Si ese proveedor falla a mitad
    del mensaje no se cambia de proveedor: la conversacion ya tiene llamadas a
    herramientas que el otro no reconoceria, y es mejor un error claro.
    """

    def __init__(self, profile: str = CLIENTE):
        self.profile = profile
        self.provider: Provider | None = None

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """Devuelve el mensaje del asistente: ``{"content": ..., "tool_calls": [...]}``."""
        if self.provider is not None:
            return _chat_with_retry(self.provider, messages, tools)

        candidates = _candidates(self.profile)
        if not candidates:
            logger.warning("Asistente IA solicitado sin ningun proveedor configurado.")
            raise AssistantUnavailable

        # Los que estan en pausa por un 429 reciente van al final: solo se
        # intentan si no queda otro.
        resting = [c for c in candidates if cache.get(c.cooldown_key)]
        ordered = [c for c in candidates if c not in resting] + resting

        all_rate_limited = True
        last_error: AssistantUnavailable | None = None
        for index, target in enumerate(ordered):
            if index:
                logger.warning(
                    "Asistente IA (%s): se usa el proveedor de respaldo (%s).", self.profile, target.profile
                )
            try:
                answer = _chat_with_retry(target, messages, tools)
            except AssistantRateLimited as exc:
                cache.set(target.cooldown_key, True, _int_setting("IA_COOLDOWN_SECONDS", 300))
                last_error = exc
                continue
            except AssistantUnavailable as exc:
                all_rate_limited = False
                last_error = exc
                continue
            self.provider = target
            return answer

        if all_rate_limited:
            raise AssistantRateLimited from last_error
        raise AssistantUnavailable from last_error


def chat(messages: list[dict], tools: list[dict] | None = None, *, profile: str = CLIENTE) -> dict:
    """Una llamada suelta, con respaldo. Para un mensaje con herramientas usar ``Session``."""
    return Session(profile).chat(messages, tools)


def transcribe(*, audio: bytes, filename: str, content_type: str, language: str = "es") -> str:
    """Convierte audio en texto con el modelo de voz (Whisper en Groq)."""
    if not voice_configured():
        logger.warning("Transcripcion solicitada sin proveedor de voz o sin IA_STT_MODEL.")
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

    payload = _send(
        provider(EMPRESA),
        TRANSCRIPTION_PATH,
        b"".join(parts),
        f"multipart/form-data; boundary={boundary}",
    )
    text = payload.get("text")
    if not isinstance(text, str):
        raise AssistantUnavailable
    return text.strip()
