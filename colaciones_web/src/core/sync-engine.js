import { ERROR_KIND, QUEUE_STATE } from "./constants.js";
import { ApiError } from "./errors.js";

/**
 * Motor de sincronización compartido.
 *
 * Reglas que no cambian entre plataformas:
 *
 * - una sola sincronización a la vez (evita enviar dos veces al recuperar red);
 * - una captura solo se marca `synced` con confirmación explícita del servidor,
 *   nunca por el hecho de haber enviado la petición;
 * - un error pasajero conserva la captura y aumenta la espera;
 * - un rechazo funcional la marca `terminal_error` y deja de reintentarla.
 */
export function createSyncEngine({
  api,
  queue,
  token,
  device = () => ({}),
  capabilities = () => ({ batchSync: false, maxBatchRecords: 1 }),
  onProgress = () => {},
} = {}) {
  if (!api || !queue) throw new TypeError("createSyncEngine necesita api y queue");

  let running = null;

  function chunk(records, size) {
    const limit = Math.max(1, Number(size) || 1);
    const out = [];
    for (let index = 0; index < records.length; index += limit) {
      out.push(records.slice(index, index + limit));
    }
    return out;
  }

  async function applyBatchResult(record, result) {
    if (!result) {
      // El servidor no informó este UUID: se conserva y se reintenta.
      await queue.markRetry(record, "El servidor no confirmó esta captura.");
      return "retry";
    }
    if (result.status === "registered" || result.status === "duplicate") {
      await queue.markSynced(record, {
        registration: result.registration || "",
        duplicate: result.status === "duplicate",
      });
      return result.status;
    }
    if (result.status === "rejected") {
      await queue.markTerminal(record, result.message);
      return "rejected";
    }
    await queue.markRetry(record, result.message);
    return "retry";
  }

  async function sendBatch(records) {
    const summary = { registered: 0, duplicate: 0, rejected: 0, retry: 0 };
    let response;
    try {
      // `token` y `device` pueden ser asincronos: en movil el token vive en
      // Keychain/Keystore y se lee con una llamada nativa.
      response = await api.sync({
        token: await token(),
        records,
        device: await device(),
      });
    } catch (error) {
      // Solo un tótem inexistente o revocado invalida el lote completo. Un
      // rechazo del contrato (lote mal formado) se reintenta: las capturas en
      // sí pueden ser válidas y perderlas sería peor que enviarlas otra vez.
      const revoked = error instanceof ApiError && error.code === "totem_not_found";
      for (const record of records) {
        if (revoked) {
          await queue.markTerminal(record, error.message);
        } else {
          await queue.markRetry(record, error.message);
        }
      }
      throw error;
    }
    const byUuid = new Map();
    for (const result of response?.results || []) {
      // Un mismo UUID puede aparecer más de una vez si el equipo lo repitió:
      // el primer resultado manda, los siguientes son duplicados idempotentes.
      if (!byUuid.has(result.client_uuid)) byUuid.set(result.client_uuid, result);
    }
    for (const record of records) {
      const outcome = await applyBatchResult(record, byUuid.get(record.clientUuid));
      summary[outcome] += 1;
    }
    return summary;
  }

  async function sendOne(record) {
    let response;
    try {
      response = await api.register({
        token: await token(),
        record,
        device: await device(),
      });
    } catch (error) {
      if (error instanceof ApiError && error.kind === ERROR_KIND.TERMINAL) {
        await queue.markTerminal(record, error.message);
        // Un token revocado invalida el ciclo completo: no tiene sentido
        // insistir captura por captura contra un tótem que ya no existe.
        if (error.code === "totem_not_found") throw error;
        return "rejected";
      }
      await queue.markRetry(record, error?.message);
      throw error;
    }
    await queue.markSynced(record, {
      registration: response?.registration || "",
      duplicate: Boolean(response?.duplicate),
    });
    return response?.duplicate ? "duplicate" : "registered";
  }

  async function run() {
    const summary = {
      registered: 0, duplicate: 0, rejected: 0, retry: 0,
      sent: 0, stopped: false, revoked: false,
    };
    await queue.recoverInterrupted();
    const pending = await queue.due();
    if (!pending.length) return summary;

    const { batchSync, maxBatchRecords } = capabilities() || {};
    const groups = batchSync ? chunk(pending, maxBatchRecords) : pending.map((record) => [record]);

    for (const group of groups) {
      await queue.markSyncing(group);
      try {
        if (batchSync) {
          const result = await sendBatch(group);
          summary.registered += result.registered;
          summary.duplicate += result.duplicate;
          summary.rejected += result.rejected;
          summary.retry += result.retry;
        } else {
          const outcome = await sendOne(group[0]);
          summary[outcome] += 1;
        }
        summary.sent += group.length;
        onProgress(summary);
      } catch (error) {
        // Un error pasajero detiene el ciclo: seguir insistiendo con el resto
        // solo agrava la congestión y ya quedó programado el reintento.
        summary.stopped = true;
        summary.error = error;
        if (error instanceof ApiError && error.code === "totem_not_found") {
          summary.revoked = true;
          summary.rejected += group.length;
        } else {
          summary.retry += group.length;
        }
        break;
      }
    }
    await queue.prune();
    return summary;
  }

  return {
    /** Sincroniza la cola. Llamadas concurrentes comparten la misma ejecución. */
    flush() {
      if (running) return running;
      running = run().finally(() => {
        running = null;
      });
      return running;
    },

    get busy() {
      return Boolean(running);
    },

    QUEUE_STATE,
  };
}
