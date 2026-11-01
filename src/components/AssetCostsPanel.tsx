import { useState } from 'react';
import { portalRequest } from '../services/fleetApi';
import './AssetCostsPanel.css';

type Indicator = { label: string; unit: string; value: number | null; partial: number | null; status: 'ok' | 'incomplete' | 'unavailable'; reasons: string[] };
type CostsData = {
  linked: boolean; message?: string;
  currency: { name: string; decimals: number };
  period: { from: string; to: string };
  hourly_metric: 'session' | 'hourmeter';
  vehicle: { name: string; plate: string };
  access: { expenses: boolean; accounting: boolean };
  real: { available: boolean; amount: number | null; lines: number; reason: string; basis: string };
  pending: { available: boolean; amount: number | null; count: number };
  unattributed: { available: boolean; count: number; amount: number };
  quantities: { km: { value: number }; session_hours: { value: number }; hourmeter_hours: { value: number; work_orders: number }; excluded: { open: number; closed_without_distance: number }; last_sync: string | null };
  indicators: { cost_per_km: Indicator; cost_per_hour: Indicator };
  by_center: { rows: { account: string; plan: string; amount: number }[]; unassigned: number };
  documents: { id: number; name: string; date: string; folio: string; state_label: string; amount: number; doc_type: string; doc_number: string }[];
  links: { vehicle: string; expenses: string | null };
};

const monthBounds = () => {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  const last = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
  return { from: `${now.getFullYear()}-${pad(now.getMonth() + 1)}-01`, to: `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(last)}` };
};

export default function AssetCostsPanel({ assetId }: { assetId: string }) {
  const [period, setPeriod] = useState(monthBounds);
  const [metric, setMetric] = useState<'session' | 'hourmeter'>('session');
  const [data, setData] = useState<CostsData | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const money = (value: number | null | undefined, currency = data?.currency) => value == null || !currency
    ? 'No disponible'
    : new Intl.NumberFormat('es-CL', { style: 'currency', currency: currency.name, maximumFractionDigits: currency.decimals }).format(value);
  const number = (value: number, digits = 1) => new Intl.NumberFormat('es-CL', { maximumFractionDigits: digits }).format(value);

  const load = async (key = assetId) => {
    setLoading(true); setError('');
    try {
      setData(await portalRequest<CostsData>(`/steps_tracker/costs/assets/${encodeURIComponent(key)}?from=${period.from}&to=${period.to}&hourly=${metric}`));
    } catch (e) { setData(null); setError((e as Error).message); } finally { setLoading(false); }
  };

  const indicator = (item: Indicator) => <li key={item.label} className={`asset-costs-indicator asset-costs-indicator--${item.status}`}>
    <span>{item.label}</span>
    {item.status === 'ok' ? <strong>{money(item.value)} / {item.unit}</strong> : <strong>No disponible / información incompleta{item.partial != null && <small> · parcial de referencia: {money(item.partial)} / {item.unit}</small>}</strong>}
    {item.status !== 'ok' && item.reasons.length > 0 && <small>{item.reasons.join(' ')}</small>}
  </li>;

  return <section className="asset-costs" aria-label="Costos y gastos del equipo">
    <h3>Costos y gastos</h3>
    <div className="asset-costs-form">
      <label>Desde<input type="date" value={period.from} max={period.to} onChange={e => setPeriod(p => ({ ...p, from: e.target.value }))} /></label>
      <label>Hasta<input type="date" value={period.to} min={period.from} onChange={e => setPeriod(p => ({ ...p, to: e.target.value }))} /></label>
      <label>Costo por hora según<select value={metric} onChange={e => setMetric(e.target.value as 'session' | 'hourmeter')}><option value="session">Horas de sesión</option><option value="hourmeter">Horas de horómetro</option></select></label>
      <button onClick={() => void load()} disabled={loading || !period.from || !period.to}>{loading ? 'Consultando…' : data ? 'Actualizar' : 'Ver costos y gastos'}</button>
    </div>
    {error && <p role="alert" className="asset-costs-error">{error}</p>}
    {data && !data.linked && <p role="status" className="asset-costs-note">{data.message}</p>}
    {data?.linked && <div className="asset-costs-body" aria-live="polite">
      <p className="asset-costs-note">{data.vehicle.name} · {data.vehicle.plate || 'sin patente'} · {data.period.from} a {data.period.to}</p>
      <dl>
        <dt>Costo real contabilizado</dt><dd>{data.real.available ? money(data.real.amount) : <em>No disponible</em>}{!data.real.available && <small> {data.real.reason}</small>}</dd>
        <dt>Gasto pendiente (no es costo real)</dt><dd>{data.pending.available ? `${money(data.pending.amount)} · ${data.pending.count} gasto(s)` : <em>No disponible con tu perfil</em>}</dd>
        {data.unattributed.available && data.unattributed.count > 0 && <><dt>Sin vehículo asignado</dt><dd>{data.unattributed.count} gasto(s) · {money(data.unattributed.amount)} <small>(no atribuidos)</small></dd></>}
        <dt>Distancia GPS válida</dt><dd>{number(data.quantities.km.value, 3)} km</dd>
        <dt>Horas de sesión</dt><dd>{number(data.quantities.session_hours.value, 2)} h <small>(reloj de la sesión; no son horas de motor)</small></dd>
        <dt>Horas de horómetro</dt><dd>{data.quantities.hourmeter_hours.work_orders ? `${number(data.quantities.hourmeter_hours.value, 2)} h` : <em>Sin lecturas registradas</em>}</dd>
      </dl>
      <ul className="asset-costs-indicators">{indicator(data.indicators.cost_per_km)}{indicator(data.indicators.cost_per_hour)}</ul>
      {(data.quantities.excluded.open > 0 || data.quantities.excluded.closed_without_distance > 0) && <p className="asset-costs-note">Sesiones excluidas: {data.quantities.excluded.open} abierta(s), {data.quantities.excluded.closed_without_distance} sin distancia GPS.</p>}
      {data.by_center.rows.length > 0 && <details><summary>Por cuenta analítica ({data.by_center.rows.length})</summary><ul>{data.by_center.rows.slice(0, 6).map(row => <li key={`${row.plan}:${row.account}`}>{row.account} <small>({row.plan})</small>: {money(row.amount)}</li>)}</ul><small>No se suman entre planes distintos.{data.by_center.unassigned ? ` Sin distribución analítica: ${money(data.by_center.unassigned)}.` : ''}</small></details>}
      {data.documents.length > 0 && <details><summary>Documentos ({data.documents.length})</summary><ul>{data.documents.slice(0, 8).map(doc => <li key={doc.id}>{doc.date} · {doc.name} <small>{doc.doc_type} {doc.doc_number} · {doc.folio || 'sin rendición'} · {doc.state_label}</small>: {money(doc.amount)}</li>)}</ul></details>}
      <p className="asset-costs-note">Base: {data.real.basis || 'Sin base disponible.'} {data.quantities.last_sync ? `Sesiones sincronizadas hasta ${new Date(data.quantities.last_sync.replace(' ', 'T') + 'Z').toLocaleString('es-CL')}` : 'Sin sesiones sincronizadas en el período.'}</p>
      <div className="tracker-inline-actions">
        <a href={data.links.vehicle}>Ficha del vehículo en Odoo ↗</a>
        {data.links.expenses && <a href={data.links.expenses}>Gastos del vehículo en Odoo ↗</a>}
      </div>
    </div>}
  </section>;
}
