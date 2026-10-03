// API simulada para probar la app en local: node scripts/mock-api.mjs  (puerto 8788)
import http from 'node:http';

const user = { id: 1, username: 'demo', full_name: 'Operador Demo', is_admin: true };
const json = (res, body, status = 200) => { res.writeHead(status, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*' }); res.end(JSON.stringify(body)); };
const openSession = { id: 'aaaaaaaa-0000-4000-8000-000000000001', machine_id: 1, machine_name: 'Tractor John Deere', started_at: new Date(Date.now() - 3600e3).toISOString(), ended_at: null, status: 'open', points_count: 12, work_order_id: 77, total_distance_m: 1200, driver_name: null, cost_center_name: 'Fundo Norte' };
const store = { routes: [], session: openSession };
const routes = {
  'POST /auth/login': () => ({ access_token: 'mock', token_type: 'bearer', user, cost_centers: [] }),
  'GET /auth/me': () => user,
  'GET /auth/me/cost_centers': () => [{ id: 1, name: 'Fundo Norte' }, { id: 2, name: 'Fundo Sur' }],
  'GET /machines': () => [{ id: 1, name: 'Tractor John Deere', plate: 'AB1234', cost_center_id: 1, tank_capacity_liters: 200, default_labor_id: 1 }, { id: 2, name: 'Camioneta', plate: 'CD5678', cost_center_id: 2, tank_capacity_liters: 80, default_labor_id: null }],
  'GET /labors': () => [{ id: 1, activity_id: 1, name: 'Aplicación' }, { id: 2, activity_id: 1, name: 'Transporte' }],
  'GET /drivers': () => [{ id: 1, name: 'Juan Pérez', is_active: true }],
  'GET /implements': () => [{ id: 1, name: 'Pulverizador', is_active: true }],
  'GET /fields': () => [{ id: 1, name: 'Potrero 1', cost_center_id: 1, polygon: [{ lat: -35.4, lon: -71.6 }, { lat: -35.4, lon: -71.592 }, { lat: -35.407, lon: -71.592 }, { lat: -35.407, lon: -71.6 }] }],
  'GET /sessions/my': () => store.session.status === 'open' ? [store.session] : [],
  'GET /sessions_active': () => [{ id: 'aaaaaaaa-0000-4000-8000-000000000001', machine_id: 1, machine_name: 'Tractor John Deere', driver_name: 'Juan Pérez', cost_center_name: 'Fundo Norte', started_at: new Date(Date.now() - 3600e3).toISOString(), status: 'open', points_count: 12, last_lat: -35.4035, last_lon: -71.597, last_speed_mps: 2.4 }],
  'GET /mobile/routes': () => store.routes.filter((r) => r.status !== 'cancelled'),
  'POST /mobile/routes': (b) => { const r = { ...b, machine_name: 'Tractor John Deere', status: 'assigned', created_by_name: 'Demo', created_at: new Date().toISOString() }; store.routes.unshift(r); return r; },
  'GET /machines/1/fuel_status': () => ({ last_liters: 120, tank_capacity_liters: 200 }),
  'POST /work_orders': () => ({ id: 77 }),
  'PUT /work_orders/77': () => ({ id: 77 }),
  'POST /sessions/start': () => ({ id: 'aaaaaaaa-0000-0000-0000-000000000001', machine_id: 1, started_at: new Date().toISOString(), ended_at: null, status: 'open' }),
  'POST /sessions/aaaaaaaa-0000-0000-0000-000000000001/points': () => ({ inserted: 1 }),
  'POST /sessions/aaaaaaaa-0000-0000-0000-000000000001/close': () => ({ id: 'aaaaaaaa-0000-0000-0000-000000000001', status: 'closed' }),
  'POST /auth/refresh': () => ({ access_token: 'mock', token_type: 'bearer', user, cost_centers: [] }),
  'GET /work_orders': () => [{ id: 77, code: 'T-77', work_date: new Date().toISOString().slice(0, 10), machine_id: 1, activity_id: 1, labor_id: 2, cost_center_id: 1, field_id: 1, notes: 'Transportar fruta al packing', scheduled_time: '08:30', mobile_status: null, progress_pct: null, implement_id: null, hourmeter_initial: 120, fuel_tank_start_liters: 50 }],
  'PUT /work_orders/5': () => ({ id: 5 }),
  'GET /mobile/checklist_template': () => ({ items: [{ key: 'lights', label: 'Luces y señalización' }, { key: 'brakes', label: 'Frenos' }, { key: 'tires', label: 'Neumáticos' }] }),
  'POST /mobile/checklists': () => ({ ok: true }),
  'POST /mobile/incidents': () => ({ ok: true }),
  'POST /mobile/expenses': () => ({ ok: true }),
  'POST /mobile/heartbeat': () => ({ ok: true }),
  'POST /mobile/diagnostics': () => ({ ok: true }),
  'GET /mobile/incidents': () => [{ id: 'i1', category: 'sos', note: 'SOS del conductor', status: 'open', machine_name: 'Tractor John Deere', user_name: 'Operador Demo', lat: -35.4, lon: -71.6, occurred_at: new Date().toISOString(), has_photo: false }],
  'GET /mobile/devices': () => [{ user_id: 1, user_name: 'Operador Demo', version: '1.2.0', platform: 'web', pending: 2, last_sync_at: new Date().toISOString(), last_seen_at: new Date().toISOString() }],
};
http.createServer((req, res) => {
  if (req.method === 'OPTIONS') return json(res, {}, 204);
  const key = `${req.method} ${req.url.split('?')[0]}`;
  const path = req.url.split('?')[0];
  const handler = routes[key] || (/^\/sessions\/[^/]+\/points$/.test(path) ? () => ({ inserted: 1 }) : /^\/sessions\/[^/]+\/close$/.test(path) ? () => ({ status: 'closed' }) : /^PUT \/work_orders\/\d+$/.test(key) ? () => ({ id: 1 }) : null);
  let raw = '';
  req.on('data', (c) => { raw += c; });
  req.on('end', () => {
    let body = {}; try { body = raw ? JSON.parse(raw) : {}; } catch { /* sin cuerpo */ }
    if (key === `GET /sessions/${store.session.id}`) return json(res, store.session);
    if (/^POST \/sessions\/[^/]+\/close$/.test(key)) { store.session = { ...store.session, status: 'closed', ended_at: new Date().toISOString() }; return json(res, store.session); }
    const m = /^PATCH \/mobile\/routes\/(.+)$/.exec(key);
    if (m) { const r = store.routes.find((x) => x.id === m[1]); if (r) r.status = body.status; return json(res, r || {}); }
    return handler ? json(res, handler(body)) : json(res, { detail: 'No encontrado: ' + key }, 404);
  });
}).listen(Number(process.env.PORT) || 8788, () => console.log('mock api'));
