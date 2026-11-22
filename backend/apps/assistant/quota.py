"""Cupo propio de Gemini para no llegar al 429 del plan gratuito.

Se cuentan los pedidos del ultimo minuto y del dia, y se deja de usar Gemini
un rato cuando falla. Mientras esta en pausa el chat va directo a Groq: no se
gasta un intento fallido en cada mensaje.

El estado vive en la memoria del proceso. Alcanza porque gunicorn corre con un
solo proceso (``gunicorn.conf.py``) y los hilos comparten el candado. Si se
reinicia, el contador vuelve a cero y en el peor caso Google responde un 429,
que tambien se maneja.

La cuota diaria de Google se reinicia a la medianoche del Pacifico.
"""

import logging
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

QUOTA_ZONE = ZoneInfo("America/Los_Angeles")
WINDOW_SECONDS = 60.0
MINUTE_PAUSE_SECONDS = 60.0
# Clave mala, sin permiso o modelo inexistente: no se arregla solo en segundos.
CONFIG_PAUSE_SECONDS = 600.0
CONFIG_STATUSES = frozenset({401, 403, 404})
# Fallas de servicio (503, 500, tiempo agotado) seguidas antes de pausar.
FAILURES_BEFORE_PAUSE = 2
# 429 seguidos sin que se sepa si eran del dia: se trata como cuota diaria.
RATE_LIMITS_BEFORE_DAY_PAUSE = 3


def _quota_day(now: datetime):
    return now.astimezone(QUOTA_ZONE).date()


def _seconds_to_reset(now: datetime) -> float:
    local = now.astimezone(QUOTA_ZONE)
    midnight = datetime.combine(local.date() + timedelta(days=1), datetime.min.time(), QUOTA_ZONE)
    return max((midnight - local).total_seconds(), 1.0)


class QuotaGate:
    def __init__(self, *, per_minute, per_day, clock=time.monotonic, now=None):
        self._per_minute = per_minute
        self._per_day = per_day
        self._clock = clock
        self._now = now or (lambda: datetime.now(QUOTA_ZONE))
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        self._recent: deque[float] = deque()
        self._day = None
        self._day_count = 0
        self._paused_until = 0.0
        self._failures = 0
        self._rate_limits = 0

    def try_acquire(self) -> bool:
        """Reserva un pedido si hay cupo; si no, el mensaje debe ir a Groq."""
        with self._lock:
            moment = self._clock()
            if moment < self._paused_until:
                return False
            day = _quota_day(self._now())
            if day != self._day:
                self._day, self._day_count = day, 0
            while self._recent and moment - self._recent[0] >= WINDOW_SECONDS:
                self._recent.popleft()
            if self._day_count >= self._per_day():
                self._pause_until_reset(moment, "se uso el cupo del dia")
                return False
            if len(self._recent) >= self._per_minute():
                return False
            self._recent.append(moment)
            self._day_count += 1
            return True

    def success(self) -> None:
        with self._lock:
            self._failures = 0
            self._rate_limits = 0

    def failure(self, *, status: int | None, daily: bool = False) -> None:
        with self._lock:
            moment = self._clock()
            if status == 429:
                self._rate_limits += 1
                if daily or self._rate_limits >= RATE_LIMITS_BEFORE_DAY_PAUSE:
                    self._pause_until_reset(moment, "Google dio 429 por la cuota del dia")
                else:
                    self._pause(moment, MINUTE_PAUSE_SECONDS, "Google dio 429")
            elif status in CONFIG_STATUSES:
                self._pause(moment, CONFIG_PAUSE_SECONDS, f"Google dio {status}, revisar clave o modelo")
            elif status == 400:
                # Problema de ese pedido, no del servicio: no se pausa.
                return
            else:
                self._failures += 1
                if self._failures >= FAILURES_BEFORE_PAUSE:
                    self._failures = 0
                    self._pause(moment, MINUTE_PAUSE_SECONDS, "fallas seguidas")

    def _pause(self, moment: float, seconds: float, why: str) -> None:
        self._paused_until = max(self._paused_until, moment + seconds)
        logger.warning("Gemini en pausa %d s (%s); el chat sigue con Groq.", seconds, why)

    def _pause_until_reset(self, moment: float, why: str) -> None:
        self._pause(moment, _seconds_to_reset(self._now()), why)
