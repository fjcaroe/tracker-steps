import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import type { ModuleProps } from '../registry';
import { useSession, useSyncState } from '../../app/context';
import { messageFor } from '../../app/messages';
import type { Trip } from '../../shared/contracts';
import type { QueueOp } from '../../sync/queue';
import { currentPosition } from '../../platform/geo';
import { Banner, Button, Card, Chip, Confirm, Empty, Field, TopBar } from '../../shared/ui';
import { buildEvent, groupFor, mobilizationApi, MODULE, rejectionText, type EventPayload } from './service';

type View = 'servicios' | 'supervisor';

export default function Mobilization({ runtime, onExit, view: initial }: ModuleProps) {
  useSession();
  const { session } = runtime;
  const canDrive = session.can('mobilization.drive'), canSup = session.can('mobilization.supervise');
  const [view, setView] = useState<View>(initial === 'supervisor' && canSup ? 'supervisor' : canDrive ? 'servicios' : 'supervisor');
  const [tripId, setTripId] = useState<number | null>(null);
  return (
    <div className="ui-shell">
      <TopBar title="Movilización" onBack={tripId ? () => setTripId(null) : onExit} />
      <main className="ui-main"><div className="ui-screen">
        {!tripId && canDrive && canSup && (
          <div className="ui-seg" role="group" aria-label="Vista">
            <Button aria-pressed={view === 'servicios'} onClick={() => setView('servicios')}>Mis servicios</Button>
            <Button aria-pressed={view === 'supervisor'} onClick={() => setView('supervisor')}>Supervisión</Button>
          </div>)}
        {!canDrive && !canSup && <Banner tone="bad">Tu acceso a Movilización no está vigente. Conéctate para validarlo o consulta a tu administrador.</Banner>}
        {view === 'servicios' && canDrive && (tripId ? <TripView runtime={runtime} tripId={tripId} /> : <TripList runtime={runtime} onOpen={setTripId} />)}
        {view === 'supervisor' && canSup && <SupervisorView runtime={runtime} />}
      </div></main>
    </div>
  );
}

const DIRECTION: Record<string, string> = { ida: 'Ida', vuelta: 'Regreso', ida_vuelta: 'Ida y regreso' };

function TripList({ runtime, onOpen }: Pick<ModuleProps, 'runtime'> & { onOpen: (id: number) => void }) {
  const api = mobilizationApi(runtime.session.api);
  const [trips, setTrips] = useState<Trip[] | null>(null);
  const [error, setError] = useState('');
  const load = useCallback(() => { setError(''); api.trips().then((r) => setTrips(r.trips)).catch((e) => { setError(messageFor(e)); setTrips((cur) => cur ?? []); }); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(load, [load]);
  if (trips === null) return <p role="status" className="muted">Cargando servicios…</p>;
  return (
    <>
      {error && <Banner tone="warn">{error}</Banner>}
      {trips.length === 0
        ? <Card><Empty title="No tienes servicios asignados" hint="Cuando el despachador te asigne uno, aparecerá aquí." /><Button onClick={load}>Actualizar</Button></Card>
        : trips.map((t) => (
          <Button key={t.id} className="ui-card--tap" onClick={() => onOpen(t.id)}>
            <div className="ui-row"><strong>{t.route}</strong><Chip tone={t.state === 'open' ? 'ok' : 'info'}>{t.state === 'open' ? 'En curso' : 'Por iniciar'}</Chip></div>
            <small>{t.name} · {DIRECTION[t.direction] ?? t.direction} · {t.vehicle}</small>
          </Button>))}
    </>
  );
}

/** Estado visible combinando lo que dice el servidor con lo que ya hizo este teléfono (sin esperar la señal). */
function localView(trip: Trip, ops: QueueOp[]) {
  const live = ops.filter((o) => o.state !== 'rejected');
  const opened = trip.state === 'open' || live.some((o) => o.kind === 'trip_open');
  const closed = ['closed', 'validated', 'costed', 'accounted'].includes(trip.state) || live.some((o) => o.kind === 'trip_close');
  const rejectedOpen = ops.find((o) => o.kind === 'trip_open' && o.state === 'rejected');
  return { opened, closed, rejectedOpen };
}

function TripView({ runtime, tripId }: Pick<ModuleProps, 'runtime'> & { tripId: number }) {
  const api = mobilizationApi(runtime.session.api);
  const sync = useSyncState();
  const [trip, setTrip] = useState<Trip | null>(null);
  const [ops, setOps] = useState<QueueOp[]>([]);
  const [type, setType] = useState<'boarding' | 'alighting'>('boarding');
  const [identifier, setIdentifier] = useState('');
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [busy, setBusy] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);
  const group = groupFor(tripId);

  const load = useCallback(() => { api.trip(tripId).then((r) => setTrip(r.trip)).catch((e) => setError(messageFor(e))); }, [tripId]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(load, [load, sync.pending === 0]);
  useEffect(() => { void runtime.ops(MODULE).then((all) => setOps(all.filter((o) => o.group === group))); }, [runtime, sync.version, group]);

  const state = useMemo(() => (trip ? localView(trip, ops) : null), [trip, ops]);
  const events = ops.filter((o) => o.kind === 'event');

  const enqueue = async (kind: string, payload: unknown) => { await runtime.enqueue({ module: MODULE, kind, group, payload }); };
  const start = async () => { setBusy(true); setError(''); try { await enqueue('trip_open', { tripId }); setInfo('Inicio guardado. Se enviará solo.'); } catch (e) { setError(messageFor(e)); } finally { setBusy(false); } };
  const finish = async () => { setConfirmClose(false); setBusy(true); setError(''); try { await enqueue('trip_close', { tripId }); setInfo('Cierre guardado. Se enviará después de tus marcas.'); } catch (e) { setError(messageFor(e)); } finally { setBusy(false); } };
  const mark = async (e: FormEvent) => {
    e.preventDefault();
    if (!trip || !identifier.trim() || busy) return;
    setBusy(true); setError(''); setInfo('');
    try {
      // La ubicación se pide solo al marcar. Si se niega o tarda, la marca sigue valiendo sin ubicación.
      const geo = await currentPosition();
      const event = buildEvent({ type, method: 'barcode', identifier, position: geo.position });
      const payload: EventPayload = { tripId, tripName: trip.name, event, label: type === 'boarding' ? 'Subida' : 'Bajada' };
      await enqueue('event', payload);
      setIdentifier('');
      setInfo(geo.reason === 'denied' ? 'Marca guardada sin ubicación (permiso de ubicación denegado). Puedes activarlo en los ajustes del teléfono.' : 'Marca guardada. Se enviará solo.');
    } catch (err) { setError(messageFor(err)); } finally { setBusy(false); }
  };

  if (!trip || !state) return error ? <><Banner tone="bad">{error}</Banner><Button onClick={load}>Reintentar</Button></> : <p role="status" className="muted">Cargando…</p>;
  const aboard = trip.aboard_count;
  return (
    <>
      <Card label="Servicio">
        <div className="ui-row"><div><small>{trip.name} · {trip.vehicle}</small><h2>{trip.route}</h2></div>
          <Chip tone={state.closed ? 'info' : state.opened ? 'ok' : 'warn'}>{state.closed ? 'Finalizado' : state.opened ? 'En curso' : 'Por iniciar'}</Chip></div>
        <div className="grid3"><div><strong>{aboard}</strong>A bordo</div><div><strong>{trip.boarded_count}</strong>Subidas</div><div><strong>{trip.alighted_count}</strong>Bajadas</div></div>
        <small>Capacidad {trip.capacity}. Las cifras confirmadas llegan del servidor; tus marcas pendientes se suman al enviarse.</small>
        {trip.overcapacity && <Banner tone="warn">Sobrecupo registrado en este servicio.</Banner>}
        {state.rejectedOpen && <Banner tone="bad">No se pudo iniciar el servicio: {rejectionText(state.rejectedOpen.error)}</Banner>}
      </Card>
      {error && <Banner tone="bad">{error}</Banner>}
      {info && <Banner tone="ok">{info}</Banner>}

      {!state.opened && !state.closed && <Button variant="primary" className="big" disabled={busy} onClick={() => void start()}>Iniciar servicio</Button>}
      {state.opened && !state.closed && (
        <>
          <form className="ui-card" onSubmit={mark}>
            <h3>Marcar pasajero</h3>
            <div className="ui-seg" role="group" aria-label="Tipo de marca">
              <Button aria-pressed={type === 'boarding'} onClick={() => setType('boarding')}>Subida</Button>
              <Button aria-pressed={type === 'alighting'} onClick={() => setType('alighting')}>Bajada</Button>
            </div>
            <Field label="Código del pasajero" hint="Escribe o escanea con un lector."><input value={identifier} onChange={(e) => setIdentifier(e.target.value)} autoFocus autoCapitalize="none" autoComplete="off" /></Field>
            <button className="ui-btn ui-btn--primary" disabled={busy || !identifier.trim()}>{busy ? 'Guardando…' : 'Registrar marca'}</button>
          </form>
          <Button variant="danger" disabled={busy} onClick={() => setConfirmClose(true)}>Finalizar servicio</Button>
        </>
      )}

      <Card label="Marcas de este teléfono">
        <h3>Marcas de este teléfono</h3>
        {events.length === 0 ? <Empty title="Aún no marcas pasajeros" /> : <ul className="ui-list">{[...events].reverse().map((o) => <EventRow key={o.id} op={o} />)}</ul>}
      </Card>
      {confirmClose && <Confirm danger title="¿Finalizar el servicio?" body={<p>No podrás marcar más pasajeros en este servicio. Las marcas pendientes se envían antes del cierre.</p>} confirmLabel="Finalizar" onCancel={() => setConfirmClose(false)} onConfirm={() => void finish()} />}
    </>
  );
}

function EventRow({ op }: { op: QueueOp }) {
  const p = op.payload as EventPayload;
  const time = new Date(p.event.device_datetime).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' });
  const what = `${p.label} · ${time}`;
  if (op.state === 'confirmed') return <li><span>{what}</span><Chip tone="ok">Confirmada</Chip></li>;
  if (op.state === 'rejected') return <li><span>{what}<small>{rejectionText(op.error)}</small></span><Chip tone="bad">Rechazada</Chip></li>;
  if (op.state === 'auth_required') return <li><span>{what}<small>Requiere que vuelvas a entrar o que se revise tu acceso.</small></span><Chip tone="bad">Requiere acceso</Chip></li>;
  return <li><span>{what}<small>Se enviará al volver la señal</small></span><Chip tone="warn">Pendiente</Chip></li>;
}

function SupervisorView({ runtime }: Pick<ModuleProps, 'runtime'>) {
  const api = mobilizationApi(runtime.session.api);
  const [trips, setTrips] = useState<Trip[] | null>(null);
  const [error, setError] = useState('');
  const load = useCallback(() => { setError(''); api.supervisorTrips().then((r) => setTrips(r.trips)).catch((e) => { setError(messageFor(e)); setTrips((cur) => cur ?? []); }); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(load, [load]);
  if (trips === null) return <p role="status" className="muted">Cargando…</p>;
  return (
    <>
      {error && <Banner tone="warn">{error}</Banner>}
      <Button onClick={load}>Actualizar</Button>
      {trips.length === 0 ? <Card><Empty title="No hay servicios hoy" /></Card> : trips.map((t) => (
        <Card key={t.id} label={t.name}>
          <div className="ui-row"><div><strong>{t.route}</strong><small>{t.name} · Chofer: {t.driver ?? '—'}</small></div><Chip tone={t.state === 'open' ? 'ok' : 'info'}>{t.state}</Chip></div>
          <div className="grid3"><div><strong>{t.aboard_count}</strong>A bordo</div><div><strong>{t.boarded_count}</strong>Subidas</div><div><strong>{t.alighted_count}</strong>Bajadas</div></div>
          {(t.events ?? []).length > 0 && <ul className="ui-list">{t.events!.slice(-8).map((e) => <li key={e.idempotency_key}><span>{e.passenger}<small>{e.event_type === 'boarding' ? 'Subió' : 'Bajó'} · registrado por {e.by ?? '—'}</small></span></li>)}</ul>}
        </Card>))}
    </>
  );
}
