import {useEffect,useState} from 'react';
import OperationsMap from '../components/OperationsMap';
import FleetHistory from '../components/FleetHistory';
import StarterControl from '../components/StarterControl';
import TrackerIcon from '../components/TrackerIcon';
import ProtectionPage from './ProtectionPage';
import AssetCostsPanel from '../components/AssetCostsPanel';
import TrackerCompanySelector from '../components/TrackerCompanySelector';
import {dateLabel,label,type FleetAsset,type FleetContext} from '../services/fleetApi';
import type {DemoVehicle} from '../demo/scenario';
import './MyVehicle.css';

type Tab='live'|'history'|'protection';
const initial=():Tab=>window.location.hash==='#protection'?'protection':window.location.hash==='#history'?'history':'live';
const selectedFromUrl=()=>new URLSearchParams(window.location.search).get('asset')||'';
export default function MyVehicle({context,assets,loading,error,refresh,onAdministration}:{context:FleetContext;assets:FleetAsset[];loading:boolean;error:string;refresh:()=>void;onAdministration?:()=>void}){
 const [tab,setTab]=useState<Tab>(initial),[selected,setSelected]=useState(selectedFromUrl),[mapRevision,setMapRevision]=useState(0),[alertsOpen,setAlertsOpen]=useState(false);
 const asset=assets.find(a=>a.asset_id===selected)||assets[0],p=asset?.last_position;
 useEffect(()=>{const sync=()=>{setTab(initial());setSelected(selectedFromUrl());};window.addEventListener('hashchange',sync);window.addEventListener('popstate',sync);return()=>{window.removeEventListener('hashchange',sync);window.removeEventListener('popstate',sync);};},[]);
 useEffect(()=>{if(!asset)return;const url=new URL(window.location.href);url.searchParams.set('asset',asset.asset_id);window.history.replaceState(window.history.state,'',url);},[asset?.asset_id]);
 const go=(next:Tab)=>{setTab(next);window.location.hash=next;window.scrollTo({top:0});};
 const changeVehicle=(id:string)=>{setSelected(id);setAlertsOpen(false);const url=new URL(window.location.href);url.searchParams.set('asset',id);window.history.replaceState(window.history.state,'',url);};
 const vehicle:DemoVehicle|null=asset&&p?{id:asset.asset_id,name:asset.plate||asset.name,plate:asset.plate||'',driver:asset.responsible||'',fieldId:'',regionId:'',status:asset.motion_state==='moving'?'working':'paused',progress:0,speedKmh:p.speed_kmh||0,fuelPct:0,engineHours:0,distanceKm:0,coveredHa:0,position:{lat:p.lat,lon:p.lon},bearing:0}:null;
 const fresh=!!p&&!asset?.position_stale&&!error;
 return <div className="fleet-app my-vehicle">
  <header className="my-vehicle-header"><a className="fleet-brand" href={context.vehicle_limited?"#live":"#home"} aria-label="Steps Tracker Inicio"><b><TrackerIcon name="live" size={25}/></b><span>Steps <strong>Tracker</strong></span></a><details className="my-vehicle-account"><summary aria-label="Mi cuenta"><TrackerIcon name="user" size={21}/></summary><div><strong>{context.user}</strong><small>{context.company}</small><a href="/web/session/logout?redirect=/tracker" aria-label="Cerrar sesión">Cerrar sesión <TrackerIcon name="logout" size={17}/></a></div></details></header>
  <main>
   <div className="my-vehicle-topline"><span className="fleet-eyebrow">{tab==='live'?'TU CAMINO, CONECTADO':tab==='history'?'CADA RECORRIDO, EN EL MAPA':'TU VEHÍCULO, BAJO CONTROL'}</span>{onAdministration&&<button className="my-vehicle-admin" onClick={onAdministration}><TrackerIcon name="settings" size={16}/>Administrar flota</button>}</div>
   <div hidden={Boolean(asset)}><TrackerCompanySelector context={context}/></div>
   {error&&<p role="alert" className="fleet-error">{error} <button onClick={refresh}>Reintentar</button></p>}
   {loading&&!asset?<div className="my-vehicle-empty" role="status"><TrackerIcon name="signal" size={32}/><h1>Preparando tu vehículo…</h1></div>:!asset?<section className="my-vehicle-empty"><TrackerIcon name="fleet" size={40}/><h1>Tu acceso está preparado</h1><p>Revisa la compañía activa o solicita al administrador que asigne tu vehículo.</p><button onClick={refresh}>Actualizar</button></section>:<>
    <section className="my-vehicle-title"><div><h1>{tab==='history'?'Tus recorridos':tab==='protection'?'Control de arranque':asset.plate||asset.name}</h1><p>{tab==='live'?label(asset.type)+' · '+(asset.name===asset.plate?'GPS del vehículo':asset.name):(asset.plate||asset.name)+' · '+label(asset.type)}</p></div>{tab==='live'&&<span className={'my-signal '+(fresh?'is-recent':'is-old')}><i/>{fresh?'Señal reciente':'Sin señal reciente'}</span>}</section>
    {assets.length>1&&<label className="my-vehicle-picker"><TrackerIcon name="fleet" size={21}/><span>Vehículo<select aria-label="Vehículo seleccionado" value={asset.asset_id} onChange={e=>changeVehicle(e.target.value)}>{assets.map(a=><option key={a.asset_id} value={a.asset_id}>{a.plate||a.name}{a.plate&&a.name!==a.plate?' · '+a.name:''}</option>)}</select></span><small>{assets.length} disponibles</small></label>}
    {tab==='live'&&<>
     <section className="my-vehicle-map" aria-label="Mapa de mi vehículo"><div className="my-map-toolbar"><span><i/>{fresh?'Ubicación del GPS':'Última ubicación conocida'}</span><button onClick={()=>{refresh();setMapRevision(n=>n+1);}} aria-label="Centrar y actualizar ubicación"><TrackerIcon name="locate" size={20}/></button></div>{vehicle?<OperationsMap mapType="roadmap" singleVehicleZoom={16} gestureHandling="cooperative" key={asset.asset_id+':'+mapRevision} fields={[]} vehicles={[vehicle]} markerLabels={{[asset.asset_id]:fresh?label(asset.motion_state):'Última posición · '+dateLabel(p?.recorded_at)}} markerTypes={{[asset.asset_id]:asset.type}} selectedVehicleId={asset.asset_id} onSelectVehicle={()=>{}} showRows={false} showRoadRoute={false} depot={vehicle.position} followVehicle={true}/>:<div className="my-vehicle-empty"><TrackerIcon name="signal" size={40}/><h2>Esperando señal del GPS</h2><p>La ubicación aparecerá cuando el equipo transmita.</p><button onClick={refresh}>Actualizar ubicación</button></div>}</section>
     <section className="my-vehicle-status" aria-live="polite"><div><strong>{fresh?label(asset.motion_state):'Última posición registrada'}</strong><small>{dateLabel(p?.recorded_at)}</small></div><div className="my-vehicle-speed"><strong>{p?.speed_kmh!=null&&fresh?Math.round(p.speed_kmh):'—'}</strong><small>km/h</small></div></section>
     <div className="my-vehicle-telemetry"><div><TrackerIcon name="power" size={18}/><span>Alimentación<strong>{p?.external_power==null?'Sin dato':p.external_power?'Conectada':'Desconectada'}</strong></span></div><div><TrackerIcon name="key" size={18}/><span>Contacto ACC<strong>{p?.acc==null?'Sin dato':p.acc?'Encendido':'Apagado'}</strong></span></div></div>
     {!fresh&&p&&<p className="my-vehicle-note">Esta ubicación es anterior. Esperamos una nueva transmisión para actualizar el movimiento y la velocidad.</p>}
     <section className="my-vehicle-actions" aria-label="Acciones del vehículo"><button onClick={()=>go('history')}><b><TrackerIcon name="history" size={23}/></b><span><strong>Ver recorridos</strong><small>Explora por fecha</small></span><TrackerIcon name="chevron" size={18}/></button><button onClick={()=>go('protection')}><b><TrackerIcon name="lock" size={23}/></b><span><strong>Control de arranque</strong><small>Bloquear o restituir</small></span><TrackerIcon name="chevron" size={18}/></button></section>
     <details className="my-vehicle-data"><summary>Detalles del GPS <TrackerIcon name="plus" size={17}/></summary><dl><dt>Equipo</dt><dd>{asset.device?asset.device.brand+' '+asset.device.model:'Sin GPS asociado'}</dd><dt>Recibido por Steps</dt><dd>{dateLabel(p?.received_at)}</dd><dt>Alertas de protección</dt><dd>{label(asset.protection_state)}</dd></dl></details>
     <details className="my-vehicle-data"><summary>Costos del vehículo <TrackerIcon name="plus" size={17}/></summary><AssetCostsPanel assetId={asset.asset_id}/></details>
    </>}
    {tab==='history'&&<FleetHistory key={asset.asset_id} embedded asset={asset} context={context} demo={false} onClose={()=>go('live')}/>}
    {tab==='protection'&&<><StarterControl key={asset.asset_id} asset={asset} context={context}/><details className="my-vehicle-data my-alerts" open={alertsOpen} onToggle={e=>setAlertsOpen(e.currentTarget.open)}><summary><span>Alertas e incidentes<small>Armar alertas, revisar avisos y registrar pruebas</small></span><TrackerIcon name="plus" size={19}/></summary>{alertsOpen&&<ProtectionPage key={asset.asset_id} includeStarter={false} context={context} assets={[asset]} selected={asset.asset_id} demo={false} refresh={refresh} demoStore={{incidents:[],policies:[]}} onDemoChange={()=>{}}/>}</details></>}
   </>}
  </main>
  <nav className="my-vehicle-nav" aria-label="Mi Tracker">{([['live','Vehículo','fleet'],['history','Recorridos','history'],['protection','Arranque','lock']] as const).map(([key,text,icon])=><button key={key} aria-current={tab===key?'page':undefined} onClick={()=>go(key)}><TrackerIcon name={icon} size={23}/><span>{text}</span></button>)}</nav>
 </div>;
}
