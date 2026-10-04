// Cola de puntos GPS en almacenamiento local: la jornada no se pierde si cae la señal.
import type { PointIn } from './api';
import { isPermanentRejection } from './outbox';

const KEY = 'steps_movil_pending';
const ACTIVE = 'steps_movil_active';
const LAST_SYNC = 'steps_movil_last_sync';
const REJECTED = 'steps_movil_points_rejected';
const FINISHED = 'steps_movil_finished_ids';
/** Jornadas terminadas que se recuerdan para ignorar respuestas atrasadas del servidor. Solo son identificadores. */
const FINISHED_MAX = 500;

export type Active = {
  sessionId: string; workOrderId: number; machineId: number; machineName: string; startedAt: number;
  hourmeterStart: number; tankStart: number; tankCapacity: number | null; distanceM: number; fromTask?: boolean;
};

function read<T>(key: string, fallback: T): T { try { const raw = localStorage.getItem(key); return raw ? (JSON.parse(raw) as T) : fallback; } catch { return fallback; } }
function write(key: string, value: unknown) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* sin espacio / modo privado */ } }

/** Escribe y comprueba que lo guardado se puede leer de vuelta. Devuelve false si no hubo persistencia real. */
function writeVerified(key: string, value: unknown): boolean {
  try {
    const raw = JSON.stringify(value);
    localStorage.setItem(key, raw);
    return localStorage.getItem(key) === raw;
  } catch { return false; }
}

const pointKey = (p: PointIn) => `${p.ts}|${p.lat}|${p.lon}`;
let storageProblem = false;
/** true si el último intento de apartar puntos rechazados no pudo guardarse (almacenamiento lleno o bloqueado). */
export const storageHealth = { hasProblem: () => storageProblem };

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
  /** Puntos que el servidor rechazó de forma definitiva: se guardan aparte y ya no cuentan como pendientes. Nunca se descartan solos. */
  rejected: () => read<Record<string, PointIn[]>>(REJECTED, {}),
  rejectedTotal: () => Object.values(pointQueue.rejected()).reduce((n, p) => n + p.length, 0),
  /** Copia legible de los puntos apartados, para entregarla a soporte. No modifica nada. */
  exportRejected: () => JSON.stringify({ exportedAt: new Date().toISOString(), points: pointQueue.rejected() }, null, 2),
  /** Devuelve a la cola de envío los puntos apartados de una jornada (p. ej. tras corregir el problema del servidor). */
  requeueRejected(sessionId: string): number {
    const aside = pointQueue.rejected();
    const rows = aside[sessionId] ?? [];
    if (!rows.length) return 0;
    const q = pointQueue.all();
    const known = new Set((q[sessionId] ?? []).map(pointKey));
    q[sessionId] = [...(q[sessionId] ?? []), ...rows.filter((p) => !known.has(pointKey(p)))];
    // Primero se guarda en la cola y solo después se quita de lo apartado: un corte entre ambos pasos duplica, nunca pierde.
    if (!writeVerified(KEY, q)) return 0;
    delete aside[sessionId];
    write(REJECTED, aside);
    return rows.length;
  },
  /**
   * Envía por lotes. Si falla la red o el servidor, se conserva todo lo pendiente para el próximo intento.
   * Si el servidor rechaza un lote de forma definitiva, se aparta para no bloquear el cierre de la jornada ni las demás;
   * el lote solo sale de la cola cuando lo apartado quedó guardado y verificado. Si no puede guardarse, sigue pendiente.
   */
  async flush(sessionId: string, send: (points: PointIn[]) => Promise<unknown>, batch = 50): Promise<number> {
    let sent = 0;
    for (;;) {
      const pending = pointQueue.all()[sessionId] ?? [];
      if (!pending.length) return sent;
      const chunk = pending.slice(0, batch);
      let delivered = true;
      try { await send(chunk); } catch (e) { if (!isPermanentRejection(e)) return sent; delivered = false; }
      if (!delivered) {
        const aside = pointQueue.rejected();
        const known = new Set((aside[sessionId] ?? []).map(pointKey));
        aside[sessionId] = [...(aside[sessionId] ?? []), ...chunk.filter((p) => !known.has(pointKey(p)))];
        storageProblem = !writeVerified(REJECTED, aside);
        if (storageProblem) return sent; // no hay dónde apartarlos: se conservan como pendientes
      }
      const fresh = pointQueue.all();
      fresh[sessionId] = (fresh[sessionId] ?? []).slice(chunk.length);
      if (!fresh[sessionId].length) delete fresh[sessionId];
      write(KEY, fresh);
      if (delivered) { write(LAST_SYNC, Date.now()); sent += chunk.length; }
    }
  },
};

/** Jornadas que la persona terminó en este teléfono, aunque su cierre ya se haya enviado. Evita que una respuesta atrasada las reofrezca. */
export const finishedStore = {
  ids: (): string[] => read<string[]>(FINISHED, []),
  add(sessionId: string) { const ids = finishedStore.ids().filter((i) => i !== sessionId); ids.push(sessionId); write(FINISHED, ids.slice(-FINISHED_MAX)); },
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
