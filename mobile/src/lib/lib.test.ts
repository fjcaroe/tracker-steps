import { beforeEach, describe, expect, it } from 'vitest';
import { acceptFix, haversineMeters, type Fix } from './geo';
import { formatDuration, parseNumber, pointQueue, syncStore, type Active } from './queue';
import { buildActive, reconcile } from './reconcile';
import type { SessionSummary } from './api';

const store = new Map<string, string>();
beforeEach(() => {
  store.clear();
  (globalThis as { localStorage?: unknown }).localStorage = {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
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
