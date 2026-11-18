import { describe, expect, it, vi } from 'vitest';
import { Runtime } from '../app/runtime';
import { SessionManager } from '../app/session';
import { MODULES } from '../modules';
import { supportedContracts } from '../modules/registry';
import { memorySecureStore } from './secureStore';
import { memoryKv } from '../shared/storage';
import { FakeSteps } from '../testing/fakeServer';
import { setWatchEnabled, startWatchCompanion, watchEnabled, watchSnapshot, type WatchBridge, type WatchSnapshot } from './watch';

async function fixture() {
  const server = new FakeSteps(), kv = memoryKv();
  server.now = Date.now();
  const person = server.addPerson('watch@example.test', 'clave-segura-2026', 'Persona');
  server.grant(person.id, 'org-a', ['colaciones', 'operador']);
  const session = new SessionManager({ kv, secure: memorySecureStore(), device: async () => ({ uuid: 'watch-phone', platform: 'ios', app_version: 't' }), supported: supportedContracts(MODULES), fetchImpl: server.fetch, baseUrl: 'https://fake.test/steps_app/v1', now: () => server.now });
  const runtime = new Runtime(session, kv, MODULES);
  await session.boot(); await session.login('watch@example.test', 'clave-segura-2026');
  return { server, kv, person, session, runtime };
}

describe('Watch context isolation', () => {
  it('sharing is off by default and requires a verified preference write', async () => {
    const { runtime, kv } = await fixture();
    expect(await watchEnabled(runtime)).toBe(false);
    expect(watchSnapshot(runtime, false).state).toBe('locked');
    kv.failWrites((key) => key.startsWith('steps.watch.'));
    await expect(setWatchEnabled(runtime, true)).rejects.toThrow('guardar');
    expect(await watchEnabled(runtime)).toBe(false);
  });
  it('only shares authorized modules, with no identity, tokens, passenger data or coordinates', async () => {
    const { runtime, server } = await fixture();
    const s = watchSnapshot(runtime, true, server.now);
    expect(s.state).toBe('ready');
    expect(s.modules.map((m) => m.id)).toEqual(['colaciones']);
    expect(s.validUntil).toBeLessThanOrEqual(server.now + 300_000);
    expect(JSON.stringify(s)).not.toMatch(/access_token|refresh_token|email|latitude|passenger|clave/);
  });
  it('locks expired authorization and an in-progress company switch', async () => {
    const { runtime, session, server } = await fixture();
    const until = Date.parse(session.getSnapshot().catalog!.offline_until);
    expect(watchSnapshot(runtime, true, until + 1).state).toBe('locked');
    server.grant(session.personId!, 'org-b', ['mobilization', 'conductor']);
    const switching = session.selectOrg('org-b');
    expect(watchSnapshot(runtime, true, server.now).state).toBe('locked');
    await switching;
    expect(watchSnapshot(runtime, true, server.now).modules.map((m) => m.id)).toEqual(['mobilization']);
  });
  it('serializes a slow publish before the subsequent logout clears the watch', async () => {
    const { runtime, session } = await fixture();
    await setWatchEnabled(runtime, true);
    const sent: WatchSnapshot[] = [];
    let release!: () => void;
    const slow = new Promise<void>((r) => { release = r; });
    const native: WatchBridge = { publish: async ({ snapshot }) => { sent.push(snapshot); if (sent.length === 1) await slow; }, addListener: async () => ({ remove: async () => {} }) };
    const stop = startWatchCompanion(runtime, () => {}, native);
    try {
      await vi.waitFor(() => expect(sent[0]?.state).toBe('ready'));
      await session.logout(); release();
      await vi.waitFor(() => expect(sent.at(-1)?.state).toBe('locked'));
      expect(sent.at(-1)?.modules).toEqual([]);
    } finally { release(); stop(); }
  });
  it('reads current-company counts even when the phone display still has old-company counts', async () => {
    const { runtime, session, server } = await fixture();
    await setWatchEnabled(runtime, true);
    await runtime.queue()!.enqueue({ module: 'colaciones', kind: 'register', group: 'a', payload: {} });
    await runtime.refresh();
    expect(runtime.getSnapshot().pending).toBe(1);
    server.grant(session.personId!, 'org-b', ['mobilization', 'conductor']);
    await session.selectOrg('org-b');
    const sent: WatchSnapshot[] = [];
    const stop = startWatchCompanion(runtime, () => {}, { publish: async ({ snapshot }) => { sent.push(snapshot); }, addListener: async () => ({ remove: async () => {} }) });
    try { await vi.waitFor(() => expect(sent.at(-1)?.state).toBe('ready')); expect(sent.at(-1)?.pending).toBe(0); }
    finally { stop(); }
  });
  it('rejects navigation from another account/company or a disabled module', async () => {
    const { runtime } = await fixture();
    await setWatchEnabled(runtime, true);
    let receive!: (event: { module: string; scope: string }) => void;
    const open = vi.fn();
    const stop = startWatchCompanion(runtime, open, { publish: async () => {}, addListener: async (_, fn) => { receive = fn; return { remove: async () => {} }; } });
    try {
      await vi.waitFor(() => expect(receive).toBeTypeOf('function'));
      const scope = watchSnapshot(runtime, true).scope;
      receive({ module: 'colaciones', scope: 'another-account' });
      receive({ module: 'tracker', scope });
      receive({ module: 'colaciones', scope });
      await vi.waitFor(() => expect(open).toHaveBeenCalledExactlyOnceWith('colaciones'));
      await setWatchEnabled(runtime, false);
      receive({ module: 'colaciones', scope });
      await new Promise((r) => setTimeout(r, 10));
      expect(open).toHaveBeenCalledTimes(1);
    } finally { stop(); }
  });
  it('sharing consent does not transfer to another person', async () => {
    const { runtime, session, server } = await fixture();
    await setWatchEnabled(runtime, true);
    server.addPerson('other@example.test', 'clave-segura-2026', 'Otra persona');
    await session.logout(); await session.login('other@example.test', 'clave-segura-2026');
    expect(await watchEnabled(runtime)).toBe(false);
    expect(watchSnapshot(runtime, await watchEnabled(runtime)).state).toBe('locked');
  });
});
