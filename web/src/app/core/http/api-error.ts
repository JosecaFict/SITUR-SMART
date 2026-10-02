import { HttpErrorResponse } from '@angular/common/http';

/**
 * Traduce un HttpErrorResponse a un mensaje legible para el usuario.
 *
 * Existe porque cada componente tenía su propia versión de esta lógica y ninguna
 * cubría todos los casos: cuando el backend respondía HTML (un 404 de Django, un
 * 502 de Railway) en lugar del JSON de DRF, el cuerpo no tenía `error.message` ni
 * `error.details` y la pantalla mostraba un mensaje genérico que no distinguía
 * "el servidor no tiene ese endpoint" de "el servicio está mal configurado".
 */

const NETWORK_MESSAGE =
  'No se pudo conectar con el servidor. Verifica tu conexión e inténtalo otra vez.';

const DEFAULT_MESSAGE = 'La solicitud no pudo completarse.';

const STATUS_MESSAGES: Record<number, string> = {
  400: 'La solicitud contiene datos inválidos.',
  401: 'Tu sesión expiró. Vuelve a iniciar sesión.',
  403: 'No tienes permisos para realizar esta acción.',
  404: 'El servidor no tiene el servicio solicitado (404). Puede que el backend esté desactualizado o reiniciándose.',
  405: 'El servidor no admite esta operación (405).',
  413: 'El archivo es demasiado grande para el servidor.',
  429: 'Demasiados intentos. Espera unos minutos antes de reintentar.',
  500: 'El servidor encontró un error interno (500).',
  502: 'El servidor no está respondiendo (502). Puede estar reiniciándose.',
  503: 'El servicio no está disponible temporalmente (503).',
  504: 'El servidor tardó demasiado en responder (504).',
};

/** Detecta una página de error HTML, que nunca contiene un mensaje útil para mostrar. */
function isHtml(body: unknown): boolean {
  return typeof body === 'string' && /<html|<!doctype|<title>/i.test(body);
}

/**
 * Busca el primer texto dentro de `details`, que DRF entrega como cadena, lista
 * (`raise ValidationError("texto")`) o diccionario por campo, con anidamiento.
 */
function firstText(value: unknown): string | null {
  if (typeof value === 'string') {
    return value.trim() || null;
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      const text = firstText(item);
      if (text) return text;
    }
    return null;
  }
  if (typeof value === 'object' && value !== null) {
    for (const item of Object.values(value as Record<string, unknown>)) {
      const text = firstText(item);
      if (text) return text;
    }
  }
  return null;
}

interface ApiErrorBody {
  error?: { message?: string; details?: unknown };
  detail?: string;
}

export function apiErrorMessage(error: HttpErrorResponse, fallback = DEFAULT_MESSAGE): string {
  // status 0: la petición nunca llegó (backend apagado, sin red, CORS bloqueado).
  if (error.status === 0) {
    return NETWORK_MESSAGE;
  }

  const body = error.error as ApiErrorBody | string | undefined;

  if (body && typeof body === 'object') {
    // Los detalles por campo son más precisos que el mensaje general.
    const fromDetails = firstText(body.error?.details);
    if (fromDetails) return fromDetails;
    if (body.error?.message) return body.error.message;
    if (body.detail) return body.detail;
  }

  // Texto plano del servidor, solo si no es una página HTML.
  if (typeof body === 'string' && !isHtml(body) && body.trim()) {
    return body.trim();
  }

  return STATUS_MESSAGES[error.status] ?? fallback;
}
