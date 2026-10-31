import { useEffect, useState } from 'react';
import { api, type PassengerService } from '../lib/api';

function localTime(value: string) {
  return new Date(value).toLocaleString('es-CL', { timeZone: 'America/Santiago', dateStyle: 'short', timeStyle: 'short' });
}

/** Online, read-only manifest. Passenger personal data is never stored locally. */
export default function MyService() {
  const [services, setServices] = useState<PassengerService[] | null>(null);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let active = true;
    setServices(null); setError('');
    void api<PassengerService[]>('/mobile/services?mine=true', { cache: 'no-store' }).then(
      (rows) => { if (active) setServices(rows); },
      (cause: unknown) => { if (active) setError(cause instanceof Error ? cause.message : 'No se pudo consultar el servicio.'); },
    );
    return () => { active = false; };
  }, [reload]);
  return <section className="stack" aria-labelledby="my-service-heading">
    <h2 id="my-service-heading">Mi servicio</h2>
    {error && <section className="card"><p role="alert">No se pudo consultar tu servicio: {error}</p><button onClick={() => setReload((n) => n + 1)}>Reintentar servicio</button></section>}
    {!services && !error && <p role="status">Consultando servicios asignados…</p>}
    {services?.length === 0 && <p className="muted">No tienes servicios de pasajeros asignados.</p>}
    {services?.map((service) => {
      const stopName = (id: string) => service.stops.find((stop) => stop.id === id)?.name ?? 'Parada';
      return <article className="card stack passenger-service" key={service.id}>
        <h3>{service.name}</h3>
        <p>{service.route_name}</p>
        {service.route_status === 'cancelled' && <p role="status" className="error">Ruta cancelada. Confirma el servicio con tu supervisor.</p>}
        <p>{service.machine_name}{service.plate ? ` · ${service.plate}` : ''}<br />Conductor: {service.driver_name}<br />Capacidad: {service.capacity} pasajeros</p>
        <h4>Paradas y horarios</h4>
        <ol>{service.stops.map((stop) => <li key={stop.id}><strong>{stop.name}</strong><br /><time dateTime={stop.scheduled_at}>{localTime(stop.scheduled_at)}</time></li>)}</ol>
        <h4>Pasajeros ({service.passengers.length})</h4>
        <ul className="passenger-service__manifest">{service.passengers.map((passenger) => <li key={passenger.id}>
          <strong>{passenger.name}</strong><br /><span>RUT/ID: {passenger.document}</span><br />
          <span>{stopName(passenger.boarding_stop_id)} → {stopName(passenger.alighting_stop_id)}</span><br />
          <span>{passenger.seat == null ? 'Sin asiento asignado' : `Asiento ${passenger.seat}`}</span>
        </li>)}</ul>
      </article>;
    })}
  </section>;
}
