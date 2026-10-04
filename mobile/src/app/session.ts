// Sesión personal: identidad → empresa activa → catálogo de módulos autorizados. Sin React: se prueba aislada.
import type { CatalogOut, DeviceInfo, MeOut, TokenPair } from '../shared/contracts';
import type { KeyValueStore } from '../shared/storage';
import { readJson, writeJson } from '../shared/storage';
import type { SecureStore } from '../platform/secureStore';
import { ApiError, createApi, type Api, type SessionTokens } from './api';
import { accessMode, mayStartProtectedAction, type AccessMode } from './offline';
import type { Scope } from '../sync/queue';

const TOKENS_KEY = 'steps.tokens.v1';
const CACHE_KEY = (personId: number) => `steps.session.v1.${personId}`;
const LAST_PERSON_KEY = 'steps.session.last_person.v1';

export type Status = 'booting' | 'signed_out' | 'signed_in';
export type Snapshot = {
  status: Status;
  me: MeOut | null;
  orgUid: string | null;
  catalog: CatalogOut | null;
  access: AccessMode;
  /** Mensaje para la persona (p. ej. sesión cerrada por el servidor). */
  notice: string | null;
  /** true cuando falta elegir empresa entre varias activas. */
  needsOrgChoice: boolean;
};
type Cache = { me: MeOut | null; orgUid: string | null; catalog: CatalogOut | null; validatedAt: string | null };

export type SessionDeps = {
  kv: KeyValueStore;
  secure: SecureStore;
  device: () => Promise<DeviceInfo>;
  /** Módulo -> versión de contrato que ESTA app entiende. */
  supported: Record<string, number>;
  fetchImpl?: typeof fetch;
  baseUrl?: string;
  now?: () => number;
};

export class SessionManager {
  private snap: Snapshot = { status: 'booting', me: null, orgUid: null, catalog: null, access: 'offline_expired', notice: null, needsOrgChoice: false };
  private listeners = new Set<() => void>();
  private tokens: SessionTokens | null = null;
  readonly api: Api;
  private now: () => number;

  constructor(private deps: SessionDeps) {
    this.now = deps.now ?? Date.now;
    this.api = createApi({
      baseUrl: deps.baseUrl, fetchImpl: deps.fetchImpl,
      tokens: () => this.tokens,
      setTokens: async (t) => { this.tokens = t; if (t) await deps.secure.set(TOKENS_KEY, JSON.stringify(t)); else await deps.secure.remove(TOKENS_KEY); },
      orgUid: () => this.snap.orgUid,
      onSignedOut: (reason) => void this.finishSignOut(reason === 'session_revoked' ? 'El administrador cerró tu sesión.' : 'Tu sesión expiró. Vuelve a entrar.'),
    });
  }

  // ---- Suscripción (useSyncExternalStore) ----
  getSnapshot = (): Snapshot => this.snap;
  subscribe = (fn: () => void) => { this.listeners.add(fn); return () => { this.listeners.delete(fn); }; };
  private set(patch: Partial<Snapshot>) { this.snap = { ...this.snap, ...patch }; this.listeners.forEach((l) => l()); }

  // ---- Derivados ----
  get personId(): number | null { return this.snap.me?.person.id ?? this.tokens?.personId ?? null; }
  scope(): Scope | null { return this.personId != null && this.snap.orgUid ? { personId: this.personId, orgUid: this.snap.orgUid } : null; }
  permissions(): Set<string> { return new Set(this.snap.catalog?.modules.flatMap((m) => m.permissions) ?? []); }
  /** ¿Puede iniciar una acción protegida con este permiso? Vencido el plazo sin conexión, no. */
  can(permission: string): boolean { return mayStartProtectedAction(this.snap.access) && this.permissions().has(permission); }

  // ---- Arranque ----
  async boot(): Promise<void> {
    const raw = await this.deps.secure.get(TOKENS_KEY);
    let tokens: SessionTokens | null = null;
    try { tokens = raw ? (JSON.parse(raw) as SessionTokens) : null; } catch { tokens = null; }
    if (!tokens) { this.set({ status: 'signed_out' }); return; }
    this.tokens = tokens;
    const cache = await readJson<Cache | null>(this.deps.kv, CACHE_KEY(tokens.personId), null);
    try {
      await this.loadMe();
      await this.chooseOrg(cache?.orgUid ?? null);
    } catch (e) {
      if (this.snap.status === 'signed_out') return; // el servidor cerró la sesión
      if (!(e instanceof ApiError) || e.status === 0 || e.status >= 500) { this.useCache(cache); return; }
      throw e;
    }
  }

  private useCache(cache: Cache | null) {
    const until = cache?.catalog?.offline_until ?? null;
    this.set({ status: 'signed_in', me: cache?.me ?? null, orgUid: cache?.orgUid ?? null, catalog: cache?.catalog ?? null,
      access: accessMode({ validatedOnline: false, offlineUntil: until, now: this.now() }), needsOrgChoice: false });
  }

  private async persistCache() {
    const personId = this.snap.me?.person.id;
    if (personId == null) return;
    try { await writeJson(this.deps.kv, CACHE_KEY(personId), { me: this.snap.me, orgUid: this.snap.orgUid, catalog: this.snap.catalog, validatedAt: new Date(this.now()).toISOString() } satisfies Cache); }
    catch { /* la caché solo acelera el arranque sin conexión */ }
  }

  private async loadMe() {
    const me = await this.api.me();
    this.set({ status: 'signed_in', me });
    await this.deps.kv.set(LAST_PERSON_KEY, String(me.person.id));
  }

  /** Elige la empresa activa: la guardada si sigue activa; la única activa; o pide elegir. */
  private async chooseOrg(preferred: string | null) {
    const active = (this.snap.me?.memberships ?? []).filter((m) => m.state === 'active');
    const pick = active.find((m) => m.org_uid === preferred) ?? (active.length === 1 ? active[0] : null);
    if (!pick) { this.set({ orgUid: null, catalog: null, access: 'online', needsOrgChoice: active.length > 1 }); await this.persistCache(); return; }
    await this.selectOrg(pick.org_uid);
  }

  /** Cambiar de empresa revalida permisos en el servidor; la cola de la otra empresa queda intacta. */
  async selectOrg(orgUid: string): Promise<void> {
    this.set({ orgUid, catalog: null, needsOrgChoice: false });
    await this.revalidate();
  }

  /** Vuelve a pedir permisos al servidor (al recuperar señal, al volver a primer plano o al cambiar de empresa). */
  async revalidate(): Promise<void> {
    if (!this.tokens) return;
    try {
      const me = await this.api.me();
      this.set({ me });
      const stillMember = me.memberships.some((m) => m.org_uid === this.snap.orgUid && m.state === 'active');
      if (!this.snap.orgUid || !stillMember) {
        const active = me.memberships.filter((m) => m.state === 'active');
        this.set({ orgUid: active.length === 1 ? active[0].org_uid : null, catalog: null, access: 'online', needsOrgChoice: active.length > 1, notice: this.snap.orgUid ? 'Ya no tienes acceso activo a esa empresa.' : null });
        if (active.length === 1) return this.revalidate();
        await this.persistCache();
        return;
      }
      const catalog = await this.api.catalog(this.deps.supported);
      this.set({ catalog, access: 'online', notice: null });
      await this.persistCache();
    } catch (e) {
      if (e instanceof ApiError && (e.status === 0 || e.status >= 500)) {
        const until = this.snap.catalog?.offline_until ?? null;
        this.set({ access: accessMode({ validatedOnline: false, offlineUntil: until, now: this.now() }) });
        return;
      }
      if (e instanceof ApiError && e.code === 'organization_not_authorized') {
        this.set({ catalog: null, orgUid: null, access: 'online', notice: 'Ya no tienes acceso activo a esa empresa.' });
        return;
      }
      if (this.snap.status === 'signed_out') return;
      throw e;
    }
  }

  // ---- Autenticación ----
  private async startWith(tokens: TokenPair) {
    this.tokens = { ...tokens, personId: -1 };
    const me = await this.api.me(tokens.access_token);
    this.tokens = { ...tokens, personId: me.person.id };
    await this.deps.secure.set(TOKENS_KEY, JSON.stringify(this.tokens));
    this.set({ status: 'signed_in', me, notice: null });
    await this.deps.kv.set(LAST_PERSON_KEY, String(me.person.id));
    await this.chooseOrg(null);
  }

  async login(email: string, password: string) { await this.startWith(await this.api.login({ email, password, device: await this.deps.device() })); }
  async register(email: string, password: string, name: string) { await this.startWith(await this.api.register({ email, password, name, device: await this.deps.device() })); }
  async loginGoogle(idToken: string) { await this.startWith(await this.api.loginGoogle({ id_token: idToken, device: await this.deps.device() })); }

  /** Tras aceptar una invitación o ser aprobado: recarga membresías y catálogo. */
  async refreshAccess() { this.set({ catalog: null }); await this.revalidate(); if (!this.snap.orgUid) await this.chooseOrg(null); }

  async logout(): Promise<void> {
    try { await this.api.logout(); } catch { /* sin red: igual se cierra localmente; el servidor expira la sesión */ }
    await this.finishSignOut(null);
  }

  /** Cierra la sesión local. Las colas de operaciones NO se tocan: siguen guardadas por identidad y empresa. */
  private async finishSignOut(notice: string | null) {
    const personId = this.snap.me?.person.id ?? this.tokens?.personId;
    this.tokens = null;
    await this.deps.secure.remove(TOKENS_KEY);
    if (personId != null) await this.deps.kv.remove(CACHE_KEY(personId));
    this.set({ status: 'signed_out', me: null, orgUid: null, catalog: null, notice, needsOrgChoice: false, access: 'offline_expired' });
  }
}
