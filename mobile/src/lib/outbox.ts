// Cola ordenada de operaciones pendientes (jornadas, checklist, incidencias y gastos creados sin señal). Núcleo puro y probado.
import type { WorkOrderIn } from './api';

export type FinishBody = { hourmeter_final: number | null; fuel_refill_liters: number | null; fuel_tank_end_liters: number | null; mobile_status?: string; progress_pct?: number };
type Base = { sessionId: string; error?: string };
export type PostKind = 'checklists' | 'incidents' | 'expenses';
export type Op =
  | (Base & { kind: 'wo_create'; body: WorkOrderIn })
  | (Base & { kind: 'session_start'; body: { machine_id: number; driver_id: number | null; cost_center_id: number | null }; startedAt: string; workOrderId?: number })
  | (Base & { kind: 'session_close'; endedAt: string })
  | (Base & { kind: 'wo_finish'; body: FinishBody; workOrderId?: number })
  // Registros de campo con id propio (idempotentes en el servidor). `sessionId` agrupa y ordena respecto de la jornada.
  | (Base & { kind: 'post'; path: PostKind; body: Record<string, unknown> });

export type Handlers = {
  createWorkOrder(body: WorkOrderIn): Promise<{ id: number }>;
  startSession(sessionId: string, workOrderId: number | null, body: Extract<Op, { kind: 'session_start' }>['body'], startedAt: string): Promise<unknown>;
  /** true si no quedan puntos GPS por enviar para esa sesión. */
  flushPoints(sessionId: string): Promise<boolean>;
  closeSession(sessionId: string, endedAt: string): Promise<unknown>;
  finishWorkOrder(id: number, body: FinishBody): Promise<unknown>;
  post(path: PostKind, body: Record<string, unknown>): Promise<unknown>;
};

export const isNetworkError = (e: unknown): boolean => {
  const status = (e as { status?: number })?.status;
  return status === 0 || (typeof status === 'number' && status >= 500);
};

export type RunResult = { ops: Op[]; resolved: Record<string, number>; done: number };

/**
 * Ejecuta las operaciones en orden. Un fallo de red/servidor detiene todo (se conserva el resto);
 * un rechazo 4xx marca la operación con su error y bloquea solo las siguientes de esa jornada.
 */
export async function runOutbox(input: Op[], resolvedIn: Record<string, number>, h: Handlers): Promise<RunResult> {
  const resolved = { ...resolvedIn };
  const remaining: Op[] = [];
  const blocked = new Set<string>();
  let done = 0, halted = false;
  for (const raw of input) {
    const op: Op = { ...raw };
    if (halted || blocked.has(op.sessionId)) { remaining.push(op); continue; }
    try {
      if (op.kind === 'wo_create') resolved[op.sessionId] = (await h.createWorkOrder(op.body)).id;
      else if (op.kind === 'session_start') await h.startSession(op.sessionId, op.workOrderId ?? resolved[op.sessionId] ?? null, op.body, op.startedAt);
      else if (op.kind === 'session_close') {
        if (!(await h.flushPoints(op.sessionId))) { halted = true; remaining.push(op); continue; }
        await h.closeSession(op.sessionId, op.endedAt);
      } else if (op.kind === 'post') {
        const body = { ...op.body };
        // El parte de la jornada puede haberse creado después de registrar el gasto.
        if (op.path === 'expenses' && !body.work_order_id && resolved[op.sessionId]) body.work_order_id = resolved[op.sessionId];
        await h.post(op.path, body);
      } else {
        const id = op.workOrderId ?? resolved[op.sessionId];
        if (!id) throw Object.assign(new Error('No se conoce el parte de trabajo de esta jornada.'), { status: 400 });
        await h.finishWorkOrder(id, op.body);
      }
      done += 1;
    } catch (e) {
      if (isNetworkError(e)) { halted = true; delete op.error; }
      else { op.error = (e as Error).message || 'Rechazada por el servidor'; blocked.add(op.sessionId); }
      remaining.push(op);
    }
  }
  return { ops: remaining, resolved, done };
}

/** ¿La jornada todavía debe crearse en el servidor? (los puntos GPS no se envían hasta entonces). */
export const startPending = (ops: Op[], sessionId: string) => ops.some((o) => o.sessionId === sessionId && (o.kind === 'wo_create' || o.kind === 'session_start'));
