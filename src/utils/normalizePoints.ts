import type { ApiLivePoint, TrackPoint } from "../types";

export function normalizeLivePoints(apiPoints: ApiLivePoint[]): TrackPoint[] {
  return apiPoints.map((p, idx) => ({
    id: p.id ?? idx,
    timestamp: Date.parse(p.ts), // ISO -> epoch ms
    lat: p.lat,
    lon: p.lon,
    speed_mps: p.speed_mps ?? null,
    accuracy: p.accuracy_m ?? null,
  }));
}
