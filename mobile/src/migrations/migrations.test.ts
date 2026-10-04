import { describe, expect, it } from 'vitest';
import { memoryKv } from '../shared/storage';
import { BACKUP_MANIFEST, BACKUP_PREFIX, legacyTrackerKeys, restoreTrackerBackup, runMigrations, snapshotTrackerLegacy, type Migration } from './index';

/** Datos representativos de una instalación 1.2.x en uso: jornada activa, cola, puntos pendientes y rechazados, y la credencial. */
const legacyData = (): Record<string, string> => ({
  steps_movil_token: 'SECRETO-NO-COPIAR',
  steps_movil_active: JSON.stringify({ sessionId: 's1', workOrderId: 7, machineId: 3, machineName: 'Tractor', startedAt: 1, hourmeterStart: 10, tankStart: 20, tankCapacity: 100, distanceM: 120 }),
  steps_movil_outbox: JSON.stringify([{ kind: 'session_close', sessionId: 's0', endedAt: '2026-10-03T13:00:00Z' }]),
  steps_movil_outbox_ids: JSON.stringify({ s1: 7 }),
  steps_movil_pending: JSON.stringify({ s1: Array.from({ length: 200 }, (_, i) => ({ ts: new Date(i * 4000).toISOString(), lat: -35, lon: -71, speed_mps: null, accuracy_m: 5 })) }),
  steps_movil_points_rejected: JSON.stringify({ s0: [{ ts: '2026-10-03T12:00:00Z', lat: -35, lon: -71, speed_mps: null, accuracy_m: 5 }] }),
  steps_movil_settings: JSON.stringify({ fontScale: 1.15 }),
  otra_cosa: 'no es del tracker',
});
const fakeStore = (data: Record<string, string>) => ({
  data,
  get length() { return Object.keys(data).length; },
  key: (i: number) => Object.keys(data)[i] ?? null,
  getItem: (k: string) => data[k] ?? null,
  setItem: (k: string, v: string) => { data[k] = v; },
});
const ctx = (kv: ReturnType<typeof memoryKv>, legacy: ReturnType<typeof fakeStore>) => ({ kv, legacy, now: () => Date.parse('2026-10-04T12:00:00Z') });

describe('migración del Tracker a la app unificada', () => {
  it('copia lo del Tracker (sin credenciales ni claves ajenas), verifica y deja el origen INTACTO', async () => {
    const legacy = fakeStore(legacyData()), kv = memoryKv();
    const before = JSON.stringify(legacy.data);
    const journal = await runMigrations(ctx(kv, legacy));
    expect(journal.done.map((d) => d.name)).toEqual(['snapshot_tracker_legacy']);
    expect(JSON.stringify(legacy.data)).toBe(before); // el origen no se tocó
    const manifest = JSON.parse((await kv.get(BACKUP_MANIFEST))!);
    expect(Object.keys(manifest.keys).sort()).toEqual(legacyTrackerKeys(legacy));
    expect(await kv.get(BACKUP_PREFIX + 'steps_movil_token')).toBeNull();
    expect(await kv.get(BACKUP_PREFIX + 'otra_cosa')).toBeNull();
    expect(await kv.get(BACKUP_PREFIX + 'steps_movil_pending')).toBe(legacy.data.steps_movil_pending);
    expect(JSON.stringify(Object.entries(kv.dump()))).not.toContain('SECRETO');
  });

  it('es repetible: una segunda ejecución no duplica ni modifica nada', async () => {
    const legacy = fakeStore(legacyData()), kv = memoryKv();
    await runMigrations(ctx(kv, legacy));
    const first = JSON.stringify(kv.dump());
    legacy.data.steps_movil_pending = '{"s1":[]}'; // el Tracker sigue funcionando y cambia sus datos
    await runMigrations(ctx(kv, legacy));
    expect(JSON.stringify(kv.dump())).toBe(first); // la copia es la del primer arranque, no se pisa
  });

  it('se recupera de una interrupción (poco espacio a mitad): no declara la copia válida y la completa después', async () => {
    const legacy = fakeStore(legacyData()), kv = memoryKv();
    let writes = 0;
    kv.failWrites((k) => k.startsWith(BACKUP_PREFIX) && ++writes > 3); // se llena a la cuarta clave
    const j1 = await runMigrations(ctx(kv, legacy));
    expect(j1.done).toEqual([]);
    expect(j1.failed?.reason).toMatch(/No se pudo copiar/);
    expect(await kv.get(BACKUP_MANIFEST)).toBeNull(); // sin manifiesto no hay copia «válida»
    kv.failWrites(null);
    const j2 = await runMigrations(ctx(kv, legacy)); // siguiente arranque
    expect(j2.done.map((d) => d.id)).toEqual([1]);
    expect(j2.failed).toBeUndefined();
    expect(JSON.parse((await kv.get(BACKUP_MANIFEST))!).keys.steps_movil_active).toBeGreaterThan(0);
  });

  it('una instalación nueva (sin datos del Tracker) no crea copias', async () => {
    const kv = memoryKv();
    const j = await runMigrations(ctx(kv, fakeStore({})));
    expect(j.done.map((d) => d.id)).toEqual([1]);
    expect(await kv.get(BACKUP_MANIFEST)).toBeNull();
  });

  it('un paso que falla detiene los siguientes y se reintenta en orden', async () => {
    const kv = memoryKv(), legacy = fakeStore({});
    const calls: string[] = [];
    let broken = true;
    const steps: Migration[] = [
      { id: 1, name: 'a', run: async () => { calls.push('a'); } },
      { id: 2, name: 'b', run: async () => { calls.push('b'); if (broken) throw new Error('falla'); } },
      { id: 3, name: 'c', run: async () => { calls.push('c'); } },
    ];
    await runMigrations(ctx(kv, legacy), steps);
    expect(calls).toEqual(['a', 'b']);
    broken = false;
    const j = await runMigrations(ctx(kv, legacy), steps);
    expect(calls).toEqual(['a', 'b', 'b', 'c']); // «a» no se repite
    expect(j.done.map((d) => d.id)).toEqual([1, 2, 3]);
  });

  it('la copia permite recuperar: solo restaura lo ausente salvo que se pida sobrescribir', async () => {
    const legacy = fakeStore(legacyData()), kv = memoryKv();
    await runMigrations(ctx(kv, legacy));
    delete legacy.data.steps_movil_active; // se perdió una clave
    legacy.data.steps_movil_settings = '{"fontScale":1}'; // otra cambió
    const restored = await restoreTrackerBackup(kv, (k, v) => { legacy.data[k] = v; }, legacy);
    expect(restored).toContain('steps_movil_active');
    expect(restored).not.toContain('steps_movil_settings');
    expect(JSON.parse(legacy.data.steps_movil_active).sessionId).toBe('s1');
    const all = await restoreTrackerBackup(kv, (k, v) => { legacy.data[k] = v; }, legacy, true);
    expect(all).toContain('steps_movil_settings');
  });

  it('el paso 1 por sí solo es idempotente aunque se invoque dos veces seguidas', async () => {
    const legacy = fakeStore(legacyData()), kv = memoryKv();
    await snapshotTrackerLegacy.run(ctx(kv, legacy)); const a = JSON.stringify(kv.dump());
    await snapshotTrackerLegacy.run(ctx(kv, legacy));
    expect(JSON.stringify(kv.dump())).toBe(a.replace(/"createdAt":"[^"]*"/, (m) => m));
  });
});
