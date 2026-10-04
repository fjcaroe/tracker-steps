import { useEffect, useState } from 'react';
import { sessions, type SessionSummary } from '../lib/api';
import { formatDuration } from '../lib/queue';

export default function History() {
  const [rows, setRows] = useState<SessionSummary[] | null>(null);
  const [error, setError] = useState('');
  const load = () => { setError(''); sessions.mine().then(setRows).catch((e: Error) => setError(e.message)); };
  useEffect(load, []);

  if (error) return <section className="card"><p className="error" role="alert">{error}</p><button onClick={load}>Reintentar</button></section>;
  if (!rows) return <p role="status" className="muted">Cargando historial…</p>;
  if (!rows.length) return <section className="card empty"><h2>Aún no hay jornadas</h2><p>Cuando registres tu primera jornada aparecerá aquí.</p></section>;

  return (
    <section className="list" aria-label="Mis jornadas">
      {rows.map((s) => {
        const ms = (s.ended_at ? new Date(s.ended_at).getTime() : Date.now()) - new Date(s.started_at).getTime();
        return (
          <article key={s.id} className="card row">
            <div>
              <strong>{s.machine_name ?? `Máquina ${s.machine_id}`}</strong>
              <small>{new Date(s.started_at).toLocaleString('es-CL', { dateStyle: 'medium', timeStyle: 'short' })}{s.cost_center_name ? ` · ${s.cost_center_name}` : ''}</small>
              <small>{formatDuration(ms)} · {s.points_count} puntos GPS</small>
            </div>
            <span className={`chip chip--${s.status}`}>{s.status === 'open' ? 'En curso' : 'Cerrada'}</span>
          </article>
        );
      })}
    </section>
  );
}
