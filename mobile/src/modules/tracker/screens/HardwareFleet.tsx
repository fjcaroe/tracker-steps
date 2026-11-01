import { useEffect, useRef, useState } from 'react';
import MapView, {type MapMarker} from '../components/MapView';
import {FleetAccessError,loadHardwareFleet,recentPosition,type HardwareFleet as Fleet} from '../lib/fleet';
import type {LatLon} from '../lib/nav';

const when=(stamp:string)=>new Date(stamp).toLocaleString('es-CL',{dateStyle:'short',timeStyle:'medium'});
/** Read-only hardware GPS; never starts a journey, geolocation watcher or sync queue. */
export default function HardwareFleet({onBack}:{onBack:()=>void}) {
 const [fleet,setFleet]=useState<Fleet|null>(null),[error,setError]=useState(''),[access,setAccess]=useState(false),[busy,setBusy]=useState(true),[tick,setTick]=useState(0),[focus,setFocus]=useState<LatLon|null>(null);
 const previousScope=useRef('');
 useEffect(()=>{
  let active=true,pending=false;let controller:AbortController|null=null;
  const load=async()=>{
   if(pending||document.visibilityState==='hidden')return;
   pending=true;controller=new AbortController();
   try {
    const result=await loadHardwareFleet(controller.signal);
    if(active){const scope=result.tenant_id+':'+result.user_id;if(previousScope.current!==scope)setFocus(null);previousScope.current=scope;setFleet(result);setError('');setAccess(false);}
   }catch(e){if(active&&(e as Error).name!=='AbortError'){setError((e as Error).message);if(e instanceof FleetAccessError){setFleet(null);setFocus(null);previousScope.current='';setAccess(true);}}}
   finally{pending=false;if(active)setBusy(false);}
  };
  const update=()=>{if(document.visibilityState!=='hidden')void load();else {controller?.abort();setFleet(null);setFocus(null);}};
  void load();const timer=setInterval(()=>void load(),10000);
  window.addEventListener('online',update);document.addEventListener('visibilitychange',update);
  return()=>{active=false;controller?.abort();clearInterval(timer);window.removeEventListener('online',update);document.removeEventListener('visibilitychange',update);};
 },[tick]);
 const installations=fleet?.installations||[];
 const testingAssets=new Set(installations.flatMap(d=>d.asset_id?[d.asset_id]:[]));
 const vehicles=(fleet?.items||[]).filter(a=>!testingAssets.has(a.asset_id));
 const hasFix=(d:(typeof installations)[number])=>d.mode==='capture'&&!!d.fix_at&&d.lat!==null&&d.lon!==null&&Number.isFinite(d.lat)&&Number.isFinite(d.lon);
 const freshFix=(d:(typeof installations)[number])=>!error&&hasFix(d)&&Date.now()-Date.parse(d.fix_at!)<300000&&Date.now()-Date.parse(d.fix_received_at||'')<300000;
 const markers:MapMarker[]=[...vehicles.flatMap(a=>a.last_position?[{lat:a.last_position.lat,lon:a.last_position.lon,kind:(!error&&recentPosition(a)?'machine':'stale') as MapMarker['kind'],label:a.name+' · '+(a.plate||'Sin patente')+' · '+when(a.last_position.recorded_at)+(!error&&recentPosition(a)?'':' · Posición antigua / sin actualización')}]:[]),...installations.flatMap(d=>hasFix(d)?[{lat:d.lat!,lon:d.lon!,kind:(freshFix(d)?'test':'stale') as MapMarker['kind'],label:d.label+' · GPS en prueba · '+when(d.fix_at!)}]:[])];
 return <section className="stack hardware-fleet"><button className="link" onClick={onBack}>‹ Volver a Tracker</button><div className="row"><h1>Autos y equipos GPS</h1><button onClick={()=>{setBusy(true);setTick(n=>n+1);}} disabled={busy}>Actualizar</button></div><p>Ubicación enviada por el GPS del vehículo. Funciona sin iniciar una jornada en el teléfono.</p>{fleet&&<p><strong>{fleet.tenant}</strong><br/><small>Consulta: {when(fleet.generated_at)} · Actualiza cada 10 segundos</small></p>}{busy&&!fleet&&<p role="status">Consultando flota…</p>}{error&&<div className="error" role="alert"><p>{error}</p>{access?<a className="btnlink" href={'/web/login?redirect='+encodeURIComponent('/truck/#gps')}>Entrar con Odoo</a>:<p>Las ubicaciones visibles corresponden a la última consulta. No confirman movimiento actual.</p>}</div>}{fleet&&<><MapView key={fleet.tenant_id+':'+fleet.user_id} markers={markers} focus={focus} height={360}/>{fleet.total>fleet.items.length&&<p className="muted">Se muestran {fleet.items.length} de {fleet.total} vehículos. Consulta la flota completa en la web.</p>}{!fleet.items.length&&!installations.length&&<p className="card" role="status">Todavía no hay vehículos registrados en esta compañía. Agrega los GPS y asócialos a sus vehículos en Configuración de Tracker.</p>}{fleet.installation_error&&<p className="error" role="alert">{fleet.installation_error}</p>}{installations.length>0&&<section className="stack gps-installation" aria-label="GPS en prueba"><h2>GPS en prueba ({installations.length})</h2><p>Ubicaciones de diagnóstico. El seguimiento del vehículo se activa después de asociarlo y validar la instalación.</p>{installations.map(d=><article className="card stack" key={d.id}><div className="row"><h3>{d.label}</h3><span className="chip">{d.asset_name||'Sin vehículo asociado'}</span></div><strong>{d.mode==='disabled'?'Recepción deshabilitada':hasFix(d)?(freshFix(d)?'Posición GPS recibida en prueba':'Posición de prueba antigua'):d.last_seen_at?'Equipo comunica · esperando posición GPS':'Esperando contacto del GPS'}</strong><small>Último contacto: {d.last_seen_at?when(d.last_seen_at):'Sin recepción todavía'}</small>{hasFix(d)&&<><small>Posición: {when(d.fix_at!)}<br/>Recibida: {d.fix_received_at?when(d.fix_received_at):'Sin dato'}</small><p>{d.lat!.toFixed(6)}, {d.lon!.toFixed(6)}</p><button onClick={()=>setFocus({lat:d.lat!,lon:d.lon!})}>Ver {d.label} en el mapa</button></>}<a className="btnlink" href="/web_tracker/#settings">Asociar vehículo y validar seguimiento</a></article>)}</section>}{vehicles.map(a=>{const p=a.last_position,fresh=!error&&recentPosition(a);return <article className="card stack" key={a.asset_id}><div className="row"><h2>{a.name}</h2><span className="chip">{a.plate||'Sin patente'}</span></div><strong>{p?(fresh?(a.motion_state==='moving'?'En movimiento':'Señal reciente'):'Última posición · sin señal reciente'):'Esperando primera posición GPS'}</strong>{p?<><small>Posición: {when(p.recorded_at)}<br/>Recibida: {when(p.received_at)}</small><p>{p.lat.toFixed(6)}, {p.lon.toFixed(6)}{fresh&&p.speed_kmh!=null?' · '+p.speed_kmh.toFixed(1)+' km/h':''}</p><button onClick={()=>setFocus({lat:p.lat,lon:p.lon})}>Ver {a.name} en el mapa</button></>:<p className="muted">{a.device?'Comprueba alimentación, cobertura y configuración del GPS.':'Asocia un GPS a este vehículo desde la web de Tracker.'}</p>}</article>;})}</>}</section>;
}
