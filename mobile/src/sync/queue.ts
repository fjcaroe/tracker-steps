// Cola durable de operaciones de campo, separada por identidad, empresa y módulo.
// Reglas (docs/STEPS_APP_MIGRACION_OFFLINE.md): se persiste ANTES de anunciar éxito; nada se borra por cierre de sesión, cambio de cuenta,
// cuota o límite; el rechazo definitivo se conserva para diagnóstico, exportación y reintento.
import { readJson, StorageError, writeJson, type KeyValueStore } from '../shared/storage';

export type OpState = 'pending' | 'sending' | 'confirmed' | 'auth_required' | 'rejected';
export type Scope = { personId: number; orgUid: string };

export type QueueOp<P = unknown> = {
  /** UUID generado en el dispositivo: es la clave de idempotencia en el servidor. */
  id: string;
  module: string;
  kind: string;
  /** Las operaciones de un mismo grupo se envían en orden (p. ej. un viaje: abrir → eventos → cerrar). */
  group: string;
  payload: P;
  createdAt: string;
  state: OpState;
  attempts: number;
  code?: string;
  error?: string;
  settledAt?: string;
  /** Dato mostrado al confirmar (p. ej. nombre del trabajador y número de registro). Nunca incluye secretos. */
  result?: unknown;
};

export const CONFIRMED_KEEP_DAYS = 7;
export const SESSION_CODES = ['unauthenticated', 'session_invalid', 'session_revoked', 'token_expired'];
const PREFIX = 'steps.queue.v1.';
export const queueKey = (s: Scope) => `${PREFIX}${s.personId}.${s.orgUid}`;
export const uuid = (): string => (globalThis.crypto?.randomUUID?.() ?? `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`);

// Una sola cadena de mutaciones por cola: un envío en vuelo no pisa lo que se encola mientras tanto.
const chains = new Map<string, Promise<unknown>>();
function exclusive<T>(key: string, job: () => Promise<T>): Promise<T> {
  const run = (chains.get(key) ?? Promise.resolve()).then(job, job);
  chains.set(key, run.catch(() => undefined));
  return run;
}

export class DurableQueue {
  constructor(private kv: KeyValueStore, readonly scope: Scope) {}
  private get key() { return queueKey(this.scope); }

  private read(): Promise<QueueOp[]> { return readJson<QueueOp[]>(this.kv, this.key, []); }

  /** Lista las operaciones. Un `sending` heredado de un cierre brusco vuelve a `pending` (el servidor es idempotente). */
  async list(): Promise<QueueOp[]> {
    return (await this.read()).map((op) => (op.state === 'sending' ? { ...op, state: 'pending' as const } : op));
  }

  /** Persiste la operación; lanza StorageError si no quedó guardada. Nunca devolver éxito al usuario antes de esto. */
  enqueue<P>(input: { module: string; kind: string; group: string; payload: P; id?: string }): Promise<QueueOp<P>> {
    return exclusive(this.key, async () => {
      const ops = await this.read();
      const existing = input.id ? ops.find((o) => o.id === input.id) : undefined;
      if (existing) return existing as QueueOp<P>; // doble pulsación o reintento de encolado: mismo UUID, una sola operación
      const op: QueueOp<P> = { id: input.id ?? uuid(), module: input.module, kind: input.kind, group: input.group, payload: input.payload,
        createdAt: new Date().toISOString(), state: 'pending', attempts: 0 };
      await writeJson(this.kv, this.key, [...ops, op]);
      return op;
    });
  }

  /** Aplica cambios a operaciones concretas sobre el estado más reciente guardado. */
  update(changes: Record<string, Partial<QueueOp>>): Promise<void> {
    return exclusive(this.key, async () => {
      const ops = await this.read();
      const next = ops.map((o) => (changes[o.id] ? { ...o, ...changes[o.id] } : o));
      await writeJson(this.kv, this.key, next);
    });
  }

  /** «Reintentar»: devuelve rechazadas o bloqueadas a pendientes para un intento real. */
  requeue(ids?: string[]): Promise<number> {
    return exclusive(this.key, async () => {
      const ops = await this.read();
      let n = 0;
      const next = ops.map((o) => {
        if ((o.state === 'rejected' || o.state === 'auth_required') && (!ids || ids.includes(o.id))) {
          n += 1;
          const { error: _e, code: _c, settledAt: _s, ...rest } = o;
          return { ...rest, state: 'pending' as const };
        }
        return o;
      });
      if (n) await writeJson(this.kv, this.key, next);
      return n;
    });
  }

  /** Reanuda las operaciones que solo esperaban una sesión válida (no las bloqueadas por permisos ni las rechazadas). */
  async requeueSessionBlocked(): Promise<number> {
    const ids = (await this.read()).filter((o) => o.state === 'auth_required' && SESSION_CODES.includes(o.code ?? '')).map((o) => o.id);
    return ids.length ? this.requeue(ids) : 0;
  }

  /** Quita solo operaciones confirmadas y antiguas (historial). Pendientes y rechazadas nunca se podan. */
  prune(now = Date.now()): Promise<void> {
    return exclusive(this.key, async () => {
      const ops = await this.read();
      const keep = ops.filter((o) => !(o.state === 'confirmed' && o.settledAt && now - Date.parse(o.settledAt) > CONFIRMED_KEEP_DAYS * 86_400_000));
      if (keep.length !== ops.length) await writeJson(this.kv, this.key, keep);
    });
  }

  async exportJson(): Promise<string> {
    return JSON.stringify({ exportedAt: new Date().toISOString(), scope: this.scope, ops: await this.read() }, null, 2);
  }

  async counts(): Promise<{ pending: number; rejected: number; authRequired: number; confirmed: number }> {
    const ops = await this.list();
    const c = (s: OpState) => ops.filter((o) => o.state === s).length;
    return { pending: c('pending') + c('sending'), rejected: c('rejected'), authRequired: c('auth_required'), confirmed: c('confirmed') };
  }
}

/** Colas de otras cuentas/empresas guardadas en este teléfono (para avisar y permitir exportar; nunca se envían con otra sesión). */
export async function foreignQueues(kv: KeyValueStore, current: Scope | null): Promise<{ scope: Scope; pending: number; rejected: number }[]> {
  const result: { scope: Scope; pending: number; rejected: number }[] = [];
  for (const key of await kv.keys(PREFIX)) {
    const [personId, ...org] = key.slice(PREFIX.length).split('.');
    const scope = { personId: Number(personId), orgUid: org.join('.') };
    if (current && scope.personId === current.personId && scope.orgUid === current.orgUid) continue;
    const ops = await readJson<QueueOp[]>(kv, key, []);
    const pending = ops.filter((o) => o.state !== 'confirmed' && o.state !== 'rejected').length;
    const rejected = ops.filter((o) => o.state === 'rejected').length;
    if (pending || rejected) result.push({ scope, pending, rejected });
  }
  return result;
}

export { StorageError };
