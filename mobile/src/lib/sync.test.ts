import { beforeEach, describe, expect, it, vi } from 'vitest';
import { activeStore, pointQueue } from './queue';
import { outboxStore, pendingTotal, syncAll } from './sync';

const handlers = vi.hoisted(() => ({
  api: vi.fn(), createWorkOrder: vi.fn(), start: vi.fn(), points: vi.fn(), close: vi.fn(), finishWorkOrder: vi.fn(), heartbeat: vi.fn(),
}));
vi.mock('./api', () => ({ api: handlers.api, APP_VERSION: 'test', sessions: handlers, mobile: { heartbeat: handlers.heartbeat } }));

beforeEach(() => {
  const storage = new Map<string, string>();
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => storage.get(k) ?? null,
    setItem: (k: string, v: string) => storage.set(k, v),
    removeItem: (k: string) => storage.delete(k),
  });
  for (const fn of Object.values(handlers)) fn.mockReset().mockResolvedValue({});
});

describe('sincronización de jornadas', () => {
  it('conserva un registro agregado mientras hay una petición en vuelo', async () => {
    let release!: () => void;
    handlers.api.mockImplementationOnce(() => new Promise<void>((r) => { release = r; }));
    outboxStore.add({ kind: 'post', sessionId: 'a', path: 'incidents', body: { id: 'first' } });
    const pending = syncAll();
    outboxStore.add({ kind: 'post', sessionId: 'a', path: 'expenses', body: { id: 'second' } });
    release();
    await pending;
    expect(outboxStore.ops()).toHaveLength(1);
    expect(outboxStore.ops()[0]).toMatchObject({ body: { id: 'second' } });
    await syncAll();
    expect(outboxStore.ops()).toEqual([]);
    expect(handlers.api).toHaveBeenCalledTimes(2);
  });

  it('envía puntos pendientes aunque la jornada ya no esté activa en pantalla', async () => {
    activeStore.set(null);
    pointQueue.push('closed', { ts: '2026-10-03T12:00:00Z', lat: -35, lon: -71, speed_mps: null, accuracy_m: 5 });
    await syncAll();
    expect(handlers.points).toHaveBeenCalledWith('closed', expect.any(Array));
    expect(pointQueue.size('closed')).toBe(0);
  });

  it('no pierde los valores finales si falla el parte después de cerrar la sesión', async () => {
    handlers.finishWorkOrder.mockRejectedValueOnce(Object.assign(new Error('offline'), { status: 0 }));
    outboxStore.add(
      { kind: 'session_close', sessionId: 'a', endedAt: '2026-10-03T13:00:00Z' },
      { kind: 'wo_finish', sessionId: 'a', workOrderId: 5, body: { hourmeter_final: 12, fuel_tank_end_liters: 30, fuel_refill_liters: null } },
    );
    await syncAll();
    expect(outboxStore.ops()).toHaveLength(1);
    expect(outboxStore.ops()[0]).toMatchObject({ kind: 'wo_finish', body: { hourmeter_final: 12 } });
    await syncAll();
    expect(outboxStore.ops()).toEqual([]);
    expect(handlers.close).toHaveBeenCalledTimes(1);
  });

  it('un rechazo permanente de los puntos no bloquea el cierre ni las demás jornadas', async () => {
    // Otro dispositivo o un supervisor ya cerró la jornada "a": el servidor responde 400 a sus puntos.
    handlers.points.mockImplementation(async (id: string) => { if (id === 'a') throw Object.assign(new Error('Session is closed; no more points can be recorded.'), { status: 400 }); return {}; });
    pointQueue.push('a', { ts: '2026-10-03T12:00:00Z', lat: -35, lon: -71, speed_mps: null, accuracy_m: 5 });
    outboxStore.add(
      { kind: 'session_close', sessionId: 'a', endedAt: '2026-10-03T13:00:00Z' },
      { kind: 'wo_finish', sessionId: 'a', workOrderId: 5, body: { hourmeter_final: 12, fuel_tank_end_liters: 30, fuel_refill_liters: null } },
      { kind: 'post', sessionId: 'b', path: 'incidents', body: { id: 'inc-b' } },
    );
    await syncAll();
    expect(handlers.close).toHaveBeenCalledWith('a', '2026-10-03T13:00:00Z');
    expect(handlers.finishWorkOrder).toHaveBeenCalledWith(5, expect.objectContaining({ hourmeter_final: 12 }));
    expect(handlers.api).toHaveBeenCalledTimes(1);
    expect(outboxStore.ops()).toEqual([]);
    // Los puntos no se descartan: quedan guardados aparte y ya no cuentan como pendientes.
    expect(pointQueue.size('a')).toBe(0);
    expect(pointQueue.rejected()['a']).toHaveLength(1);
    expect(pendingTotal()).toBe(0);
  });

  it('un corte de red al enviar puntos sí los conserva como pendientes', async () => {
    handlers.points.mockRejectedValue(Object.assign(new Error('offline'), { status: 0 }));
    pointQueue.push('a', { ts: '2026-10-03T12:00:00Z', lat: -35, lon: -71, speed_mps: null, accuracy_m: 5 });
    outboxStore.add({ kind: 'session_close', sessionId: 'a', endedAt: '2026-10-03T13:00:00Z' });
    await syncAll();
    expect(handlers.close).not.toHaveBeenCalled();
    expect(outboxStore.ops()).toHaveLength(1);
    expect(pointQueue.size('a')).toBe(1);
    expect(pointQueue.rejected()).toEqual({});
  });
});
