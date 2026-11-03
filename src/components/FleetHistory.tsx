import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { dateLabel, fleetRequest, type FleetAsset, type FleetContext } from '../services/fleetApi';
import {buildTrail,nextTrailStep,type TrailGap} from '../services/fleetTrail';
import './FleetHistory.css';
import {duration as gpsDuration} from '../services/fleetZones';
import './FleetHistoryEmbedded.css';
import './FleetHistoryGaps.css';
import './FleetTripExpense.css';
import FleetTripExpense from './FleetTripExpense';
const FleetTrailMap=lazy(()=>import('./FleetTrailMap'));
type Position = NonNullable<FleetAsset['last_position']>;
export default function FleetHistory({ asset, context, demo, onClose, embedded=false }: {asset:FleetAsset; context:FleetContext; demo:boolean; onClose:()=>void; embedded?:boolean}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [rows,setRows] = useState<Position[]>([]);
  const [cursor,setCursor] = useState<string|null>(null);
  const [busy,setBusy] = useState(true); const [error,setError] = useState('');
  const [period,setPeriod]=useState(()=>{const start=new Date();start.setHours(0,0,0,0);return {from:embedded?start.getTime():Date.now()-86400000,to:Date.now()};});
  const local=(value:number)=>{const d=new Date(value);return new Date(value-d.getTimezoneOffset()*60000).toISOString().slice(0,16);};
  const [from,setFrom]=useState(()=>local(period.from)),[to,setTo]=useState(()=>local(period.to));
  const [index,setIndex]=useState(0),[playing,setPlaying]=useState(false),[rate,setRate]=useState(750);
  const [pausedGap,setPausedGap]=useState<TrailGap|null>(null);
  const generation=useRef(0);
  const [minimumStop,setMinimumStop]=useState(10),[showStops,setShowStops]=useState(true),[follow,setFollow]=useState(false);
  const [eventPage,setEventPage]=useState(1);
  useEffect(()=>{setEventPage(1);},[minimumStop,period]);
  const trail=useMemo(()=>buildTrail(rows,period.from,period.to),[rows,period]);
  const [preview,setPreview]=useState<{from:number;to:number}|null>(null);
  const mapRef=useRef<HTMLDivElement>(null);
  const shown=useMemo(()=>preview?buildTrail(rows,preview.from,preview.to):trail,[rows,preview,trail]);
  const stops=useMemo(()=>trail.stops.filter(s=>s.minutes>=minimumStop),[trail.stops,minimumStop]);
  const visibleStops=useMemo(()=>showStops?stops:[],[showStops,stops]);
  const point=trail.playback[index];
  const canReplay=trail.playback.length>1&&!trail.onlyParking;
  const load=async(before:string|null=null)=>{
    const token=++generation.current;setBusy(true);setError('');setPlaying(false);setPausedGap(null);setPreview(null);
    try{
      let next=before;const found:Position[]=[];const seen=new Set<string>();
      for(let page=0;page<20;page++){
        const r=await fleetRequest<{items:Position[];next_cursor:string|null}>(`assets/${asset.asset_id}/positions?limit=500&since=${encodeURIComponent(new Date(period.from).toISOString())}&until=${encodeURIComponent(new Date(period.to).toISOString())}${next?'&before='+encodeURIComponent(next):''}`,context);
        if(token!==generation.current)return;
        found.push(...r.items);next=r.next_cursor;if(!next)break;
        if(seen.has(next))throw new Error('La paginación no avanzó. Vuelve a consultar el período.');seen.add(next);
      }
      setRows(previous=>before?[...previous,...found]:found);setCursor(next);if(!before)setIndex(0);
    }catch(e){if(token===generation.current){setError((e as Error).message);setRows([]);setCursor(null);}}
    finally{if(token===generation.current)setBusy(false);}
  };
  useEffect(() => {
    if(!embedded)dialog.current?.showModal();
    if (demo) { setRows(asset.last_position ? [asset.last_position] : []); setBusy(false); return; }
    setRows([]);setCursor(null);void load();
    return () => {generation.current++;};
  },[asset.asset_id,context.tenant_key,context.user_id,context.company_id,demo,period,embedded]);
  useEffect(()=>{if(!playing)return;const timer=setTimeout(()=>{const next=nextTrailStep(trail.playback,trail.gaps,index);if(next.ended){setPlaying(false);return;}if(next.gap){setPlaying(false);setPausedGap(next.gap);return;}setIndex(next.index);},rate);return()=>clearTimeout(timer);},[playing,rate,index,trail]);
  const seek=(next:number)=>{setPlaying(false);setPausedGap(null);setIndex(next);};
  const continueAfterGap=()=>{if(!pausedGap)return;const next=trail.playback.findIndex(p=>p.id===pausedGap.after.id);setPausedGap(null);if(next>=0){setIndex(next);setPlaying(true);}};
  const togglePlayback=()=>{if(pausedGap){continueAfterGap();return;}if(index===trail.playback.length-1)setIndex(0);setPlaying(v=>!v);};
  const apply=(event:React.FormEvent)=>{event.preventDefault();const start=Date.parse(from),end=Date.parse(to);if(!Number.isFinite(start)||!Number.isFinite(end)||end<=start||end-start>31*86400000){setError('Selecciona un período válido de hasta 31 días.');return;}setPeriod({from:start,to:end});};
  const quick=(hours:number)=>{const end=Date.now(),start=end-hours*3600000;setFrom(local(start));setTo(local(end));setPeriod({from:start,to:end});};
  const day=(offset:number)=>{const start=new Date();start.setHours(0,0,0,0);start.setDate(start.getDate()+offset);const end=offset===0?Date.now():new Date(start.getFullYear(),start.getMonth(),start.getDate()+1).getTime()-1;setFrom(local(start.getTime()));setTo(local(end));setPeriod({from:start.getTime(),to:end});};
  const exportGpx=()=>{const segments=trail.segments.filter(s=>s.length>1).map(s=>'<trkseg>'+s.map(p=>`<trkpt lat="${p.lat}" lon="${p.lon}"><time>${new Date(p.recorded_at).toISOString()}</time></trkpt>`).join('')+'</trkseg>').join('');const url=URL.createObjectURL(new Blob([`<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="Steps Tracker" xmlns="http://www.topografix.com/GPX/1/1"><trk><name>Recorrido GPS filtrado</name>${segments}</trk></gpx>`],{type:'application/gpx+xml'}));const a=document.createElement('a');a.href=url;a.download='recorrido-gps.gpx';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  const duration=(minutes:number)=>gpsDuration(minutes*60);
  const gapLabel=(gap:TrailGap)=>gap.reason==='time_gap'?'Sin posiciones · '+duration(gap.seconds/60):'Cambio de posición no verificable';
  const events=[...(showStops?stops:[]).map(stop=>({kind:'stop' as const,at:Date.parse(stop.start),stop})),...trail.gaps.map(gap=>({kind:'gap' as const,at:Date.parse(gap.before.recorded_at),gap}))].sort((a,b)=>a.at-b.at);
  const samples=trail.playback.filter((_,i)=>i%Math.max(1,Math.ceil(trail.playback.length/300))===0);
  const plots:string[]=[];let speedLine:string[]=[];
  samples.forEach((p,i)=>{const t=Date.parse(p.recorded_at),previous=i?Date.parse(samples[i-1].recorded_at):t;if(p.speed_kmh==null||trail.gaps.some(g=>Date.parse(g.after.recorded_at)>previous&&Date.parse(g.after.recorded_at)<=t)){if(speedLine.length)plots.push(speedLine.join(' '));speedLine=[];if(p.speed_kmh==null)return;}speedLine.push(`${samples.length>1?i/(samples.length-1)*100:0},${38-Math.min(36,p.speed_kmh/Math.max(10,trail.maxSpeed)*36)}`);});
  if(speedLine.length)plots.push(speedLine.join(' '));
  const content=<><header className="trail-header"><div><span className="fleet-eyebrow">RECORRIDOS · {asset.plate||'GPS'}</span><h2 id="history-title">{asset.name}</h2><p>Un recorrido completo. Las paradas son eventos, no carreras independientes.</p></div><button aria-label="Cerrar historial" onClick={onClose}>×</button></header>
  <form className="trail-period" onSubmit={apply}><details className="trail-date-range"><summary>Elegir fechas</summary><div><label>Desde<input type="datetime-local" value={from} onChange={e=>setFrom(e.target.value)} required/></label><label>Hasta<input type="datetime-local" value={to} onChange={e=>setTo(e.target.value)} required/></label><button className="fleet-primary" disabled={busy}>Ver recorrido</button><button type="button" disabled={busy} onClick={()=>quick(24)}>Últimas 24 h</button><button type="button" disabled={busy} onClick={()=>quick(2)}>Últimas 2 h</button></div></details><button type="button" disabled={busy} onClick={()=>day(0)}>Hoy</button><button type="button" disabled={busy} onClick={()=>day(-1)}>Ayer</button><button type="button" disabled={busy} onClick={()=>quick(168)}>Últimos 7 días</button><small>{dateLabel(new Date(period.from).toISOString())} → {dateLabel(new Date(period.to).toISOString())} · Hora de tu dispositivo</small></form>
  <details className="trail-options" open={!embedded}><summary>Filtros y exportación</summary><div className="trail-filters"><label>Paradas de al menos<select aria-label="Duración mínima de parada" value={minimumStop} onChange={e=>setMinimumStop(Number(e.target.value))}>{[3,5,10,15,30,60].map(v=><option key={v} value={v}>{v} minutos</option>)}</select></label><label className="trail-toggle"><input type="checkbox" checked={showStops} onChange={e=>setShowStops(e.target.checked)}/>Mostrar paradas</label><label className="trail-toggle"><input type="checkbox" checked={follow} onChange={e=>setFollow(e.target.checked)}/>Seguir reproducción</label><button disabled={busy||!!error||!trail.segments.some(s=>s.length>1)} onClick={exportGpx}>Descargar GPX</button><small>Estos filtros cambian los eventos visibles; conservan el recorrido y su distancia.</small>{embedded&&<small>{trail.points.length} muestras GPS cargadas · {stops.length} paradas de al menos {minimumStop} min.</small>}</div></details>
  {demo&&<p className="fleet-notice">Demostración de una posición. No representa un viaje real.</p>}{error&&<p role="alert" className="fleet-error">{error}</p>}{busy&&<p role="status">Consultando posiciones del período…</p>}{cursor&&!busy&&<p className="fleet-notice">Historial parcial: se alcanzó el límite de esta carga. Las cifras corresponden a las muestras cargadas.<button onClick={()=>void load(cursor)}>Cargar más muestras</button></p>}
  {!busy&&!trail.points.length&&!error&&<div className="fleet-empty">No hay posiciones en este período. Prueba con otro rango.</div>}
  {!!trail.points.length&&!busy&&<><div className="trail-stats"><div><span>Distancia GPS aproximada</span><strong>{(trail.distanceM/1000).toLocaleString('es-CL',{maximumFractionDigits:2})} <small>km</small></strong></div><div><span>Tiempo estimado en movimiento</span><strong>{trail.points.length<2?"—":trail.movingSeconds>0&&trail.movingSeconds<60?"Menos de 1 min":gpsDuration(trail.movingSeconds)}</strong></div><div><span>Paradas ≥ {minimumStop} min</span><strong>{stops.length}</strong></div><div><span>Muestras GPS</span><strong>{trail.points.length}</strong></div></div>
  {trail.onlyParking&&<p className="trail-info"><strong>Reposo probable · {duration(trail.stops[0].minutes)}</strong> · {dateLabel(trail.stops[0].start)} → {dateLabel(trail.stops[0].end)}. {trail.stops[0].sparse?'Estimado a partir de lecturas espaciadas en el mismo lugar.':'Las posiciones cercanas se agruparon en el mapa.'}</p>}{trail.stationary&&!trail.onlyParking&&<p className="trail-info">Sin desplazamiento confirmado en estas muestras. Se filtraron variaciones de baja velocidad. Las muestras originales siguen disponibles en diagnóstico.</p>}{trail.gapCount>0&&<section className="trail-gap-summary" aria-label="Cortes del historial"><strong>{trail.gapCount} {trail.gapCount===1?'intervalo sin recorrido comprobado':'intervalos sin recorrido comprobado'}</strong><p>La reproducción pausa en cada corte. El mapa y la distancia conservan esos espacios sin completar.</p>{trail.gaps.slice(0,5).map(gap=><button key={gap.after.id} onClick={()=>{seek(Math.max(0,trail.playback.findIndex(p=>p.id===gap.before.id)));setPausedGap(gap);setFollow(true);}}><b>{gapLabel(gap)}</b><span>{dateLabel(gap.before.recorded_at)} → {dateLabel(gap.after.recorded_at)}</span></button>)}{trail.gaps.length>5&&<small>Los otros cortes aparecen en Eventos del recorrido.</small>}</section>}
  {preview&&<div className="trail-preview-banner">Vista del tramo seleccionado<button onClick={()=>setPreview(null)}>Ver recorrido completo</button></div>}
  <div className="trail-workspace" ref={mapRef}><Suspense fallback={<p role="status">Preparando mapa…</p>}><FleetTrailMap key={(preview?.from??period.from)+':'+(preview?.to??period.to)+':'+rows.length} points={shown.playback} onlyParking={shown.onlyParking} segments={shown.segments} stops={preview?(showStops?shown.stops.filter(s=>s.minutes>=minimumStop):[]):visibleStops} gaps={shown.gaps} cursor={preview||trail.onlyParking?undefined:point} follow={follow}/></Suspense><aside className="trail-timeline"><h3>Eventos del recorrido</h3><p>{stops.length} paradas de al menos {minimumStop} min. Selecciona un evento para verlo en el mapa.</p>{!trail.onlyParking&&<button onClick={()=>seek(0)}><b>Inicio</b><span>{dateLabel(trail.points[0].recorded_at)}</span></button>}{events.slice(0,eventPage*10).map((event,i)=>event.kind==='gap'?<button className="trail-gap-event" key={'gap-'+i} onClick={()=>{seek(Math.max(0,trail.playback.findIndex(p=>p.id===event.gap.before.id)));setPausedGap(event.gap);setFollow(true);}}><b>{gapLabel(event.gap)}</b><span>{dateLabel(event.gap.before.recorded_at)} → {dateLabel(event.gap.after.recorded_at)}</span></button>:showStops&&<button key={'stop-'+i} onClick={()=>{seek(Math.max(0,trail.playback.findIndex(p=>p.id===event.stop.point.id)));setFollow(true);}}><b>{event.stop.sparse?'Reposo probable':'Parada'} · {duration(event.stop.minutes)}</b><span>{dateLabel(event.stop.start)} → {dateLabel(event.stop.end)}</span></button>)}{events.length>eventPage*10&&<button onClick={()=>setEventPage(v=>v+1)}>Mostrar más eventos</button>}{!trail.onlyParking&&<button onClick={()=>seek(trail.playback.length-1)}><b>Fin</b><span>{dateLabel(trail.points[trail.points.length-1].recorded_at)}</span></button>}<p>No se infiere el camino durante los cortes de señal. La aproximación por calles se calcula solo cuando la solicitas.</p></aside></div>
  {canReplay&&!preview&&<section className="trail-playback" aria-label="Reproducción del recorrido">{pausedGap&&<div className="trail-gap-pause" role="status"><strong>Reproducción pausada en un corte</strong><span>{gapLabel(pausedGap)}</span><small>{dateLabel(pausedGap.before.recorded_at)} → {dateLabel(pausedGap.after.recorded_at)}. El desplazamiento en este intervalo es desconocido.</small></div>}<div><button onClick={togglePlayback}>{pausedGap?'Continuar después del corte':playing?'Pausar':'Reproducir'}</button><label>Ritmo<select value={rate} onChange={e=>setRate(Number(e.target.value))}><option value={750}>Normal</option><option value={250}>Rápido</option></select></label><strong>{point?dateLabel(point.recorded_at):'—'}</strong><span>{point?.speed_kmh!=null?point.speed_kmh.toFixed(1)+' km/h':'Velocidad no disponible'}</span></div><input type="range" aria-label="Posición en el recorrido" min={0} max={Math.max(0,trail.playback.length-1)} value={index} onChange={e=>seek(Number(e.target.value))}/><svg viewBox="0 0 100 40" preserveAspectRatio="none" role="img" aria-label="Perfil de velocidad registrada">{plots.map((plot,i)=><polyline key={i} points={plot} fill="none" stroke="#277453" strokeWidth="1" vectorEffect="non-scaling-stroke"/>)}</svg><small>Reproducción de muestras, no tiempo real. La distancia omite saltos y filtra deriva; no sustituye un odómetro.</small></section>}
  {!demo&&canReplay&&trail.distanceM>0&&<FleetTripExpense key={asset.asset_id+':'+period.from+':'+period.to+':'+rows.length} asset={asset} context={context} points={trail.points} incomplete={!!cursor}
    onFocus={p=>{setPreview(null);const i=trail.playback.findIndex(x=>x.id===p.id);if(i>=0){seek(i);setFollow(true);}}}
    onPreview={(start,end)=>{setPlaying(false);setPreview({from:start,to:end});requestAnimationFrame(()=>mapRef.current?.scrollIntoView({block:'start'}));}}/>}
  <details className="trail-diagnostics"><summary>Datos GPS para diagnóstico</summary><p>Las últimas 100 muestras del período; las coordenadas originales se conservan.</p><div>{trail.points.slice(-100).reverse().map(p=><p key={p.id}>{dateLabel(p.recorded_at)} · {p.lat.toFixed(5)}, {p.lon.toFixed(5)} · {p.speed_kmh??'—'} km/h</p>)}</div></details></>}
  <footer className="trail-footer"><span>Google Maps · GPS del vehículo · Sin iniciar jornada</span>{error&&<button disabled={busy} onClick={()=>void load()}>Reintentar</button>}{canReplay&&!busy&&!preview&&<button className="fleet-primary" onClick={togglePlayback}>{pausedGap?'Continuar después del corte':playing?'Pausar recorrido':'Reproducir recorrido'}</button>}<button onClick={onClose}>Cerrar</button></footer></>;
  return embedded?<section className="tracker-history trail-embedded" aria-labelledby="history-title">{content}</section>:<dialog ref={dialog} className="tracker-dialog tracker-history trail-dialog" onCancel={onClose} aria-labelledby="history-title">{content}</dialog>;
}
