import { useEffect, useRef, useState } from 'react';
import { dateLabel, fleetRequest, type FleetAsset, type FleetContext } from '../services/fleetApi';
type Position = NonNullable<FleetAsset['last_position']>;
export default function FleetHistory({ asset, context, demo, onClose }: {asset:FleetAsset; context:FleetContext; demo:boolean; onClose:()=>void}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [rows,setRows] = useState<Position[]>([]);
  const [cursor,setCursor] = useState<string|null>(null);
  const [busy,setBusy] = useState(true); const [error,setError] = useState('');
  useEffect(() => {
    dialog.current?.showModal(); let active = true;
    if (demo) { setRows(asset.last_position ? [asset.last_position] : []); setBusy(false); return; }
    fleetRequest<{items:Position[];next_cursor:string|null}>(`assets/${asset.asset_id}/positions?limit=50`,context).then(r => {if(active){setRows(r.items);setCursor(r.next_cursor);}}).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setBusy(false);});
    return () => {active=false;};
  },[asset,context,demo]);
  const more = async () => {
    setBusy(true);setError('');
    try { const r = await fleetRequest<{items:Position[];next_cursor:string|null}>(`assets/${asset.asset_id}/positions?limit=50${cursor ? '&before='+encodeURIComponent(cursor) : ''}`,context); setRows(previous => cursor ? [...previous,...r.items] : r.items);setCursor(r.next_cursor); }
    catch(e){setError((e as Error).message);} finally{setBusy(false);}
  };
  return <dialog ref={dialog} className="tracker-dialog tracker-history" onCancel={onClose} aria-labelledby="history-title"><div className="tracker-section-title"><div><span className="fleet-eyebrow">{asset.plate || 'HISTORIAL GPS'}</span><h2 id="history-title">{asset.name}</h2></div><button aria-label="Cerrar historial" onClick={onClose}>×</button></div><p>Posiciones registradas, de la más reciente a la más antigua.</p>{demo && <p className="fleet-notice">Muestra sintética de la última posición. No es un recorrido real.</p>}{!rows.length && !busy && !error && <div className="fleet-empty">Todavía no hay posiciones registradas para este vehículo.</div>}<ol className="tracker-position-list">{rows.map(p=><li key={p.id}><div><strong>{dateLabel(p.recorded_at)}</strong><span>{p.speed_kmh == null ? 'Velocidad no disponible' : p.speed_kmh.toFixed(1)+' km/h'}</span></div><p>{p.lat.toFixed(5)}, {p.lon.toFixed(5)} · {p.quality}</p><small>Recibido por Steps: {dateLabel(p.received_at)}</small></li>)}</ol>{error && <p role="alert" className="fleet-error">{error}</p>}{busy && <p role="status">Cargando posiciones…</p>}{(cursor || error) && <button disabled={busy} onClick={()=>void more()}>{error ? 'Reintentar' : 'Cargar anteriores'}</button>}<div className="tracker-dialog-actions"><button onClick={onClose}>Cerrar</button></div></dialog>;
}
