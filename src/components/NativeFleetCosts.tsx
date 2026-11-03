import { FleetApiError, portalRequest, type FleetContext } from '../services/fleetApi';
import { odooCall, readAssetLink } from '../services/odooOperations';

type Relation = [number, string] | false;
type Service = { id: number; date: string; service_type_id: Relation; amount: number; currency_id: Relation; state: string; account_move_state: string | false };
type Contract = { id: number; name: string; start_date: string; expiration_date: string | false; amount: number; cost_generated: number; cost_frequency: string; currency_id: Relation; state: string };
type Records<T> = { rows: T[]; error?: string };
export type NativeCosts = { vehicle: number; services: Records<Service>; contracts: Records<Contract> };

const labels: Record<string, string> = {
  new: 'Nuevo', running: 'En curso', done: 'Realizado', cancelled: 'Cancelado',
  futur: 'Nuevo', open: 'Vigente', expired: 'Vencido', closed: 'Cancelado',
  daily: 'diario', weekly: 'semanal', monthly: 'mensual', yearly: 'anual',
};

function result<T>(value: PromiseSettledResult<T[]>): Records<T> {
  if (value.status === 'fulfilled') return { rows: value.value };
  const denied = value.reason instanceof FleetApiError && value.reason.status === 403;
  return { rows: [], error: denied ? 'Tu perfil no tiene acceso a estos registros de Flota.' : 'No se pudo consultar esta sección de Flota.' };
}

export async function readNativeFleetCosts(assetId: string, period: { from: string; to: string }): Promise<NativeCosts | null> {
  const context = await portalRequest<FleetContext>('/steps_tracker/context');
  const link = await readAssetLink(context, assetId);
  if (!link) return null;
  const vehicle = link.vehicle_id[0];
  const domain = [['company_id', '=', context.company_id], ['vehicle_id', '=', vehicle]];
  const [services, contracts] = await Promise.allSettled([
    odooCall<Service[]>(context, 'fleet.vehicle.log.services', 'search_read', [], {
      domain: [...domain, ['date', '>=', period.from], ['date', '<=', period.to]],
      fields: ['id', 'date', 'service_type_id', 'amount', 'currency_id', 'state', 'account_move_state'],
      order: 'date desc,id desc', limit: 101,
    }),
    odooCall<Contract[]>(context, 'fleet.vehicle.log.contract', 'search_read', [], {
      domain: [...domain, ['start_date', '<=', period.to], '|', ['expiration_date', '=', false], ['expiration_date', '>=', period.from]],
      fields: ['id', 'name', 'start_date', 'expiration_date', 'amount', 'cost_generated', 'cost_frequency', 'currency_id', 'state'],
      order: 'start_date desc,id desc', limit: 101,
    }),
  ]);
  return { vehicle, services: result(services), contracts: result(contracts) };
}

function money(amount: number, currency: Relation) {
  const code = currency && currency[1];
  return code && /^[A-Z]{3}$/.test(code)
    ? new Intl.NumberFormat('es-CL', { style: 'currency', currency: code }).format(amount)
    : new Intl.NumberFormat('es-CL').format(amount);
}

export default function NativeFleetCosts({ data, km }: { data: NativeCosts; km?: number }) {
  const { vehicle, services, contracts } = data;
  const completed = services.rows.filter(row => row.state === 'done');
  const currency = completed[0]?.currency_id;
  const canTotal = services.rows.length <= 100 && completed.length > 0 && currency &&
    completed.every(row => row.currency_id && row.currency_id[0] === currency[0]);
  const total = completed.reduce((sum, row) => sum + row.amount, 0);
  return <section className="asset-costs-gps" aria-label="Costos registrados en Flota">
    <h4>Servicios y contratos de Flota</h4>
    <p>Registra mantenciones, reparaciones, seguros y contratos en la ficha de Odoo. Los importes de Flota se muestran aparte del neto de rendiciones contabilizadas.</p>
    <a href={'/odoo/action-fleet.fleet_vehicle_action/' + vehicle}>Abrir ficha de Flota ↗</a>
    <details open><summary>Servicios del período</summary>
      {services.error ? <p>{services.error}</p> : !services.rows.length ? <p>Sin servicios registrados en el período.</p> : <>
        {canTotal && <p>Servicios realizados: <strong>{money(total, currency)}</strong>
          {km != null && km > 0 && <small> · {money(total / km, currency)} por km GPS</small>}</p>}
        <ul>{services.rows.slice(0, 100).map(row => <li key={row.id}>
          {row.date} · <a href={'/odoo/fleet.vehicle.log.services/' + row.id}>{row.service_type_id ? row.service_type_id[1] : 'Servicio'} ↗</a>
          {' · '}{labels[row.state] || row.state} · {money(row.amount, row.currency_id)}
          {row.account_move_state === 'posted' && <small> · Vinculado a un asiento publicado</small>}
        </li>)}</ul>
        {services.rows.length > 100 && <p>Mostrando los primeros 100 servicios. Acota el período para ver el total.</p>}
      </>}
    </details>
    <details><summary>Contratos con cobertura en el período</summary>
      {contracts.error ? <p>{contracts.error}</p> : !contracts.rows.length ? <p>Sin contratos registrados para estas fechas.</p> : <>
        <ul>{contracts.rows.slice(0, 100).map(row => <li key={row.id}>
          <a href={'/odoo/fleet.vehicle.log.contract/' + row.id}>{row.name} ↗</a>
          {' · '}{labels[row.state] || row.state} · {row.start_date}{row.expiration_date ? ' a ' + row.expiration_date : ''}
          <br />Importe del contrato: {money(row.amount, row.currency_id)}
          {row.cost_generated !== 0 && row.cost_frequency !== 'no' && <small> · {money(row.cost_generated, row.currency_id)} {labels[row.cost_frequency] || row.cost_frequency}</small>}
        </li>)}</ul>
        {contracts.rows.length > 100 && <p>Mostrando los primeros 100 contratos.</p>}
      </>}
    </details>
  </section>;
}
