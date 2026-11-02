import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError, type PassengerService } from '../lib/api';
import { findPassenger, passengerStore, project, syncPassengers, type BoardingEvent, type Manifest, type Workspace } from '../lib/passengers';
import PassengerScanner from '../components/PassengerScanner';
import './passenger-service.css';

const labels = { pending: 'Pendiente', boarded: 'A bordo', alighted: 'Descendió', no_show: 'Ausente' };
const localTime = (value: string) => new Date(value).toLocaleString('es-CL', { timeZone: 'America/Santiago', dateStyle: 'short', timeStyle: 'short' });

export default function MyService({ userId }: { userId: number }) {
  const [services, setServices] = useState<PassengerService[]>([]);
  const [selected, setSelected] = useState('');
  const [remote, setRemote] = useState<Manifest | null>(null);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('Consultando servicios asignados…');
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [code, setCode] = useState('');
  const [camera, setCamera] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [locationEnabled, setLocationEnabled] = useState(false);
  const location = useRef<GeolocationPosition | null>(null);
  const alive = useRef(true);
  const generation = useRef(0);

  const refresh = useCallback(async () => {
    const current = ++generation.current;
    setError(''); setConflict(false);
    try {
      const cached = await passengerStore.read(userId);
      if (!alive.current || generation.current !== current) return;
      const chosen = selected || cached.find((r) => r.base)?.serviceId || cached.find((r) => r.queue.length)?.serviceId || '';
      setWorkspace(cached.find((r) => r.serviceId === chosen) ?? null);
      if (!navigator.onLine) {
        setServices(cached.flatMap((r) => r.base ? [r.base] : []));
        setSelected(chosen); setRemote(null); setStatus('Sin señal. Solo puedes operar servicios preparados durante las últimas 24 horas.'); return;
      }
      await syncPassengers(userId);
      const rows = await api<PassengerService[]>('/mobile/services?mine=true', { cache: 'no-store' });
      const id = selected && rows.some((r) => r.id === selected) ? selected : rows[0]?.id ?? '';
      const manifest = id ? await api<Manifest>('/mobile/services/' + id + '/manifest', { cache: 'no-store' }) : null;
      if (!alive.current || generation.current !== current) return;
      const existing = (await passengerStore.read(userId)).find((r) => r.serviceId === id);
      if (manifest && existing?.base && !existing.queue.length) await passengerStore.prepare(userId, manifest);
      if (!alive.current || generation.current !== current) return;
      setServices(rows); setSelected(id); setRemote(manifest);
      setWorkspace((await passengerStore.read(userId)).find((r) => r.serviceId === id) ?? null);
      setStatus('Consulta actualizada. Los cambios confirmados están guardados en el servidor.');
    } catch (cause) {
      if (!alive.current || generation.current !== current) return;
      if (cause instanceof ApiError && [401, 403, 404].includes(cause.status)) {
        await passengerStore.forget(userId); setRemote(null); setWorkspace(null); setServices([]);
      }
      setError(cause instanceof Error ? cause.message : 'No se pudo consultar tu servicio.');
      setConflict(cause instanceof ApiError && cause.status === 409);
      setStatus('Los pendientes se conservan. No borres los datos del navegador.');
    }
  }, [userId, selected]);

  useEffect(() => {
    alive.current = true; void refresh();
    const update = () => { if (document.visibilityState !== 'hidden') void refresh(); };
    window.addEventListener('online', update); window.addEventListener('offline', update); document.addEventListener('visibilitychange', update);
    const timer = window.setInterval(update, 30_000);
    return () => { alive.current = false; generation.current++; clearInterval(timer); window.removeEventListener('online', update); window.removeEventListener('offline', update); document.removeEventListener('visibilitychange', update); };
  }, [refresh]);
  useEffect(() => {
    if (!locationEnabled) return;
    if (!navigator.geolocation) { setError('No hay ubicación disponible. Puedes registrar sin ubicación.'); return; }
    const id = navigator.geolocation.watchPosition((position) => { location.current = position; }, () => {
      location.current = null; setError('Sin ubicación disponible. El evento se registrará sin coordenadas.');
    }, { enableHighAccuracy: true, maximumAge: 15_000, timeout: 10_000 });
    return () => { navigator.geolocation.clearWatch(id); location.current = null; };
  }, [locationEnabled]);

  const manifest = workspace && project(workspace) || remote;
  const manifestRef = useRef(manifest);
  manifestRef.current = manifest;
  const prepared = Boolean(workspace && project(workspace));
  const review = async () => {
    setBusy(true);
    try {
      const confirmed = await api<Manifest>('/mobile/services/' + selected + '/manifest', { cache: 'no-store' });
      const queued = (await passengerStore.read(userId)).find((r) => r.serviceId === selected)?.queue ?? [];
      const lines = queued.map((e) => (confirmed.passengers.find((p) => p.id === e.passenger_id)?.name ?? 'Pasajero') + ': ' + labels[e.kind]);
      if (!confirm('El servidor tiene ' + confirmed.occupied + ' pasajeros a bordo. Revisa tus pendientes:\n' + lines.join('\n') + '\n¿Validar estos eventos contra el manifiesto actual y reintentar? No se descartarán eventos sin confirmar.')) return;
      await passengerStore.reconcile(userId, confirmed); await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'No se pudo revisar.'); }
    finally { setBusy(false); }
  };
  const act = async (passengerId: string, kind: BoardingEvent['kind']) => {
    setBusy(true); setError('');
    try {
      const pos = location.current;
      const fresh = locationEnabled && pos && Date.now() - pos.timestamp < 30_000;
      await passengerStore.enqueue(userId, selected, passengerId, kind, fresh ? {
        lat: pos.coords.latitude, lon: pos.coords.longitude, accuracy_m: pos.coords.accuracy,
      } : null);
      setWorkspace((await passengerStore.read(userId)).find((r) => r.serviceId === selected) ?? null);
      setStatus('Registro guardado en este teléfono. Pendiente de confirmación del servidor.');
      if (navigator.onLine) await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'No se pudo guardar.'); }
    finally { if (alive.current) setBusy(false); }
  };
  const onCode = useCallback((value: string) => {
    setCamera(false);
    const manifest = manifestRef.current;
    const id = manifest && findPassenger(manifest, value);
    if (!id) { setError('El código no corresponde a un pasajero de este servicio. No se registró nada.'); return; }
    setCode(value); setQuery(manifest!.passengers.find((p) => p.id === id)!.name); setFilter('all');
  }, []);

  return <section className="stack" aria-labelledby="my-service-heading">
    <div className="row"><h2 id="my-service-heading">Mi servicio</h2><button disabled={busy} onClick={() => void refresh()}>Actualizar servicio</button></div>
    {error && <p role="alert" className="error">{error}</p>}
    {conflict && <button disabled={busy || !navigator.onLine} onClick={() => void review()}>Revisar pendientes con el servidor</button>}
    <p role="status" className="muted">{status}</p>
    {!services.length && !manifest && !error && status !== 'Consultando servicios asignados…' && <p>No tienes servicios de pasajeros asignados.</p>}
    {services.length > 1 && <label>Servicio<select value={selected} onChange={(e) => { setSelected(e.target.value); setRemote(null); setWorkspace(null); setQuery(''); setFilter('all'); }}>{services.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>}
    {manifest && <article className="card stack passenger-service">
      <header><h3>{manifest.name}</h3><p>{manifest.route_name} · {manifest.machine_name}{manifest.plate ? ' · ' + manifest.plate : ''}</p><small>Conductor: {manifest.driver_name}</small></header>
      {manifest.route_status === 'cancelled' && <p role="alert">Ruta cancelada. Confirma el servicio con tu supervisor.</p>}
      <div className="passenger-stats" aria-label="Ocupación"><strong>{manifest.occupied} / {manifest.capacity}<small>A bordo / capacidad</small></strong><strong>{manifest.passengers.filter((p) => p.state === 'no_show').length}<small>Ausentes</small></strong><strong>{workspace?.queue.length ?? 0}<small>Por sincronizar</small></strong></div>
      {manifest.occupied >= manifest.capacity && <p role="status">Capacidad completa. Registra los descensos antes de nuevas subidas.</p>}
      {!prepared ? <section className="passenger-notice"><p>Prepara la nómina para registrar pasajeros, incluso sin señal. Se guardará en este teléfono por 24 horas y se retirará al cerrar sesión. Los eventos pendientes se conservan sin nombres ni RUT.</p><button className="primary" disabled={busy || !navigator.onLine} onClick={() => {
        setBusy(true); void passengerStore.prepare(userId, manifest).then(refresh).catch((e: Error) => setError(e.message)).finally(() => setBusy(false));
      }}>Preparar servicio en este teléfono</button></section> : <p className="muted">Preparado hasta {localTime(new Date(workspace!.expiresAt).toISOString())}. Mantén la app abierta durante el viaje sin señal.</p>}
      <details><summary>Paradas y horarios</summary><ol>{manifest.stops.map((stop) => <li key={stop.id}><strong>{stop.name}</strong><br /><time dateTime={stop.scheduled_at}>{localTime(stop.scheduled_at)}</time></li>)}</ol></details>
      <label>Buscar pasajero<input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Nombre o RUT / ID" /></label>
      <label>Mostrar<select value={filter} onChange={(e) => setFilter(e.target.value)}><option value="all">Todos los pasajeros</option>{Object.entries(labels).map(([state, label]) => <option key={state} value={state}>{label}</option>)}</select></label>
      <details><summary>Leer QR o ingresar código</summary><p>El QR debe contener el UUID de la nómina, solo o precedido de steps:passenger:. Un lector externo también puede escribirlo aquí. Confirma la acción después de leer.</p><label>Código del pasajero<input value={code} onChange={(e) => setCode(e.target.value)} /></label><div className="passenger-actions"><button onClick={() => onCode(code)}>Buscar código</button><button onClick={() => setCamera(true)}>Abrir cámara</button></div></details>
      {camera && <PassengerScanner onCode={onCode} onClose={() => setCamera(false)} />}
      <label className="passenger-location"><input type="checkbox" checked={locationEnabled} onChange={(e) => setLocationEnabled(e.target.checked)} />Incluir ubicación del teléfono cuando esté disponible</label>
      <p className="muted">Sin permiso o sin lectura reciente se guarda la hora sin coordenadas.</p>
      <ul className="passenger-service__manifest">{manifest.passengers.filter((p) => (filter === 'all' || p.state === filter) && (p.name + ' ' + p.document).toLocaleLowerCase().includes(query.toLocaleLowerCase())).map((passenger) => {
        const last = [...(workspace?.queue ?? []), ...manifest.events].filter((e) => e.passenger_id === passenger.id).sort((a, b) => Date.parse(b.occurred_at) - Date.parse(a.occurred_at))[0];
        const waiting = workspace?.queue.some((e) => e.passenger_id === passenger.id);
        const stop = (id: string) => manifest.stops.find((s) => s.id === id)?.name ?? 'Parada';
        return <li key={passenger.id}>
          <div className="row"><strong>{passenger.name}</strong><span className={'chip passenger-' + passenger.state}>{labels[passenger.state]}</span></div>
          <small>RUT/ID: {passenger.document} · {passenger.seat == null ? 'Sin asiento asignado' : 'Asiento ' + passenger.seat}</small>
          <small>{stop(passenger.boarding_stop_id)} → {stop(passenger.alighting_stop_id)}</small>
          {last && <small>{localTime(last.occurred_at)}{waiting ? ' · Por sincronizar' : ' · Confirmado'}</small>}
          <div className="passenger-actions">
            {['pending', 'no_show'].includes(passenger.state) && <button className="primary" disabled={!prepared || busy || conflict || manifest.route_status === 'cancelled' || manifest.occupied >= manifest.capacity} onClick={() => void act(passenger.id, 'boarded')}>Registrar subida</button>}
            {passenger.state === 'boarded' && <button className="primary" disabled={!prepared || busy || conflict || manifest.route_status === 'cancelled'} onClick={() => void act(passenger.id, 'alighted')}>Registrar bajada</button>}
            {passenger.state === 'pending' && <button disabled={!prepared || busy || conflict || manifest.route_status === 'cancelled'} onClick={() => { if (confirm('¿Marcar a ' + passenger.name + ' como ausente? Podrás registrar su subida si llega después.')) void act(passenger.id, 'no_show'); }}>Marcar ausente</button>}
          </div>
        </li>;
      })}</ul>
      <button disabled={busy || !navigator.onLine} onClick={() => void refresh()}>Sincronizar pendientes</button>
    </article>}
    {!manifest && workspace && workspace.queue.length > 0 && <p role="alert">La preparación venció. Conservamos {workspace.queue.length} eventos. Recupera señal para sincronizarlos.</p>}
  </section>;
}
