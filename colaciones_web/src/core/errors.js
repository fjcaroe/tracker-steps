import { ERROR_KIND } from "./constants.js";

/**
 * Error de la API con la clasificación ya resuelta.
 *
 * `kind` decide el comportamiento de la cola: `temporary` conserva la captura y
 * reintenta; `terminal` la marca como rechazada y deja de reintentar.
 */
export class ApiError extends Error {
  constructor(message, { kind = ERROR_KIND.TEMPORARY, status = 0, code = "", body = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
    this.code = code;
    this.body = body;
  }

  get terminal() {
    return this.kind === ERROR_KIND.TERMINAL;
  }
}

/** Estados HTTP que siempre representan una condición pasajera del servidor. */
const TEMPORARY_STATUSES = new Set([0, 408, 425, 429, 500, 502, 503, 504, 507, 598, 599]);

/** Estados HTTP que representan un rechazo definitivo del contrato. */
const TERMINAL_STATUSES = new Set([400, 401, 403, 404, 405, 409, 410, 415, 422]);

/**
 * Decide si una respuesta debe reintentarse.
 *
 * El cuerpo manda sobre el código: Odoo responde `terminal: true` en los
 * rechazos funcionales, y eso evita reintentar para siempre una captura que
 * nunca va a ser aceptada.
 */
export function classifyResponse(status, body) {
  if (body && typeof body === "object") {
    if (body.terminal === true) return ERROR_KIND.TERMINAL;
    if (body.terminal === false) return ERROR_KIND.TEMPORARY;
  }
  if (TEMPORARY_STATUSES.has(status)) return ERROR_KIND.TEMPORARY;
  if (TERMINAL_STATUSES.has(status)) return ERROR_KIND.TERMINAL;
  // Ante un código desconocido se prefiere reintentar: perder una marcación es
  // peor que enviarla dos veces, y el UUID de cliente hace idempotente el envío.
  return ERROR_KIND.TEMPORARY;
}

/** Mensaje mostrable al operador, sin filtrar detalles internos del servidor. */
export function friendlyMessage(error) {
  if (error instanceof ApiError && error.message) return error.message;
  if (error && error.name === "AbortError") return "El servidor tardó demasiado en responder.";
  return "No fue posible comunicarse con el servidor.";
}
