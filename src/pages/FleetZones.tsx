import { useEffect, useState } from 'react';
import ZoneMap from '../components/ZoneMap';
import TrackerIcon from '../components/TrackerIcon';
import { fleetRequest, dateLabel, type FleetAsset, type FleetContext } from '../services/fleetApi';
import { area, blankZone, duration, exportReport, exportZone, number, purposes, type Vertex, type Zone, type ZoneDraft, type ZoneReport } from '../services/fleetZones';
import { demoZoneReport } from '../hooks/useFleetZones';
import './FleetZones.css';

const localDate = (date: Date) => new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16);
export default function FleetZones({ context, assets, zones, error, refresh, save, demo, initialZoneId }: {
  initialZoneId?: string; context: FleetContext; assets: FleetAsset[]; zones: Zone[]; error: string; refresh: () => void;
  save: (draft: ZoneDraft, existing?: Zone) => Promise<Zone>; demo: boolean;
}) {
  const [selected, setSelected] = useState(initialZoneId || '');
  const [editor, setEditor] = useState<{ draft: ZoneDraft; original?: Zone } | null>(null);
  const [drawing, setDrawing] = useState(false);
  const [coordinates, setCoordinates] = useState('');
  const [search, setSearch] = useState(''); const [archived, setArchived] = useState(false);
  const [notice, setNotice] = useState(''); const [editError, setEditError] = useState(''); const [saving, setSaving] = useState(false);
  const [assetId, setAssetId] = useState(assets[0]?.asset_id || '');
  const [period, setPeriod] = useState('8'); const [auto, setAuto] = useState(true); const [tick, setTick] = useState(0);
  const [from, setFrom] = useState(() => localDate(new Date(Date.now()-8*3600000)));
  const [to, setTo] = useState(() => localDate(new Date()));
  const [report, setReport] = useState<ZoneReport | null>(null); const [reportError, setReportError] = useState(''); const [busy, setBusy] = useState(false);
  const [focus, setFocus] = useState(0);
  const zone = zones.find(z => z.id === selected) || (!selected ? zones.find(z => z.active) : undefined);
  const chosenAsset = assets.find(a => a.asset_id === assetId) || (!assetId ? assets[0] : undefined);
  const shown = zones.filter(z => (archived || z.active) && z.name.toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  const vertices = editor?.draft.vertices || zone?.vertices || [];
  const center = zone?.vertices[0] || assets.find(a => a.last_position)?.last_position || { lat: -33.445, lon: -70.655 };
  const manager = context.role === 'manager';
  const setVertices = (vertices: Vertex[]) => { setEditor(e => e ? { ...e, draft: { ...e.draft, vertices } } : e); setCoordinates(vertices.map(p => `${p.lat.toFixed(7)}, ${p.lon.toFixed(7)}`).join('\n')); };
  const edit = (existing?: Zone) => { const draft = existing ? { name: existing.name, purpose: existing.purpose, color: existing.color, active: existing.active, vertices: existing.vertices } : blankZone(); setEditor({ draft, original: existing }); setDrawing(!existing); setCoordinates(draft.vertices.map(p => `${p.lat}, ${p.lon}`).join('\n')); setEditError(''); setNotice(''); setFocus(n => n+1); };
  const submit = async () => {
    if (!editor || saving) return;
    setSaving(true); setEditError('');
    try { const saved = await save(editor.draft, editor.original); setSelected(saved.id); setEditor(null); setDrawing(false); setNotice(demo ? 'Zona guardada solo en esta demostración. Las métricas del ejemplo no se recalculan para zonas editadas.' : 'Zona guardada. Sus métricas se calculan con este perímetro.'); }
    catch (e) { setEditError((e as Error).message); } finally { setSaving(false); }
  };
  const applyCoordinates = () => {
    try {
      const points = coordinates.trim().split(/\n/).filter(Boolean).map(line => { const parts = line.trim().split(/[;,\s]+/); if (parts.length !== 2) throw new Error(); const [lat, lon] = parts.map(Number); if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat)>80 || Math.abs(lon)>180) throw new Error(); return { lat, lon }; });
      if (points.length < 3 || points.length > 100) throw new Error();
      setVertices(points); setDrawing(false); setFocus(n => n+1); setEditError('');
    } catch { setEditError('Ingresa de 3 a 100 líneas con latitud, longitud en grados decimales. Usa punto decimal; no repitas el primer vértice al final.'); }
  };
  const zoneId = zone?.id; const zoneVersion = zone?.version; const chosenAssetId = chosenAsset?.asset_id; const isEditing = !!editor;
  useEffect(() => {
    let active = true; let pending = false;
    setReport(null); setReportError(''); setBusy(false);
    if (!zoneId || isEditing) return;
    if (demo) { if (zoneId === demoZoneReport.zone.id && zoneVersion === 1) setReport(demoZoneReport); return; }
    if (!chosenAssetId) return;
    const load = async () => {
      if (pending) return;
      const end = period === 'custom' ? new Date(to) : new Date();
      const start = period === 'custom' ? new Date(from) : period === 'today' ? new Date(new Date().setHours(0,0,0,0)) : new Date(end.getTime()-Number(period)*3600000);
      if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime()) || end<=start || end.getTime()-start.getTime()>31*86400000 || end.getTime()>Date.now()+300000) { setReportError('Selecciona un período válido, sin fechas futuras, de hasta 31 días.'); return; }
      pending = true; setBusy(true);
      try { const result = await fleetRequest<ZoneReport>(`zones/${zoneId}/report?${new URLSearchParams({ asset_id: chosenAssetId, start: start.toISOString(), end: end.toISOString() })}`, context); if (active) { setReport(result); setReportError(''); } }
      catch (e) { if (active) { setReport(null); setReportError((e as Error).message); } }
      finally { pending = false; if (active) setBusy(false); }
    };
    void load(); const timer = auto && period !== 'custom' ? setInterval(() => void load(), 60000) : undefined;
    return () => { active = false; clearInterval(timer); };
  }, [zoneId, zoneVersion, chosenAssetId, context, period, from, to, auto, tick, demo, isEditing]);
  return <div className="zones-page">
    <section className="zone-intro"><div><span className="fleet-eyebrow">CADA LUGAR CUENTA</span><h2>Del recorrido al contexto.</h2><p>Delimita faenas, clientes y bases. Descubre cuánto tiempo pasa tu flota dentro y fuera de cada lugar.</p></div>{manager && <button className="fleet-primary" disabled={!!editor} onClick={() => edit()}><TrackerIcon name="plus" size={18}/> Nueva zona</button>}</section>
    {error && <p className="fleet-error" role="alert">No se pudieron actualizar las zonas: {error} <button onClick={refresh}>Reintentar</button></p>}
    {notice && <p className="fleet-notice" role="status">{notice}</p>}
    <div className="zone-workspace">
      <aside className="zone-panel">
        {editor ? <form onSubmit={e => { e.preventDefault(); void submit(); }}>
          <span className="fleet-eyebrow">{editor.original ? `EDITAR · VERSIÓN ${editor.original.version}` : 'TRAZAR UN NUEVO LUGAR'}</span><h3>{editor.original ? 'Ajusta tu zona' : 'Dale forma a tu zona'}</h3>
          <label>Nombre de la zona<input required maxLength={150} value={editor.draft.name} onChange={e => setEditor({ ...editor, draft: { ...editor.draft, name: e.target.value } })} placeholder="Ej. Patio norte o Cliente Las Palmas"/></label>
          <label>Uso<select value={editor.draft.purpose} onChange={e => setEditor({ ...editor, draft: { ...editor.draft, purpose: e.target.value as ZoneDraft['purpose'] } })}>{Object.entries(purposes).map(([key,label]) => <option key={key} value={key}>{label}</option>)}</select></label>
          <label className="zone-color">Color en el mapa<input type="color" value={editor.draft.color} onChange={e => setEditor({ ...editor, draft: { ...editor.draft, color: e.target.value } })}/></label>
          <div className="zone-draw-help"><b>{drawing ? '1. Marca el perímetro' : '2. Revisa y guarda'}</b><p>{drawing ? 'Toca o haz clic en el mapa para añadir vértices. Desplaza el mapa con dos dedos en el teléfono.' : 'Arrastra los puntos del borde para ajustar la forma. Los puntos intermedios añaden vértices.'}</p><strong>{vertices.length} / 100 vértices</strong></div>
          <div className="zone-actions"><button type="button" disabled={vertices.length<3} onClick={() => setDrawing(!drawing)}>{drawing ? 'Terminar trazado' : 'Añadir vértices'}</button><button type="button" disabled={!vertices.length} onClick={() => setVertices(vertices.slice(0,-1))}>Quitar último</button><button type="button" disabled={!vertices.length} onClick={() => { setVertices([]); setDrawing(true); }}>Reiniciar</button></div>
          <details className="zone-coordinates"><summary>Usar coordenadas / quitar vértices</summary><label>Un punto por línea: latitud, longitud<textarea rows={6} value={coordinates} onChange={e => setCoordinates(e.target.value)} placeholder={'-33.450, -70.660\n-33.450, -70.650\n-33.440, -70.655'}/></label><p>Grados decimales, sin repetir el punto inicial. Puedes borrar una línea para quitar un vértice.</p><button type="button" onClick={applyCoordinates}>Aplicar coordenadas</button></details>
          {editor.original && <><label className="zone-check"><input type="checkbox" checked={editor.draft.active} onChange={e => setEditor({ ...editor, draft: { ...editor.draft, active: e.target.checked } })}/>Zona activa</label><p className="fleet-note">Al desactivarla se archiva y conserva sus reportes. Cambiar el perímetro recalcula el historial con la nueva forma.</p></>}
          {editError && <p role="alert" className="fleet-error">{editError}</p>}
          <div className="zone-actions"><button className="fleet-primary" disabled={saving || vertices.length<3 || !editor.draft.name.trim()}>{saving ? 'Guardando…' : 'Guardar zona'}</button><button type="button" disabled={saving} onClick={() => { setEditor(null); setDrawing(false); }}>Cancelar</button></div>
        </form> : <><div className="zone-list-title"><h3>Tus zonas</h3><span>{zones.filter(z => z.active).length} activas</span></div><label>Buscar zona<input type="search" value={search} onChange={e => setSearch(e.target.value)} placeholder="Nombre del lugar"/></label><label className="zone-check"><input type="checkbox" checked={archived} onChange={e => setArchived(e.target.checked)}/>Incluir archivadas</label>
          <div className="zone-list">{shown.map(z => <button key={z.id} className={zone?.id === z.id ? 'is-selected' : ''} onClick={() => { setSelected(z.id); setNotice(''); }}><span className="zone-swatch" style={{ background: z.color }}/><span><strong>{z.name}</strong><small>{purposes[z.purpose]} · {z.area_m2 ? area(z.area_m2) : 'Área de ejemplo'}{!z.active ? ' · Archivada' : ''}</small></span><TrackerIcon name="arrow" size={16}/></button>)}</div>
          {!shown.length && <div className="zone-empty"><TrackerIcon name="zones" size={36}/><h3>{zones.length ? 'Sin coincidencias' : 'Tu primer lugar'}</h3><p>{manager ? 'Crea una zona y marca su perímetro en el mapa. Servirá para cualquier vehículo de esta compañía.' : 'Tu administrador puede registrar zonas para consultar sus métricas.'}</p></div>}
          <p className="fleet-note">Las zonas pertenecen a {context.company}. Se analizan por vehículo y período; una zona restringida es una clasificación, no activa alertas automáticas.</p>
        </>}
      </aside>
      <section className="zone-canvas"><div className="zone-map-heading"><div><strong>{editor ? editor.draft.name || 'Nueva zona' : zone?.name || 'Ubica tu operación'}</strong><small>{editor ? 'Los cambios aún no están guardados' : zone ? `${zone.area_m2 ? area(zone.area_m2) : 'Área de ejemplo'} · perímetro ${number(zone.perimeter_m)} m · v${zone.version}` : 'Faenas, clientes, estacionamientos y más'}</small></div>{zone && !editor && <div className="zone-actions">{manager && <button onClick={() => edit(zone)}>Editar zona</button>}<button onClick={() => exportZone(zone)}>GeoJSON ↓</button></div>}</div>
        <div className="zone-canvas-tools" hidden={!editor}>{editor && <><span>{vertices.length} vértices · {drawing ? 'Toca el mapa para dibujar' : 'Arrastra los puntos para ajustar'}</span><button disabled={vertices.length<3} onClick={() => setDrawing(!drawing)}>{drawing ? 'Cerrar polígono' : 'Seguir trazando'}</button><button disabled={saving || vertices.length<3 || !editor.draft.name.trim()} className="fleet-primary" onClick={() => void submit()}>Guardar polígono</button></>}</div>
        <div className="zone-map"><ZoneMap zones={zones} selected={editor ? editor.original?.id : zone?.id} vertices={vertices} color={editor?.draft.color || zone?.color || '#4d7c3d'} editing={!!editor} drawing={drawing} onVertices={setVertices} onSelect={setSelected} center={center} segments={!editor ? report?.segments : undefined} focusKey={`${zone?.id}:${!!editor}:${focus}`}/></div>
        <div className="zone-map-legend"><span><i style={{ background: '#a5cb45' }}/>Recorrido dentro</span><span><i style={{ background: '#65c5ff' }}/>Recorrido fuera</span><span>Superficie del polígono ≠ superficie trabajada</span></div>
      </section>
    </div>
    {zone && !editor && <section className="zone-analysis"><div className="zone-section-heading"><div><span className="fleet-eyebrow">EL MOVIMIENTO, EN CIFRAS</span><h2>Dentro y fuera de {zone.name}</h2></div>{report && <button onClick={() => exportReport(report)}>Exportar reporte CSV ↓</button>}</div>
      {demo ? <p className="fleet-notice">Ejemplo sintético: camioneta, recorrido y período ilustrativos. Las métricas de este ejemplo solo corresponden a la zona original.</p> : <div className="zone-report-controls"><label>Vehículo<select value={chosenAsset?.asset_id || ''} onChange={e => setAssetId(e.target.value)}><option value="" disabled>Selecciona un vehículo</option>{assets.map(a => <option key={a.asset_id} value={a.asset_id}>{a.name}{a.plate ? ` · ${a.plate}` : ''}</option>)}</select></label><label>Período<select value={period} onChange={e => setPeriod(e.target.value)}><option value="8">Últimas 8 horas</option><option value="24">Últimas 24 horas</option><option value="today">Hoy</option><option value="custom">Personalizado</option></select></label>{period === 'custom' && <><label>Desde<input type="datetime-local" value={from} onChange={e => setFrom(e.target.value)}/></label><label>Hasta<input type="datetime-local" value={to} onChange={e => setTo(e.target.value)}/></label></>}</div>}
      {!demo && <div className="zone-actions"><button disabled={busy || !chosenAsset} onClick={() => setTick(n => n+1)}>{busy ? 'Calculando…' : 'Actualizar reporte'}</button>{period !== 'custom' && <label className="zone-check"><input type="checkbox" checked={auto} onChange={e => setAuto(e.target.checked)}/>Actualizar cada minuto</label>}<small>Horarios de tu navegador: {Intl.DateTimeFormat().resolvedOptions().timeZone}</small></div>}
      {reportError && <p className="fleet-error" role="alert">{reportError}</p>}
      {!chosenAsset && !demo && <p className="zone-empty">Registra un vehículo y asocia su GPS para analizar sus recorridos.</p>}
      {demo && !report && <p className="zone-empty">Esta zona de prueba no tiene historial asociado. En tu flota real, el reporte usará las posiciones GPS recibidas.</p>}
      {busy && !report && <p role="status">Analizando posiciones y cruces…</p>}
      {report && <ZoneReportView report={report}/>}
    </section>}
    <details className="zone-method"><summary>Cómo se calculan estas métricas</summary><p>Se unen posiciones GPS válidas consecutivas con líneas rectas y se estima dónde y cuándo atraviesan el borde. El borde se considera dentro. No se prolonga el recorrido antes del primer dato ni después del último.</p><p>Los huecos mayores a 5 minutos, cambios de GPS, posiciones ambiguas y saltos superiores a 200 km/h quedan sin observación. Movimiento: ambos extremos sobre 2 km/h. Detenido: ambos hasta 2 km/h. Sin velocidad suficiente, el movimiento es desconocido; detenido no significa motor apagado.</p><p>Las distancias y los cruces son estimaciones, sensibles a la frecuencia y precisión del GPS. La cobertura indica tiempo respaldado por pares válidos, no precisión satelital ni cobertura celular. Las zonas se analizan independientemente: si se superponen, no sumes sus tiempos como si fueran excluyentes. Máximo 31 días y 20.000 posiciones por consulta.</p><p>El reporte utiliza la geometría actual de la zona. Su superficie describe el terreno delimitado, no hectáreas efectivamente trabajadas; eso necesita ancho del implemento y validación del trabajo. Los cruces iniciales o durante un corte de señal no se inventan.</p></details>
  </div>;
}

function ZoneReportView({ report: r }: { report: ZoneReport }) {
  const has = r.observed_seconds > 0;
  return <div className="zone-report-result"><p className="zone-report-stamp">{r.asset.name} · {dateLabel(r.start)} → {dateLabel(r.end)} · actualizado {dateLabel(r.generated_at)} · zona v{r.zone.version}</p>
    <div className="zone-quality"><div><strong>{number(r.coverage_pct)}%</strong><span>del período con observación GPS</span></div><div className="zone-coverage" role="meter" aria-label="Cobertura temporal GPS" aria-valuemin={0} aria-valuemax={100} aria-valuenow={r.coverage_pct}><span style={{ width: `${r.coverage_pct}%` }}/></div><span>{duration(r.unobserved_seconds)} sin observación · {r.point_count} posiciones</span></div>
    {!has && <p className="fleet-notice"><strong>Aún no hay tramos GPS suficientes.</strong> Se necesitan al menos dos posiciones válidas cercanas en el tiempo. Esto no significa que el vehículo haya estado detenido o fuera de la zona.</p>}
    <div className="zone-comparison">{(['inside','outside'] as const).map(key => { const s = r[key]; return <article key={key} className={`zone-stat-card zone-stat-card--${key}`}><span className="fleet-eyebrow">{key === 'inside' ? 'DENTRO DE LA ZONA' : 'FUERA DE LA ZONA'}</span><strong className="zone-stat-value">{has ? duration(s.seconds) : '—'}</strong><p>tiempo observado</p><dl><div><dt>Distancia GPS estimada</dt><dd>{has ? `${number(s.distance_m/1000,2)} km` : '—'}</dd></div><div><dt>En movimiento</dt><dd>{has ? duration(s.moving_seconds) : '—'}</dd></div><div><dt>Detenido</dt><dd>{has ? duration(s.stationary_seconds) : '—'}</dd></div><div><dt>Movimiento desconocido</dt><dd>{has ? duration(s.unknown_motion_seconds) : '—'}</dd></div><div><dt>Velocidad máxima observada</dt><dd>{s.max_speed_kmh === null ? '—' : `${number(s.max_speed_kmh)} km/h`}</dd></div></dl></article>; })}<article className="zone-stat-card zone-crossings"><span className="fleet-eyebrow">CRUCES ESTIMADOS</span><div><strong>{r.entries}</strong><span>Entradas</span></div><div><strong>{r.exits}</strong><span>Salidas</span></div><p>No incluye cruces durante cortes de señal ni una entrada al iniciar ya dentro.</p></article></div>
    {Object.values(r.rejected_intervals).some(n => n>0) && <p className="fleet-note">Tramos excluidos: {r.rejected_intervals.long_gap} por cortes de señal, {r.rejected_intervals.invalid_fix} por datos inválidos, {r.rejected_intervals.assignment_change} por cambio de GPS y {r.rejected_intervals.implausible_jump} por saltos de velocidad.</p>}
    {r.map_truncated && <p className="fleet-note">El mapa muestra los últimos 500 segmentos. Los totales incluyen todo el período.</p>}
    <details className="zone-events"><summary>Ver entradas y salidas ({r.entries+r.exits})</summary>{r.events_truncated && <p>Se muestran los últimos 1.000 cruces; los totales incluyen todos.</p>}{r.events.length ? <ol>{r.events.map((e,i) => <li key={i}><span className={e.type === 'entry' ? 'zone-entry' : 'zone-exit'}>{e.type === 'entry' ? 'Entrada' : 'Salida'}</span><time dateTime={e.at}>{dateLabel(e.at)}</time><small>{e.lat.toFixed(5)}, {e.lon.toFixed(5)}</small></li>)}</ol> : <p>No se estimaron cruces en los tramos observados.</p>}</details>
  </div>;
}
