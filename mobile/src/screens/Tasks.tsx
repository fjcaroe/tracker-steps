import { useEffect, useState } from 'react';
import { catalogs, mobile, type Field, type Labor, type Machine, type Task } from '../lib/api';
import { beep, loadSettings } from '../lib/settings';

/** Minutos hasta la hora programada de hoy ("HH:MM"); null si no hay hora o ya pasó hace más de 2 h. */
export function minutesUntil(time: string | null, now = new Date()): number | null {
  const m = /^(\d{1,2}):(\d{2})/.exec(time ?? '');
  if (!m) return null;
  const at = new Date(now); at.setHours(Number(m[1]), Number(m[2]), 0, 0);
  const diff = Math.round((at.getTime() - now.getTime()) / 60000);
  return diff < -120 ? null : diff;
}

export default function Tasks({ onStart }: { onStart: (t: Task) => void }) {
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

  if (error) return <section className="card"><p className="error" role="alert">{error}</p><button onClick={load}>Reintentar</button></section>;
  if (!tasks) return <p role="status" className="muted">Cargando tus tareas…</p>;
  const pending = tasks.filter((t) => t.mobile_status !== 'done');
  const label = (t: Task) => `${names.labors.find((l) => l.id === t.labor_id)?.name ?? 'Labor'} · ${names.machines.find((m) => m.id === t.machine_id)?.name ?? 'Sin máquina'}`;

  return (
    <section className="stack">
      <h1>Mis tareas</h1>
      {perm === 'default' && <button onClick={() => void Notification.requestPermission().then(setPerm)}>Activar recordatorios</button>}
      {!pending.length && <section className="card empty"><h2>Sin tareas pendientes</h2><p>Cuando tu supervisor te asigne una tarea aparecerá aquí.</p></section>}
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
