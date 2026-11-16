import { useEffect, useState } from 'react';
import { mobile, type DeviceOut } from '../lib/api';

const formatTime = new Intl.DateTimeFormat('es-CL', { timeZone: 'America/Santiago', dateStyle: 'short', timeStyle: 'short' });

function ReportTime({ value }: { value: string | null }) {
  if (!value || !Number.isFinite(Date.parse(value))) return <>Sin registro</>;
  return <time dateTime={value}>{formatTime.format(new Date(value))}</time>;
}

export default function TrackerHealth() {
  const [records, setRecords] = useState<DeviceOut[] | null>(null);
  const [query, setQuery] = useState('');
  const [failure, setFailure] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [requested, setRequested] = useState(0);

  useEffect(() => {
    let active = true;
    let running = false;
    async function load() {
      if (!active || running) return;
      running = true;
      setRefreshing(true);
      try {
        const next = await mobile.devices();
        if (active) { setRecords(next); setFailure(false); }
      } catch {
        if (active) setFailure(true);
      } finally {
        running = false;
        if (active) setRefreshing(false);
      }
    }
    void load();
    const timer = window.setInterval(() => void load(), 30_000);
    return () => { active = false; window.clearInterval(timer); };
  }, [requested]);

  const search = query.trim().toLocaleLowerCase('es-CL');
  const visible = (records ?? []).filter(({ user_name, user_id }) =>
    (user_name ?? `Usuario ${user_id}`).toLocaleLowerCase('es-CL').includes(search));

  return <section className="stack" aria-label="Salud de Steps Móvil">
    <label>Buscar conductor <input type="search" value={query} onChange={event => setQuery(event.target.value)} /></label>
    <button type="button" onClick={() => setRequested(value => value + 1)} disabled={refreshing}>
      {refreshing ? 'Consultando…' : 'Actualizar estado'}
    </button>
    {failure && <p role="alert">{records ? 'No se pudo actualizar. Se muestra la última consulta.' : 'No se pudo consultar el estado de Steps Móvil.'}</p>}
    {!records && refreshing && <p role="status">Consultando el estado de Steps Móvil.</p>}
    {records && !visible.length && <p role="status">{search ? 'No hay conductores que coincidan con la búsqueda.' : 'Aún no hay reportes de Steps Móvil.'}</p>}
    {visible.map(record => <article key={record.user_id} className="card">
      <h3>{record.user_name ?? `Usuario ${record.user_id}`}</h3>
      <dl>
        <dt>Versión</dt><dd>{record.version ?? 'Sin registro'}</dd>
        <dt>Plataforma</dt><dd>{record.platform ?? 'Sin registro'}</dd>
        <dt>Última sincronización confirmada</dt><dd><ReportTime value={record.last_sync_at} /></dd>
        <dt>Último reporte de la app</dt><dd><ReportTime value={record.last_seen_at} /></dd>
        <dt>Registros pendientes</dt><dd>{record.pending ?? 'Sin registro'}</dd>
      </dl>
    </article>)}
  </section>;
}
