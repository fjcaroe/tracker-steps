// Seguimiento de rutas asignadas: avance por puntos, desvío respecto del trazado y enlace de navegación. Puro y probado.
import { haversineMeters } from './geo';

export type LatLon = { lat: number; lon: number };
export type Waypoint = LatLon & { label?: string | null };

/** Distancia (m) de un punto a un segmento, en plano local equirectangular (suficiente para tramos de campo). */
export function distToSegmentM(p: LatLon, a: LatLon, b: LatLon): number {
  const k = Math.cos((p.lat * Math.PI) / 180), m = 111320;
  const ax = (a.lon - p.lon) * k * m, ay = (a.lat - p.lat) * m, bx = (b.lon - p.lon) * k * m, by = (b.lat - p.lat) * m;
  const dx = bx - ax, dy = by - ay, len2 = dx * dx + dy * dy;
  const t = len2 === 0 ? 0 : Math.max(0, Math.min(1, -(ax * dx + ay * dy) / len2));
  return Math.hypot(ax + t * dx, ay + t * dy);
}

/** Distancia mínima (m) del punto al trazado completo; null si hay menos de dos puntos. */
export function routeDeviationM(p: LatLon, wps: LatLon[]): number | null {
  if (wps.length < 2) return null;
  let best = Infinity;
  for (let i = 1; i < wps.length; i += 1) best = Math.min(best, distToSegmentM(p, wps[i - 1], wps[i]));
  return best;
}

/** Índice del próximo punto por alcanzar: avanza mientras el vehículo esté a menos de `radiusM` del punto actual. */
export function nextWaypoint(p: LatLon, wps: LatLon[], from = 0, radiusM = 40): number {
  let i = Math.max(0, from);
  while (i < wps.length && haversineMeters(p, wps[i]) <= radiusM) i += 1;
  return i;
}

export function routeLengthM(wps: LatLon[]): number {
  let d = 0;
  for (let i = 1; i < wps.length; i += 1) d += haversineMeters(wps[i - 1], wps[i]);
  return d;
}

export const directionsUrl = (to: LatLon) => `https://www.google.com/maps/dir/?api=1&destination=${to.lat},${to.lon}&travelmode=driving`;

export const formatDistance = (m: number) => (m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`);

/** Centro de un polígono (promedio de vértices): suficiente para ofrecer un campo como destino. */
export function centroid(poly: LatLon[]): LatLon | null {
  if (!poly.length) return null;
  return { lat: poly.reduce((s, q) => s + q.lat, 0) / poly.length, lon: poly.reduce((s, q) => s + q.lon, 0) / poly.length };
}
