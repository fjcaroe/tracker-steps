// Migraciones locales: versionadas, repetibles sin duplicar, recuperables tras una interrupción y que NO borran el origen.
// Registro (diario) en `steps.migration.journal.v1`. Cada paso es idempotente: si la app se cierra a mitad, el siguiente arranque lo repite.
import { readJson, writeJson, type KeyValueStore } from '../shared/storage';

export type LegacyStore = { length: number; key(i: number): string | null; getItem(k: string): string | null };
export type MigrationContext = { kv: KeyValueStore; legacy: LegacyStore; now: () => number };
export type Migration = { id: number; name: string; run(ctx: MigrationContext): Promise<void> };
export type Journal = { done: { id: number; name: string; at: string }[]; failed?: { id: number; name: string; reason: string; at: string } };

const JOURNAL = 'steps.migration.journal.v1';
export const BACKUP_PREFIX = 'steps.backup.tracker.v1.';
export const BACKUP_MANIFEST = `${BACKUP_PREFIX}manifest`;
const LEGACY_PREFIX = 'steps_movil_';
/** Credenciales: nunca se copian. */
const SECRET_KEYS = new Set(['steps_movil_token']);

export function legacyTrackerKeys(legacy: LegacyStore): string[] {
  const keys: string[] = [];
  for (let i = 0; i < legacy.length; i++) { const k = legacy.key(i); if (k && k.startsWith(LEGACY_PREFIX) && !SECRET_KEYS.has(k)) keys.push(k); }
  return keys.sort();
}

/**
 * 1 · Copia de seguridad de los datos del Tracker anteriores a la app unificada (jornadas, puntos GPS, cola, rechazados).
 * El origen NO se toca: el Tracker sigue usando sus claves. La copia se verifica leyendo cada clave de vuelta; solo entonces se
 * escribe el manifiesto. No se atribuye ningún dato a ningún usuario (el propietario no es demostrable).
 */
export const snapshotTrackerLegacy: Migration = {
  id: 1, name: 'snapshot_tracker_legacy',
  async run({ kv, legacy, now }) {
    const keys = legacyTrackerKeys(legacy);
    if (!keys.length) return; // instalación nueva: no hay nada que resguardar
    const copied: Record<string, number> = {};
    for (const key of keys) {
      const value = legacy.getItem(key);
      if (value == null) continue;
      if (!(await kv.set(BACKUP_PREFIX + key, value))) throw new Error(`No se pudo copiar ${key} (¿poco espacio?)`);
      copied[key] = value.length;
    }
    // Verificación de destino ANTES de declarar la copia válida.
    for (const [key, length] of Object.entries(copied)) {
      const back = await kv.get(BACKUP_PREFIX + key);
      if (back == null || back.length !== length) throw new Error(`La copia de ${key} no coincide con el origen`);
    }
    await writeJson(kv, BACKUP_MANIFEST, { createdAt: new Date(now()).toISOString(), keys: copied, note: 'Copia previa a la app unificada; el propietario de estos datos no está identificado.' });
  },
};

export const MIGRATIONS: Migration[] = [snapshotTrackerLegacy];

/** Ejecuta las migraciones pendientes en orden. Un fallo se registra y se reintentará en el próximo arranque; nunca bloquea la app. */
export async function runMigrations(ctx: MigrationContext, migrations: Migration[] = MIGRATIONS): Promise<Journal> {
  const journal = await readJson<Journal>(ctx.kv, JOURNAL, { done: [] });
  for (const m of [...migrations].sort((a, b) => a.id - b.id)) {
    if (journal.done.some((d) => d.id === m.id)) continue;
    try {
      await m.run(ctx);
      journal.done.push({ id: m.id, name: m.name, at: new Date(ctx.now()).toISOString() });
      delete journal.failed;
    } catch (e) {
      journal.failed = { id: m.id, name: m.name, reason: (e as Error).message, at: new Date(ctx.now()).toISOString() };
      await writeJson(ctx.kv, JOURNAL, journal).catch(() => undefined);
      return journal; // los pasos siguientes dependen del orden
    }
    await writeJson(ctx.kv, JOURNAL, journal).catch(() => { journal.done.pop(); }); // si no se pudo anotar, se repetirá (es idempotente)
  }
  return journal;
}

/**
 * Recuperación: devuelve al Tracker los datos de la copia. Por seguridad solo escribe claves AUSENTES, salvo `overwrite`.
 * Devuelve las claves restauradas.
 */
export async function restoreTrackerBackup(kv: KeyValueStore, legacyWrite: (k: string, v: string) => void, legacy: LegacyStore, overwrite = false): Promise<string[]> {
  const manifest = await readJson<{ keys: Record<string, number> } | null>(kv, BACKUP_MANIFEST, null);
  if (!manifest) return [];
  const restored: string[] = [];
  const existing = new Set(legacyTrackerKeys(legacy));
  for (const key of Object.keys(manifest.keys)) {
    if (!overwrite && existing.has(key)) continue;
    const value = await kv.get(BACKUP_PREFIX + key);
    if (value != null) { legacyWrite(key, value); restored.push(key); }
  }
  return restored;
}
