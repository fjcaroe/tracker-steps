import { IDBFactory } from 'fake-indexeddb';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { api, ApiError } from './api';
import { findPassenger, passengerStore, project, syncPassengers } from './passengers';
import { manifestFixture as fixture } from './passengers.fixture';
vi.mock('./api', async (original) => ({ ...await original<typeof import('./api')>(), api: vi.fn() }));
beforeEach(() => { vi.stubGlobal('indexedDB', new IDBFactory()); });
afterEach(() => { vi.unstubAllGlobals(); vi.resetAllMocks(); vi.useRealTimers(); });

it('durably orders a complete offline service and retries a lost receipt with identical UUID and payload', async () => {
  await passengerStore.prepare(2, fixture);
  for (const [id, kind] of [['1', 'boarded'], ['2', 'boarded'], ['3', 'no_show'], ['1', 'alighted'], ['2', 'alighted']] as const) await passengerStore.enqueue(2, fixture.id, id, kind);
  const [before] = await passengerStore.read(2);
  expect(project(before)?.occupied).toBe(0);
  expect(before.queue.map((e) => e.expected_version)).toEqual([0, 1, 2, 3, 4]);
  vi.mocked(api).mockRejectedValueOnce(new ApiError('Sin conexión', 0));
  await expect(syncPassengers(2)).rejects.toThrow();
  expect((await passengerStore.read(2))[0].queue).toEqual(before.queue);
  const server = structuredClone(fixture);
  vi.mocked(api).mockImplementation(async (_path, init) => {
    const value = JSON.parse(init!.body as string);
    server.events.push(value); server.manifest_version++;
    server.passengers.find((p) => p.id === value.passenger_id)!.state = value.kind;
    server.occupied = server.passengers.filter((p) => p.state === 'boarded').length;
    return structuredClone(server) as never;
  });
  await Promise.all([syncPassengers(2), syncPassengers(2)]);
  const [after] = await passengerStore.read(2);
  expect(after.queue).toEqual([]); expect(project(after)?.occupied).toBe(0);
  expect(server.events.map((e) => e.id)).toEqual(before.queue.map((e) => e.id));
  expect(api).toHaveBeenCalledTimes(6);
});

it('serializes two tabs and enforces current occupancy, transitions and seats before persisting', async () => {
  await passengerStore.prepare(2, { ...fixture, capacity: 1 });
  const result = await Promise.allSettled([passengerStore.enqueue(2, fixture.id, '1', 'boarded'), passengerStore.enqueue(2, fixture.id, '2', 'boarded')]);
  expect(result.filter((r) => r.status === 'fulfilled')).toHaveLength(1);
  await expect(passengerStore.enqueue(2, fixture.id, '1', 'boarded')).rejects.toThrow();
  await expect(passengerStore.enqueue(2, fixture.id, '2', 'alighted')).rejects.toThrow();
  expect((await passengerStore.read(2))[0].queue).toHaveLength(1);
});

it('never exposes another account, expires personal data, and preserves anonymous pending events on logout', async () => {
  await passengerStore.prepare(2, fixture); await passengerStore.enqueue(2, fixture.id, '1', 'boarded');
  expect(await passengerStore.read(3)).toEqual([]);
  await passengerStore.forget(2);
  let [row] = await passengerStore.read(2);
  expect(row.base).toBeNull(); expect(row.queue).toHaveLength(1);
  expect(JSON.stringify(row)).not.toContain('TEST-');
  await passengerStore.prepare(3, fixture);
  vi.spyOn(Date, 'now').mockReturnValue(Date.now() + 25 * 3600_000);
  [row] = await passengerStore.read(3); expect(row.base).toBeNull();
  await expect(passengerStore.enqueue(3, fixture.id, '1', 'boarded')).rejects.toThrow();
});

it('keeps a conflict intact and removes cached personal information after permission revocation', async () => {
  await passengerStore.prepare(2, fixture); await passengerStore.enqueue(2, fixture.id, '1', 'boarded');
  vi.mocked(api).mockRejectedValueOnce(new ApiError('Conflicto', 409));
  await expect(syncPassengers(2)).rejects.toThrow();
  expect((await passengerStore.read(2))[0].base).not.toBeNull();
  vi.mocked(api).mockRejectedValueOnce(new ApiError('Permiso retirado', 403));
  await expect(syncPassengers(2)).rejects.toThrow();
  expect((await passengerStore.read(2))[0].base).toBeNull();
  expect((await passengerStore.read(2))[0].queue).toHaveLength(1);
});

it('accepts only codes from this manifest without treating a RUT or arbitrary URL as identity', () => {
  expect(findPassenger(fixture, 'steps:passenger:1')).toBe('1');
  expect(findPassenger(fixture, 'TEST-1')).toBeNull();
  expect(findPassenger(fixture, 'https://example.org/1')).toBeNull();
});

it('requires explicit reconciliation of a stale revision and preserves contradictory events for review', async () => {
  await passengerStore.prepare(2, fixture); await passengerStore.enqueue(2, fixture.id, '1', 'boarded');
  const otherPhone = structuredClone(fixture);
  otherPhone.events = [{ id: 'other-phone', passenger_id: '2', kind: 'no_show', occurred_at: new Date().toISOString() }];
  otherPhone.manifest_version = 1; otherPhone.passengers[1].state = 'no_show';
  await passengerStore.reconcile(2, otherPhone);
  expect((await passengerStore.read(2))[0].queue[0].expected_version).toBe(1);
  otherPhone.passengers[0].state = 'alighted';
  await expect(passengerStore.reconcile(2, otherPhone)).rejects.toThrow('contradice');
  expect((await passengerStore.read(2))[0].queue).toHaveLength(1);
});
