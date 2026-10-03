import { beforeEach, describe, expect, it } from 'vitest';
import { acceptFix, haversineMeters, type Fix } from './geo';
import { activeFromServer, reconcile } from './reconcile';
import type { SessionSummary } from './api';
import { formatDuration, lastSentStore, parseNumber, pointQueue } from './queue';

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

describe('reconciliación con el servidor', () => {
  const srv = (id: string): SessionSummary => ({ id, machine_id: 3, started_at: '2026-10-03T12:00:00Z', ended_at: null, status: 'open', machine_name: 'Tractor 1', driver_name: null, cost_center_name: null, points_count: 0, work_order_id: 9 });
  const local = { sessionId: 'a', workOrderId: 9, machineId: 3, machineName: 'T', startedAt: 0, hourmeterStart: 1, tankStart: 2, tankCapacity: null, distanceM: 0 };
  it('mantiene, limpia u ofrece según el servidor', () => {
    expect(reconcile(local, [srv('a')]).action).toBe('keep');
    expect(reconcile(local, [srv('b')]).action).toBe('clear');
    expect(reconcile(local, []).action).toBe('clear');
    expect(reconcile(null, [srv('b')])).toEqual({ action: 'offer', sessions: [srv('b')] });
    expect(reconcile(null, []).action).toBe('none');
  });
  it('reconstruye la jornada con el reloj real', () => {
    const a = activeFromServer(srv('a'), { id: 9, hourmeter_initial: 100, fuel_tank_start_liters: 50 }, undefined);
    expect(a?.startedAt).toBe(Date.parse('2026-10-03T12:00:00Z'));
    expect(a?.hourmeterStart).toBe(100);
    expect(activeFromServer(srv('a'), undefined, undefined)).toBeNull();
  });
});

describe('último envío', () => {
  it('se registra al enviar puntos', async () => {
    pointQueue.push('s1', point(1));
    await pointQueue.flush('s1', async () => {});
    expect(lastSentStore.get()).toBeGreaterThan(0);
  });
});
