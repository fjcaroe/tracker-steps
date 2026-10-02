import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
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
import './TrackerHome.css';
import FleetHome from './FleetHome';
import FleetZones from './FleetZones';
import { useFleetZones } from '../hooks/useFleetZones';
import FleetSettings from './FleetSettings';
import FleetAssetEditor, { type AssetDetails } from '../components/FleetAssetEditor';
import FleetHistory from '../components/FleetHistory';
import TrackerIcon from '../components/TrackerIcon';
import type { TokenOut } from '../services/auth';
import { exportFleet } from '../services/fleetExport';
import type { Configuration } from '../services/fleetConfiguration';
import type { FleetFilters as Filters } from '../services/fleetApi';

const ClassicApp = lazy(() => import('../ClassicApp'));
type View = 'home' | 'live' | 'fleet' | 'protection' | 'settings' | 'zones' | 'ops';
const initialPreference: ViewPreference = { schema_version: 1, columns: defaultColumns, filters: emptyFilters, sort: 'name' };
// Enlace profundo ?asset=<id>: lo usan la ficha del vehículo en Odoo y el regreso desde Odoo para conservar la selección.
function assetFromQuery(): string | null { const id = new URLSearchParams(window.location.search).get('asset'); return id && /^[0-9a-fA-F-]{8,64}$/.test(id) ? id : null; }
function viewFromHash(): View { const hash = window.location.hash.slice(1); return ['live','fleet','protection','settings','zones','ops'].includes(hash) ? hash as View : 'home'; }
function syntheticAssets(): FleetAsset[] {
  return getDemoVehicles(0).map((v, i) => ({ asset_id: v.id, name: ['Auto comercial','Camioneta de servicio','Camión de reparto','Furgón de soporte','Tractor de campo','Equipo de faena'][i%6]+' '+String(Math.floor(i/6)+1).padStart(2,'0'), plate: v.plate, type: ['car','pickup','truck','van','tractor','machinery'][i%6], cost_center: DEMO_FIELDS.find(f => f.id === v.fieldId)?.name || null, responsible: v.driver,
    created_at: '2026-01-15T12:00:00Z', signal_state: i === 1 ? 'stale' : i === 2 ? 'no_signal' : 'received', motion_state: i === 1 || i === 2 ? 'unknown' : 'moving', position_stale: i === 1 || i === 2, protection_state: 'disarmed',
    last_position: i === 2 ? null : { id: v.id, recorded_at: new Date(Date.now()-(i === 1 ? 7200000 : 15000)).toISOString(), received_at: new Date(Date.now()-(i === 1 ? 7200000 : 10000)).toISOString(), lat: v.position.lat, lon: v.position.lon, speed_kmh: v.speedKmh, quality: 'gps', acc: true, external_power: true },
    device: { brand: 'Simulado', model: '401C · demo', firmware: null, protocol: null }, capabilities: { tracking: 'not_approved', remote_start_inhibit: 'not_approved' } }));
}

export default function FleetWorkspace() {
  const [context, setContext] = useState<FleetContext | null>(null);
  const [contextError, setContextError] = useState('');
  const [view, setView] = useState<View>(viewFromHash);
  const [demo, setDemo] = useState(false);
  const zoneStore = useFleetZones(context, demo);
  const [selectedZone, setSelectedZone] = useState('');
  const [selected, setSelected] = useState<string | null>(assetFromQuery);
  const [preference, setPreference] = useState<ViewPreference>(initialPreference);
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);
  const [demoStore, setDemoStore] = useState<DemoProtection>({ incidents: [], policies: [] });
  const { assets, error, loading, refresh } = useFleetSnapshot(context, demo);
  const [demoAssets, setDemoAssets] = useState(syntheticAssets);
  const [editor,setEditor]=useState<FleetAsset|'new'|null>(null);
  const [history,setHistory]=useState<FleetAsset|null>(null);
  const [configuration,setConfiguration]=useState<Configuration|null>(null);
  const [configError,setConfigError]=useState('');
  const [configLoading,setConfigLoading]=useState(false);
  const [configTick,setConfigTick]=useState(0);
  const source = useMemo(() => demo ? demoAssets.map(a => ({ ...a, protection_state: demoStore.incidents.some(i => i.asset_id === a.asset_id && i.state !== 'closed') ? 'incident_open' as const : demoStore.policies.some(p => p.asset_id === a.asset_id && p.armed) ? 'armed' as const : 'disarmed' as const })) : assets, [demo, demoAssets, demoStore, assets]);
  const filtered = useMemo(() => filterFleet(source, preference.filters).sort((a,b) => String(a[preference.sort]).localeCompare(String(b[preference.sort]))), [source, preference]);
  const current = filtered.find(a => a.asset_id === selected);
  const demoKey = `tracker:demo:${context?.tenant_key}:${context?.user_id}:fleet:v1`;
  useEffect(() => {
    // Sin sesión Odoo, Odoo responde con una redirección al login: se va directo a él.
    fetch('/steps_tracker/context', { credentials: 'same-origin', redirect: 'manual', headers: { Accept: 'application/json' } })
      .then(r => { if (r.type === 'opaqueredirect' || r.status === 302 || r.status === 303) { window.location.replace('/web/login?redirect=' + encodeURIComponent(window.location.pathname + window.location.search + window.location.hash)); return null; } return portalRequest<FleetContext>('/steps_tracker/context').then(setContext); })
      .catch(e => setContextError(e.message));
  }, []);
  useEffect(() => { if (demo) return; const url = new URL(window.location.href); if (selected) url.searchParams.set('asset', selected); else url.searchParams.delete('asset'); window.history.replaceState(window.history.state, '', url); }, [selected, demo]);
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
  useEffect(() => {
    if (!context || context.role !== 'manager' || demo) return;
    let active = true;
    const load = async () => {
      setConfigLoading(true);
      try { const r = await fleetRequest<Configuration>('configuration',context); if(active){setConfiguration(r);setConfigError('');} }
      catch(e){if(active)setConfigError((e as Error).message);}
      finally{if(active)setConfigLoading(false);}
    };
    void load(); const timer=setInterval(() => void load(),60000);
    return () => {active=false;clearInterval(timer);};
  },[context,demo,configTick]);
  const onFilter=(filters:Partial<Filters>,next:View='fleet')=>{setPreference(p=>({...p,filters:{...emptyFilters,...filters}}));navigate(next);};
  const savedAsset=(id:string,data:AssetDetails)=>{
    if(demo)setDemoAssets(previous=>previous.some(a=>a.asset_id===id)?previous.map(a=>a.asset_id===id?{...a,...data}:a):[...previous,{...data,asset_id:id,created_at:new Date().toISOString(),position_stale:true,signal_state:'no_signal',motion_state:'unknown',protection_state:'disarmed',last_position:null,device:null,capabilities:{tracking:'not_approved',remote_start_inhibit:'not_approved'}}]);
    else refresh();
    setSelected(id);setEditor(null);setNotice(demo?'Registro actualizado en la demostración.':'Ficha guardada. Puedes asociar su GPS desde Configuración.');setPreference(p=>({...p,filters:emptyFilters}));navigate('fleet');
  };
  const navigate = (v: View) => { window.location.hash = v; setView(v); window.scrollTo({top:0}); };
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
  const markerLabels = Object.fromEntries(filtered.map(a => [a.asset_id, a.position_stale ? 'Posición antigua · '+(a.last_position ? new Date(a.last_position.recorded_at).toLocaleString('es-CL') : 'Sin dato') : a.motion_state === 'unknown' ? 'Movimiento desconocido' : `${a.last_position?.speed_kmh?.toFixed(1) ?? '—'} km/h`]));
  if (!context) return <main className="fleet-app tracker-login"><div className="tracker-home-card"><span className="fleet-eyebrow">STEPS TRACKER</span><h1>Tu flota, siempre cerca.</h1>{contextError ? <><p role="alert">{contextError}</p><a href="/web/login?redirect=/web_tracker/">Entrar con Odoo →</a></> : <p role="status">Cargando tu compañía y permisos…</p>}</div></main>;
  const title = {home:'Tu centro de movilidad',live:'Tu flota en el mapa',fleet:'Vehículos y equipos',protection:'Steps Protección',settings:'Configuración y ayuda',zones:'Zonas y actividad',ops:'Operación'}[view];
  const detail = <FleetAssetDetail asset={current} onProtect={() => navigate('protection')} onEdit={context.role === 'manager' ? () => current && setEditor(current) : undefined} onHistory={() => current && setHistory(current)} onConfigure={() => navigate('settings')} costs={!demo}/>;
  if (view === 'ops') return <Suspense fallback={<p role="status">Cargando operación…</p>}><ClassicApp onExit={() => navigate('home')} exchange={() => portalRequest<TokenOut>('/steps_tracker/classic-session', context, 'POST')}/></Suspense>;
  return <div className="fleet-app">
    <header className="fleet-header"><a className="fleet-brand" href="#home" aria-label="Steps Tracker Inicio"><b><TrackerIcon name="live" size={25}/></b><span>Steps <strong>Tracker</strong></span></a><div className="fleet-identity"><strong>{context.company}</strong><span>{context.user}</span></div><a className="tracker-odoo-link" href="/odoo">Odoo ↗</a></header>
    <nav className="fleet-nav" aria-label="Áreas Tracker">{([['home','Inicio'],['live','Mapa'],['fleet','Flota'],['zones','Zonas'],['protection','Protección'],['ops','Operación'],['settings','Configuración']] as const).map(([key,text]) => <button key={key} aria-current={view === key ? 'page' : undefined} onClick={() => navigate(key)}><TrackerIcon name={key} size={19}/><span>{text}</span></button>)}</nav>
    <main><div className="fleet-heading"><div><span className="fleet-eyebrow">{demo ? 'ESPACIO DE DEMOSTRACIÓN' : 'GPS · MOVILIDAD · PROTECCIÓN'}</span>{view === 'home' ? <p className="tracker-welcome">Hola, {context.user.split(' ')[0]}. Este es el estado de tu flota.</p> : <h1>{title}</h1>}</div><label className="fleet-demo"><input type="checkbox" checked={demo} onChange={e => {setDemo(e.target.checked);setSelected(null);setSelectedZone('');setNotice('');}}/>Explorar demo</label></div>
    {demo && <div className="fleet-notice"><strong>Demostración sintética</strong><span>Vehículos y acciones de ejemplo. No modifican tu flota real ni actúan sobre GPS.</span></div>}
    {view === 'live' && zoneStore.error && <p className="fleet-error" role="alert">No se pudieron actualizar las zonas. <button onClick={zoneStore.refresh}>Reintentar</button></p>}
    {notice && <p className="fleet-notice" role="status">{notice}<button aria-label="Cerrar aviso" onClick={() => setNotice('')}>×</button></p>}
    {!demo && error && <p role="alert" className="fleet-error">{error} <button onClick={refresh}>Reintentar</button></p>}
    {view === 'home' && !demo && configuration && configuration.reminders.length > 0 && <button className="tracker-reminder-banner" onClick={() => navigate('settings')}><TrackerIcon name="signal"/><span><strong>{configuration.reminders.length} recordatorios de conectividad</strong>Revisa recargas, datos y vigencia de tus líneas.</span><TrackerIcon name="arrow"/></button>}
    {view === 'home' && !demo && configError && <p className="fleet-error" role="alert">No pudimos consultar los recordatorios de SIM. <button onClick={() => setConfigTick(n => n+1)}>Reintentar</button></p>}
    {view === 'zones' ? <FleetZones initialZoneId={selectedZone} key={`${demo}:${context.tenant_key}`} context={context} assets={source} zones={zoneStore.zones} error={zoneStore.error} refresh={zoneStore.refresh} save={zoneStore.save} demo={demo}/> : view === 'settings' ? <FleetSettings context={context} assets={source} configuration={configuration} error={configError} loading={configLoading} refresh={() => {setConfigTick(n => n+1);refresh();}} demo={demo}/> :
    !demo && loading ? <p role="status">Cargando flota…</p> :
    view === 'home' ? <FleetHome assets={source} context={context} demo={demo} navigate={navigate} onCreate={() => setEditor('new')} onImport={() => void importFleet()} onFilter={onFilter} busy={saving}/> :
    <><FleetFilters assets={source} value={preference.filters} onChange={filters => setPreference(p => ({...p,filters}))}/>
      <div className="fleet-metrics" aria-live="polite"><span><strong>{filtered.length}</strong> Vehículos y equipos</span><span><strong>{filtered.filter(a => a.signal_state === 'received').length}</strong> Señal reciente</span><span><strong>{filtered.filter(a => a.signal_state !== 'received').length}</strong> Sin señal reciente</span><span><strong>{filtered.filter(a => a.protection_state === 'incident_open').length}</strong> Con incidentes</span></div>
      <div className="fleet-toolbar"><label>Ordenar<select value={preference.sort} onChange={e => setPreference(p => ({...p,sort:e.target.value as ViewPreference['sort']}))}><option value="name">Nombre</option><option value="created_at">Fecha de alta</option><option value="signal_state">Estado de señal</option></select></label><button disabled={saving} onClick={() => void save()}>Guardar vista</button><button onClick={refresh} disabled={demo}>Actualizar</button><button disabled={!filtered.length} onClick={() => exportFleet(filtered,demo)}>Exportar CSV</button>{context.role === 'manager' && <button className="fleet-primary" onClick={() => setEditor('new')}>+ Registrar vehículo</button>}{context.role === 'manager' && !demo && <button disabled={saving} onClick={() => void importFleet()}>Sincronizar Odoo</button>}{view === 'fleet' && <details className="fleet-columns"><summary>Columnas</summary>{Object.entries(columnLabels).map(([key,text]) => <label key={key}><input type="checkbox" checked={preference.columns.includes(key)} disabled={key === 'name'} onChange={e => setPreference(p => ({...p,columns:e.target.checked ? [...p.columns,key] : p.columns.filter(c => c !== key)}))}/>{text}</label>)}</details>}</div>
      {!filtered.length && <div className="fleet-empty"><h2>{source.length ? 'No hay coincidencias' : 'Tu flota empieza aquí'}</h2><p>{source.length ? 'Ajusta los filtros para ver otros vehículos.' : 'Registra un vehículo o sincroniza tu flota desde Odoo. Luego asocia su GPS en Configuración.'}</p>{source.length > 0 && <button onClick={() => setPreference(p => ({...p,filters:emptyFilters}))}>Ver toda la flota</button>}</div>}
      {view === 'protection' ? <ProtectionPage key={`${demo}:${context.tenant_key}`} context={context} assets={filtered} selected={selected} demo={demo} refresh={refresh} demoStore={demoStore} onDemoChange={setDemoStore}/> :
      view === 'fleet' ? <div className="fleet-control-layout"><FleetTable assets={filtered} columns={preference.columns} selected={selected} onSelect={setSelected}/>{detail}</div> :
      <div className="fleet-operation-layout"><FleetList assets={filtered} selected={selected} onSelect={setSelected}/><section className="fleet-map" aria-label="Mapa de última posición"><div className="fleet-map-caption">{mapVehicles.length} posiciones · {zoneStore.zones.filter(z => z.active).length} zonas · los datos antiguos se indican en cada marcador</div>{(mapVehicles.length > 0 || zoneStore.zones.some(z => z.active)) ? <OperationsMap zones={zoneStore.zones.filter(z => z.active)} onSelectZone={id => {setSelectedZone(id);navigate('zones');}} fields={demo ? DEMO_FIELDS : []} vehicles={mapVehicles} markerLabels={markerLabels} markerTypes={Object.fromEntries(filtered.map(a => [a.asset_id,a.type]))} selectedVehicleId={selected} onSelectVehicle={setSelected} showRows={false} showRoadRoute={false} depot={mapVehicles[0]?.position || REGIONS[0].depot} followVehicle={false}/> : <div className="fleet-empty"><TrackerIcon name="live" size={42}/><h2>Esperando la primera posición</h2><p>Tu flota ya puede administrarse. Un GPS asociado y conectado habilitará el mapa.</p><button onClick={() => navigate('settings')}>Ver guía de conexión</button></div>}</section>{detail}</div>}
    </>}</main>
    <footer className="fleet-footer"><strong>Steps Tracker</strong><span>GPS para personas, empresas y operaciones.</span><button onClick={() => navigate('settings')}>Ayuda y configuración →</button></footer>
    {editor && <FleetAssetEditor asset={editor === 'new' ? undefined : editor} context={context} demo={demo} onClose={() => setEditor(null)} onSaved={savedAsset}/>}
    {history && <FleetHistory asset={history} context={context} demo={demo} onClose={() => setHistory(null)}/>}
  </div>;
}
