import { createContext, useContext, useSyncExternalStore, type ReactNode } from 'react';
import type { Runtime, SyncSnapshot } from './runtime';
import type { Snapshot } from './session';

const RuntimeContext = createContext<Runtime | null>(null);
export const RuntimeProvider = ({ runtime, children }: { runtime: Runtime; children: ReactNode }) => <RuntimeContext.Provider value={runtime}>{children}</RuntimeContext.Provider>;

export function useRuntime(): Runtime {
  const runtime = useContext(RuntimeContext);
  if (!runtime) throw new Error('RuntimeProvider ausente');
  return runtime;
}
export function useSession(): Snapshot {
  const { session } = useRuntime();
  return useSyncExternalStore(session.subscribe, session.getSnapshot);
}
export function useSyncState(): SyncSnapshot {
  const runtime = useRuntime();
  return useSyncExternalStore(runtime.subscribe, runtime.getSnapshot);
}
