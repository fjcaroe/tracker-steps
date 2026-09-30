import { dateLabel, label, type FleetAsset } from './fleetApi';
// Quote every field and neutralize spreadsheet formulas in user-controlled data.
export function fleetCsv(assets: FleetAsset[]) {
  const cell = (value: unknown) => {
    const text = String(value ?? '');
    const first = Array.from(text).find(c => c.charCodeAt(0) > 32 && c.trim());
    return '"' + (first && '=+@-'.includes(first) ? "'"+text : text).replaceAll('"','""') + '"';
  };
  const rows = [['Nombre','Patente','Tipo','Responsable','Centro de costo','Señal','Movimiento','Protección','Última posición','Recibido por Steps'], ...assets.map(a=>[a.name,a.plate,label(a.type),a.responsible,a.cost_center,label(a.signal_state),label(a.motion_state),label(a.protection_state),dateLabel(a.last_position?.recorded_at),dateLabel(a.last_position?.received_at)])];
  return '\uFEFF'+rows.map(row=>row.map(cell).join(';')).join('\r\n');
}
export function exportFleet(assets: FleetAsset[], demo: boolean) {
  const url = URL.createObjectURL(new Blob([fleetCsv(assets)], {type:'text/csv;charset=utf-8'}));
  const link = document.createElement('a');link.href=url;link.download=`steps-${demo ? 'demo-' : ''}flota-${new Date().toISOString().slice(0,10)}.csv`;link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
