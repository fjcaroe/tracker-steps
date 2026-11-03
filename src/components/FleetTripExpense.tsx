import { useMemo, useState } from 'react';
import { dateLabel, type FleetAsset, type FleetContext } from '../services/fleetApi';
import { buildTrail, type TrailPoint } from '../services/fleetTrail';

export default function FleetTripExpense({ asset, context, points, incomplete, onFocus, onPreview }: {
  asset: FleetAsset; context: FleetContext; points: TrailPoint[]; incomplete: boolean;
  onFocus: (point: TrailPoint) => void; onPreview: (from: number, to: number) => void;
}) {
  const [start, setStart] = useState(0);
  const [end, setEnd] = useState(points.length - 1);
  const [error, setError] = useState('');
  const first = points[start], last = points[end];
  const from = Date.parse(first.recorded_at), to = Date.parse(last.recorded_at);
  const selection = useMemo(() => buildTrail(points, from, to), [points, from, to]);
  const km = Math.round(selection.distanceM / 10) / 100;
  const blocked = incomplete || km < .01 || selection.gapCount > 0;
  const locate = (p: TrailPoint) => p.lat.toFixed(5) + ', ' + p.lon.toFixed(5);
  const open = () => {
    if (blocked) return;
    try {
      sessionStorage.setItem('steps.tracker.expenseTrip', JSON.stringify({
        created: Date.now(), company: context.company_id, asset: asset.asset_id,
        start: first.recorded_at, end: last.recorded_at, km, origin: locate(first), destination: locate(last),
      }));
      window.location.assign('/odoo/action-step_expense_tracker.action_gps_trip_expense');
    } catch {
      setError('No se pudo preparar el tramo en este navegador. Comprueba que permita guardar datos de sesión.');
    }
  };
  return <section className="trail-claim" aria-labelledby="trail-claim-title">
    <div className="trail-claim-intro"><div><h3 id="trail-claim-title">Rendir un viaje especial</h3>
      <p>Marca el inicio y el fin en el historial. Podrás editar los lugares y adjuntar el comprobante en Odoo.</p></div>
      <strong>{km.toLocaleString('es-CL', { maximumFractionDigits: 2 })} km <small>GPS estimados</small></strong></div>
    <div className="trail-claim-bounds">
      <label>Inicio del tramo <output>{dateLabel(first.recorded_at)}</output>
        <input type="range" min={0} max={points.length - 2} value={start}
          aria-label="Inicio del tramo" aria-valuetext={dateLabel(first.recorded_at)}
          onChange={e => { const i = Math.min(Number(e.target.value), end - 1); setStart(i); onFocus(points[i]); }} /></label>
      <label>Fin del tramo <output>{dateLabel(last.recorded_at)}</output>
        <input type="range" min={1} max={points.length - 1} value={end}
          aria-label="Fin del tramo" aria-valuetext={dateLabel(last.recorded_at)}
          onChange={e => { const i = Math.max(Number(e.target.value), start + 1); setEnd(i); onFocus(points[i]); }} /></label>
    </div>
    <div className="trail-claim-actions">
      <button type="button" onClick={() => onPreview(from, to)}>Ver tramo en el mapa</button>
      <button type="button" className="fleet-primary" disabled={blocked} onClick={open}>Abrir en Rendiciones</button>
    </div>
    <p aria-live="polite">{incomplete ? 'Carga las muestras restantes antes de rendir.' : selection.gapCount ? 'Hay cortes de señal en este tramo. Ajusta los extremos para elegir un tramo continuo.' : km < .01 ? 'Selecciona un tramo con desplazamiento confirmado.' : 'Revisa la distancia y el gasto antes de guardar. Tracker no crea una rendición automáticamente.'}</p>
    {error && <p role="alert">{error}</p>}
  </section>;
}
