import {useEffect,useState} from 'react';
import OperationsMap from '../components/OperationsMap';
import FleetHistory from '../components/FleetHistory';
import TrackerIcon from '../components/TrackerIcon';
import ProtectionPage from './ProtectionPage';
import AssetCostsPanel from '../components/AssetCostsPanel';
import {dateLabel,label,type FleetAsset,type FleetContext} from '../services/fleetApi';
import type {DemoVehicle} from '../demo/scenario';
import './MyVehicle.css';

type Tab='live'|'history'|'protection';
const initial=():Tab=>window.location.hash==='#protection'?'protection':window.location.hash==='#history'?'history':'live';
export default function MyVehicle({context,assets,loading,error,refresh}:{context:FleetContext;assets:FleetAsset[];loading:boolean;error:string;refresh:()=>void}){
 const [tab,setTab]=useState<Tab>(initial),[selected,setSelected]=useState('');
 const asset=assets.find(a=>a.asset_id===selected)||assets[0];const p=asset?.last_position;
 useEffect(()=>{const sync=()=>setTab(initial());window.addEventListener('hashchange',sync);return()=>window.removeEventListener('hashchange',sync);},[]);
 const go=(next:Tab)=>{setTab(next);window.location.hash=next;window.scrollTo({top:0});};
 const vehicle:DemoVehicle|null=asset&&p?{id:asset.asset_id,name:asset.name,plate:asset.plate||'',driver:asset.responsible||'',fieldId:'',regionId:'',status:asset.motion_state==='moving'?'working':'paused',progress:0,speedKmh:p.speed_kmh||0,fuelPct:0,engineHours:0,distanceKm:0,coveredHa:0,position:{lat:p.lat,lon:p.lon},bearing:0}:null;
 return <div className="fleet-app my-vehicle">
  <header className="my-vehicle-header"><a className="fleet-brand" href="#live"><b><TrackerIcon name="live" size={24}/></b><span>Steps <strong>Tracker</strong></span></a><div><strong>{context.user}</strong><small>{context.company}</small></div><a href="/web/session/logout?redirect=/web/login" aria-label="Cerrar sesión">Salir</a></header>
  <main>
   {error&&<p role="alert" className="fleet-error">{error}<button onClick={refresh}>Reintentar</button></p>}
   {loading&&!asset?<p role="status">Cargando tu vehículo…</p>:!asset?<section className="my-vehicle-empty"><TrackerIcon name="fleet" size={40}/><h1>Tu acceso está preparado</h1><p>Un administrador debe asignarte un vehículo en Acceso Tracker.</p><button onClick={refresh}>Actualizar</button></section>:<>
    <section className="my-vehicle-title"><div><span className="fleet-eyebrow">MI VEHÍCULO</span><h1>{asset.plate||asset.name}</h1><p>{label(asset.motion_state)} · {label(asset.protection_state)}</p></div>{assets.length>1&&<label>Vehículo<select value={asset.asset_id} onChange={e=>setSelected(e.target.value)}>{assets.map(a=><option key={a.asset_id} value={a.asset_id}>{a.plate||a.name}</option>)}</select></label>}<button onClick={refresh} aria-label="Actualizar ubicación"><TrackerIcon name="signal" size={20}/></button></section>
    {tab==='protection'?<ProtectionPage key={asset.asset_id} context={context} assets={[asset]} selected={asset.asset_id} demo={false} refresh={refresh} demoStore={{incidents:[],policies:[]}} onDemoChange={()=>{}}/>:<>
     <section className="my-vehicle-map" aria-label="Mapa de mi vehículo">{vehicle?<OperationsMap fields={[]} vehicles={[vehicle]} markerLabels={{[asset.asset_id]:asset.position_stale?'Última posición · '+dateLabel(p?.recorded_at):label(asset.motion_state)}} markerTypes={{[asset.asset_id]:asset.type}} selectedVehicleId={asset.asset_id} onSelectVehicle={()=>{}} showRows={false} showRoadRoute={false} depot={vehicle.position} followVehicle={true}/>:<div className="my-vehicle-empty"><TrackerIcon name="signal" size={40}/><h2>Esperando señal del GPS</h2><p>La ubicación aparecerá cuando el equipo transmita. No necesitas iniciar una jornada.</p></div>}</section>
     <section className="my-vehicle-status" aria-live="polite"><div><span className={'fleet-state fleet-state--'+asset.signal_state}>{label(asset.signal_state)}</span><strong>{asset.position_stale?'Última ubicación conocida':'Ubicación del GPS'}</strong><small>{dateLabel(p?.recorded_at)}</small></div><div className="my-vehicle-speed"><strong>{p?.speed_kmh!=null&&!asset.position_stale?Math.round(p.speed_kmh):'—'}</strong><small>km/h</small></div></section>
     <section className="my-vehicle-actions"><button className="fleet-primary" onClick={()=>go('history')}><TrackerIcon name="fleet"/>Ver recorridos</button><button onClick={()=>go('protection')}><TrackerIcon name="protection"/>Protección</button></section>
     <details className="my-vehicle-data"><summary>Equipo y última recepción</summary><dl><dt>Equipo</dt><dd>{asset.device?asset.device.brand+' '+asset.device.model:'Sin GPS asociado'}</dd><dt>Recibido por Steps</dt><dd>{dateLabel(p?.received_at)}</dd><dt>Contacto ACC</dt><dd>{p?.acc==null?'No informado':p.acc?'Encendido':'Apagado'}</dd><dt>Alimentación externa</dt><dd>{p?.external_power==null?'No informada':p.external_power?'Conectada':'Desconectada'}</dd></dl></details>
     <details className="my-vehicle-data"><summary>Costos de mi vehículo</summary><AssetCostsPanel assetId={asset.asset_id}/></details>
    </>}
    {tab==='history'&&<FleetHistory asset={asset} context={context} demo={false} onClose={()=>go('live')}/>}
   </>}
  </main>
  <nav className="my-vehicle-nav" aria-label="Mi Tracker">{([['live','Mi vehículo'],['history','Recorridos'],['protection','Protección']] as const).map(([key,text])=><button key={key} aria-current={tab===key?'page':undefined} onClick={()=>go(key)}><TrackerIcon name={key==='history'?'fleet':key} size={22}/><span>{text}</span></button>)}</nav>
 </div>;
}
