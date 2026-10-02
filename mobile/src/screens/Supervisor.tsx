import { useEffect, useMemo, useState } from 'react';
import { catalogs, mobile, sessions, type ActiveSession, type AssignedRoute, type DeviceOut, type Field, type IncidentOut, type Machine } from '../lib/api';
import MapView, { type MapField, type MapMarker } from '../components/MapView';
import { centroid, formatDistance, routeLengthM, type LatLon, type Waypoint } from '../lib/nav';
import { Sheet } from './Sheets';

const CATEGORY: Record<string, string> = { breakdown: 'Falla mecánica', accident: 'Accidente', damage: 'Daño', theft: 'Robo', sos: 'SOS', other: 'Otro' };
const when = (iso: string) => new Date(iso).toLocaleString('es-CL', { dateStyle: 'short', timeStyle: 'short' });

/** Vista de supervisor: flota en el mapa, incidentes por atender, asignación de rutas y estado de los teléfonos. */
export default function Supervisor() {
  const [incidents, setIncidents] = useState<IncidentOut[]>([]);
  const [open, setOpen] = useState<ActiveSession[]>([]);
  const [devices, setDevices] = useState<DeviceOut[]>([]);
  const [routes, setRoutes] = useState<AssignedRoute[]>([]);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [fields, setFields] = useState<Field[]>([]);
  const [error, setError] = useState('');
  const [photo, setPhoto] = useState<{ id: string; url: string } | null>(null);
  const [focus, setFocus] = useState<LatLon | null>(null);
  const [builder, setBuilder] = useState<{ machineId: number | null } | null>(null);

  const load = () => {
    setError('');
    Promise.all([mobile.incidents(), sessions.active(), mobile.devices(), mobile.routes(), catalogs.machines(), catalogs.fields()])
      .then(([i, s, d, r, m, f]) => { setIncidents(i); setOpen(s); setDevices(d); setRoutes(r); setMachines(m); setFields(f); })
      .catch((e: Error) => setError(e.message));
  };
  useEffect(load, []);
  // La flota se refresca sola mientras la pestaña está abierta.
  useEffect(() => { const t = setInterval(() => { sessions.active().then(setOpen).catch(() => {}); }, 20000); return () => clearInterval(t); }, []);

  const act = async (i: IncidentOut, status: 'attended' | 'closed') => {
    try { const next = await mobile.setIncident(i.id, status); setIncidents((p) => p.map((x) => (x.id === i.id ? next : x))); }
    catch (e) { setError((e as Error).message); }
  };
  const showPhoto = async (i: IncidentOut) => { try { setPhoto({ id: i.id, url: await mobile.photo('incidents', i.id) }); } catch (e) { setError((e as Error).message); } };
  const cancelRoute = async (r: AssignedRoute) => {
    if (!confirm(`¿Cancelar la ruta "${r.name}"?`)) return;
    try { await mobile.setRoute(r.id, 'cancelled'); setRoutes((p) => p.filter((x) => x.id !== r.id)); } catch (e) { setError((e as Error).message); }
  };

  const pending = incidents.filter((i) => i.status !== 'closed');
  const mapFields: MapField[] = useMemo(() => fields.flatMap((f) => (f.polygon && f.polygon.length > 2 ? [{ name: f.name, polygon: f.polygon }] : [])), [fields]);
  const markers: MapMarker[] = useMemo(() => [
    ...open.flatMap((s) => (s.last_lat != null && s.last_lon != null ? [{ lat: s.last_lat, lon: s.last_lon, kind: 'machine' as const, label: `${s.machine_name ?? 'Máquina'}${s.driver_name ? ` · ${s.driver_name}` : ''}` }] : [])),
    ...pending.flatMap((i) => (i.lat != null && i.lon != null ? [{ lat: i.lat, lon: i.lon, kind: (i.category === 'sos' || i.category === 'theft' ? 'sos' : 'incident') as 'sos' | 'incident', label: CATEGORY[i.category] ?? i.category }] : [])),
  ], [open, pending]);
  const moving = open.filter((s) => s.last_speed_mps != null && s.last_speed_mps > 0.5);

  return (
    <section className="stack">
      <h1>Supervisor</h1>
      {error && <p className="error" role="alert">{error}</p>}
      <article className="card stack">
        <div className="row"><h2>Flota en vivo</h2><span className="chip">{open.length} en jornada{moving.length ? ` · ${moving.length} en movimiento` : ''}</span></div>
        <MapView markers={markers} fields={mapFields} focus={focus} height={300} />
        <small className="muted">Verde: máquinas con jornada abierta (última posición). Naranja/rojo: incidentes y SOS. Se actualiza cada 20 s.</small>
        <button className="primary" onClick={() => setBuilder({ machineId: null })}>Asignar una ruta</button>
      </article>

      <h2>Incidentes por atender ({pending.length})</h2>
      {!pending.length && <p className="muted">Sin incidentes pendientes.</p>}
      {pending.map((i) => {
        const grave = i.category === 'sos' || i.category === 'theft';
        return (
          <article key={i.id} className={`card stack ${grave ? 'card--alert' : ''}`}>
            <div className="row"><div><strong>{CATEGORY[i.category] ?? i.category}</strong><small>{i.machine_name ?? 'Sin máquina'} · {i.user_name ?? ''} · {when(i.occurred_at)}</small></div>
              <span className="chip">{i.status === 'open' ? 'Abierto' : 'Atendiendo'}</span></div>
            {i.note && <p>{i.note}</p>}
            {grave && <small className="muted">Detención remota del vehículo: aún no disponible (la web la mantiene bloqueada hasta homologar el equipo en Protección). Mientras tanto, sigue la posición en el mapa y avisa a las autoridades.</small>}
            <div className="grid2">
              {i.lat != null && i.lon != null && <button onClick={() => { setFocus({ lat: i.lat as number, lon: i.lon as number }); window.scrollTo({ top: 0, behavior: 'smooth' }); }}>Ver en el mapa</button>}
              {i.lat != null && i.lon != null && <a className="btnlink" href={`https://www.google.com/maps?q=${i.lat},${i.lon}`} target="_blank" rel="noreferrer">Abrir en Google Maps</a>}
              {i.has_photo && <button onClick={() => void showPhoto(i)}>Ver foto</button>}
              {i.status === 'open' && <button onClick={() => void act(i, 'attended')}>Atender</button>}
              <button className="primary" onClick={() => void act(i, 'closed')}>Cerrar</button>
            </div>
            {photo?.id === i.id && <img src={photo.url} alt="Foto del incidente" className="photo" />}
          </article>
        );
      })}

      <h2>Jornadas abiertas ({open.length})</h2>
      {open.map((s) => (
        <article key={s.id} className="card stack">
          <div className="row"><div><strong>{s.machine_name ?? `Máquina ${s.machine_id}`}</strong>
            <small>Desde {when(s.started_at)} · {s.points_count} puntos{s.cost_center_name ? ` · ${s.cost_center_name}` : ''}{s.last_speed_mps != null ? ` · ${(s.last_speed_mps * 3.6).toFixed(0)} km/h` : ''}</small></div>
            <span className={`chip ${s.last_speed_mps != null && s.last_speed_mps > 0.5 ? 'chip--open' : ''}`}>{s.last_speed_mps != null && s.last_speed_mps > 0.5 ? 'En movimiento' : 'Detenida'}</span></div>
          <div className="grid2">
            {s.last_lat != null && s.last_lon != null && <button onClick={() => { setFocus({ lat: s.last_lat as number, lon: s.last_lon as number }); window.scrollTo({ top: 0, behavior: 'smooth' }); }}>Ver en el mapa</button>}
            <button className="primary" onClick={() => setBuilder({ machineId: s.machine_id })}>Asignar ruta</button>
          </div>
        </article>
      ))}
      {!open.length && <p className="muted">No hay jornadas abiertas.</p>}

      <h2>Rutas asignadas ({routes.length})</h2>
      {!routes.length && <p className="muted">Aún no hay rutas pendientes.</p>}
      {routes.map((r) => (
        <article key={r.id} className="card row routecard">
          <div><strong>{r.name}</strong><small>{r.machine_name ?? `Máquina ${r.machine_id}`} · {r.waypoints.length} puntos · {formatDistance(routeLengthM(r.waypoints))} · {r.status === 'in_progress' ? 'en curso' : 'sin iniciar'}</small></div>
          <button onClick={() => void cancelRoute(r)}>Cancelar</button>
        </article>
      ))}

      <h2>Teléfonos</h2>
      {!devices.length && <p className="muted">Aún no hay teléfonos reportando.</p>}
      {devices.map((d) => <article key={d.user_id} className="card"><strong>{d.user_name ?? `Usuario ${d.user_id}`}</strong><small>v{d.version ?? '?'} · {d.platform ?? 'web'} · {d.pending ?? 0} pendientes · última sincronización {d.last_sync_at ? when(d.last_sync_at) : 'nunca'}</small></article>)}
      <button onClick={load}>Actualizar</button>

      {builder && <RouteBuilder machines={machines} fields={fields} mapFields={mapFields} open={open} initialMachine={builder.machineId}
        onClose={() => setBuilder(null)} onCreated={(r) => { setRoutes((p) => [r, ...p]); setBuilder(null); }} />}
    </section>
  );
}

/** Asignar una ruta: tocar el mapa para agregar puntos, o usar un campo como destino. */
function RouteBuilder({ machines, fields, mapFields, open, initialMachine, onClose, onCreated }: {
  machines: Machine[]; fields: Field[]; mapFields: MapField[]; open: ActiveSession[]; initialMachine: number | null; onClose: () => void; onCreated: (r: AssignedRoute) => void;
}) {
  const [machine, setMachine] = useState(initialMachine != null ? String(initialMachine) : '');
  const [name, setName] = useState('');
  const [note, setNote] = useState('');
  const [pts, setPts] = useState<Waypoint[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const live = open.find((s) => String(s.machine_id) === machine);

  const startFromMachine = () => { if (live?.last_lat != null && live.last_lon != null) setPts((p) => [{ lat: live.last_lat as number, lon: live.last_lon as number, label: 'Posición actual' }, ...p]); };
  const addField = (id: string) => {
    const f = fields.find((x) => String(x.id) === id);
    const c = f?.polygon ? centroid(f.polygon) : null;
    if (f && c) setPts((p) => [...p, { ...c, label: f.name }]);
  };
  const save = async () => {
    if (!machine) { setErr('Elige la máquina.'); return; }
    if (!name.trim()) { setErr('Ponle un nombre a la ruta.'); return; }
    if (pts.length < 2) { setErr('Marca al menos dos puntos en el mapa.'); return; }
    setBusy(true); setErr('');
    try { onCreated(await mobile.createRoute({ id: crypto.randomUUID(), name: name.trim(), machine_id: Number(machine), waypoints: pts.map((p) => ({ lat: p.lat, lon: p.lon, ...(p.label ? { label: p.label } : {}) })), note: note.trim() || undefined })); }
    catch (e) { setErr((e as Error).message); setBusy(false); }
  };

  return (
    <Sheet title="Asignar ruta" onClose={onClose}>
      <label>Máquina<select value={machine} onChange={(e) => setMachine(e.target.value)}><option value="">Seleccionar…</option>
        {machines.map((m) => <option key={m.id} value={m.id}>{m.name}{open.some((s) => s.machine_id === m.id) ? ' · en jornada' : ''}</option>)}</select></label>
      <label>Nombre de la ruta<input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ej.: Potrero norte → bodega" /></label>
      <MapView draft={pts} fields={mapFields} markers={live?.last_lat != null && live.last_lon != null ? [{ lat: live.last_lat, lon: live.last_lon, kind: 'machine', label: live.machine_name ?? '' }] : []}
        height={260} onTap={(p) => setPts((cur) => [...cur, p])} />
      <small className="muted">Toca el mapa para marcar los puntos en orden. {pts.length ? `${pts.length} puntos · ${formatDistance(routeLengthM(pts))}` : ''}</small>
      <div className="grid2">
        <button type="button" onClick={() => setPts((p) => p.slice(0, -1))} disabled={!pts.length}>Quitar último</button>
        <button type="button" onClick={() => setPts([])} disabled={!pts.length}>Limpiar</button>
        {live?.last_lat != null && <button type="button" onClick={startFromMachine}>Partir desde la máquina</button>}
      </div>
      {fields.some((f) => f.polygon?.length) && (
        <label>Agregar un campo como destino<select value="" onChange={(e) => addField(e.target.value)}><option value="">Elegir campo…</option>
          {fields.filter((f) => f.polygon?.length).map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</select></label>
      )}
      <label>Indicaciones (opcional)<input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Ej.: cerrar el portón al salir" /></label>
      {err && <p className="error" role="alert">{err}</p>}
      <button className="primary big" onClick={() => void save()} disabled={busy}>{busy ? 'Guardando…' : 'Asignar ruta'}</button>
    </Sheet>
  );
}
