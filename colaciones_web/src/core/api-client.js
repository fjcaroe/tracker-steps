import { SUPPORTED_API_VERSION } from "./constants.js";
import { ApiError, classifyResponse } from "./errors.js";

/**
 * Cliente del contrato HTTP de Colaciones.
 *
 * No conoce `fetch`: recibe un `transport` que devuelve `{status, body}`. La
 * PWA usa `fetch` mismo origen y la App móvil un cliente HTTP nativo, que
 * además evita CORS porque la petición no sale del WebView.
 */
export function createApiClient({ transport, baseUrl = "", timeoutMs = 15_000 } = {}) {
  if (typeof transport !== "function") {
    throw new TypeError("createApiClient necesita un transport(request) -> {status, body}");
  }
  const root = String(baseUrl || "").replace(/\/+$/, "");

  async function call(method, path, body) {
    let response;
    try {
      response = await transport({ method, url: `${root}${path}`, body, timeoutMs });
    } catch (error) {
      // Fallo de red, DNS, TLS o timeout: siempre pasajero.
      throw new ApiError(error?.message || "Sin conexión con el servidor.", {
        kind: "temporary",
        status: 0,
        code: "network",
      });
    }
    const { status, body: payload } = response;
    const ok = status >= 200 && status < 300;
    if (!ok) {
      throw new ApiError(payload?.message || `El servidor respondió ${status}.`, {
        kind: classifyResponse(status, payload),
        status,
        code: payload?.error || "",
        body: payload,
      });
    }
    return payload;
  }

  return {
    /** Capacidades y hora del servidor. No requiere token. */
    health() {
      return call("GET", "/colaciones/api/health");
    },

    /** Configuración operativa del tótem asociado. */
    totem(token) {
      return call("GET", `/colaciones/api/totem/${encodeURIComponent(token)}`);
    },

    /** Envío individual, usado por la captura en línea. */
    register({ token, record, device }) {
      return call("POST", "/colaciones/api/register", {
        token,
        device,
        identifier: record.identifier,
        client_uuid: record.clientUuid,
        event_datetime: record.eventDatetime,
        offline: Boolean(record.offline),
      });
    },

    /** Envío por lote con respuesta individual por UUID. */
    sync({ token, records, device }) {
      return call("POST", "/colaciones/api/sync", {
        token,
        device,
        records: records.map((record) => ({
          client_uuid: record.clientUuid,
          identifier: record.identifier,
          event_datetime: record.eventDatetime,
          offline: true,
        })),
      });
    },
  };
}

/**
 * Decide qué endpoints puede usar la App contra un servidor concreto.
 * Un servidor antiguo (sin `/health`) sigue soportando el envío individual.
 */
export function readCapabilities(health) {
  const capabilities = Array.isArray(health?.capabilities) ? health.capabilities : [];
  const apiVersion = Number(health?.api_version) || 1;
  return {
    apiVersion,
    supported: apiVersion <= SUPPORTED_API_VERSION,
    batchSync: capabilities.includes("batch_sync"),
    deviceInfo: capabilities.includes("device_info"),
    maxBatchRecords: Number(health?.max_batch_records) || 1,
    serverTime: health?.server_time || null,
    minAppVersion: health?.min_app_version || null,
    recommendedAppVersion: health?.recommended_app_version || null,
  };
}
