// Runtime de la app unificada: une sesión, colas durables y envío. Sin React.
import type { KeyValueStore } from '../shared/storage';
import { foreignQueues, DurableQueue, type QueueOp, type Scope } from '../sync/queue';
import { runQueue, type Handler, type RunSummary } from '../sync/engine';
import type { ModuleManifest } from '../modules/registry';
import type { SessionManager } from './session';

export type SyncSnapshot = {
  pending: number; rejected: number; authRequired: number; syncing: boolean;
  lastSyncAt: string | null; lastHalt: RunSummary['halted'];
  /** Colas de otras cuentas/empresas guardadas en este teléfono (no se envían con esta sesión). */
  foreign: { scope: Scope; pending: number; rejected: number }[];
  /** Cambia con cada modificación de las colas: las pantallas lo usan para releer. */
  version: number;
};

const EMPTY: SyncSnapshot = { pending: 0, rejected: 0, authRequired: 0, syncing: false, lastSyncAt: null, lastHalt: null, foreign: [], version: 0 };

export class Runtime {
  private snap: SyncSnapshot = EMPTY;
  private listeners = new Set<() => void>();
  private running: Promise<RunSummary | null> | null = null;
  private again = false;
  private timer: ReturnType<typeof setInterval> | null = null;
  private teardown: (() => void) | null = null;

  constructor(readonly session: SessionManager, readonly kv: KeyValueStore, readonly manifests: ModuleManifest[]) {}

  getSnapshot = () => this.snap;
  subscribe = (fn: () => void) => { this.listeners.add(fn); return () => { this.listeners.delete(fn); }; };

  queue(): DurableQueue | null { const scope = this.session.scope(); return scope ? new DurableQueue(this.kv, scope) : null; }

  /** Handlers atados al ámbito (persona + empresa) de la cola que se envía, no a la empresa «actual» de la pantalla. */
  private handlers(scope: Scope): Record<string, Handler> {
    const api = this.session.api.scoped(scope);
    return Object.assign({}, ...this.manifests.map((m) => m.handlers?.(api) ?? {}));
  }

  /** Persiste la operación. Lanza si no quedó guardada: la interfaz nunca debe anunciar éxito antes. */
  async enqueue<P>(input: { module: string; kind: string; group: string; payload: P; id?: string }): Promise<QueueOp<P>> {
    const queue = this.queue();
    if (!queue) throw new Error('No hay empresa activa.');
    const op = await queue.enqueue(input);
    await this.refresh();
    void this.sync();
    return op;
  }

  async ops(module?: string): Promise<QueueOp[]> {
    const all = (await this.queue()?.list()) ?? [];
    return module ? all.filter((o) => o.module === module) : all;
  }

  async refresh(patch: Partial<SyncSnapshot> = {}): Promise<void> {
    const queue = this.queue();
    const counts = queue ? await queue.counts() : { pending: 0, rejected: 0, authRequired: 0 };
    const foreign = await foreignQueues(this.kv, this.session.scope());
    this.snap = { ...this.snap, ...patch, pending: counts.pending, rejected: counts.rejected, authRequired: counts.authRequired, foreign, version: this.snap.version + 1 };
    this.listeners.forEach((l) => l());
  }

  /**
   * Envío de un solo vuelo. Si se pide mientras hay uno en curso, se encadena otra pasada al terminar:
   * lo encolado o reintentado durante el envío nunca queda esperando al temporizador.
   */
  sync(): Promise<RunSummary | null> {
    if (this.running) { this.again = true; return this.running; }
    if (!this.queue()) { void this.refresh(); return Promise.resolve(null); }
    this.running = (async () => {
      let summary: RunSummary | null = null;
      try {
        do {
          this.again = false;
          const queue = this.queue();
          if (!queue) break;
          await queue.requeueSessionBlocked(); // volver a entrar reanuda lo que esperaba sesión; el resto lo decide la persona
          await this.refresh({ syncing: true });
          try {
            summary = await runQueue({ queue, handlers: this.handlers(queue.scope), sessionPersonId: this.session.personId });
          } finally {
            await this.refresh({ syncing: false, lastHalt: summary?.halted ?? null, lastSyncAt: summary && summary.confirmed ? new Date().toISOString() : this.snap.lastSyncAt });
            await queue.prune();
          }
        } while (this.again);
      } finally { this.running = null; }
      return summary;
    })();
    return this.running;
  }

  async retry(ids?: string[]): Promise<RunSummary | null> {
    await this.queue()?.requeue(ids);
    return this.sync();
  }

  /** Eventos que reintentan solos: volver la señal, volver a primer plano, y un temporizador de respaldo. */
  start(target: { addEventListener: Window['addEventListener']; removeEventListener: Window['removeEventListener'] } = window): void {
    if (this.timer) return;
    const online = () => { void this.session.revalidate().then(() => this.sync()); };
    const visible = () => { if (typeof document === 'undefined' || document.visibilityState === 'visible') online(); };
    target.addEventListener('online', online);
    if (typeof document !== 'undefined') document.addEventListener('visibilitychange', visible);
    this.timer = setInterval(() => { if (this.snap.pending) void this.sync(); }, 20_000);
    this.teardown = () => { target.removeEventListener('online', online); if (typeof document !== 'undefined') document.removeEventListener('visibilitychange', visible); };
    void this.refresh();
  }

  stop(): void { if (this.timer) clearInterval(this.timer); this.timer = null; this.teardown?.(); this.teardown = null; }
}
