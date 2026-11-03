import { useState } from 'react';
import { fleetRequest, type FleetContext, type FleetAsset, portalRequest } from '../services/fleetApi';
import './AssetCostsPanel.css';
import {buildTrail} from '../services/fleetTrail';
import {odooCall,readAssetLink} from '../services/odooOperations';
import NativeFleetCosts, { readNativeFleetCosts, type NativeCosts } from './NativeFleetCosts';

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
  const [expenses,setExpenses]=useState<{id:number;name:string;date:string;total_amount:number}[]|null>(null),[expensesError,setExpensesError]=useState(''),[expensesBusy,setExpensesBusy]=useState(false);
  const [gps,setGps]=useState<{km:number;partial:boolean;error:string}|null>(null);
  const [native,setNative]=useState<NativeCosts|null>(null);
  const [nativeError,setNativeError]=useState('');
  const money = (value: number | null | undefined, currency = data?.currency) => value == null || !currency
    ? 'No disponible'
    : new Intl.NumberFormat('es-CL', { style: 'currency', currency: currency.name, maximumFractionDigits: currency.decimals }).format(value);
  const number = (value: number, digits = 1) => new Intl.NumberFormat('es-CL', { maximumFractionDigits: digits }).format(value);

  const load = async (key = assetId) => {
    setLoading(true); setError('');setData(null);setGps(null);setExpenses(null);setExpensesError('');setNative(null);setNativeError('');
    const fleet = readNativeFleetCosts(key, period).then(setNative).catch(() => {
      setNativeError('No se pudo consultar la ficha de Flota con tu perfil.');
    });
    try {
      const report=await portalRequest<CostsData>(`/steps_tracker/costs/assets/${encodeURIComponent(key)}?from=${period.from}&to=${period.to}&hourly=${metric}`);
      setData(report);
      if(report.linked){
       try{
        const from=Date.parse(period.from+'T00:00:00'),to=Date.parse(period.to+'T23:59:59.999');
        if(to-from>31*86400000)throw new Error('Para calcular distancia del GPS, consulta hasta 31 días.');
        const context=await portalRequest<FleetContext>('/steps_tracker/context');
        let cursor:string|null=null;const points:NonNullable<FleetAsset['last_position']>[]=[];const seen=new Set<string>();
        for(let i=0;i<20;i++){
         const page:{items:NonNullable<FleetAsset['last_position']>[];next_cursor:string|null}=await fleetRequest<{items:NonNullable<FleetAsset['last_position']>[];next_cursor:string|null}>(`assets/${key}/positions?limit=500&since=${encodeURIComponent(new Date(from).toISOString())}${cursor?'&before='+encodeURIComponent(cursor):''}`,context);
         points.push(...page.items);cursor=page.next_cursor;if(!cursor)break;
         if(seen.has(cursor))throw new Error('No se pudo completar el historial GPS.');seen.add(cursor);
        }
        setGps({km:buildTrail(points,from,to).distanceM/1000,partial:!!cursor,error:''});
       }catch(e){setGps({km:0,partial:true,error:(e as Error).message});}
      }
    } catch (e) { setData(null); setError((e as Error).message); } finally { await fleet; setLoading(false); }
  };

  const openExpenses=async()=>{
   setExpensesBusy(true);setExpensesError('');setExpenses(null);
   try{
    const context=await portalRequest<FleetContext>('/steps_tracker/context'),link=await readAssetLink(context,assetId);
    if(!link)throw new Error('El vínculo del vehículo cambió. Actualiza el informe.');
    const action=await odooCall<{res_model:string;domain:unknown[]}>(context,'fleet.vehicle','action_open_step_expenses',[[link.vehicle_id[0]]]);
    if(action.res_model!=='hr.expense'||!Array.isArray(action.domain))throw new Error('Odoo no devolvió la consulta de gastos esperada.');
    const result=await odooCall<{id:number;name:string;date:string;total_amount:number}[]>(context,'hr.expense','search_read',[],{domain:[...action.domain,['company_id','=',context.company_id],['date','>=',data!.period.from],['date','<=',data!.period.to]],fields:['id','name','date','total_amount'],order:'date desc,id desc',limit:101});
    setExpenses(result);
   }catch(e){setExpensesError((e as Error).message);}finally{setExpensesBusy(false);}
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
      <button onClick={() => void load()} disabled={loading || !period.from || !period.to || period.to<period.from}>{loading ? 'Consultando…' : data ? 'Actualizar' : 'Ver costos y gastos'}</button>
    </div>
    {error && <p role="alert" className="asset-costs-error">{error}</p>}
    {nativeError && <p role="status" className="asset-costs-note">{nativeError}</p>}
    {native && <NativeFleetCosts data={native} km={gps && !gps.partial && !gps.error ? gps.km : undefined}/>}
    {data && !data.linked && <p role="status" className="asset-costs-note">{data.message}</p>}
    {data?.linked && <div className="asset-costs-body" aria-live="polite">
      <p className="asset-costs-note">{data.vehicle.name} · {data.vehicle.plate || 'sin patente'} · {data.period.from} a {data.period.to}</p>
      <dl>
        <dt>Rendiciones contabilizadas</dt><dd>{data.real.available ? data.real.lines ? money(data.real.amount) : <em>Sin apuntes atribuidos en el período</em> : <em>No disponible</em>}{!data.real.available && <small> {data.real.reason}</small>}</dd>
        <dt>Gasto pendiente (no es costo real)</dt><dd>{data.pending.available ? `${money(data.pending.amount)} · ${data.pending.count} gasto(s)` : <em>No disponible con tu perfil</em>}</dd>
        {data.unattributed.available && data.unattributed.count > 0 && <><dt>Sin vehículo asignado</dt><dd>{data.unattributed.count} gasto(s) · {money(data.unattributed.amount)} <small>(no atribuidos)</small></dd></>}
        <dt>Distancia de sesiones sincronizadas</dt><dd>{number(data.quantities.km.value, 3)} km</dd>
        <dt>Horas de sesión</dt><dd>{number(data.quantities.session_hours.value, 2)} h <small>(reloj de la sesión; no son horas de motor)</small></dd>
        <dt>Horas de horómetro</dt><dd>{data.quantities.hourmeter_hours.work_orders ? `${number(data.quantities.hourmeter_hours.value, 2)} h` : <em>Sin lecturas registradas</em>}</dd>
      </dl>
      <section className="asset-costs-gps"><h4>GPS del vehículo · mismo período</h4>
       <p>Desde y hasta usan la hora de tu dispositivo. La distancia es aproximada, filtrada y funciona sin iniciar jornada.</p>
       {loading?<p role="status">Consultando kilómetros del GPS…</p>:gps?.error?<p role="status">{gps.error}</p>:gps&&<><p>Distancia GPS aproximada: <strong>{number(gps.km,3)} km</strong>{gps.partial?' · Historial parcial; no se calcula costo por km.':''}</p>
       <p><b>Costo por km GPS (estimación): </b>{gps.partial?'Información incompleta':!data.real.available?'Sin acceso al costo contabilizado':!data.real.lines?'Sin gastos contabilizados atribuibles a este vehículo en el período':gps.km<=0?'Sin desplazamiento GPS confirmado en el período':data.real.amount==null?'Costo no disponible':money(data.real.amount/gps.km)+' / km'}</p></>}
       <small>Utiliza el mismo neto contabilizado indicado abajo; no altera el odómetro físico ni genera documentos contables.</small>
      </section>
      <details><summary>Indicadores basados en sesiones / horómetro de Odoo</summary><p>Estas bases requieren sesiones cerradas o lecturas de horómetro; recibir posiciones Coban no crea una sesión ni mide horas de motor.</p><ul className="asset-costs-indicators">{indicator(data.indicators.cost_per_km)}{indicator(data.indicators.cost_per_hour)}</ul></details>
      {(data.quantities.excluded.open > 0 || data.quantities.excluded.closed_without_distance > 0) && <p className="asset-costs-note">Sesiones excluidas: {data.quantities.excluded.open} abierta(s), {data.quantities.excluded.closed_without_distance} sin distancia GPS.</p>}
      {data.by_center.rows.length > 0 && <details><summary>Por cuenta analítica ({data.by_center.rows.length})</summary><ul>{data.by_center.rows.slice(0, 6).map(row => <li key={`${row.plan}:${row.account}`}>{row.account} <small>({row.plan})</small>: {money(row.amount)}</li>)}</ul><small>No se suman entre planes distintos.{data.by_center.unassigned ? ` Sin distribución analítica: ${money(data.by_center.unassigned)}.` : ''}</small></details>}
      {data.documents.length > 0 && <details><summary>Documentos ({data.documents.length})</summary><ul>{data.documents.slice(0, 8).map(doc => <li key={doc.id}>{doc.date} · {doc.name} <small>{doc.doc_type} {doc.doc_number} · {doc.folio || 'sin rendición'} · {doc.state_label}</small>: {money(doc.amount)}</li>)}</ul></details>}
      <p className="asset-costs-note">Base: {data.real.basis || 'Sin base disponible.'} {data.quantities.last_sync ? `Sesiones sincronizadas hasta ${new Date(data.quantities.last_sync.replace(' ', 'T') + 'Z').toLocaleString('es-CL')}` : 'Sin sesiones sincronizadas en el período.'}</p>
      <div className="tracker-inline-actions">
        <a href={data.links.vehicle}>Ficha del vehículo en Odoo ↗</a>
        {data.links.expenses && <button disabled={loading||expensesBusy} onClick={()=>void openExpenses()}>{expensesBusy?'Consultando gastos…':'Ver gastos del vehículo'}</button>}
      </div>
      {expensesError&&<p role="alert">{expensesError}</p>}
      {expenses&&<section aria-label="Gastos del vehículo en Odoo"><h4>Gastos del vehículo · {data.period.from} a {data.period.to}</h4><p>Registros nativos visibles con tus permisos, incluidos pendientes. El costo contabilizado se informa por separado.</p>{!expenses.length?<p role="status">Sin gastos registrados para este vehículo en el período.</p>:<ul>{expenses.slice(0,100).map(row=><li key={row.id}>{row.date} · <a href={'/odoo/hr.expense/'+row.id}>{row.name} ↗</a> · {money(row.total_amount)}</li>)}</ul>}{expenses.length>100&&<p>Mostrando los últimos 100 gastos. Acota el período para consultar más.</p>}</section>}
    </div>}
  </section>;
}
