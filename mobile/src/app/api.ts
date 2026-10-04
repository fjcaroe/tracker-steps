// Cliente HTTP de /steps_app/v1: Bearer + empresa activa (X-Steps-Org), renovación de sesión de un solo vuelo y errores con código estable.
import type { CatalogOut, DeviceInfo, DeviceOut, ErrorBody, HealthOut, MeOut, TokenPair } from '../shared/contracts';

export const API_BASE = ((import.meta.env.VITE_STEPS_API_BASE as string | undefined) || 'https://stepsapp.cl/steps_app/v1').replace(/\/+$/, '');

export class ApiError extends Error {
  constructor(readonly code: string, readonly status: number, message?: string, readonly terminal = false) { super(message || code); this.name = 'ApiError'; }
}

export type SessionTokens = TokenPair & { personId: number };
export type HttpDeps = {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
  tokens: () => SessionTokens | null;
  setTokens: (t: SessionTokens | null) => Promise<void> | void;
  orgUid: () => string | null;
  /** Se invoca solo cuando el servidor confirma que la sesión ya no vale (no ante fallos de red). */
  onSignedOut: (reason: string) => void;
};

export function createApi(deps: HttpDeps) {
  const base = (deps.baseUrl ?? API_BASE).replace(/\/+$/, '');
  const doFetch = () => deps.fetchImpl ?? fetch;
  let refreshing: Promise<boolean> | null = null;

  async function raw<T>(method: string, path: string, opts: { body?: unknown; token?: string | null; org?: string | null } = {}): Promise<T> {
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (opts.body !== undefined) headers['Content-Type'] = 'application/json';
    if (opts.token) headers.Authorization = `Bearer ${opts.token}`;
    if (opts.org) headers['X-Steps-Org'] = opts.org;
    let response: Response;
    try { response = await doFetch()(base + path, { method, headers, body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined }); }
    catch { throw new ApiError('network', 0, 'Sin conexión con el servidor'); }
    let payload: unknown = null;
    try { payload = await response.json(); } catch { /* sin cuerpo JSON */ }
    if (!response.ok || (payload as { ok?: boolean } | null)?.ok === false) {
      const body = (payload ?? {}) as Partial<ErrorBody>;
      throw new ApiError(body.error ?? `http_${response.status}`, response.status, body.message, body.terminal ?? false);
    }
    return payload as T;
  }

  /** Renueva el par de tokens una sola vez aunque varias peticiones lo pidan a la vez. */
  function refresh(): Promise<boolean> {
    if (refreshing) return refreshing;
    refreshing = (async () => {
      const current = deps.tokens();
      if (!current) return false;
      try {
        const next = await raw<TokenPair & { ok: true }>('POST', '/auth/refresh', { body: { refresh_token: current.refresh_token } });
        await deps.setTokens({ ...next, personId: current.personId });
        return true;
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) { await deps.setTokens(null); deps.onSignedOut(e.code); return false; }
        throw e; // sin red o error del servidor: se conserva la sesión
      }
    })().finally(() => { refreshing = null; });
    return refreshing;
  }

  async function authed<T>(method: string, path: string, body?: unknown, org = true): Promise<T> {
    const attempt = () => raw<T>(method, path, { body, token: deps.tokens()?.access_token ?? null, org: org ? deps.orgUid() : null });
    if (!deps.tokens()) throw new ApiError('unauthenticated', 401, 'Inicia sesión');
    try { return await attempt(); }
    catch (e) {
      if (e instanceof ApiError && e.status === 401 && e.code === 'token_expired') {
        if (await refresh()) return attempt();
        throw new ApiError('session_invalid', 401, 'Tu sesión expiró. Vuelve a entrar.');
      }
      if (e instanceof ApiError && e.status === 401) { await deps.setTokens(null); deps.onSignedOut(e.code); }
      throw e;
    }
  }

  const tokensFrom = async (p: Promise<TokenPair & { ok: true }>): Promise<TokenPair> => { const { ok: _ok, ...t } = await p; return t; };

  return {
    request: authed,
    health: () => raw<HealthOut>('GET', '/health'),
    register: (b: { email: string; password: string; name: string; device: DeviceInfo }) => tokensFrom(raw('POST', '/auth/register', { body: b })),
    login: (b: { email: string; password: string; device: DeviceInfo }) => tokensFrom(raw('POST', '/auth/login', { body: b })),
    loginGoogle: (b: { id_token: string; device: DeviceInfo }) => tokensFrom(raw('POST', '/auth/google', { body: b })),
    verifyEmail: (b: { email: string; code: string }) => raw<{ ok: true }>('POST', '/auth/verify_email', { body: b }),
    me: (tokenOverride?: string) => tokenOverride ? raw<MeOut>('GET', '/me', { token: tokenOverride }) : authed<MeOut>('GET', '/me', undefined, false),
    logout: () => authed<{ ok: true }>('POST', '/auth/logout', {}, false),
    acceptInvitation: (token: string) => authed<{ ok: true; org_uid: string }>('POST', '/invitations/accept', { token }, false),
    requestAccess: (org_code: string, note?: string) => authed<{ ok: true; state: string }>('POST', '/access/request', { org_code, note }, false),
    catalog: (supported: Record<string, number>) =>
      authed<CatalogOut>('GET', `/catalog?supported=${encodeURIComponent(Object.entries(supported).map(([k, v]) => `${k}:${v}`).join(','))}`),
    devices: () => authed<{ ok: true; devices: DeviceOut[] }>('GET', '/devices', undefined, false),
    revokeDevice: (id: number) => authed<{ ok: true }>('POST', `/devices/${id}/revoke`, {}, false),
    deleteAccount: () => authed<{ ok: true }>('POST', '/account/delete', {}, false),
  };
}
export type Api = ReturnType<typeof createApi>;
