// Sincronización: cola de operaciones + puntos GPS, con almacenamiento local.
import { api, sessions } from './api';
import { recordHealthSync } from './health';
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

/** Total de elementos sin enviar (operaciones + puntos GPS de todas las jornadas). */
export function pendingTotal(): number {
  return outboxStore.ops().length + Object.values(pointQueue.all()).reduce((n, p) => n + p.length, 0);
}

let running: Promise<number> | null = null;
const receivedEmergencies = new Set<string>();
export const emergencyReceived = (id: string) => receivedEmergencies.has(id);

/** Compuerta de propietario: mientras devuelva false no se envía nada (datos de otra cuenta o de dueño desconocido). */
let gate: () => boolean = () => true;
export function setSyncGate(fn: () => boolean) { gate = fn; }
/** Ejecuta la cola y luego envía los puntos de la jornada activa (si ya existe en el servidor). Devuelve operaciones completadas. */
export function syncAll(userId?: number): Promise<number> {
  if (!gate()) return Promise.resolve(0);
  if (running) return running;
  running = (async () => {
    const flushPoints = async (sessionId: string) => {
      await pointQueue.flush(sessionId, async (points) => {
        const receipt = await sessions.points(sessionId, points);
        if (userId != null) recordHealthSync(userId);
        return receipt;
      });
      return pointQueue.size(sessionId) === 0;
    };
    const snapshot = outboxStore.ops();
    const result = await runOutbox(snapshot, outboxStore.resolved(), {
      createWorkOrder: sessions.createWorkOrder,
      startSession: (id, workOrderId, body, startedAt) => sessions.start({ ...body, id, work_order_id: workOrderId, started_at: startedAt }),
      flushPoints,
      closeSession: (id, endedAt) => sessions.close(id, endedAt),
      finishWorkOrder: sessions.finishWorkOrder,
      post: async (path, body) => {
        await api(`/mobile/${path}`, { method: 'POST', body: JSON.stringify(body) });
        if (path === 'incidents' && body.category === 'sos' && typeof body.id === 'string') {
          receivedEmergencies.add(body.id);
          if (receivedEmergencies.size > 50) {
            const oldest = receivedEmergencies.values().next().value;
            if (oldest) receivedEmergencies.delete(oldest);
          }
        }
      },
    });
    if (userId != null && result.done > 0) recordHealthSync(userId);
    // Registros agregados mientras una petición estaba en vuelo deben sobrevivir al resultado.
    write(OPS, [...result.ops, ...outboxStore.ops().slice(snapshot.length)]);
    write(RESOLVED, result.resolved);
    // Cuando la jornada activa ya existe en el servidor, adoptar el id de su parte para cerrarla después.
    const active = activeStore.get();
    if (active) {
      const id = result.resolved[active.sessionId];
      if (id && active.workOrderId !== id) activeStore.set({ ...active, workOrderId: id });
    }
    // También quedan puntos de jornadas cerradas o ya retiradas de la pantalla activa.
    for (const id of Object.keys(pointQueue.all())) {
      if (!startPending(outboxStore.ops(), id)) await flushPoints(id);
    }
    return result.done;
  })().finally(() => { running = null; });
  return running;
}
