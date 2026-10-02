import { useEffect, useState } from 'react';
import { catalogs, mobile, type AssignedRoute, type Field, type Labor, type Machine, type Task } from '../lib/api';
import MapView from '../components/MapView';
import { formatDistance, routeLengthM } from '../lib/nav';
import { activeStore, formatDuration } from '../lib/queue';
import { routeStore } from '../lib/route';
import { beep, loadSettings } from '../lib/settings';

/** Minutos hasta la hora programada de hoy ("HH:MM"); null si no hay hora o ya pasó hace más de 2 h. */
export function minutesUntil(time: string | null, now = new Date()): number | null {
  const m = /^(\d{1,2}):(\d{2})/.exec(time ?? '');
  if (!m) return null;
  const at = new Date(now); at.setHours(Number(m[1]), Number(m[2]), 0, 0);
  const diff = Math.round((at.getTime() - now.getTime()) / 60000);
  return diff < -120 ? null : diff;
}

/** Jornada en curso en este teléfono (con su mapa), para que "Hoy" nunca aparezca vacío mientras se trabaja. */
function TodayJourney({ onOpen }: { onOpen: () => void }) {
  const [a, setA] = useState(activeStore.get());
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = setInterval(() => { setA(activeStore.get()); setNow(Date.now()); }, 3000); return () => clearInterval(t); }, []);
  const [routes, setRoutes] = useState<AssignedRoute[]>([]);
  useEffect(() => { if (a) mobile.routes(a.machineId).then(setRoutes).catch(() => {}); }, [a?.machineId]);
  if (!a) return null;
  const track = routeStore.get(a.sessionId);
  const route = routes.find((r) => r.status === 'in_progress') ?? routes[0];
  return (
    <article className="card stack">
      <div className="row"><div><strong>Jornada en curso · {a.machineName}</strong><small>{formatDuration(now - a.startedAt)} · {(a.distanceM / 1000).toFixed(2)} km{route ? ` · ruta ${route.name}` : ''}</small></div><span className="chip chip--open">● En curso</span></div>
      <MapView me={track.length ? track[track.length - 1] : null} track={track} route={route?.waypoints ?? []} height={220} />
      <button className="primary" onClick={onOpen}>Ir a mi jornada</button>
    </article>
  );
}

/** Rutas que el supervisor asignó a máquinas visibles para esta persona. */
function AssignedRoutes() {
  const [routes, setRoutes] = useState<AssignedRoute[]>([]);
  const [open, setOpen] = useState('');
  useEffect(() => { mobile.routes().then(setRoutes).catch(() => {}); }, []);
  if (!routes.length) return null;
  return (
    <>
      <h2>Rutas asignadas</h2>
      {routes.map((r) => (
        <article key={r.id} className="card stack routecard">
          <div className="row"><div><strong>{r.name}</strong><small>{r.machine_name ?? `Máquina ${r.machine_id}`} · {r.waypoints.length} puntos · {formatDistance(routeLengthM(r.waypoints))}</small></div>
            <span className={`chip ${r.status === 'in_progress' ? 'chip--open' : ''}`}>{r.status === 'in_progress' ? 'En curso' : 'Asignada'}</span></div>
          {r.note && <p>{r.note}</p>}
          <button onClick={() => setOpen(open === r.id ? '' : r.id)}>{open === r.id ? 'Ocultar mapa' : 'Ver en el mapa'}</button>
          {open === r.id && <MapView route={r.waypoints} height={240} />}
        </article>
      ))}
    </>
  );
}

export default function Tasks({ onStart, onOpenJourney }: { onStart: (t: Task) => void; onOpenJourney: () => void }) {
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [names, setNames] = useState<{ machines: Machine[]; labors: Labor[]; fields: Field[] }>({ machines: [], labors: [], fields: [] });
  const [error, setError] = useState('');
  const [perm, setPerm] = useState<string>(() => (typeof Notification === 'undefined' ? 'unsupported' : Notification.permission));

  const load = () => {
    setError('');
    mobile.tasks().then(setTasks).catch((e: Error) => setError(e.message));
    Promise.all([catalogs.machines(), catalogs.labors(), catalogs.fields()]).then(([machines, labors, fields]) => setNames({ machines, labors, fields })).catch(() => {});
  };
  useEffect(load, []);

  // Recordatorios locales mientras la app está abierta: aviso 15 min antes de la hora programada.
  useEffect(() => {
    if (!tasks) return;
    const timers = tasks.filter((t) => t.mobile_status !== 'done').flatMap((t) => {
      const left = minutesUntil(t.scheduled_time);
      if (left == null || left <= 15) return [];
      return [window.setTimeout(() => {
        beep(loadSettings().sound);
        try { if (typeof Notification !== 'undefined' && Notification.permission === 'granted') new Notification('Steps Móvil', { body: `Tarea ${t.code} a las ${t.scheduled_time}` }); } catch { /* sin notificaciones */ }
      }, (left - 15) * 60000)];
    });
    return () => timers.forEach(clearTimeout);
  }, [tasks]);

  const pending = (tasks ?? []).filter((t) => t.mobile_status !== 'done');
  const label = (t: Task) => `${names.labors.find((l) => l.id === t.labor_id)?.name ?? 'Labor'} · ${names.machines.find((m) => m.id === t.machine_id)?.name ?? 'Sin máquina'}`;

  return (
    <section className="stack">
      <h1>Hoy</h1>
      <TodayJourney onOpen={onOpenJourney} />
      <AssignedRoutes />
      <h2>Mis tareas</h2>
      {perm === 'default' && <button onClick={() => void Notification.requestPermission().then(setPerm)}>Activar recordatorios</button>}
      {error && <section className="card"><p className="error" role="alert">No se pudieron cargar tus tareas: {error}</p><button onClick={load}>Reintentar</button></section>}
      {!tasks && !error && <p role="status" className="muted">Cargando tus tareas…</p>}
      {tasks && !pending.length && <section className="card empty"><h2>Sin tareas pendientes</h2><p>Cuando tu supervisor te asigne una tarea aparecerá aquí.</p></section>}
      {pending.map((t) => {
        const left = minutesUntil(t.scheduled_time);
        return (
          <article key={t.id} className="card stack">
            <div className="row">
              <div><strong>{label(t)}</strong>
                <small>{new Date(t.work_date + 'T00:00:00').toLocaleDateString('es-CL', { dateStyle: 'medium' })}{t.scheduled_time ? ` · ${t.scheduled_time}` : ''}{names.fields.find((f) => f.id === t.field_id) ? ` · ${names.fields.find((f) => f.id === t.field_id)?.name}` : ''}</small></div>
              <span className={`chip ${t.mobile_status === 'in_progress' ? 'chip--open' : ''}`}>{t.mobile_status === 'in_progress' ? 'En curso' : left != null && left <= 30 && left >= -30 ? 'Ahora' : 'Pendiente'}</span>
            </div>
            {t.notes && <p>{t.notes}</p>}
            <button className="primary" onClick={() => onStart(t)}>{t.mobile_status === 'in_progress' ? 'Retomar tarea' : 'Iniciar tarea'}</button>
          </article>
        );
      })}
      <button onClick={load}>Actualizar</button>
    </section>
  );
}
