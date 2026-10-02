// Sincronización: cola de operaciones + puntos GPS, con almacenamiento local.
import { sessions } from './api';
import { runOutbox, startPending, type Op } from './outbox';
import { activeStore, pointQueue } from './queue';

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

let running: Promise<number> | null = null;

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
    return result.done;
  })().finally(() => { running = null; });
  return running;
}
