// Cola de puntos GPS en almacenamiento local: la jornada no se pierde si cae la señal.
import type { PointIn } from './api';

const KEY = 'steps_movil_pending';
const ACTIVE = 'steps_movil_active';
const LAST_SENT = 'steps_movil_last_sent';

export type Active = {
  sessionId: string; workOrderId: number; machineId: number; machineName: string; startedAt: number;
  hourmeterStart: number; tankStart: number; tankCapacity: number | null; distanceM: number;
};

function read<T>(key: string, fallback: T): T { try { const raw = localStorage.getItem(key); return raw ? (JSON.parse(raw) as T) : fallback; } catch { return fallback; } }
function write(key: string, value: unknown) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* sin espacio / modo privado */ } }

export const activeStore = {
  get: () => read<Active | null>(ACTIVE, null),
  set: (a: Active | null) => { if (a) write(ACTIVE, a); else { try { localStorage.removeItem(ACTIVE); } catch { /* nada */ } } },
};

export const lastSent = {
  get: () => read<number | null>(LAST_SENT, null),
  mark: () => write(LAST_SENT, Date.now()),
};

export const pointQueue = {
  /** Descarta lo pendiente de una sesión (p. ej. ya cerrada en el servidor). */
  drop(sessionId: string) { const q = pointQueue.all(); delete q[sessionId]; write(KEY, q); },
  all: () => read<Record<string, PointIn[]>>(KEY, {}),
  push(sessionId: string, point: PointIn) { const q = pointQueue.all(); (q[sessionId] ||= []).push(point); write(KEY, q); },
  size(sessionId: string) { return pointQueue.all()[sessionId]?.length ?? 0; },
  /** Envía por lotes; si un lote falla se conserva todo lo pendiente para el próximo intento. */
  async flush(sessionId: string, send: (points: PointIn[]) => Promise<unknown>, batch = 50): Promise<number> {
    let sent = 0;
    for (;;) {
      const pending = pointQueue.all()[sessionId] ?? [];
      if (!pending.length) return sent;
      const chunk = pending.slice(0, batch);
      try { await send(chunk); } catch { return sent; }
      const fresh = pointQueue.all();
      fresh[sessionId] = (fresh[sessionId] ?? []).slice(chunk.length);
      if (!fresh[sessionId].length) delete fresh[sessionId];
      write(KEY, fresh);
      sent += chunk.length;
      lastSent.mark();
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
