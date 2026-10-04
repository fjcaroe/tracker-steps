import { beforeEach, describe, expect, it } from 'vitest';
import { ApiError } from '../app/api';
import { memoryKv } from '../shared/storage';
import { backoffMs, MAX_AUTO_ATTEMPTS, runQueue, type Handler } from './engine';
import { acquireLease, releaseLease } from './lease';
import { DurableQueue, type QueueOp } from './queue';

const A = { personId: 1, orgUid: 'org-a' };
let kv: ReturnType<typeof memoryKv>, clock: number;
beforeEach(() => { kv = memoryKv(); clock = Date.parse('2026-10-04T12:00:00Z'); });
const handler = (fn: (ops: QueueOp[]) => unknown): Record<string, Handler> => ({ 'm:k': { send: async (ops) => fn(ops) as never } });
const run = (q: DurableQueue, h: Record<string, Handler>, force = false) => runQueue({ queue: q, handlers: h, sessionPersonId: 1, force, now: () => clock });
const enq = (q: DurableQueue, id = 'a') => q.enqueue({ module: 'm', kind: 'k', group: id, payload: {}, id });

describe('reintentos con límites y espera progresiva', () => {
  it('la espera crece y tiene techo', () => {
    expect([1, 2, 3, 4].map(backoffMs)).toEqual([5_000, 10_000, 20_000, 40_000]);
    expect(backoffMs(30)).toBe(15 * 60_000);
  });

  it('un fallo del servidor espera antes del siguiente intento automático, y «Reintentar» lo ignora', async () => {
    const q = new DurableQueue(kv, A); await enq(q);
    let calls = 0;
    const h = handler(() => { calls += 1; throw new ApiError('boom', 500); });
    await run(q, h);
    expect(calls).toBe(1);
    const [op] = await q.list();
    expect(op).toMatchObject({ state: 'pending', attempts: 1 });
    expect(Date.parse(op.nextAttemptAt!)).toBe(clock + 5_000);
    await run(q, h); expect(calls).toBe(1);            // aún no toca
    clock += 6_000; await run(q, h); expect(calls).toBe(2);
    await run(q, h); expect(calls).toBe(2);            // volvió a esperar (ahora 10 s)
    await run(q, h, true); expect(calls).toBe(3);      // manual: intento real inmediato
  });

  it('tras MAX intentos fallidos del servidor la operación queda «detenida» (no se descarta) y reintentar la reanuda', async () => {
    const q = new DurableQueue(kv, A); await enq(q);
    const h = handler(() => { throw new ApiError('batch_invalid', 422); });
    for (let i = 0; i < MAX_AUTO_ATTEMPTS; i++) { clock += 20 * 60_000; await run(q, h); }
    const [op] = await q.list();
    expect(op).toMatchObject({ state: 'blocked', attempts: MAX_AUTO_ATTEMPTS });
    expect(await q.counts()).toMatchObject({ blocked: 1, pending: 0 });
    expect(await q.requeueRecoverable()).toBe(1);
    expect((await q.list())[0]).toMatchObject({ state: 'pending', attempts: 0 });
  });

  it('la falta de señal nunca detiene una operación, por muchas veces que ocurra', async () => {
    const q = new DurableQueue(kv, A); await enq(q);
    const h = handler(() => { throw new ApiError('network', 0); });
    for (let i = 0; i < MAX_AUTO_ATTEMPTS * 3; i++) await run(q, h);
    const [op] = await q.list();
    expect(op).toMatchObject({ state: 'pending', attempts: 0 });
    expect(op.nextAttemptAt).toBeUndefined(); // al volver la señal se reintenta de inmediato
  });

  it('«Reintentar ahora» no repite lo rechazado por una regla de negocio', async () => {
    const q = new DurableQueue(kv, A);
    const [r, b] = [await enq(q, 'r'), await enq(q, 'b')];
    await q.update({ [r.id]: { state: 'rejected', error: 'no' }, [b.id]: { state: 'blocked' } });
    expect(await q.requeueRecoverable()).toBe(1);
    expect((await q.list()).map((o) => o.state)).toEqual(['rejected', 'pending']);
  });
});

describe('interrupciones y almacenamiento', () => {
  it('si no se puede guardar el estado tras enviar, se informa «storage» y al reintentar sigue siendo una sola operación en el servidor', async () => {
    const q = new DurableQueue(kv, A); await enq(q);
    const serverSeen = new Set<string>();   // el servidor deduplica por UUID
    const h = handler((ops) => ops.map((o) => { serverSeen.add(o.id); return { status: 'confirmed' }; }));
    kv.failWrites((k) => k.startsWith('steps.queue.'));
    const s = await run(q, h);
    expect(s.halted).toBe('storage');
    kv.failWrites(null);
    expect((await q.list())[0].state).toBe('pending');      // lo guardado no se tocó
    expect((await run(q, h)).confirmed).toBe(1);
    expect(serverSeen.size).toBe(1);
    expect((await q.list())[0].state).toBe('confirmed');
  });

  it('cuota llena al encolar: la operación anterior sigue intacta y no hay duplicado al reintentar', async () => {
    const q = new DurableQueue(kv, A); await enq(q, 'x');
    kv.failWrites(() => true);
    await expect(enq(q, 'y')).rejects.toThrow(/No se pudo guardar/);
    kv.failWrites(null);
    await enq(q, 'y'); await enq(q, 'y');
    expect((await q.list()).map((o) => o.id)).toEqual(['x', 'y']);
  });

  it('reinicio durante el envío: un «sending» heredado se reenvía y la respuesta duplicada también confirma', async () => {
    const q = new DurableQueue(kv, A); const op = await enq(q);
    await q.update({ [op.id]: { state: 'sending' } });            // la app murió con la petición en vuelo
    const reopened = new DurableQueue(kv, A);
    const h = handler((ops) => ops.map(() => ({ status: 'confirmed', result: { duplicate: true } }))); // el servidor ya la tenía
    const s = await run(reopened, h);
    expect(s.confirmed).toBe(1);
    expect((await reopened.list())[0]).toMatchObject({ state: 'confirmed' });
  });

  it('un lote con respuesta mezclada conserva cada operación según su propio resultado', async () => {
    const q = new DurableQueue(kv, A);
    for (const id of ['1', '2', '3']) await q.enqueue({ module: 'm', kind: 'k', group: 'g', payload: {}, id });
    const h: Record<string, Handler> = { 'm:k': { batch: 3, send: async () => [{ status: 'confirmed' }, { status: 'rejected', code: 'x', message: 'no' }, { status: 'retry', code: 'server' }] } };
    await run(q, h);
    expect((await q.list()).map((o) => o.state)).toEqual(['confirmed', 'rejected', 'pending']);
  });
});

describe('un solo proceso envía', () => {
  it('el arrendamiento impide el envío simultáneo y caduca si el dueño muere', async () => {
    expect(await acquireLease(kv, 'tab-1', 1_000)).toBe(true);
    expect(await acquireLease(kv, 'tab-2', 2_000)).toBe(false);
    expect(await acquireLease(kv, 'tab-1', 2_000)).toBe(true);      // el dueño puede renovar
    await releaseLease(kv, 'tab-2');                                 // quien no es dueño no lo libera
    expect(await acquireLease(kv, 'tab-3', 3_000)).toBe(false);
    expect(await acquireLease(kv, 'tab-3', 2_000 + 61_000)).toBe(true); // caducó
    await releaseLease(kv, 'tab-3');
    expect(await acquireLease(kv, 'tab-4', 3_000)).toBe(true);
  });
});
