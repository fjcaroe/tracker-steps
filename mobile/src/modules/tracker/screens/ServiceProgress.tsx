import { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api';
import type { Manifest } from '../lib/passengers';

type Stop = {
  id: string;
  name: string;
  scheduled_at: string;
  arrived_at: string | null;
  departed_at: string | null;
  eta: string | null;
  delay_minutes: number;
  arrival_notes: string | null;
  departure_notes: string | null;
};

type Progress = {
  id: string;
  name: string;
  route_name: string;
  route_status: string;
  driver_name: string;
  version: number;
  stops: Stop[];
  closure: { closed_at: string; signature: string; notes: string | null; manifest_hash: string } | null;
};

type Update = {
  id: string;
  kind: 'arrived' | 'departed' | 'closed';
  expected_version: number;
  stop_id?: string;
  notes: string;
  signature?: string;
  manifest_version?: number;
};

const time = (value: string) => new Date(value).toLocaleString('es-CL', {
  timeZone: 'America/Santiago', dateStyle: 'short', timeStyle: 'short',
});

function Stops({ stops }: { stops: Stop[] }) {
  return <ol className="stack">{stops.map((stop) => <li key={stop.id}>
    <strong>{stop.name}</strong>
    <div>Horario previsto {time(stop.scheduled_at)}</div>
    {stop.arrived_at && <div>Llegada {time(stop.arrived_at)}</div>}
    {stop.departed_at && <div>Salida {time(stop.departed_at)}</div>}
    {stop.eta && <div>Llegada estimada {time(stop.eta)}</div>}
    {stop.delay_minutes > 0 && <div>Retraso de {stop.delay_minutes} min</div>}
    {stop.arrival_notes && <div>{stop.arrival_notes}</div>}
    {stop.departure_notes && <div>{stop.departure_notes}</div>}
  </li>)}</ol>;
}

function Closure({ closure }: { closure: NonNullable<Progress['closure']> }) {
  return <div>
    <strong>Manifiesto firmado</strong>
    <div>{closure.signature} · {time(closure.closed_at)}</div>
    {closure.notes && <div>{closure.notes}</div>}
  </div>;
}

export default function ServiceProgress({ manifest, pending, online, onClosed }: {
  manifest: Manifest; pending: number; online: boolean; onClosed: () => void;
}) {
  const [progress, setProgress] = useState<Progress | null>(null);
  const [error, setError] = useState('');
  const [notes, setNotes] = useState('');
  const [signature, setSignature] = useState('');
  const [busy, setBusy] = useState(false);
  const retry = useRef<Update | null>(null);
  const path = '/mobile/services/' + manifest.id + '/progress';

  useEffect(() => {
    if (!online) return;
    const controller = new AbortController();
    let requesting = false;
    const update = async () => {
      if (requesting || document.visibilityState === 'hidden') return;
      requesting = true;
      try {
        const result = await api<Progress>(path, { cache: 'no-store', signal: controller.signal });
        if (!controller.signal.aborted) setProgress((old) => !old || result.version >= old.version ? result : old);
      } catch (cause) {
        if (!controller.signal.aborted) setError((cause as Error).message);
      } finally { requesting = false; }
    };
    void update();
    const timer = window.setInterval(() => void update(), 10_000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [path, online]);

  const record = async (values: Omit<Update, 'id'>) => {
    if (!online || busy) return;
    setBusy(true); setError('');
    const previous = retry.current;
    const payload = previous && JSON.stringify({ ...values, id: previous.id }) === JSON.stringify(previous)
      ? previous : { ...values, id: crypto.randomUUID() };
    retry.current = payload;
    try {
      const result = await api<Progress>(path, { method: 'POST', body: JSON.stringify(payload) });
      setProgress((old) => !old || result.version >= old.version ? result : old);
      retry.current = null;
      setNotes(''); setSignature('');
      if (result.closure) onClosed();
    } catch (cause) {
      setError((cause as Error).message);
    } finally { setBusy(false); }
  };

  const stops = progress?.stops ?? manifest.stops.map((stop) => ({
    ...stop, arrived_at: null, departed_at: null, eta: null, delay_minutes: 0,
    arrival_notes: null, departure_notes: null,
  }));
  const next = stops.find((stop) => !stop.departed_at);
  const readyToClose = pending === 0 && manifest.passengers.every((passenger) =>
    passenger.state === 'alighted' || passenger.state === 'no_show');
  return <div className="stack">
    {error && <p role="alert" className="error">{error}</p>}
    {!online && <p>Conéctate para registrar el avance o firmar el manifiesto.</p>}
    <Stops stops={stops} />
    {progress?.closure && <Closure closure={progress.closure} />}
    {progress && !progress.closure && progress.route_status !== 'cancelled' && <div className="stack">
      <label>{next ? 'Desvío o novedad de la parada' : 'Novedades del servicio'}
        <textarea value={notes} onChange={(event) => setNotes(event.target.value)} maxLength={1000} />
      </label>
      {next ? <button disabled={!online || busy} onClick={() => void record({
        kind: next.arrived_at ? 'departed' : 'arrived',
        stop_id: next.id, expected_version: progress.version, notes,
      })}>{next.arrived_at ? 'Registrar salida' : 'Registrar llegada'} de {next.name}</button> : <>
        {!readyToClose && <p>Sincroniza la nómina y registra los descensos y ausencias pendientes antes de firmar.</p>}
        <label>Firma del conductor<input value={signature} onChange={(event) => setSignature(event.target.value)} maxLength={200} /></label>
        <button disabled={!online || busy || !readyToClose || signature.trim().length < 2}
          onClick={() => void record({ kind: 'closed', expected_version: progress.version,
            manifest_version: manifest.manifest_version, signature: signature.trim(), notes })}>Firmar y cerrar el manifiesto</button>
      </>}
    </div>}
  </div>;
}

export function ServiceProgressMonitor() {
  const [services, setServices] = useState<Progress[] | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    let requesting = false;
    const update = async () => {
      if (requesting || document.visibilityState === 'hidden') return;
      requesting = true;
      try {
        const data = await api<Progress[]>('/mobile/services/progress', { cache: 'no-store', signal: controller.signal });
        if (!controller.signal.aborted) { setServices(data); setError(''); }
      } catch (cause) {
        if (!controller.signal.aborted) setError((cause as Error).message);
      } finally { requesting = false; }
    };
    void update();
    const timer = window.setInterval(() => void update(), 10_000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, []);
  return <div className="stack">
    {error && <p role="alert" className="error">{error}</p>}
    {!services && !error && <p role="status">Consultando servicios…</p>}
    {services?.length === 0 && <p>Sin servicios de pasajeros.</p>}
    {services?.map((service) => <article className="stack" key={service.id}>
      <h3>{service.name}</h3>
      <small>{service.route_name} · {service.driver_name}</small>
      {service.route_status === 'cancelled' && <p>Ruta cancelada</p>}
      <Stops stops={service.stops} />
      {service.closure && <Closure closure={service.closure} />}
    </article>)}
  </div>;
}
