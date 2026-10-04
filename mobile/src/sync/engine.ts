// Motor de envío. Clasifica por el contrato de cada endpoint: un HTTP 400 NO autoriza a descartar datos; solo un `rejected`
// explícito del servidor (resultado por registro) es definitivo.
import { ApiError } from '../app/api';
import { StorageError } from '../shared/storage';
import type { DurableQueue, QueueOp, Scope } from './queue';

export type Outcome = { status: 'confirmed' | 'rejected' | 'retry' | 'auth_required'; code?: string; message?: string; result?: unknown };
export type Handler = {
  /** Cuántas operaciones consecutivas del mismo tipo y grupo pueden viajar juntas. */
  batch?: number;
  /** Debe devolver un resultado por operación, en el mismo orden. Los errores de red/HTTP se lanzan como ApiError. */
  send(ops: QueueOp[]): Promise<Outcome[]>;
  /** Minimización de datos: devuelve el payload que se conserva tras confirmar (p. ej. sin el identificador del trabajador). */
  redact?(op: QueueOp): unknown;
};
/** `storage`: el teléfono no pudo guardar el nuevo estado de las operaciones (cuota llena o bloqueado); lo ya guardado sigue intacto. */
export type Halt = null | 'network' | 'auth' | 'other_account' | 'storage';

/** Espera progresiva entre reintentos automáticos: 5 s, 10 s, 20 s… hasta 15 min; tras MAX_AUTO_ATTEMPTS la operación queda «bloqueada». */
export const MAX_AUTO_ATTEMPTS = 8;
export const backoffMs = (attempts: number): number => Math.min(5_000 * 2 ** Math.max(0, attempts - 1), 15 * 60_000);
export type RunSummary = { confirmed: number; rejected: number; retried: number; halted: Halt };

/** Traduce un error lanzado por el cliente HTTP a un resultado de lote. Nunca convierte un 4xx genérico en descarte. */
export function outcomeFromError(error: unknown): Outcome {
  if (error instanceof ApiError) {
    if (error.status === 401 || error.status === 403) return { status: 'auth_required', code: error.code, message: error.message };
    if (error.status === 0) return { status: 'retry', code: 'network', message: error.message };
    if (error.status >= 500 || error.status === 408 || error.status === 429) return { status: 'retry', code: 'server', message: error.message };
    // 4xx de lote completo (formato inválido, etc.): se conserva y se reintenta; solo bloquea su grupo.
    return { status: 'retry', code: error.code, message: error.message };
  }
  return { status: 'retry', code: 'network', message: (error as Error)?.message };
}

export async function runQueue(opts: { queue: DurableQueue; handlers: Record<string, Handler>; sessionPersonId: number | null; scope?: Scope; /** «Reintentar» manual: ignora la espera progresiva. */ force?: boolean; now?: () => number }): Promise<RunSummary> {
  const { queue, handlers, sessionPersonId } = opts;
  const now = opts.now ?? Date.now;
  const summary: RunSummary = { confirmed: 0, rejected: 0, retried: 0, halted: null };
  // Nunca se reenvían operaciones de la cuenta A con la sesión de la cuenta B.
  if (sessionPersonId == null || sessionPersonId !== queue.scope.personId) return { ...summary, halted: 'other_account' };

  const ops = (await queue.list()).filter((o) => o.state === 'pending' && (opts.force || !o.nextAttemptAt || Date.parse(o.nextAttemptAt) <= now()));
  const haltedGroups = new Set<string>();
  let i = 0;
  while (i < ops.length && !summary.halted) {
    const first = ops[i];
    const handler = handlers[`${first.module}:${first.kind}`];
    if (haltedGroups.has(first.group) || !handler) { i += 1; continue; }
    const batch = [first];
    while (i + batch.length < ops.length && batch.length < (handler.batch ?? 1)) {
      const next = ops[i + batch.length];
      if (next.module !== first.module || next.kind !== first.kind || next.group !== first.group) break;
      batch.push(next);
    }
    i += batch.length;
    let outcomes: Outcome[];
    try {
      outcomes = await handler.send(batch);
      if (outcomes.length !== batch.length) throw new Error('El servidor respondió un número distinto de resultados.');
    } catch (error) {
      const outcome = outcomeFromError(error);
      outcomes = batch.map(() => outcome);
    }
    const settledAt = new Date().toISOString();
    const changes: Record<string, Partial<QueueOp>> = {};
    batch.forEach((op, k) => {
      const o = outcomes[k];
      if (o.status === 'confirmed') { changes[op.id] = { state: 'confirmed', settledAt, attempts: op.attempts + 1, result: o.result, ...(handler.redact ? { payload: handler.redact(op) } : {}) }; summary.confirmed += 1; }
      else if (o.status === 'rejected') { changes[op.id] = { state: 'rejected', code: o.code, error: o.message ?? o.code ?? 'Rechazada por el servidor', settledAt, attempts: op.attempts + 1 }; summary.rejected += 1; }
      else if (o.status === 'auth_required') { changes[op.id] = { state: 'auth_required', code: o.code, error: o.message, attempts: op.attempts + 1 }; summary.halted = 'auth'; }
      else {
        const attempts = op.attempts + 1;
        // Los fallos de red no cuentan para el tope (no es culpa de la operación); los demás sí.
        const exhausted = o.code !== 'network' && attempts >= MAX_AUTO_ATTEMPTS;
        changes[op.id] = exhausted
          ? { state: 'blocked', code: o.code, error: o.message ?? 'Reintentos agotados', attempts }
          : o.code === 'network'
            // Sin señal no hay espera: se reintenta apenas vuelva la conexión (evento «online» o temporizador).
            ? { state: 'pending', code: o.code, error: o.message, attempts: op.attempts, nextAttemptAt: undefined }
            : { state: 'pending', code: o.code, error: o.message, attempts, nextAttemptAt: new Date(now() + backoffMs(attempts)).toISOString() };
        summary.retried += 1; haltedGroups.add(first.group); if (o.code === 'network' || o.code === 'server') summary.halted = summary.halted ?? 'network'; }
    });
    try { await queue.update(changes); }
    catch (e) {
      // No se pudo guardar el nuevo estado: lo ya guardado queda intacto y se reenviará (el servidor es idempotente).
      if (e instanceof StorageError) return { ...summary, halted: 'storage' };
      throw e;
    }
  }
  return summary;
}
