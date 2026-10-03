// Cliente de la API Tracker (JWT). El mismo código corre en web, Android e iOS.
const TOKEN_KEY = 'steps_movil_token';
export const API_BASE = ((import.meta.env.VITE_API_BASE_URL as string | undefined) || 'https://stepsapp.cl/tracker-steps').replace(/\/+$/, '');

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) { super(message); this.status = status; }
}

export const tokenStore = {
  get(): string | null { try { return localStorage.getItem(TOKEN_KEY); } catch { return null; } },
  set(token: string | null) { try { if (token) localStorage.setItem(TOKEN_KEY, token); else localStorage.removeItem(TOKEN_KEY); } catch { /* modo privado */ } },
};

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void) { onUnauthorized = fn; }

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = tokenStore.get();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  let response: Response;
  try { response = await fetch(API_BASE + path, { ...init, headers }); }
  catch { throw new ApiError('Sin conexión con el servidor', 0); }
  if (response.status === 401) { tokenStore.set(null); onUnauthorized(); throw new ApiError('Tu sesión expiró. Vuelve a entrar.', 401); }
  if (!response.ok) {
    let detail = '';
    try { const body = await response.json(); detail = typeof body.detail === 'string' ? body.detail : ''; } catch { /* sin cuerpo */ }
    throw new ApiError(detail || `Error ${response.status}`, response.status);
  }
  return response.status === 204 ? (undefined as T) : (response.json() as Promise<T>);
}

export type User = { id: number; username: string; full_name: string; is_admin: boolean };
export type CostCenter = { id: number; name: string };
export type Machine = { id: number; name: string; plate: string | null; cost_center_id: number | null; tank_capacity_liters: number | null; default_labor_id: number | null };
export type Labor = { id: number; activity_id: number; name: string };
export type Driver = { id: number; name: string; is_active: boolean };
export type Implement = { id: number; name: string; is_active: boolean };
export type Field = { id: number; name: string; cost_center_id: number | null };
export type Session = { id: string; machine_id: number; started_at: string; ended_at: string | null; status: 'open' | 'closed' };
export type SessionSummary = Session & { work_order_id?: number | null; machine_name: string | null; driver_name: string | null; cost_center_name: string | null; points_count: number };
export type TokenOut = { access_token: string; token_type: string; user: User; cost_centers: CostCenter[] };
export type FuelStatus = { last_liters: number | null; tank_capacity_liters: number | null };
export type WorkOrder = { id: number };
export type WorkOrderFull = WorkOrder & { hourmeter_initial: number | null; fuel_tank_start_liters: number | null };
export type PointIn = { ts: string; lat: number; lon: number; speed_mps: number | null; accuracy_m: number | null };

export async function login(username: string, password: string): Promise<TokenOut> {
  const data = await api<TokenOut>('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) });
  tokenStore.set(data.access_token);
  return data;
}
export const me = () => api<User>('/auth/me');

/** Sesión Odoo (solo web alojada junto a Odoo): cambia la cookie por un token de la API. */
export async function loginWithOdoo(): Promise<TokenOut | null> {
  try {
    const ctx = await fetch('/steps_tracker/context', { credentials: 'same-origin', redirect: 'manual', headers: { Accept: 'application/json' } });
    if (ctx.type === 'opaqueredirect' || ctx.status === 0 || !ctx.ok) return null;
    const { csrf_token } = await ctx.json();
    const body = new URLSearchParams({ csrf_token, method: 'POST', payload: '{}' });
    const r = await fetch('/steps_tracker/classic-session', { method: 'POST', body, credentials: 'same-origin', headers: { Accept: 'application/json' } });
    if (!r.ok) return null;
    const data = (await r.json()) as TokenOut;
    tokenStore.set(data.access_token);
    return data;
  } catch { return null; }
}

export const catalogs = {
  machines: () => api<Machine[]>('/machines'),
  labors: () => api<Labor[]>('/labors'),
  drivers: () => api<Driver[]>('/drivers'),
  implements: () => api<Implement[]>('/implements'),
  fields: () => api<Field[]>('/fields'),
  costCenters: () => api<CostCenter[]>('/auth/me/cost_centers'),
  fuelStatus: (machineId: number) => api<FuelStatus>(`/machines/${machineId}/fuel_status`),
};

export type WorkOrderIn = {
  code: string; work_date: string; season: string; machine_id: number; activity_id: number; labor_id: number;
  cost_center_id: number | null; field_id: number | null; implement_id: number | null; hourmeter_initial: number | null; fuel_tank_start_liters: number | null;
};
export const sessions = {
  createWorkOrder: (body: WorkOrderIn) => api<WorkOrder>('/work_orders', { method: 'POST', body: JSON.stringify(body) }),
  workOrdersOf: (isoDate: string) => api<WorkOrderFull[]>(`/work_orders?date=${encodeURIComponent(isoDate)}`),
  finishWorkOrder: (id: number, body: { hourmeter_final: number | null; fuel_refill_liters: number | null; fuel_tank_end_liters: number | null }) =>
    api<WorkOrder>(`/work_orders/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  start: (body: { machine_id: number; driver_id: number | null; cost_center_id: number | null; work_order_id: number }) =>
    api<Session>('/sessions/start', { method: 'POST', body: JSON.stringify(body) }),
  points: (id: string, points: PointIn[]) => api<{ inserted: number }>(`/sessions/${id}/points`, { method: 'POST', body: JSON.stringify({ points }) }),
  close: (id: string) => api<Session>(`/sessions/${id}/close`, { method: 'POST' }),
  mine: (limit = 40) => api<SessionSummary[]>(`/sessions/my?limit=${limit}`),
  open: () => api<SessionSummary[]>('/sessions/my?status=open&limit=100'),
};
