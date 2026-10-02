// API simulada para probar la app en local: node scripts/mock-api.mjs  (puerto 8788)
import http from 'node:http';

const user = { id: 1, username: 'demo', full_name: 'Operador Demo', is_admin: true };
const json = (res, body, status = 200) => { res.writeHead(status, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*' }); res.end(JSON.stringify(body)); };
const routes = {
  'POST /auth/login': () => ({ access_token: 'mock', token_type: 'bearer', user, cost_centers: [] }),
  'GET /auth/me': () => user,
  'GET /auth/me/cost_centers': () => [{ id: 1, name: 'Fundo Norte' }, { id: 2, name: 'Fundo Sur' }],
  'GET /machines': () => [{ id: 1, name: 'Tractor John Deere', plate: 'AB1234', cost_center_id: 1, tank_capacity_liters: 200, default_labor_id: 1 }, { id: 2, name: 'Camioneta', plate: 'CD5678', cost_center_id: 2, tank_capacity_liters: 80, default_labor_id: null }],
  'GET /labors': () => [{ id: 1, activity_id: 1, name: 'Aplicación' }, { id: 2, activity_id: 1, name: 'Transporte' }],
  'GET /drivers': () => [{ id: 1, name: 'Juan Pérez', is_active: true }],
  'GET /implements': () => [{ id: 1, name: 'Pulverizador', is_active: true }],
  'GET /fields': () => [{ id: 1, name: 'Potrero 1', cost_center_id: 1 }],
  'GET /machines/1/fuel_status': () => ({ last_liters: 120, tank_capacity_liters: 200 }),
  'POST /work_orders': () => ({ id: 77 }),
  'PUT /work_orders/77': () => ({ id: 77 }),
  'POST /sessions/start': () => ({ id: 'aaaaaaaa-0000-0000-0000-000000000001', machine_id: 1, started_at: new Date().toISOString(), ended_at: null, status: 'open' }),
  'POST /sessions/aaaaaaaa-0000-0000-0000-000000000001/points': () => ({ inserted: 1 }),
  'POST /sessions/aaaaaaaa-0000-0000-0000-000000000001/close': () => ({ id: 'aaaaaaaa-0000-0000-0000-000000000001', status: 'closed' }),
  'GET /sessions/my': () => [{ id: 'x', machine_id: 1, machine_name: 'Tractor John Deere', driver_name: null, cost_center_name: 'Fundo Norte', started_at: new Date(Date.now() - 7200000).toISOString(), ended_at: new Date().toISOString(), status: 'closed', points_count: 412 }],
  'POST /auth/refresh': () => ({ access_token: 'mock', token_type: 'bearer', user, cost_centers: [] }),
  'GET /work_orders': () => [{ id: 5, code: 'T-5', work_date: new Date().toISOString().slice(0, 10), machine_id: 1, activity_id: 1, labor_id: 2, cost_center_id: 1, field_id: 1, notes: 'Transportar fruta al packing', scheduled_time: '08:30', mobile_status: null, progress_pct: null, implement_id: null }],
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
  req.resume();
  return handler ? json(res, handler()) : json(res, { detail: 'No encontrado: ' + key }, 404);
}).listen(Number(process.env.PORT) || 8788, () => console.log('mock api'));
