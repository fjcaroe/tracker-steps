export type FleetAsset = {
  asset_id: string; name: string; plate: string | null; type: string; cost_center: string | null;
  responsible: string | null; created_at: string; position_stale: boolean;
  signal_state: 'received' | 'stale' | 'no_signal'; motion_state: 'moving' | 'stationary' | 'unknown';
  protection_state: 'armed' | 'disarmed' | 'incident_open';
  last_position: null | { id: string; recorded_at: string; received_at: string; lat: number; lon: number; speed_kmh: number | null; quality: string; acc: boolean | null; external_power: boolean | null };
  device: null | { model: string; brand: string; firmware: string | null; protocol: string | null };
  capabilities: { tracking: string; remote_start_inhibit: string };
};
export type FleetContext = { user_id: number; user: string; company_id: number; company: string; tenant_key: string; role: 'viewer' | 'operator' | 'manager'; csrf_token: string };
export type FleetFilters = { q: string; type: string; cost_center: string; motion: string; signal: string; protection: string; gps: string };
export const emptyFilters: FleetFilters = { q: '', type: '', cost_center: '', motion: '', signal: '', protection: '', gps: '' };
export const columnLabels: Record<string, string> = { name: 'Equipo', motion_state: 'Estado', signal_state: 'Última señal', protection_state: 'Protección', type: 'Tipo', created_at: 'Fecha de alta', device: 'GPS instalado', cost_center: 'Centro de costo', responsible: 'Responsable', acc: 'Contacto ACC' };
export const defaultColumns = ['name', 'motion_state', 'signal_state', 'protection_state'];
export type ViewPreference = { schema_version: 1; columns: string[]; filters: FleetFilters; sort: 'name' | 'created_at' | 'signal_state' };
export type Incident = { id: string; asset_id: string; type: string; severity: string; state: string; responsible: string | null; created_at: string; updated_at: string; timeline?: { id: string; actor: string; action: string; detail: Record<string, unknown>; created_at: string }[] };
export type Policy = { asset_id: string; armed: boolean; version: number; contacts: string[]; allowed_hours_utc: number[]; zone: null | { lat: number; lon: number; radius_m: number } };
export type Snapshot = { items: FleetAsset[]; total: number; next_cursor: string | null; counts: Record<string, number> };

export async function portalRequest<T>(path: string, context?: FleetContext, method = 'GET', payload?: unknown): Promise<T> {
  const body = method === 'GET' ? undefined : new URLSearchParams({ csrf_token: context?.csrf_token || '', method, payload: JSON.stringify(payload ?? {}) });
  const response = await fetch(path, { method: method === 'GET' ? 'GET' : 'POST', body, credentials: 'same-origin', headers: { Accept: 'application/json' } });
  if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) {
    let detail = '';
    try { const data = await response.json(); detail = typeof data.detail === 'string' ? data.detail : ''; } catch { /* login HTML / unavailable gateway */ }
    throw new Error(detail || (response.status === 403 ? 'Tu usuario no tiene permiso para esta acción.' : 'No se pudo cargar Tracker. Comprueba tu sesión Odoo o vuelve a intentar.'));
  }
  return response.json() as Promise<T>;
}
export function fleetRequest<T>(path: string, context: FleetContext, method = 'GET', body?: unknown) {
  return portalRequest<T>(`/steps_tracker/api/${path}`, context, method, body);
}
export async function allPages<T>(path: string, context: FleetContext): Promise<T[]> {
  const items: T[] = []; let cursor: string | null = '';
  do {
    const data: { items: T[]; next_cursor: string | null } = await fleetRequest(`${path}${path.includes('?') ? '&' : '?'}limit=500&after=${encodeURIComponent(cursor)}`, context);
    items.push(...data.items); cursor = data.next_cursor;
  } while (cursor);
  return items;
}
export const labels: Record<string, string> = { moving: 'En movimiento', stationary: 'Detenido · señal reciente', unknown: 'Movimiento desconocido', received: 'Dato recibido', stale: 'Sin señal reciente', no_signal: 'Sin señal', armed: 'Armada', disarmed: 'Desarmada', incident_open: 'Incidente abierto', open: 'Abierto', acknowledged: 'Reconocido', closed: 'Cerrado', communication_failure: 'Falla de comunicación', suspected_movement: 'Sospecha de movimiento', external_power_lost: 'Alimentación desconectada', acc_outside_schedule: 'ACC fuera de horario', outside_zone: 'Salida de zona', sos: 'SOS', manual: 'Aviso manual', high: 'Alta', medium: 'Media', vehicle: 'Vehículo', tractor: 'Tractor', truck: 'Camión' };
const auditLabels: Record<string, string> = { incident_opened: 'Incidente registrado', notification_pending: 'Aviso en bandeja', policy_changed: 'Política modificada', command_denied: 'Solicitud denegada', approval_denied: 'Aprobación denegada', device_assigned: 'GPS asociado', asset_upsert: 'Equipo sincronizado' };
export const label = (s: string) => labels[s] || auditLabels[s] || s;
export const dateLabel = (s?: string | null) => s ? new Date(s).toLocaleString('es-CL', { dateStyle: 'short', timeStyle: 'short' }) : 'Sin dato';
export function filterFleet(rows: FleetAsset[], f: FleetFilters) {
  return rows.filter(a => (!f.q || `${a.name} ${a.plate || ''}`.toLocaleLowerCase().includes(f.q.toLocaleLowerCase())) && (!f.type || a.type === f.type) && (!f.cost_center || a.cost_center === f.cost_center) && (!f.motion || a.motion_state === f.motion) && (!f.signal || a.signal_state === f.signal) && (!f.protection || a.protection_state === f.protection) && (!f.gps || a.device?.model === f.gps));
}
