import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { DemoTrackPoint } from "../demo/scenario";

export type PlaybackSample = { lat: number; lon: number; speedKmh: number; headingDeg: number };

// Interpola la posición/velocidad de un track en un instante arbitrario
// (segundos desde el inicio). Determinista: el mismo `atSeconds` siempre
// produce el mismo resultado, sin importar cómo se llegó a él (play, seek,
// pausa/reanudación).
function sampleAt(points: DemoTrackPoint[], atSeconds: number): PlaybackSample {
  if (points.length === 0) return { lat: 0, lon: 0, speedKmh: 0, headingDeg: 0 };
  if (atSeconds <= points[0].atSeconds) return points[0];
  const last = points[points.length - 1];
  if (atSeconds >= last.atSeconds) return last;

  let lo = 0;
  let hi = points.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (points[mid].atSeconds <= atSeconds) lo = mid; else hi = mid;
  }
  const a = points[lo];
  const b = points[hi];
  const span = b.atSeconds - a.atSeconds;
  const t = span > 0 ? (atSeconds - a.atSeconds) / span : 0;
  const headingDelta = (((b.headingDeg - a.headingDeg + 540) % 360) - 180) * t;
  return {
    lat: a.lat + (b.lat - a.lat) * t,
    lon: a.lon + (b.lon - a.lon) * t,
    speedKmh: a.speedKmh + (b.speedKmh - a.speedKmh) * t,
    headingDeg: a.headingDeg + headingDelta,
  };
}

export function useTrackPlayback(points: DemoTrackPoint[], durationSeconds: number) {
  const [playing, setPlaying] = useState(true);
  const [rate, setRate] = useState(1);
  const [elapsed, setElapsed] = useState(0);
  const rafRef = useRef<number | null>(null);
  const lastTickRef = useRef<number | null>(null);

  useEffect(() => {
    if (!playing) {
      lastTickRef.current = null;
      return;
    }
    let cancelled = false;
    const tick = (now: number) => {
      if (cancelled) return;
      if (lastTickRef.current != null) {
        const deltaS = ((now - lastTickRef.current) / 1000) * rate;
        setElapsed((prev) => {
          const next = prev + deltaS;
          if (next >= durationSeconds) {
            setPlaying(false);
            return durationSeconds;
          }
          return next;
        });
      }
      lastTickRef.current = now;
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      cancelled = true;
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    };
  }, [playing, rate, durationSeconds]);

  const play = useCallback(() => {
    setElapsed((prev) => (prev >= durationSeconds ? 0 : prev));
    setPlaying(true);
  }, [durationSeconds]);
  const pause = useCallback(() => setPlaying(false), []);
  const toggle = useCallback(() => {
    setElapsed((prev) => (prev >= durationSeconds && !playing ? 0 : prev));
    setPlaying((prev) => !prev);
  }, [durationSeconds, playing]);
  const seek = useCallback(
    (seconds: number) => setElapsed(Math.min(durationSeconds, Math.max(0, seconds))),
    [durationSeconds],
  );

  const sample = useMemo(() => sampleAt(points, elapsed), [points, elapsed]);

  return { playing, rate, elapsed, sample, play, pause, toggle, setRate, seek };
}
