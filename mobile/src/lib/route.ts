// Ruta recorrida de la jornada activa (guardada en el teléfono) y cálculos del resumen. Puro y probado.
import { haversineMeters } from './geo';

export type RoutePoint = { ts: number; lat: number; lon: number; speed_mps: number | null };
const KEY = 'steps_movil_route';
const MAX_POINTS = 4000;

function read(): Record<string, RoutePoint[]> { try { const raw = localStorage.getItem(KEY); return raw ? (JSON.parse(raw) as Record<string, RoutePoint[]>) : {}; } catch { return {}; } }
function write(v: Record<string, RoutePoint[]>) { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch { /* sin espacio */ } }

export const routeStore = {
  get: (sessionId: string): RoutePoint[] => read()[sessionId] ?? [],
  push(sessionId: string, p: RoutePoint) {
    const all = read();
    const list = (all[sessionId] ||= []);
    list.push(p);
    if (list.length > MAX_POINTS) list.splice(0, list.length - MAX_POINTS);
    write(all);
  },
  clear(sessionId: string) { const all = read(); delete all[sessionId]; write(all); },
};

export type Stop = { start: number; end: number; lat: number; lon: number };

/** Paradas: tramos de al menos `minMs` con desplazamiento menor a `radiusM` respecto del punto inicial del tramo. */
export function detectStops(points: RoutePoint[], minMs = 3 * 60 * 1000, radiusM = 25): Stop[] {
  const stops: Stop[] = [];
  let i = 0;
  while (i < points.length) {
    let j = i;
    while (j + 1 < points.length && haversineMeters(points[i], points[j + 1]) <= radiusM) j += 1;
    if (points[j].ts - points[i].ts >= minMs) { stops.push({ start: points[i].ts, end: points[j].ts, lat: points[i].lat, lon: points[i].lon }); i = j + 1; }
    else i += 1;
  }
  return stops;
}

export function routeDistanceM(points: RoutePoint[]): number {
  let d = 0;
  for (let i = 1; i < points.length; i += 1) d += haversineMeters(points[i - 1], points[i]);
  return d;
}

export type Summary = { durationMs: number; km: number; stops: number; stoppedMs: number; avgKmh: number; maxKmh: number; fuelUsedL: number | null };

export function summarize(points: RoutePoint[], startedAt: number, endedAt: number, tank: { start: number; end: number; refill: number | null }): Summary {
  const km = routeDistanceM(points) / 1000;
  const stops = detectStops(points);
  const stoppedMs = stops.reduce((n, s) => n + (s.end - s.start), 0);
  const moving = Math.max(1, endedAt - startedAt - stoppedMs) / 3600000;
  const maxKmh = points.reduce((m, p) => Math.max(m, (p.speed_mps ?? 0) * 3.6), 0);
  const fuel = tank.start - tank.end + (tank.refill ?? 0);
  return { durationMs: endedAt - startedAt, km, stops: stops.length, stoppedMs, avgKmh: km / moving, maxKmh, fuelUsedL: Number.isFinite(fuel) && fuel >= 0 ? fuel : null };
}

/** Proyecta lat/lon a un recuadro SVG (equirectangular con corrección de latitud). */
export function projectRoute(points: Pick<RoutePoint, 'lat' | 'lon'>[], width: number, height: number, pad = 12): [number, number][] {
  if (!points.length) return [];
  const lats = points.map((p) => p.lat), lons = points.map((p) => p.lon);
  const minLat = Math.min(...lats), maxLat = Math.max(...lats), minLon = Math.min(...lons), maxLon = Math.max(...lons);
  const k = Math.cos(((minLat + maxLat) / 2 * Math.PI) / 180);
  const w = Math.max((maxLon - minLon) * k, 1e-9), h = Math.max(maxLat - minLat, 1e-9);
  const scale = Math.min((width - 2 * pad) / w, (height - 2 * pad) / h);
  const offX = (width - w * scale) / 2, offY = (height - h * scale) / 2;
  return points.map((p) => [offX + (p.lon - minLon) * k * scale, height - (offY + (p.lat - minLat) * scale)]);
}

/** Texto para compartir el resumen de la jornada. */
export function summaryText(machine: string, s: Summary): string {
  const h = Math.floor(s.durationMs / 3600000), m = Math.round((s.durationMs % 3600000) / 60000);
  return `Jornada ${machine}: ${h} h ${m} min · ${s.km.toFixed(1)} km · ${s.stops} paradas${s.fuelUsedL != null ? ` · ${s.fuelUsedL.toFixed(0)} L` : ''}`;
}
