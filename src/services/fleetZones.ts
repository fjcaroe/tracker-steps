export type Vertex = { lat: number; lon: number };
export const purposes = { operation: 'Área de operación', customer: 'Cliente / entrega', base: 'Base / estacionamiento', restricted: 'Zona restringida' };
export type ZoneDraft = { name: string; purpose: keyof typeof purposes; color: string; vertices: Vertex[]; active: boolean };
export type Zone = ZoneDraft & { id: string; version: number; area_m2: number; perimeter_m: number; created_at: string; updated_at: string };
export type ZoneStats = { seconds: number; distance_m: number; moving_seconds: number; stationary_seconds: number; unknown_motion_seconds: number; max_speed_kmh: number | null };
export type ZoneReport = {
  zone: Zone; asset: { id: string; name: string; plate: string | null }; start: string; end: string; generated_at: string;
  inside: ZoneStats; outside: ZoneStats; period_seconds: number; observed_seconds: number; unobserved_seconds: number;
  coverage_pct: number; entries: number; exits: number; point_count: number;
  events: { type: 'entry' | 'exit'; at: string; lat: number; lon: number }[]; events_truncated: boolean;
  segments: { state: 'inside' | 'outside'; start: string; end: string; path: Vertex[] }[]; map_truncated: boolean;
  rejected_intervals: Record<string, number>; max_gap_seconds: number; max_speed_threshold_kmh: number;
};
export const blankZone = (): ZoneDraft => ({ name: '', purpose: 'operation', color: '#4d7c3d', vertices: [], active: true });
export const duration = (seconds: number) => { const minutes = Math.round(seconds / 60); return minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} h ${minutes % 60} min`; };
export const number = (value: number, decimals = 1) => value.toLocaleString('es-CL', { maximumFractionDigits: decimals });
export const area = (value: number) => value >= 10000 ? `${number(value / 10000, 2)} ha` : `${number(value, 0)} m²`;
export function download(contents: string, name: string, type: string) {
  const url = URL.createObjectURL(new Blob([contents], { type })); const a = document.createElement('a');
  a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function exportZone(zone: Zone) {
  const coordinates = zone.vertices.map(p => [p.lon, p.lat]);
  download(JSON.stringify({ type: 'Feature', properties: { name: zone.name, purpose: zone.purpose, version: zone.version }, geometry: { type: 'Polygon', coordinates: [[...coordinates, coordinates[0]]] } }, null, 2), `zona-${zone.id}.geojson`, 'application/geo+json');
}
export function exportReport(report: ZoneReport) {
  const rows: unknown[][] = [
    ['Zona', report.zone.name], ['Versión del polígono', report.zone.version], ['Vehículo', report.asset.name], ['Patente', report.asset.plate],
    ['Inicio ISO', report.start], ['Fin ISO', report.end], ['Generado ISO', report.generated_at], ['Cobertura temporal %', report.coverage_pct],
    ['Sin observación (s)', report.unobserved_seconds], ['Superficie del polígono (m²), no trabajada', report.zone.area_m2],
    ['Entradas estimadas', report.entries], ['Salidas estimadas', report.exits],
    ['Métrica', 'Dentro', 'Fuera'], ['Tiempo observado (s)', report.inside.seconds, report.outside.seconds],
    ['Distancia GPS estimada (m)', report.inside.distance_m, report.outside.distance_m],
    ['Movimiento (s)', report.inside.moving_seconds, report.outside.moving_seconds],
    ['Detenido (s)', report.inside.stationary_seconds, report.outside.stationary_seconds],
    ['Movimiento desconocido (s)', report.inside.unknown_motion_seconds, report.outside.unknown_motion_seconds],
    ['Velocidad máxima de muestras (km/h)', report.inside.max_speed_kmh, report.outside.max_speed_kmh],
    ['Cruces incluidos', report.events_truncated ? 'Últimos 1000; totales completos arriba' : 'Todos'],
    ['Tipo de cruce estimado', 'Fecha ISO', 'Latitud', 'Longitud'], ...report.events.map(e => [e.type === 'entry' ? 'Entrada' : 'Salida', e.at, e.lat, e.lon]),
    ['Método', `Interpolación lineal; huecos >${report.max_gap_seconds}s, saltos >${report.max_speed_threshold_kmh}km/h y cambios de GPS excluidos. Sin extrapolación. Geometría actual.`],
  ];
  const cell = (value: unknown) => { let text = String(value ?? ''); if ('=+@-'.includes([...text].find(c => c.charCodeAt(0)>32 && c.trim()) || '\uFFFF')) text = "'" + text; return '"' + text.replaceAll('"', '""') + '"'; };
  download('\uFEFF' + rows.map(row => row.map(cell).join(';')).join('\r\n'), `reporte-zona-${report.zone.id}.csv`, 'text/csv;charset=utf-8');
}
