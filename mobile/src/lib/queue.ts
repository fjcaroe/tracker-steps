// Cola de puntos GPS en almacenamiento local: la jornada no se pierde si cae la señal.
import type { PointIn } from './api';
import { isPermanentRejection } from './outbox';

const KEY = 'steps_movil_pending';
const ACTIVE = 'steps_movil_active';
const LAST_SYNC = 'steps_movil_last_sync';
const REJECTED = 'steps_movil_points_rejected';
/** Tope de puntos rechazados que se conservan en el teléfono (los más recientes). */
const REJECTED_MAX = 5000;

export type Active = {
  sessionId: string; workOrderId: number; machineId: number; machineName: string; startedAt: number;
  hourmeterStart: number; tankStart: number; tankCapacity: number | null; distanceM: number; fromTask?: boolean;
};

function read<T>(key: string, fallback: T): T { try { const raw = localStorage.getItem(key); return raw ? (JSON.parse(raw) as T) : fallback; } catch { return fallback; } }
function write(key: string, value: unknown) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* sin espacio / modo privado */ } }

export const activeStore = {
  get: () => read<Active | null>(ACTIVE, null),
  set: (a: Active | null) => { if (a) write(ACTIVE, a); else { try { localStorage.removeItem(ACTIVE); } catch { /* nada */ } } },
};

/** Hora (ms) del último envío correcto de puntos al servidor. */
export const syncStore = {
  get: () => read<number | null>(LAST_SYNC, null),
};

export const pointQueue = {
  all: () => read<Record<string, PointIn[]>>(KEY, {}),
  push(sessionId: string, point: PointIn) { const q = pointQueue.all(); (q[sessionId] ||= []).push(point); write(KEY, q); },
  size(sessionId: string) { return pointQueue.all()[sessionId]?.length ?? 0; },
  clear(sessionId: string) { const q = pointQueue.all(); delete q[sessionId]; write(KEY, q); },
  /** Puntos que el servidor rechazó de forma definitiva: se guardan aparte (no se pierden) y ya no cuentan como pendientes. */
  rejected: () => read<Record<string, PointIn[]>>(REJECTED, {}),
  /**
   * Envía por lotes. Si falla la red o el servidor, se conserva todo lo pendiente para el próximo intento.
   * Si el servidor rechaza un lote de forma definitiva, se aparta para no bloquear el cierre de la jornada ni las demás.
   */
  async flush(sessionId: string, send: (points: PointIn[]) => Promise<unknown>, batch = 50, keepRejected = REJECTED_MAX): Promise<number> {
    let sent = 0;
    for (;;) {
      const pending = pointQueue.all()[sessionId] ?? [];
      if (!pending.length) return sent;
      const chunk = pending.slice(0, batch);
      let delivered = true;
      try { await send(chunk); } catch (e) { if (!isPermanentRejection(e)) return sent; delivered = false; }
      const fresh = pointQueue.all();
      fresh[sessionId] = (fresh[sessionId] ?? []).slice(chunk.length);
      if (!fresh[sessionId].length) delete fresh[sessionId];
      // Primero se guarda lo apartado y después se quita de la cola: un corte entre ambos pasos duplica, nunca pierde.
      if (!delivered) {
        const aside = pointQueue.rejected();
        aside[sessionId] = [...(aside[sessionId] ?? []), ...chunk].slice(-keepRejected);
        write(REJECTED, aside);
      }
      write(KEY, fresh);
      if (delivered) { write(LAST_SYNC, Date.now()); sent += chunk.length; }
    }
  },
};

export function formatDuration(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

export function parseNumber(value: string): number | null {
  const n = parseFloat((value || '').replace(',', '.'));
  return Number.isFinite(n) ? n : null;
}
