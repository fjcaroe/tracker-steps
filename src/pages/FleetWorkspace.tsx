import { useEffect, useMemo, useState } from 'react';
import OperationsMap from '../components/OperationsMap';
import FleetFilters from '../components/FleetFilters';
import FleetList from '../components/FleetList';
import FleetTable from '../components/FleetTable';
import FleetAssetDetail from '../components/FleetAssetDetail';
import ProtectionPage, { type DemoProtection } from './ProtectionPage';
import { useFleetSnapshot } from '../hooks/useFleetSnapshot';
import { DEMO_FIELDS, getDemoVehicles, REGIONS, type DemoVehicle } from '../demo/scenario';
import { columnLabels, defaultColumns, emptyFilters, filterFleet, fleetRequest, portalRequest, type FleetAsset, type FleetContext, type ViewPreference } from '../services/fleetApi';
import './OperationsWorkspace.css';
import './FleetWorkspace.css';

type View = 'live' | 'fleet' | 'protection';
const initialPreference: ViewPreference = { schema_version: 1, columns: defaultColumns, filters: emptyFilters, sort: 'name' };
function viewFromHash(): View { const hash = window.location.hash.slice(1); return hash === 'fleet' || hash === 'protection' ? hash : 'live'; }
function syntheticAssets(): FleetAsset[] {
  return getDemoVehicles(0).map((v, i) => ({ asset_id: v.id, name: v.name, plate: v.plate, type: 'tractor', cost_center: DEMO_FIELDS.find(f => f.id === v.fieldId)?.name || null, responsible: v.driver,
    created_at: '2026-01-15T12:00:00Z', signal_state: i === 1 ? 'stale' : i === 2 ? 'no_signal' : 'received', motion_state: i === 1 || i === 2 ? 'unknown' : 'moving', position_stale: i === 1 || i === 2, protection_state: 'disarmed',
    last_position: i === 2 ? null : { id: v.id, recorded_at: new Date(Date.now()-(i === 1 ? 7200000 : 15000)).toISOString(), received_at: new Date(Date.now()-(i === 1 ? 7200000 : 10000)).toISOString(), lat: v.position.lat, lon: v.position.lon, speed_kmh: v.speedKmh, quality: 'gps', acc: true, external_power: true },
    device: { brand: 'Simulado', model: '401C · demo', firmware: null, protocol: null }, capabilities: { tracking: 'not_approved', remote_start_inhibit: 'not_approved' } }));
}

export default function FleetWorkspace() {
  const [context, setContext] = useState<FleetContext | null>(null);
  const [contextError, setContextError] = useState('');
  const [view, setView] = useState<View>(viewFromHash);
  const [demo, setDemo] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [preference, setPreference] = useState<ViewPreference>(initialPreference);
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);
  const [demoStore, setDemoStore] = useState<DemoProtection>({ incidents: [], policies: [] });
  const { assets, error, loading, refresh } = useFleetSnapshot(context, demo);
  const demoAssets = useMemo(syntheticAssets, []);
  const source = useMemo(() => demo ? demoAssets.map(a => ({ ...a, protection_state: demoStore.incidents.some(i => i.asset_id === a.asset_id && i.state !== 'closed') ? 'incident_open' as const : demoStore.policies.some(p => p.asset_id === a.asset_id && p.armed) ? 'armed' as const : 'disarmed' as const })) : assets, [demo, demoAssets, demoStore, assets]);
  const filtered = useMemo(() => filterFleet(source, preference.filters).sort((a,b) => String(a[preference.sort]).localeCompare(String(b[preference.sort]))), [source, preference]);
  const current = filtered.find(a => a.asset_id === selected);
  const demoKey = `tracker:demo:${context?.tenant_key}:${context?.user_id}:fleet:v1`;
  useEffect(() => { portalRequest<FleetContext>('/steps_tracker/context').then(setContext).catch(e => setContextError(e.message)); }, []);
  useEffect(() => { const sync = () => setView(viewFromHash()); window.addEventListener('hashchange', sync); return () => window.removeEventListener('hashchange', sync); }, []);
  useEffect(() => {
    if (!context) return;
    let active = true;
    const load = async () => {
      try {
        const raw = demo ? JSON.parse(localStorage.getItem(demoKey) || 'null') : await fleetRequest<ViewPreference | null>('view-preferences/fleet', context);
        if (active) setPreference(raw?.schema_version === 1 ? { ...initialPreference, ...raw, columns: raw.columns.filter((c: string) => c in columnLabels), filters: { ...emptyFilters, ...raw.filters } } : initialPreference);
      } catch { if (active) setNotice('No se pudieron cargar las preferencias guardadas.'); }
    };
    void load(); return () => { active = false; };
  }, [context, demo, demoKey]);
  const navigate = (v: View) => { window.location.hash = v; setView(v); };
  const save = async () => {
    if (!context) return;
    setSaving(true);
    try { if (demo) localStorage.setItem(demoKey, JSON.stringify(preference)); else await fleetRequest('view-preferences/fleet', context, 'PUT', preference); setNotice('Vista guardada para tu usuario y compañía.'); }
    catch (e) { setNotice((e as Error).message); } finally { setSaving(false); }
  };
  const importFleet = async () => {
    if (!context) return;
    setSaving(true);
    try { const result = await portalRequest<{ imported: number }>('/steps_tracker/import-fleet', context, 'POST'); setNotice(`${result.imported} equipos sincronizados desde Flota Odoo. Asocia un GPS para recibir posiciones.`); refresh(); }
    catch (e) { setNotice((e as Error).message); } finally { setSaving(false); }
  };
  const mapVehicles: DemoVehicle[] = filtered.filter(a => a.last_position).map(a => ({ id: a.asset_id, name: a.name, plate: a.plate || '', driver: a.responsible || '', fieldId: '', regionId: '', status: a.motion_state === 'moving' ? 'working' : 'paused', progress: 0, speedKmh: a.last_position?.speed_kmh || 0, fuelPct: 0, engineHours: 0, distanceKm: 0, coveredHa: 0, position: { lat: a.last_position!.lat, lon: a.last_position!.lon }, bearing: 0 }));
  const markerLabels = Object.fromEntries(filtered.map(a => [a.asset_id, a.position_stale ? 'Posición antigua · '+(a.last_position ? new Date(a.last_position.recorded_at).toLocaleString('es-CL') : 'Sin dato') : a.motion_state === 'unknown' ? 'Movimiento desconocido' : `${a.last_position?.speed_kmh ?? '—'} km/h`]));
  if (!context) return <main className="fleet-app"><h1>Steps Tracker</h1>{contextError ? <><p role="alert">{contextError}</p><a href="/web/login?redirect=/web_tracker/">Entrar con Odoo</a></> : <p role="status">Cargando tu compañía y permisos…</p>}</main>;
  return <div className="fleet-app"><header className="fleet-header"><a className="fleet-brand" href="/odoo"><b>S</b><span>Steps <strong>Tracker</strong></span></a><div className="fleet-identity"><strong>{context.company}</strong><span>{context.user}</span></div><a href="/odoo">Volver a Odoo</a></header><nav className="fleet-nav" aria-label="Áreas Tracker">{([['live','Operación'],['fleet','Control de flota'],['protection','Protección']] as const).map(([key,title]) => <button key={key} aria-current={view === key ? 'page' : undefined} onClick={() => navigate(key)}>{title}</button>)}</nav><main><div className="fleet-heading"><div><span className="fleet-eyebrow">{demo ? 'Laboratorio · datos sintéticos' : 'Monitoreo de tu compañía'}</span><h1>{view === 'live' ? 'Toda tu flota, a la vista.' : view === 'fleet' ? 'Control de flota' : 'Steps Protección'}</h1></div><label className="fleet-demo"><input type="checkbox" checked={demo} onChange={e => { setDemo(e.target.checked); setSelected(null); setNotice(''); }}/>Explorar demo</label></div>{demo && <div className="fleet-notice"><strong>Demostración sintética</strong><span>Las acciones de Protección se simulan durante esta visita. No escriben datos reales ni actúan sobre equipos.</span></div>}{notice && <p className="fleet-notice" role="status">{notice}</p>}{!demo && error && <p role="alert" className="fleet-error">{error} <button onClick={refresh}>Reintentar</button></p>}{!demo && loading ? <p role="status">Cargando flota…</p> : <><FleetFilters assets={source} value={preference.filters} onChange={filters => setPreference(p => ({ ...p, filters }))}/><div className="fleet-metrics" aria-live="polite"><span><strong>{filtered.length}</strong> Equipos filtrados</span><span><strong>{filtered.filter(a => a.signal_state === 'received').length}</strong> Señal reciente</span><span><strong>{filtered.filter(a => a.signal_state !== 'received').length}</strong> Sin señal reciente</span><span><strong>{filtered.filter(a => a.protection_state === 'incident_open').length}</strong> Con incidentes</span></div><div className="fleet-toolbar"><label>Ordenar<select value={preference.sort} onChange={e => setPreference(p => ({ ...p, sort: e.target.value as ViewPreference['sort'] }))}><option value="name">Equipo</option><option value="created_at">Fecha de alta</option><option value="signal_state">Estado de señal</option></select></label><button disabled={saving} onClick={() => void save()}>Guardar vista</button><button onClick={refresh} disabled={demo}>Actualizar</button>{context.role === 'manager' && !demo && <button disabled={saving} onClick={() => void importFleet()}>Sincronizar Flota Odoo</button>}{view === 'fleet' && <details className="fleet-columns"><summary>Columnas</summary>{Object.entries(columnLabels).map(([key,title]) => <label key={key}><input type="checkbox" checked={preference.columns.includes(key)} disabled={key === 'name'} onChange={e => setPreference(p => ({ ...p, columns: e.target.checked ? [...p.columns,key] : p.columns.filter(c => c !== key) }))}/>{title}</label>)}</details>}</div>{!filtered.length && <div className="fleet-empty"><h2>{source.length ? 'Ningún equipo coincide con estos filtros' : 'Tu flota está lista para conectar'}</h2><p>{source.length ? 'Ajusta o limpia los filtros para volver a ver tus equipos.' : 'Sincroniza los vehículos de Odoo. Cada GPS requiere una asignación verificada; no se mezclan datos de otras compañías.'}</p></div>}{view === 'protection' ? <ProtectionPage key={`${demo}:${context.tenant_key}`} context={context} assets={filtered} selected={selected} demo={demo} refresh={refresh} demoStore={demoStore} onDemoChange={setDemoStore}/> : view === 'fleet' ? <div className="fleet-control-layout"><FleetTable assets={filtered} columns={preference.columns} selected={selected} onSelect={setSelected}/><FleetAssetDetail asset={current} onProtect={() => navigate('protection')}/></div> : <div className="fleet-operation-layout"><FleetList assets={filtered} selected={selected} onSelect={setSelected}/><section className="fleet-map" aria-label="Mapa de última posición"><div className="fleet-map-caption">{mapVehicles.length} posiciones · los datos antiguos se indican en cada marcador</div>{mapVehicles.length ? <OperationsMap fields={demo ? DEMO_FIELDS : []} vehicles={mapVehicles} markerLabels={markerLabels} selectedVehicleId={selected} onSelectVehicle={setSelected} showRows={false} showRoadRoute={false} depot={mapVehicles[0]?.position || REGIONS[0].depot} followVehicle={false}/> : <div className="fleet-empty">Sin posiciones disponibles. Los equipos permanecen visibles en la lista.</div>}</section><FleetAssetDetail asset={current} onProtect={() => navigate('protection')}/></div>}</>}</main><footer className="fleet-footer">Steps Tracker · Posición registrada y señal recibida son datos distintos. Control físico pendiente de homologación.</footer></div>;
}
