// Sincronización: cola de operaciones + puntos GPS, con almacenamiento local.
import { api, APP_VERSION, mobile, sessions } from './api';
import { runOutbox, startPending, type Op } from './outbox';
import { activeStore, pointQueue, syncStore } from './queue';

const OPS = 'steps_movil_outbox';
const RESOLVED = 'steps_movil_outbox_ids';

function read<T>(key: string, fallback: T): T { try { const raw = localStorage.getItem(key); return raw ? (JSON.parse(raw) as T) : fallback; } catch { return fallback; } }
function write(key: string, value: unknown) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* sin espacio */ } }

export const outboxStore = {
  ops: () => read<Op[]>(OPS, []),
  add(...ops: Op[]) { write(OPS, [...outboxStore.ops(), ...ops]); },
  /** Quita los errores para que "Reintentar" vuelva a intentar las operaciones rechazadas. */
  clearErrors() { write(OPS, outboxStore.ops().map((o) => { const { error: _e, ...rest } = o; return rest as Op; })); },
  resolved: () => read<Record<string, number>>(RESOLVED, {}),
};

/** Total de elementos sin enviar (operaciones + puntos GPS de todas las jornadas). */
export function pendingTotal(): number {
  return outboxStore.ops().length + Object.values(pointQueue.all()).reduce((n, p) => n + p.length, 0);
}

const platform = (): string => { try { return (window as unknown as { Capacitor?: { getPlatform?: () => string } }).Capacitor?.getPlatform?.() ?? 'web'; } catch { return 'web'; } };

let running: Promise<number> | null = null;
let lastBeat = 0;
let lastBeatPending = -1;
const BEAT_EVERY_MS = 60_000;

/** Ejecuta la cola y luego envía los puntos de la jornada activa (si ya existe en el servidor). Devuelve operaciones completadas. */
export function syncAll(): Promise<number> {
  if (running) return running;
  running = (async () => {
    const flushPoints = async (sessionId: string) => {
      await pointQueue.flush(sessionId, (p) => sessions.points(sessionId, p));
      return pointQueue.size(sessionId) === 0;
    };
    const result = await runOutbox(outboxStore.ops(), outboxStore.resolved(), {
      createWorkOrder: sessions.createWorkOrder,
      startSession: (id, workOrderId, body, startedAt) => sessions.start({ ...body, id, work_order_id: workOrderId, started_at: startedAt }),
      flushPoints,
      closeSession: (id, endedAt) => sessions.close(id, endedAt),
      finishWorkOrder: sessions.finishWorkOrder,
      post: (path, body) => api(`/mobile/${path}`, { method: 'POST', body: JSON.stringify(body) }),
    });
    write(OPS, result.ops);
    write(RESOLVED, result.resolved);
    // Cuando la jornada activa ya existe en el servidor, adoptar el id de su parte para cerrarla después.
    const active = activeStore.get();
    if (active) {
      const id = result.resolved[active.sessionId];
      if (id && active.workOrderId !== id) activeStore.set({ ...active, workOrderId: id });
      if (!startPending(result.ops, active.sessionId)) await flushPoints(active.sessionId);
    }
    // Señal de vida para soporte: versión de la app, pendientes y última sincronización.
    const last = syncStore.get();
    const pending = pendingTotal();
    if (Date.now() - lastBeat > BEAT_EVERY_MS || pending !== lastBeatPending) {
      lastBeat = Date.now(); lastBeatPending = pending;
      void mobile.heartbeat({ version: APP_VERSION, platform: platform(), pending, last_sync_at: last ? new Date(last).toISOString() : null }).catch(() => {});
    }
    return result.done;
  })().finally(() => { running = null; });
  return running;
}
