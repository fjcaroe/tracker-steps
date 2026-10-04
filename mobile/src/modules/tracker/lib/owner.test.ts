import { beforeEach, describe, expect, it } from 'vitest';
import { claimLocalData, exportLocalData, ownerState, ownerStore } from './owner';
import { pointQueue } from './queue';
import { outboxStore, setSyncGate, syncAll } from './sync';

const store = new Map<string, string>();
beforeEach(() => {
  store.clear(); setSyncGate(() => true);
  (globalThis as { localStorage?: unknown }).localStorage = {
    getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v), removeItem: (k: string) => void store.delete(k),
    key: (i: number) => [...store.keys()][i] ?? null, get length() { return store.size; },
  };
});
const ana = { id: 1, full_name: 'Ana' }, beto = { id: 2, full_name: 'Beto' };
const point = { ts: '2026-10-03T12:00:00Z', lat: -35, lon: -71, speed_mps: null, accuracy_m: 5 };

describe('propietario de los datos locales del Tracker', () => {
  it('sin datos locales, quien entra pasa a ser el dueño', () => {
    expect(ownerState(ana)).toEqual({ kind: 'ok' });
    expect(ownerStore.get()).toEqual({ userId: 1, name: 'Ana' });
  });
  it('datos de una versión anterior (sin dueño) NO se atribuyen solos: se pide confirmación', () => {
    pointQueue.push('s1', point);
    expect(ownerState(ana)).toEqual({ kind: 'claim' });
    expect(ownerStore.get()).toBeNull();
    expect(claimLocalData(ana)).toBe(true);
    expect(ownerState(ana)).toEqual({ kind: 'ok' });
  });
  it('datos pendientes de otra cuenta se bloquean y se identifica al dueño', () => {
    pointQueue.push('s1', point); claimLocalData(ana);
    expect(ownerState(beto)).toEqual({ kind: 'foreign', owner: { userId: 1, name: 'Ana' } });
    expect(pointQueue.size('s1')).toBe(1); // nada se borra
  });
  it('mientras la compuerta esté cerrada no se envía nada con la sesión equivocada', async () => {
    outboxStore.add({ kind: 'session_close', sessionId: 'a', endedAt: '2026-10-03T13:00:00Z' });
    setSyncGate(() => false);
    expect(await syncAll()).toBe(0);
    expect(outboxStore.ops()).toHaveLength(1);
  });
  it('la copia de recuperación incluye los datos y excluye la credencial', () => {
    pointQueue.push('s1', point); store.set('steps_movil_token', 'secreto');
    const out = JSON.parse(exportLocalData());
    expect(out.data.steps_movil_pending.s1).toHaveLength(1);
    expect(JSON.stringify(out)).not.toContain('secreto');
  });
});
