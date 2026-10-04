import { describe, expect, it } from 'vitest';
import { centroid, directionsUrl, distToSegmentM, formatDistance, nextWaypoint, routeDeviationM, routeLengthM } from './nav';

const A = { lat: -35.4, lon: -71.6 }, B = { lat: -35.4, lon: -71.59 }, C = { lat: -35.39, lon: -71.59 };

describe('rutas asignadas', () => {
  it('mide la distancia a un segmento', () => {
    const mid = { lat: -35.4009, lon: -71.595 }; // ~100 m al sur del tramo A-B
    expect(distToSegmentM(mid, A, B)).toBeGreaterThan(90);
    expect(distToSegmentM(mid, A, B)).toBeLessThan(110);
    expect(distToSegmentM(A, A, B)).toBeLessThan(1);
    expect(distToSegmentM(A, B, B)).toBeGreaterThan(800); // segmento degenerado
  });
  it('detecta desvío del trazado', () => {
    expect(routeDeviationM({ lat: -35.4, lon: -71.595 }, [A, B, C])).toBeLessThan(1);
    expect(routeDeviationM({ lat: -35.4, lon: -71.595 }, [A])).toBeNull();
    expect(routeDeviationM({ lat: -35.395, lon: -71.6 }, [A, B, C])!).toBeGreaterThan(400);
  });
  it('avanza los puntos alcanzados', () => {
    expect(nextWaypoint(A, [A, B, C])).toBe(1);
    expect(nextWaypoint({ lat: -35.4, lon: -71.595 }, [A, B, C])).toBe(0);
    expect(nextWaypoint(C, [A, B, C], 2)).toBe(3);
    expect(nextWaypoint(A, [], 0)).toBe(0);
  });
  it('largo, formato y enlaces', () => {
    expect(routeLengthM([A, B, C])).toBeGreaterThan(1900);
    expect(formatDistance(350)).toBe('350 m');
    expect(formatDistance(1530)).toBe('1.5 km');
    expect(directionsUrl(B)).toContain('destination=-35.4,-71.59');
    expect(centroid([])).toBeNull();
    expect(centroid([A, C])!.lat).toBeCloseTo(-35.395, 5);
  });
});
