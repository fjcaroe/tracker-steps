import { QUEUE_STATE } from "./constants.js";
import { maskIdentifier } from "./identity.js";

/**
 * Migración de la cola de la versión 1 de la PWA.
 *
 * La versión anterior guardaba en `localStorage`, bajo la clave
 * `steps_colaciones_queue_<token>`, un arreglo plano de capturas
 * `{identifier, client_uuid, event_datetime, offline}` sin estado ni intentos.
 * Un equipo que se actualiza con marcaciones sin transmitir no debe perderlas.
 */
export function normalizeLegacyRecord(legacy, { now = () => new Date().toISOString() } = {}) {
  if (!legacy || typeof legacy !== "object") return null;
  const clientUuid = legacy.client_uuid || legacy.clientUuid;
  if (!clientUuid) return null;
  const identifier = String(legacy.identifier || "").trim();
  const stamp = legacy.event_datetime || legacy.eventDatetime || now();
  return {
    clientUuid,
    identifier,
    identifierMasked: maskIdentifier(identifier),
    eventDatetime: stamp,
    createdAt: stamp,
    updatedAt: now(),
    state: QUEUE_STATE.PENDING,
    offline: true,
    attempts: 0,
    nextAttemptAt: now(),
    lastError: "",
    migratedFrom: "v1",
  };
}

/**
 * Copia la cola anterior al repositorio nuevo y borra el origen solo cuando
 * cada captura quedó escrita. Es idempotente: si ya existe el UUID no lo pisa.
 */
export async function migrateLegacyQueue({ legacySource, repository, now }) {
  if (!legacySource || !repository) return { migrated: 0, skipped: 0 };
  const legacyRecords = await legacySource.read();
  if (!Array.isArray(legacyRecords) || !legacyRecords.length) {
    await legacySource.clear();
    return { migrated: 0, skipped: 0 };
  }
  const existing = new Set((await repository.list()).map((record) => record.clientUuid));
  let migrated = 0;
  let skipped = 0;
  for (const legacy of legacyRecords) {
    const record = normalizeLegacyRecord(legacy, { now });
    if (!record) {
      skipped += 1;
      continue;
    }
    if (existing.has(record.clientUuid)) {
      skipped += 1;
      continue;
    }
    await repository.put(record);
    migrated += 1;
  }
  await legacySource.clear();
  return { migrated, skipped };
}
