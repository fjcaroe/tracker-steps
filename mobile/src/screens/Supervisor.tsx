import { useEffect, useState } from 'react';
import { mobile, sessions, type DeviceOut, type IncidentOut, type SessionSummary } from '../lib/api';

const CATEGORY: Record<string, string> = { breakdown: 'Falla mecánica', accident: 'Accidente', damage: 'Daño', theft: 'Robo', sos: 'SOS', other: 'Otro' };
const when = (iso: string) => new Date(iso).toLocaleString('es-CL', { dateStyle: 'short', timeStyle: 'short' });

/** Vista de supervisor (I13): solo lo urgente — incidentes por atender, jornadas abiertas y estado de los teléfonos. */
export default function Supervisor() {
  const [incidents, setIncidents] = useState<IncidentOut[]>([]);
  const [open, setOpen] = useState<SessionSummary[]>([]);
  const [devices, setDevices] = useState<DeviceOut[]>([]);
  const [error, setError] = useState('');
  const [photo, setPhoto] = useState<{ id: string; url: string } | null>(null);

  const load = () => {
    setError('');
    Promise.all([mobile.incidents(), sessions.mine(100), mobile.devices()])
      .then(([i, s, d]) => { setIncidents(i); setOpen(s.filter((x) => x.status === 'open')); setDevices(d); })
      .catch((e: Error) => setError(e.message));
  };
  useEffect(load, []);

  const act = async (i: IncidentOut, status: 'attended' | 'closed') => {
    try { const next = await mobile.setIncident(i.id, status); setIncidents((p) => p.map((x) => (x.id === i.id ? next : x))); }
    catch (e) { setError((e as Error).message); }
  };
  const showPhoto = async (i: IncidentOut) => { try { setPhoto({ id: i.id, url: await mobile.photo('incidents', i.id) }); } catch (e) { setError((e as Error).message); } };

  const pending = incidents.filter((i) => i.status !== 'closed');
  return (
    <section className="stack">
      <h1>Supervisor</h1>
      {error && <p className="error" role="alert">{error}</p>}
      <h2>Incidentes por atender ({pending.length})</h2>
      {!pending.length && <p className="muted">Sin incidentes pendientes.</p>}
      {pending.map((i) => (
        <article key={i.id} className={`card stack ${i.category === 'sos' ? 'card--alert' : ''}`}>
          <div className="row"><div><strong>{CATEGORY[i.category] ?? i.category}</strong><small>{i.machine_name ?? 'Sin máquina'} · {i.user_name ?? ''} · {when(i.occurred_at)}</small></div>
            <span className="chip">{i.status === 'open' ? 'Abierto' : 'Atendiendo'}</span></div>
          {i.note && <p>{i.note}</p>}
          <div className="grid2">
            {i.lat != null && i.lon != null && <a className="btnlink" href={`https://www.google.com/maps?q=${i.lat},${i.lon}`} target="_blank" rel="noreferrer">Ver ubicación</a>}
            {i.has_photo && <button onClick={() => void showPhoto(i)}>Ver foto</button>}
            {i.status === 'open' && <button onClick={() => void act(i, 'attended')}>Atender</button>}
            <button className="primary" onClick={() => void act(i, 'closed')}>Cerrar</button>
          </div>
          {photo?.id === i.id && <img src={photo.url} alt="Foto del incidente" className="photo" />}
        </article>
      ))}
      <h2>Jornadas abiertas ({open.length})</h2>
      {open.map((s) => <article key={s.id} className="card row"><div><strong>{s.machine_name ?? `Máquina ${s.machine_id}`}</strong><small>Desde {when(s.started_at)} · {s.points_count} puntos{s.cost_center_name ? ` · ${s.cost_center_name}` : ''}</small></div><span className="chip chip--open">En curso</span></article>)}
      <h2>Teléfonos</h2>
      {!devices.length && <p className="muted">Aún no hay teléfonos reportando.</p>}
      {devices.map((d) => <article key={d.user_id} className="card"><strong>{d.user_name ?? `Usuario ${d.user_id}`}</strong><small>v{d.version ?? '?'} · {d.platform ?? 'web'} · {d.pending ?? 0} pendientes · última sincronización {d.last_sync_at ? when(d.last_sync_at) : 'nunca'}</small></article>)}
      <button onClick={load}>Actualizar</button>
    </section>
  );
}
