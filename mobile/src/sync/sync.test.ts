import { beforeEach, describe, expect, it } from 'vitest';
import { ApiError } from '../app/api';
import { memoryKv, StorageError } from '../shared/storage';
import { runQueue, type Handler, type Outcome } from './engine';
import { DurableQueue, foreignQueues, queueKey, type QueueOp } from './queue';

const A = { personId: 1, orgUid: 'org-a' };
let kv: ReturnType<typeof memoryKv>;
beforeEach(() => { kv = memoryKv(); });

const enq = (q: DurableQueue, kind: string, group: string, extra: Partial<{ id: string; module: string }> = {}) =>
  q.enqueue({ module: extra.module ?? 'm', kind, group, payload: { n: Math.random() }, id: extra.id });
const ok: Outcome = { status: 'confirmed' };
const handler = (fn: (ops: QueueOp[]) => Promise<Outcome[]> | Outcome[], batch = 1): Handler => ({ batch, send: async (ops) => fn(ops) });

describe('cola durable', () => {
  it('persiste antes de devolver y falla visiblemente si no pudo guardar', async () => {
    const q = new DurableQueue(kv, A);
    await enq(q, 'k', 'g');
    expect(await q.list()).toHaveLength(1);
    kv.failWrites(() => true);
    await expect(enq(q, 'k', 'g')).rejects.toBeInstanceOf(StorageError);
    kv.failWrites(null);
    expect(await q.list()).toHaveLength(1); // nada se perdió ni se duplicó
  });

  it('la doble pulsación con el mismo UUID produce una sola operación', async () => {
    const q = new DurableQueue(kv, A);
    await Promise.all([enq(q, 'k', 'g', { id: 'same' }), enq(q, 'k', 'g', { id: 'same' }), enq(q, 'k', 'g', { id: 'same' })]);
    expect(await q.list()).toHaveLength(1);
  });

  it('lo encolado mientras hay un envío en vuelo sobrevive al resultado', async () => {
    const q = new DurableQueue(kv, A);
    await enq(q, 'k', 'g1', { id: 'first' });
    let release!: () => void;
    const gate = new Promise<void>((r) => { release = r; });
    const running = runQueue({ queue: q, sessionPersonId: 1, handlers: { 'm:k': handler(async () => { await gate; return [ok]; }) } });
    await new Promise((r) => setTimeout(r, 5));
    await enq(q, 'k', 'g2', { id: 'second' });
    release();
    await running;
    const ops = await q.list();
    expect(ops.map((o) => [o.id, o.state])).toEqual([['first', 'confirmed'], ['second', 'pending']]);
  });

  it('un envío interrumpido (sending) vuelve a pendiente al reabrir', async () => {
    const q = new DurableQueue(kv, A);
    const op = await enq(q, 'k', 'g');
    await q.update({ [op.id]: { state: 'sending' } });
    expect((await new DurableQueue(kv, A).list())[0].state).toBe('pending');
  });

  it('las colas de cada empresa/persona están separadas y se listan las ajenas', async () => {
    const a = new DurableQueue(kv, A), b = new DurableQueue(kv, { personId: 2, orgUid: 'org-a' }), c = new DurableQueue(kv, { personId: 1, orgUid: 'org-b' });
    await enq(a, 'k', 'g'); await enq(b, 'k', 'g'); await enq(c, 'k', 'g');
    expect(Object.keys(kv.dump()).sort()).toEqual([queueKey(A), queueKey({ personId: 1, orgUid: 'org-b' }), queueKey({ personId: 2, orgUid: 'org-a' })].sort());
    const foreign = await foreignQueues(kv, A);
    expect(foreign.map((f) => `${f.scope.personId}/${f.scope.orgUid}`).sort()).toEqual(['1/org-b', '2/org-a']);
    expect(await a.list()).toHaveLength(1);
  });

  it('poda solo confirmadas antiguas: pendientes y rechazadas nunca se borran', async () => {
    const q = new DurableQueue(kv, A);
    const [p, r, c] = [await enq(q, 'k', 'g1'), await enq(q, 'k', 'g2'), await enq(q, 'k', 'g3')];
    const old = new Date(Date.now() - 30 * 86_400_000).toISOString();
    await q.update({ [r.id]: { state: 'rejected', settledAt: old }, [c.id]: { state: 'confirmed', settledAt: old } });
    await q.prune();
    expect((await q.list()).map((o) => o.id).sort()).toEqual([p.id, r.id].sort());
  });

  it('exportar incluye lo rechazado y reintentar lo devuelve a pendiente', async () => {
    const q = new DurableQueue(kv, A);
    const op = await enq(q, 'k', 'g');
    await q.update({ [op.id]: { state: 'rejected', code: 'x', error: 'no' } });
    expect(JSON.parse(await q.exportJson()).ops[0].state).toBe('rejected');
    expect(await q.requeue()).toBe(1);
    const [again] = await q.list();
    expect([again.state, again.error]).toEqual(['pending', undefined]);
  });
});

describe('motor de envío', () => {
  it('envía en orden dentro del grupo y agrupa lo que el handler permite', async () => {
    const q = new DurableQueue(kv, A);
    for (const id of ['1', '2', '3']) await enq(q, 'k', 'g', { id });
    const seen: string[][] = [];
    const s = await runQueue({ queue: q, sessionPersonId: 1, handlers: { 'm:k': handler((ops) => { seen.push(ops.map((o) => o.id)); return ops.map(() => ok); }, 2) } });
    expect(seen).toEqual([['1', '2'], ['3']]);
    expect(s).toMatchObject({ confirmed: 3, halted: null });
  });

  it('el rechazo definitivo se conserva, no bloquea a las demás ni a su propio grupo', async () => {
    const q = new DurableQueue(kv, A);
    await enq(q, 'open', 'trip-1', { id: 'a' }); await enq(q, 'ev', 'trip-1', { id: 'b' }); await enq(q, 'ev', 'trip-2', { id: 'c' });
    const s = await runQueue({ queue: q, sessionPersonId: 1, handlers: {
      'm:open': handler(() => [{ status: 'rejected', code: 'cannot_open', message: 'Inspección rechazada' }]),
      'm:ev': handler((ops) => ops.map(() => ok)),
    } });
    expect(s).toMatchObject({ confirmed: 2, rejected: 1 });
    const byId = Object.fromEntries((await q.list()).map((o) => [o.id, o]));
    expect(byId.a).toMatchObject({ state: 'rejected', code: 'cannot_open', error: 'Inspección rechazada' });
    expect(byId.b.state).toBe('confirmed');
  });

  it('un corte de red detiene todo y conserva cada operación', async () => {
    const q = new DurableQueue(kv, A);
    await enq(q, 'k', 'g1', { id: 'a' }); await enq(q, 'k', 'g2', { id: 'b' });
    const s = await runQueue({ queue: q, sessionPersonId: 1, handlers: { 'm:k': handler(() => { throw new ApiError('network', 0); }) } });
    expect(s).toMatchObject({ halted: 'network', confirmed: 0, rejected: 0 });
    expect((await q.list()).map((o) => [o.id, o.state])).toEqual([['a', 'pending'], ['b', 'pending']]);
  });

  it.each([400, 404, 409, 422])('un HTTP %i del lote completo NO descarta datos', async (status) => {
    const q = new DurableQueue(kv, A);
    await enq(q, 'k', 'g1', { id: 'a' }); await enq(q, 'k', 'g2', { id: 'b' });
    await runQueue({ queue: q, sessionPersonId: 1, handlers: { 'm:k': handler((ops) => { if (ops[0].id === 'a') throw new ApiError('batch_invalid', status); return [ok]; }) } });
    const [a, b] = await q.list();
    expect([a.state, b.state]).toEqual(['pending', 'confirmed']);
    expect(a.attempts).toBe(1);
  });

  it('sesión vencida: pide autenticación y conserva la cola sin presentarla como rechazo del negocio', async () => {
    const q = new DurableQueue(kv, A);
    await enq(q, 'k', 'g', { id: 'a' });
    const s = await runQueue({ queue: q, sessionPersonId: 1, handlers: { 'm:k': handler(() => { throw new ApiError('session_invalid', 401); }) } });
    expect(s.halted).toBe('auth');
    const [a] = await q.list();
    expect(a.state).toBe('auth_required');
    expect(await q.requeue()).toBe(1);
  });

  it('nunca reenvía operaciones de la cuenta A con la sesión de la cuenta B', async () => {
    const q = new DurableQueue(kv, A);
    await enq(q, 'k', 'g');
    let called = false;
    const handlers = { 'm:k': handler((ops) => { called = true; return ops.map(() => ok); }) };
    expect((await runQueue({ queue: q, sessionPersonId: 2, handlers })).halted).toBe('other_account');
    expect((await runQueue({ queue: q, sessionPersonId: null, handlers })).halted).toBe('other_account');
    expect(called).toBe(false);
    expect((await q.list())[0].state).toBe('pending');
  });

  it('una operación sin handler (módulo no instalado) se conserva', async () => {
    const q = new DurableQueue(kv, A);
    await enq(q, 'zzz', 'g');
    await runQueue({ queue: q, sessionPersonId: 1, handlers: {} });
    expect((await q.list())[0].state).toBe('pending');
  });

  it('reenviar un lote ya confirmado en el servidor es seguro: el resultado duplicado también confirma', async () => {
    const q = new DurableQueue(kv, A);
    await enq(q, 'k', 'g', { id: 'a' });
    await runQueue({ queue: q, sessionPersonId: 1, handlers: { 'm:k': handler(() => { throw new ApiError('network', 0); }) } });
    const s = await runQueue({ queue: q, sessionPersonId: 1, handlers: { 'm:k': handler(() => [ok]) } }); // «duplicate» llega como confirmed
    expect(s.confirmed).toBe(1);
  });
});
