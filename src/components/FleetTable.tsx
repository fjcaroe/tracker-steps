import { columnLabels, dateLabel, label, type FleetAsset } from '../services/fleetApi';
export default function FleetTable({ assets, columns, selected, onSelect }: { assets: FleetAsset[]; columns: string[]; selected: string | null; onSelect: (id: string) => void }) {
  const cell = (a: FleetAsset, key: string) => {
    if (key === 'name') return <button aria-pressed={selected === a.asset_id} onClick={() => onSelect(a.asset_id)}>{a.name}<small>{a.plate || 'Sin patente'}</small></button>;
    if (key === 'signal_state') return <>{label(a.signal_state)}<small>{dateLabel(a.last_position?.received_at)}</small></>;
    if (key === 'device') return a.device ? `${a.device.brand} ${a.device.model}` : 'No asociado';
    if (key === 'acc') return a.position_stale ? 'Dato antiguo / sin dato' : a.last_position?.acc == null ? 'No disponible' : a.last_position.acc ? 'Contacto encendido' : 'Contacto apagado';
    if (key === 'created_at') return dateLabel(a.created_at);
    return label(String(a[key as keyof FleetAsset] || 'Sin dato'));
  };
  const visible = columns.filter(c => c in columnLabels);
  return <div className="fleet-table-scroll" tabIndex={0} role="region" aria-label="Tabla de flota desplazable"><table className="fleet-table"><thead><tr>{visible.map(c => <th key={c} scope="col">{columnLabels[c]}</th>)}</tr></thead><tbody>{assets.map(a => <tr key={a.asset_id} className={selected === a.asset_id ? 'is-selected' : ''}>{visible.map(c => <td key={c}>{cell(a, c)}</td>)}</tr>)}</tbody></table></div>;
}
