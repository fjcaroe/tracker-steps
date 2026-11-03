import { Capacitor, registerPlugin, type PluginListenerHandle } from '@capacitor/core';
import type { Runtime } from '../app/runtime';
import { visibleModules } from '../modules/registry';
import { StorageError } from '../shared/storage';

export type WatchSnapshot = {
  version: 1; issuedAt: number; validUntil: number; scope: string;
  state: 'ready' | 'locked'; company: string; demo: boolean;
  modules: { id: string; name: string }[];
  pending: number; problems: number; syncing: boolean;
};
export interface WatchBridge {
  publish(options: { snapshot: WatchSnapshot }): Promise<void>;
  addListener(event: 'openModule', listener: (event: { module: string; scope: string }) => void): Promise<PluginListenerHandle>;
}
const bridge = registerPlugin<WatchBridge>('StepsWatch');
export const watchAvailable = () => Capacitor.getPlatform() === 'ios';
const preferenceKey = (id: number) => `steps.watch.enabled.v1.${id}`;

export async function watchEnabled(runtime: Runtime): Promise<boolean> {
  const id = runtime.session.personId;
  return id !== null && (await runtime.kv.get(preferenceKey(id))) === 'yes';
}
export async function setWatchEnabled(runtime: Runtime, enabled: boolean): Promise<void> {
  const id = runtime.session.personId;
  if (id === null) throw new Error('Inicia sesión antes de asociar el reloj.');
  if (!(await runtime.kv.set(preferenceKey(id), enabled ? 'yes' : 'no'))) throw new StorageError();
  // This notification also republishes the context after opting out.
  await runtime.refresh();
}

/** Only an allowlist of presentation data crosses to the watch, never credentials or passenger data. */
export function watchSnapshot(runtime: Runtime, enabled: boolean, now = Date.now(), counts = { pending: 0, problems: 0, syncing: false }): WatchSnapshot {
  const s = runtime.session.getSnapshot();
  const locked: WatchSnapshot = { version: 1, issuedAt: now, validUntil: now, scope: '', state: 'locked', company: '', demo: runtime.demo, modules: [], pending: 0, problems: 0, syncing: false };
  if (!enabled || s.status !== 'signed_in' || !s.me || !s.orgUid || !s.catalog || s.catalog.organization.org_uid !== s.orgUid || s.access === 'offline_expired') return locked;
  const expires = Date.parse(s.catalog.offline_until);
  if (!Number.isFinite(expires) || expires <= now) return locked;
  return { ...locked, validUntil: Math.min(now + 5 * 60_000, expires), scope: `${s.me.person.id}:${s.orgUid}`, state: 'ready', company: s.catalog.organization.name,
    modules: visibleModules(runtime.manifests, s.catalog).map(({ manifest }) => ({ id: manifest.id, name: manifest.name })),
    ...counts };
}

/** Serialized publishing: a slow old request cannot overwrite a later logout or company switch. */
export function startWatchCompanion(runtime: Runtime, onOpen: (module: string) => void, native: WatchBridge = bridge): () => void {
  let stopped = false, dirty = false, running = false;
  let listener: PluginListenerHandle | undefined;
  const request = () => {
    dirty = true;
    if (running || stopped) return;
    running = true;
    void (async () => {
      try {
        while (dirty && !stopped) {
          dirty = false;
          const scope = JSON.stringify(runtime.session.scope());
          const enabled = await watchEnabled(runtime);
          // Read the active queue directly: Runtime's displayed counts may still belong to the previous company.
          const counts = await runtime.queue()?.counts();
          if (scope !== JSON.stringify(runtime.session.scope())) { dirty = true; continue; }
          if (!stopped) await native.publish({ snapshot: watchSnapshot(runtime, enabled, Date.now(), counts ? { pending: counts.pending, problems: counts.rejected + counts.authRequired + counts.blocked, syncing: runtime.getSnapshot().syncing } : undefined) });
        }
      } catch { /* Native connectivity failure must never interrupt phone capture/sync. The next event retries. */ }
      finally { running = false; }
    })();
  };
  const offSession = runtime.session.subscribe(request), offSync = runtime.subscribe(request);
  const timer = setInterval(request, 60_000);
  void native.addListener('openModule', (event) => {
    void (async () => {
      const current = watchSnapshot(runtime, await watchEnabled(runtime));
      if (!stopped && current.state === 'ready' && event.scope === current.scope && current.modules.some((m) => m.id === event.module)) onOpen(event.module);
    })().catch(() => undefined);
  }).then((handle) => { if (stopped) void handle.remove(); else listener = handle; }).catch(() => undefined);
  request();
  return () => { stopped = true; offSession(); offSync(); clearInterval(timer); void listener?.remove(); };
}
