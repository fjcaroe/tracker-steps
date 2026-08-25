import { CORE_VERSION } from "./constants.js";
import { maskToken } from "./identity.js";

/**
 * Diagnóstico exportable para soporte.
 *
 * Nunca incluye el token completo, el nombre del trabajador ni el
 * identificador leído: solo lo necesario para entender por qué un equipo no
 * está sincronizando.
 */
export async function buildDiagnostics({
  queue,
  session,
  deviceInfo,
  appVersion = "",
  online = null,
  clock = () => new Date(),
} = {}) {
  const stats = queue ? await queue.stats() : null;
  const records = queue ? await queue.list() : [];
  const info = deviceInfo ? await deviceInfo.describe() : {};
  return {
    generated_at: clock().toISOString(),
    app_version: appVersion,
    core_version: CORE_VERSION,
    platform: info.platform || "",
    install_id: info.installId || "",
    app_build: info.appBuild || "",
    online,
    token: maskToken(session?.token ? await session.token() : ""),
    totem_code: session?.config?.code || "",
    api_version: session?.capabilities?.apiVersion ?? null,
    batch_sync: Boolean(session?.capabilities?.batchSync),
    clock_skew_seconds: Math.round((session?.clockSkewMs || 0) / 1000),
    queue: stats,
    // Solo estado y tiempos; nada que permita reconstruir quién marcó.
    records: records.slice(-50).map((record) => ({
      state: record.state,
      attempts: record.attempts || 0,
      created_at: record.createdAt,
      next_attempt_at: record.nextAttemptAt || null,
      synced_at: record.syncedAt || null,
      last_error: record.lastError || "",
    })),
  };
}
