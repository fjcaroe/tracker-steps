import { describe, expect, it } from 'vitest';
import { runOutbox, startPending, type Handlers, type Op } from './outbox';

const body = { machine_id: 1, driver_id: null, cost_center_id: 1 };
const wo = { code: 'c', work_date: '2026-10-02', season: '2026', machine_id: 1, activity_id: 1, labor_id: 1, cost_center_id: 1, field_id: null, implement_id: null, hourmeter_initial: 0, fuel_tank_start_liters: 0 };
const net = () => Object.assign(new Error('Sin conexión'), { status: 0 });
const full = (): Op[] => [
  { kind: 'wo_create', sessionId: 's1', body: wo },
  { kind: 'session_start', sessionId: 's1', body, startedAt: 't0' },
  { kind: 'session_close', sessionId: 's1', endedAt: 't1' },
  { kind: 'wo_finish', sessionId: 's1', body: { hourmeter_final: 1, fuel_refill_liters: null, fuel_tank_end_liters: 5 } },
];
function handlers(log: string[], over: Partial<Handlers> = {}): Handlers {
  return {
    createWorkOrder: async () => { log.push('wo'); return { id: 77 }; },
    startSession: async (_id, woId) => { log.push(`start:${woId}`); },
    flushPoints: async () => { log.push('points'); return true; },
    closeSession: async () => { log.push('close'); },
    finishWorkOrder: async (id) => { log.push(`finish:${id}`); },
    ...over,
  };
}

describe('outbox', () => {
  it('ejecuta en orden: parte, inicio, puntos, cierre, final; resuelve el id del parte', async () => {
    const log: string[] = [];
    const r = await runOutbox(full(), {}, handlers(log));
    expect(log).toEqual(['wo', 'start:77', 'points', 'close', 'finish:77']);
    expect(r.ops).toEqual([]);
    expect(r.done).toBe(4);
  });
  it('un corte de red conserva lo pendiente y reintenta sin duplicar lo ya hecho', async () => {
    const log: string[] = [];
    let first = true;
    const flaky = handlers(log, { startSession: async () => { if (first) { first = false; throw net(); } log.push('start:ok'); } });
    const a = await runOutbox(full(), {}, flaky);
    expect(a.ops.map((o) => o.kind)).toEqual(['session_start', 'session_close', 'wo_finish']);
    expect(a.resolved.s1).toBe(77);
    const b = await runOutbox(a.ops, a.resolved, flaky);
    expect(b.ops).toEqual([]);
    expect(log.filter((x) => x === 'wo')).toHaveLength(1);
    expect(log).toContain('finish:77');
  });
  it('no cierra si quedan puntos GPS por enviar', async () => {
    const log: string[] = [];
    const r = await runOutbox(full().slice(2), { s1: 5 }, handlers(log, { flushPoints: async () => false }));
    expect(log).toEqual([]);
    expect(r.ops).toHaveLength(2);
  });
  it('un rechazo 4xx marca el error y bloquea solo esa jornada', async () => {
    const log: string[] = [];
    const other: Op = { kind: 'session_close', sessionId: 's2', endedAt: 't' };
    const bad = Object.assign(new Error('Máquina inactiva'), { status: 400 });
    const r = await runOutbox([...full(), other], {}, handlers(log, { createWorkOrder: async () => { throw bad; } }));
    expect(r.ops.find((o) => o.kind === 'wo_create')?.error).toBe('Máquina inactiva');
    expect(log).toEqual(['points', 'close']);
    expect(r.ops).toHaveLength(4);
  });
  it('startPending indica si la jornada aún no existe en el servidor', () => {
    expect(startPending(full(), 's1')).toBe(true);
    expect(startPending(full().slice(2), 's1')).toBe(false);
  });
});
