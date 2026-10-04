// Arnés LOCAL de prueba visual (no se despliega): simula el puente Odoo con datos sintéticos.
// Uso: VITE_ODOO_PORTAL=true npx vite --config scripts/mock-portal/vite.mock.config.ts  →  http://localhost:5199/web_tracker/?asset=ffeaac2c-228b-4a79-bd2e-b2d2798a896b#fleet
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

const A = 'ffeaac2c-228b-4a79-bd2e-b2d2798a896b';
const B = '10798d72-2a70-481d-9622-ce2f4b3d92b4';
const asset = (id: string, name: string, plate: string) => ({
  asset_id: id, name, plate, type: 'tractor', cost_center: null, linked_to_odoo: id === A, responsible: null, created_at: '2026-09-01T12:00:00Z',
  position_stale: false, signal_state: 'received', motion_state: 'stationary', protection_state: 'disarmed',
  last_position: { id: 'p1', recorded_at: new Date().toISOString(), received_at: new Date().toISOString(), lat: -35.42, lon: -71.66, speed_kmh: 0, quality: 'gps', acc: null, external_power: null },
  device: null, capabilities: { tracking: 'not_approved', remote_start_inhibit: 'not_approved' },
});
const costs = (incomplete: boolean, denied: boolean) => ({
  linked: true, asset_id: A, currency: { name: 'CLP', symbol: '$', decimals: 0 }, period: { from: '2026-09-01', to: '2026-09-30' }, hourly_metric: 'session',
  vehicle: { id: 24, name: '[QA] Tractor/TRKQA-01', plate: 'TRKQA-01' }, access: { expenses: !denied, accounting: !denied },
  real: { available: !denied, amount: denied ? null : 123450, lines: 1, reason: denied ? 'Sin permiso de lectura contable.' : '', basis: 'Neto: apuntes publicados de cuentas de gasto atribuidos explícitamente al vehículo, con sus reversas.' },
  pending: { available: !denied, amount: incomplete ? 50000 : 0, count: incomplete ? 1 : 0 },
  unattributed: { available: true, count: incomplete ? 1 : 0, amount: incomplete ? 7000 : 0 },
  quantities: { sessions: 3, km: { value: 12.345, sessions: 1 }, session_hours: { value: 2, sessions: 1 }, hourmeter_hours: { value: 7.5, work_orders: 1 }, excluded: { open: 1, closed_without_distance: 1 }, last_sync: '2026-09-30 23:33:08' },
  indicators: {
    cost_per_km: incomplete ? { label: 'Costo por km', unit: 'km', value: null, partial: 10000, status: 'incomplete', reasons: ['1 gasto pendiente aún no contabilizado no está en el costo real.'] } : { label: 'Costo por km', unit: 'km', value: 10000, partial: null, status: 'ok', reasons: [] },
    cost_per_hour: { label: 'Costo por hora de sesión', unit: 'h', value: null, partial: null, status: 'unavailable', reasons: ['Sin horas de sesión cerradas en el período.'] },
  },
  by_center: { rows: [{ account: 'Cuartel QA 1', plan: 'Plan A', amount: 100000 }, { account: 'Actividad QA', plan: 'Plan B', amount: 50000 }], unassigned: 0 },
  documents: [{ id: 1, name: 'Combustible', date: '2026-09-10', folio: 'FC-000042', state_label: 'Aprobado', amount: 123450, doc_type: 'Boleta', doc_number: '1234' }],
  links: { vehicle: '/odoo/action-fleet.fleet_vehicle_action/24', expenses: '/odoo/action-step_management_costs_tracker.action_server_vehicle_expenses/24' },
});

export default defineConfig({
  root: path.resolve(__dirname, '../..'),
  plugins: [react(), {
    name: 'mock-odoo-bridge',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = new URL(req.url || '/', 'http://x');
        const json = (body: unknown, status = 200) => { res.statusCode = status; res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify(body)); };
        if (url.pathname === '/steps_tracker/context') return json({ user_id: 2, user: 'Usuaria QA', company_id: 1, company: 'Empresa QA', tenant_key: 'QA:1', role: 'manager', csrf_token: 'x' });
        if (url.pathname === '/steps_tracker/api/fleet/snapshot') return json({ items: [asset(A, '[QA] Tractor', 'TRKQA-01'), asset(B, '[QA] Activo manual', 'TRKQA-01')], total: 2, next_cursor: null, counts: { received: 2, stale: 0, no_signal: 0 } });
        if (url.pathname.startsWith('/steps_tracker/api/view-preferences')) return json(null);
        if (url.pathname.startsWith('/steps_tracker/api/configuration')) return json({ reminders: [], devices: [] });
        if (url.pathname === '/steps_tracker/costs/assets/' + A) { const mode = url.searchParams.get('mode') || globalThis.__mode; return json(costs(url.searchParams.get('to') === '2026-09-15', mode === 'denied')); }
        if (url.pathname === '/steps_tracker/costs/assets/' + B) return json({ linked: false, asset_id: B, reason: 'unlinked', message: 'Este activo no está asociado a un vehículo de Odoo (por ejemplo, fue creado en el portal). No se asocia por nombre ni por patente.' });
        if (url.pathname.startsWith('/steps_tracker/')) return json({ detail: 'Ruta simulada no disponible' }, 404);
        next();
      });
    },
  }],
  base: '/web_tracker/',
  resolve: { alias: { '@': path.resolve(__dirname, '../../src') } },
  server: { port: 5199, strictPort: true },
});
