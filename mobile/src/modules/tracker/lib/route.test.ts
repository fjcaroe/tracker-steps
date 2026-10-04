import { describe, expect, it } from 'vitest';
import { continuousDrivingMs, detectStops, projectRoute, routeDistanceM, summarize, summaryText, type RoutePoint } from './route';
import { minutesUntil } from '../screens/Tasks';

const pt = (min: number, lat: number, lon: number, speed: number | null = null): RoutePoint => ({ ts: Date.UTC(2026, 9, 2, 8, min), lat, lon, speed_mps: speed });

describe('ruta y resumen', () => {
  it('mide la distancia recorrida', () => {
    expect(routeDistanceM([pt(0, -35.4, -71.6), pt(1, -35.399, -71.6)])).toBeGreaterThan(100);
    expect(routeDistanceM([pt(0, -35.4, -71.6)])).toBe(0);
  });
  it('detecta paradas largas y no las breves', () => {
    const quiet = [0, 1, 2, 3, 4].map((m) => pt(m, -35.4, -71.6));
    const moving = [5, 6, 7].map((m, i) => pt(m, -35.4 + 0.001 * (i + 1), -71.6));
    const stops = detectStops([...quiet, ...moving]);
    expect(stops).toHaveLength(1);
    expect(stops[0].end - stops[0].start).toBe(4 * 60000);
    expect(detectStops([pt(0, -35.4, -71.6), pt(1, -35.4, -71.6)])).toEqual([]);
  });
  it('resume tiempo, km, paradas y combustible', () => {
    const points = [pt(0, -35.4, -71.6, 5), pt(10, -35.39, -71.6, 6), pt(20, -35.38, -71.6, 8)];
    const s = summarize(points, points[0].ts, points[2].ts, { start: 50, end: 30, refill: 5 });
    expect(s.km).toBeGreaterThan(2);
    expect(s.fuelUsedL).toBe(25);
    expect(s.maxKmh).toBeCloseTo(28.8, 1);
    expect(summaryText('Tractor', s)).toContain('Tractor');
  });
  it('combustible no se informa si el cálculo es negativo', () => {
    expect(summarize([], 0, 1000, { start: 10, end: 30, refill: null }).fuelUsedL).toBeNull();
  });
  it('proyecta dentro del recuadro', () => {
    const xy = projectRoute([pt(0, -35.4, -71.6), pt(1, -35.39, -71.59), pt(2, -35.38, -71.6)], 320, 220);
    for (const [x, y] of xy) { expect(x).toBeGreaterThanOrEqual(0); expect(x).toBeLessThanOrEqual(320); expect(y).toBeGreaterThanOrEqual(0); expect(y).toBeLessThanOrEqual(220); }
    expect(projectRoute([], 320, 220)).toEqual([]);
  });
});

describe('recordatorios de tareas', () => {
  it('calcula minutos hasta la hora programada', () => {
    const now = new Date(2026, 9, 2, 7, 30);
    expect(minutesUntil('08:00', now)).toBe(30);
    expect(minutesUntil('07:00', now)).toBe(-30);
    expect(minutesUntil('04:00', now)).toBeNull();
    expect(minutesUntil(null, now)).toBeNull();
  });
});

describe('pausas de conducción', () => {
  it('cuenta la conducción desde la última pausa de 15 min', () => {
    const pts = [pt(0, -35.4, -71.6), pt(5, -35.39, -71.6), pt(10, -35.38, -71.6), pt(11, -35.38, -71.6), pt(27, -35.38, -71.6), pt(40, -35.37, -71.6), pt(50, -35.36, -71.6)];
    expect(continuousDrivingMs(pts)).toBe(23 * 60000);
  });
  it('sin pausas cuenta desde el primer punto y en pausa vale 0', () => {
    expect(continuousDrivingMs([pt(0, -35.4, -71.6), pt(30, -35.3, -71.6)])).toBe(30 * 60000);
    expect(continuousDrivingMs([pt(0, -35.4, -71.6), pt(5, -35.4, -71.6), pt(20, -35.4, -71.6)])).toBe(0);
    expect(continuousDrivingMs([])).toBe(0);
  });
});
