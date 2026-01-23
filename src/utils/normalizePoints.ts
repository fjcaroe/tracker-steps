import type { ApiLivePoint, TrackPoint } from "../types";

export function normalizeLivePoints(apiPoints: ApiLivePoint[]): TrackPoint[] {
  return apiPoints.map((p, idx) => ({
    id: (p as any).id ?? idx, // si el backend trae id úsalo; si no, idx
    timestamp: Date.parse(p.ts), // ISO -> epoch ms
    lat: p.lat,
    lon: p.lon,
    speed: p.speed_mps ?? null,
    accuracy: p.accuracy_m ?? null,
  }));
}
