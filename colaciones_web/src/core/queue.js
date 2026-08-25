import { BACKOFF, DEFAULT_LIMITS, QUEUE_STATE } from "./constants.js";
import { createUuid, maskIdentifier } from "./identity.js";

/**
 * Cola local de capturas.
 *
 * Depende de un `QueueRepository` con la interfaz mínima:
 *
 *   list()            -> Promise<record[]>
 *   put(record)       -> Promise<void>
 *   remove(clientUuid)-> Promise<void>
 *
 * La PWA lo implementa sobre IndexedDB y la App móvil sobre SQLite. Toda la
 * política —estados, límites, reintentos, purga— vive aquí y es idéntica en
 * ambas plataformas.
 */

export class QueueFullError extends Error {
  constructor(limit) {
    super(`El equipo alcanzó el máximo de ${limit} capturas sin sincronizar.`);
    this.name = "QueueFullError";
    this.limit = limit;
  }
}

/** Espera antes del próximo intento, creciente y con tope. */
export function backoffDelay(attempts, { random = Math.random, config = BACKOFF } = {}) {
  const exponent = Math.max(0, attempts - 1);
  const raw = Math.min(config.baseMs * config.factor ** exponent, config.maxMs);
  const jitter = raw * config.jitterRatio * (random() * 2 - 1);
  return Math.max(config.baseMs, Math.round(raw + jitter));
}

export function createQueue({
  repository,
  clock = () => new Date(),
  limits = DEFAULT_LIMITS,
  random = Math.random,
} = {}) {
  if (!repository) throw new TypeError("createQueue necesita un repository");
  const settings = { ...DEFAULT_LIMITS, ...limits };

  const nowIso = () => clock().toISOString();

  async function all() {
    const records = await repository.list();
    return Array.isArray(records) ? records : [];
  }

  function isOpen(record) {
    return record.state === QUEUE_STATE.PENDING || record.state === QUEUE_STATE.SYNCING;
  }

  return {
    settings,

    /** Crea una captura nueva en estado `pending`. */
    async enqueue({ identifier, eventDatetime, clientUuid, offline = true }) {
      const records = await all();
      const open = records.filter(isOpen);
      if (open.length >= settings.maxQueueRecords) throw new QueueFullError(settings.maxQueueRecords);
      const record = {
        clientUuid: clientUuid || createUuid(),
        identifier: String(identifier || "").trim(),
        identifierMasked: maskIdentifier(identifier),
        eventDatetime: eventDatetime || nowIso(),
        createdAt: nowIso(),
        updatedAt: nowIso(),
        state: QUEUE_STATE.PENDING,
        offline: Boolean(offline),
        attempts: 0,
        nextAttemptAt: nowIso(),
        lastError: "",
      };
      await repository.put(record);
      return record;
    },

    async list() {
      return all();
    },

    /** Capturas listas para transmitir según su espera de reintento. */
    async due() {
      const records = await all();
      const now = clock().getTime();
      return records
        .filter((record) => isOpen(record))
        .filter((record) => !record.nextAttemptAt || Date.parse(record.nextAttemptAt) <= now)
        .sort((left, right) => Date.parse(left.createdAt) - Date.parse(right.createdAt));
    },

    async markSyncing(records) {
      const stamped = nowIso();
      for (const record of records) {
        await repository.put({ ...record, state: QUEUE_STATE.SYNCING, updatedAt: stamped });
      }
    },

    /**
     * Confirmación explícita del servidor. Se conserva un rastro corto para el
     * diagnóstico, pero sin el identificador completo del trabajador.
     */
    async markSynced(record, { registration = "", duplicate = false } = {}) {
      await repository.put({
        ...record,
        identifier: "",
        state: QUEUE_STATE.SYNCED,
        duplicate,
        registration,
        syncedAt: nowIso(),
        updatedAt: nowIso(),
        lastError: "",
      });
    },

    /** Rechazo definitivo: deja de reintentarse y queda visible para el administrador. */
    async markTerminal(record, message) {
      await repository.put({
        ...record,
        identifier: "",
        state: QUEUE_STATE.TERMINAL_ERROR,
        updatedAt: nowIso(),
        lastError: String(message || "").slice(0, 300),
      });
    },

    /** Error pasajero: vuelve a `pending` con una espera mayor. */
    async markRetry(record, message) {
      const attempts = (record.attempts || 0) + 1;
      const delay = backoffDelay(attempts, { random });
      await repository.put({
        ...record,
        state: QUEUE_STATE.PENDING,
        attempts,
        nextAttemptAt: new Date(clock().getTime() + delay).toISOString(),
        updatedAt: nowIso(),
        lastError: String(message || "").slice(0, 300),
      });
      return delay;
    },

    /** Devuelve capturas atascadas en `syncing` (por ejemplo, tras un cierre forzado). */
    async recoverInterrupted() {
      const records = await all();
      const stuck = records.filter((record) => record.state === QUEUE_STATE.SYNCING);
      for (const record of stuck) {
        await repository.put({ ...record, state: QUEUE_STATE.PENDING, updatedAt: nowIso() });
      }
      return stuck.length;
    },

    /** Elimina confirmaciones antiguas para no crecer sin límite. */
    async prune() {
      const records = await all();
      const synced = records
        .filter((record) => record.state === QUEUE_STATE.SYNCED)
        .sort((left, right) => Date.parse(right.syncedAt || right.updatedAt) - Date.parse(left.syncedAt || left.updatedAt));
      const excess = synced.slice(settings.keepSyncedRecords);
      for (const record of excess) {
        await repository.remove(record.clientUuid);
      }
      return excess.length;
    },

    async discardTerminal() {
      const records = await all();
      const rejected = records.filter((record) => record.state === QUEUE_STATE.TERMINAL_ERROR);
      for (const record of rejected) {
        await repository.remove(record.clientUuid);
      }
      return rejected.length;
    },

    /** Resumen para la interfaz y el diagnóstico. */
    async stats() {
      const records = await all();
      const counters = {
        pending: 0,
        syncing: 0,
        synced: 0,
        terminal_error: 0,
      };
      let oldestPending = null;
      let lastSyncedAt = null;
      for (const record of records) {
        if (counters[record.state] !== undefined) counters[record.state] += 1;
        if (isOpen(record)) {
          const created = Date.parse(record.createdAt);
          if (!oldestPending || created < oldestPending) oldestPending = created;
        }
        if (record.state === QUEUE_STATE.SYNCED && record.syncedAt) {
          const synced = Date.parse(record.syncedAt);
          if (!lastSyncedAt || synced > lastSyncedAt) lastSyncedAt = synced;
        }
      }
      const open = counters.pending + counters.syncing;
      const oldestPendingHours = oldestPending
        ? (clock().getTime() - oldestPending) / 3_600_000
        : 0;
      return {
        ...counters,
        open,
        total: records.length,
        oldestPendingAt: oldestPending ? new Date(oldestPending).toISOString() : null,
        oldestPendingHours,
        lastSyncedAt: lastSyncedAt ? new Date(lastSyncedAt).toISOString() : null,
        nearlyFull: open >= settings.warnQueueRecords,
        full: open >= settings.maxQueueRecords,
        staleOffline: oldestPendingHours >= settings.warnOfflineHours,
      };
    },
  };
}
