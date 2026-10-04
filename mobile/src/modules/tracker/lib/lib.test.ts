import { beforeEach, describe, expect, it } from 'vitest';
import { acceptFix, haversineMeters, type Fix } from './geo';
import { finishedStore, formatDuration, parseNumber, pointQueue, storageHealth, syncStore, type Active } from './queue';
import { buildActive, isStale, reconcile } from './reconcile';
import type { SessionSummary } from './api';

const store = new Map<string, string>();
/** Simula fallos de escritura (cuota llena o corte): `failing(key)` decide qué claves no se pueden guardar. */
let failing: (key: string) => boolean = () => false;
beforeEach(() => {
  store.clear();
  failing = () => false;
  (globalThis as { localStorage?: unknown }).localStorage = {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => { if (failing(k)) throw new DOMException('quota', 'QuotaExceededError'); store.set(k, v); },
    removeItem: (k: string) => void store.delete(k),
  };
});
const fix = (ts: number, lat: number, lon: number, accuracy_m: number | null = 5): Fix => ({ ts, lat, lon, speed_mps: null, accuracy_m });
const point = (n: number) => ({ ts: new Date(n * 1000).toISOString(), lat: -35, lon: -71, speed_mps: null, accuracy_m: 5 });

describe('geo', () => {
  it('mide distancia', () => { expect(Math.round(haversineMeters({ lat: 0, lon: 0 }, { lat: 0, lon: 0.001 }))).toBe(111); });
  it('descarta imprecisos y saltos imposibles', () => {
    expect(acceptFix(null, fix(0, -35, -71, 200))).toBe(false);
    expect(acceptFix(null, fix(0, -35, -71))).toBe(true);
    expect(acceptFix(fix(0, -35, -71), fix(1000, -35, -70))).toBe(false);
    expect(acceptFix(fix(0, -35, -71), fix(10_000, -35, -70.9999))).toBe(true);
    expect(acceptFix(fix(5000, -35, -71), fix(5000, -35, -71))).toBe(false);
  });
});

describe('cola de puntos', () => {
  it('envía por lotes y vacía la cola', async () => {
    for (let i = 0; i < 120; i++) pointQueue.push('s1', point(i));
    const sizes: number[] = [];
    expect(await pointQueue.flush('s1', async (p) => { sizes.push(p.length); })).toBe(120);
    expect(sizes).toEqual([50, 50, 20]);
    expect(pointQueue.size('s1')).toBe(0);
  });
  it('conserva lo pendiente si falla la red', async () => {
    for (let i = 0; i < 60; i++) pointQueue.push('s1', point(i));
    let calls = 0;
    const sent = await pointQueue.flush('s1', async () => { if (++calls === 2) throw new Error('offline'); });
    expect(sent).toBe(50);
    expect(pointQueue.size('s1')).toBe(10);
  });
});

describe('rechazos del servidor al enviar puntos', () => {
  const rejected = (status: number) => Object.assign(new Error(`HTTP ${status}`), { status });
  it('un rechazo permanente guarda el lote aparte y sigue con el resto', async () => {
    for (let i = 0; i < 60; i++) pointQueue.push('s1', point(i));
    let calls = 0;
    const sent = await pointQueue.flush('s1', async () => { if (++calls === 1) throw rejected(400); });
    expect(sent).toBe(10);
    expect(pointQueue.size('s1')).toBe(0);
    expect(pointQueue.rejected().s1).toHaveLength(50);
  });
  it.each([0, 401, 403, 408, 429, 500, 503])('el estado %i es transitorio: los puntos siguen pendientes', async (status) => {
    for (let i = 0; i < 3; i++) pointQueue.push('s1', point(i));
    expect(await pointQueue.flush('s1', async () => { throw rejected(status); })).toBe(0);
    expect(pointQueue.size('s1')).toBe(3);
    expect(pointQueue.rejected()).toEqual({});
  });
  it('no descarta puntos rechazados por ningún límite (5.001 puntos de una jornada)', async () => {
    store.set('steps_movil_pending', JSON.stringify({ s1: Array.from({ length: 5001 }, (_, i) => point(i)) }));
    await pointQueue.flush('s1', async () => { throw rejected(400); }, 500);
    expect(pointQueue.size('s1')).toBe(0);
    expect(pointQueue.rejected().s1).toHaveLength(5001);
    expect(pointQueue.rejected().s1[0].ts).toBe(point(0).ts);
  });
  it('si no se pueden guardar aparte (cuota llena) el lote sigue pendiente y no se pierde', async () => {
    for (let i = 0; i < 3; i++) pointQueue.push('s1', point(i));
    failing = (k) => k === 'steps_movil_points_rejected';
    await pointQueue.flush('s1', async () => { throw rejected(400); });
    expect(pointQueue.size('s1')).toBe(3);
    expect(pointQueue.rejectedTotal()).toBe(0);
    expect(storageHealth.hasProblem()).toBe(true);
    failing = () => false;
    // Con espacio otra vez, un segundo intento aparta el lote una sola vez.
    await pointQueue.flush('s1', async () => { throw rejected(400); });
    await pointQueue.flush('s1', async () => { throw rejected(400); });
    expect(pointQueue.size('s1')).toBe(0);
    expect(pointQueue.rejected().s1).toHaveLength(3);
    expect(storageHealth.hasProblem()).toBe(false);
  });
  it('un corte entre apartar y quitar de la cola duplica, nunca pierde ni cuenta dos veces', async () => {
    for (let i = 0; i < 2; i++) pointQueue.push('s1', point(i));
    let first = true;
    failing = (k) => { if (k === 'steps_movil_pending' && first) { first = false; return true; } return false; };
    await pointQueue.flush('s1', async () => { throw rejected(400); });
    await pointQueue.flush('s1', async () => { throw rejected(400); });
    expect(pointQueue.rejected().s1).toHaveLength(2);
  });
  it('devolver a la cola los puntos apartados permite reintentarlos', async () => {
    for (let i = 0; i < 2; i++) pointQueue.push('s1', point(i));
    await pointQueue.flush('s1', async () => { throw rejected(400); });
    expect(pointQueue.requeueRejected('s1')).toBe(2);
    expect(pointQueue.size('s1')).toBe(2);
    expect(pointQueue.rejectedTotal()).toBe(0);
    expect(await pointQueue.flush('s1', async () => {})).toBe(2);
  });
  it('la copia de exportación incluye todos los puntos apartados', async () => {
    pointQueue.push('s1', point(0));
    await pointQueue.flush('s1', async () => { throw rejected(422); });
    expect(JSON.parse(pointQueue.exportRejected()).points.s1).toHaveLength(1);
  });
});

describe('formato', () => {
  it('duración y números con coma', () => {
    expect(formatDuration(3_725_000)).toBe('01:02:05');
    expect(parseNumber('12,5')).toBe(12.5);
    expect(parseNumber('')).toBeNull();
  });
});

const remote = (id: string, status: 'open' | 'closed'): SessionSummary => ({
  id, machine_id: 7, started_at: '2026-10-02T12:00:00Z', ended_at: null, status, machine_name: 'Tractor 7', driver_name: null,
  cost_center_name: null, points_count: 3, work_order_id: 55, total_distance_m: 1200,
});
const local = (id: string): Active => ({ sessionId: id, workOrderId: 55, machineId: 7, machineName: 'Tractor 7', startedAt: 1, hourmeterStart: 10, tankStart: 20, tankCapacity: 100, distanceM: 0 });

describe('reconciliación con el servidor', () => {
  it('mantiene la jornada local si sigue abierta o el servidor no la conoce', () => {
    expect(reconcile(local('a'), [remote('a', 'open')])).toEqual({ kind: 'keep' });
    expect(reconcile(local('a'), [])).toEqual({ kind: 'keep' });
  });
  it('limpia la jornada local si el servidor ya la cerró', () => {
    expect(reconcile(local('a'), [remote('a', 'closed')])).toEqual({ kind: 'closed' });
  });
  it('no ofrece retomar una jornada que el teléfono ya terminó y aún está por cerrar en el servidor', () => {
    const r = reconcile(null, [remote('a', 'open'), remote('b', 'open')], new Set(['a']));
    expect(r.kind === 'choose' && r.candidates.map((c) => c.id)).toEqual(['b']);
    expect(reconcile(null, [remote('a', 'open')], new Set(['a']))).toEqual({ kind: 'keep' });
  });
  it('retira la jornada local que ya se terminó en el teléfono aunque el servidor la vea abierta', () => {
    expect(reconcile(local('a'), [remote('a', 'open')], new Set(['a']))).toEqual({ kind: 'finished' });
    expect(reconcile(local('a'), [], new Set(['a']))).toEqual({ kind: 'finished' });
    expect(reconcile(local('a'), [remote('a', 'open')], new Set(['otra']))).toEqual({ kind: 'keep' });
  });
  it('ofrece retomar jornadas abiertas cuando el teléfono no tiene ninguna', () => {
    const r = reconcile(null, [remote('a', 'open'), remote('b', 'closed')]);
    expect(r.kind).toBe('choose');
    expect(r.kind === 'choose' && r.candidates.map((c) => c.id)).toEqual(['a']);
    expect(reconcile(null, [remote('b', 'closed')])).toEqual({ kind: 'keep' });
  });
  it('reconstruye la jornada activa con el tiempo real del servidor', () => {
    const a = buildActive(remote('a', 'open'), { id: 55, hourmeter_initial: 120.5, fuel_tank_start_liters: 40 }, null);
    expect(a).toMatchObject({ sessionId: 'a', workOrderId: 55, hourmeterStart: 120.5, tankStart: 40, distanceM: 1200 });
    expect(a.startedAt).toBe(Date.parse('2026-10-02T12:00:00Z'));
  });
  it('no inventa horómetro y combustible si falta el parte original', () => {
    expect(() => buildActive(remote('a', 'open'), null, null)).toThrow('parte');
    expect(() => buildActive(remote('a', 'open'), { id: 99, hourmeter_initial: 1, fuel_tank_start_liters: 2 }, null)).toThrow('parte');
  });
});

describe('último envío', () => {
  it('se registra al enviar puntos y se conserva', async () => {
    expect(syncStore.get()).toBeNull();
    pointQueue.push('s1', point(1));
    await pointQueue.flush('s1', async () => {});
    expect(syncStore.get()).toBeGreaterThan(0);
  });
  it('clear descarta la cola de una jornada', () => {
    pointQueue.push('s1', point(1));
    pointQueue.clear('s1');
    expect(pointQueue.size('s1')).toBe(0);
  });
});

describe('respuestas atrasadas del servidor', () => {
  it('una jornada cerrada que ya consta en el historial no se vuelve a ofrecer aunque su cierre ya no esté en la cola', () => {
    finishedStore.add('a');
    const closing = new Set(finishedStore.ids());
    const r = reconcile(null, [remote('a', 'open')], closing);
    expect(r).toEqual({ kind: 'keep' });
  });
  it('el historial de jornadas terminadas no repite ni pierde identificadores', () => {
    finishedStore.add('a'); finishedStore.add('b'); finishedStore.add('a');
    expect(finishedStore.ids()).toEqual(['b', 'a']);
  });
  it('si la jornada local cambió mientras viajaba la consulta, la respuesta se descarta', () => {
    expect(isStale(local('a'), local('a'))).toBe(false);
    expect(isStale(local('a'), null)).toBe(true);
    expect(isStale(null, local('b'))).toBe(true);
    expect(isStale(null, null)).toBe(false);
  });
});
